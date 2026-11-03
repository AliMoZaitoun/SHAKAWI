from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import current_employee
from app.db.session import get_db
from app.models.complaint import Complaint, PriorityEnum, StatusEnum
from app.models.user import UserRole

router = APIRouter()


@router.get("")
@router.get("/")
def analytics(start_date: date | None = None, end_date: date | None = None,
              directorate_id: int | None = Query(None, ge=1, le=2),
              employee=Depends(current_employee), db: Session = Depends(get_db)):
    end = end_date or date.today()
    start = start_date or end - timedelta(days=29)
    if start > end:
        raise HTTPException(422, "بداية الفترة يجب أن تسبق نهايتها")
    if (end - start).days > 366:
        raise HTTPException(422, "اختر فترة لا تتجاوز سنة")
    if employee.role != UserRole.GOVERNOR:
        if directorate_id is not None and directorate_id != employee.directorate_id:
            raise HTTPException(403, "لا تملك صلاحية إحصائيات هذه الجهة")
        directorate_id = employee.directorate_id
    query = db.query(Complaint).filter(
        Complaint.created_at >= datetime.combine(start, time.min),
        Complaint.created_at < datetime.combine(end + timedelta(days=1), time.min),
    )
    if directorate_id is not None:
        query = query.filter(Complaint.directorate_id == directorate_id)
    total = query.count()
    statuses = {status.value: 0 for status in StatusEnum}
    for status, count in query.with_entities(Complaint.status, func.count(Complaint.id)).group_by(Complaint.status):
        statuses[status.value] = count
    priorities = {priority.value: 0 for priority in PriorityEnum}
    for priority, count in query.with_entities(Complaint.priority, func.count(Complaint.id)).group_by(Complaint.priority):
        priorities[priority.value] = count
    categories = [
        {"label": category, "count": count}
        for category, count in query.with_entities(Complaint.category, func.count(Complaint.id)).group_by(
            Complaint.category
        ).order_by(func.count(Complaint.id).desc(), Complaint.category)
    ]
    by_day = {
        str(day): count for day, count in query.with_entities(
            func.date(Complaint.created_at), func.count(Complaint.id)
        ).group_by(func.date(Complaint.created_at))
    }
    daily = [{"date": (start + timedelta(days=offset)).isoformat(),
              "count": by_day.get((start + timedelta(days=offset)).isoformat(), 0)}
             for offset in range((end - start).days + 1)]
    average = query.with_entities(func.avg(Complaint.progress)).scalar() or 0
    return {
        "total": total, "counts_by_status": statuses,
        "counts_by_category": categories, "counts_by_priority": priorities, "daily": daily,
        "resolution_rate": round(100 * statuses["RESOLVED"] / total, 2) if total else 0,
        "average_progress": round(float(average), 2),
        "scope": {"role": employee.role.value, "directorate_id": directorate_id},
        "filters": {"start_date": start.isoformat(), "end_date": end.isoformat(),
                    "directorate_id": directorate_id},
        "definitions": {
            "resolution_rate": "الشكاوى المحلولة ÷ جميع الشكاوى في الفترة × 100؛ تشمل جميع الشكاوى المرفوضة",
            "average_progress": "متوسط تقدير الموظفين لتقدم المعالجة، وليس نسبة الشكاوى المحلولة",
            "dates": "الفلترة حسب تاريخ تقديم الشكوى بتوقيت UTC، شاملة يوم البداية والنهاية",
        },
    }
