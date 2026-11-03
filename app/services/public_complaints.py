"""Allow-listed public view; never reuse staff or secret-tracking serializers."""
import re


def public_text(text, complaint):
    value = text or ""
    citizen = complaint.citizen
    private_values = [complaint.tracking_code]
    if citizen:
        private_values.extend([
            citizen.first_name + " " + citizen.last_name,
            citizen.first_name, citizen.last_name,
            citizen.phone, citizen.national_id,
            str(citizen.telegram_id) if citizen.telegram_id else "",
        ])
    for private in sorted(set(private_values), key=len, reverse=True):
        if private and len(private) >= 2:
            value = value.replace(private, "[بيانات محجوبة]")
    value = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[بريد محجوب]", value)
    value = re.sub(r"(?<!\w)\+?\d[\d\s().-]{5,}\d(?!\w)", "[رقم محجوب]", value)
    value = re.sub(r"CMP-[A-Z0-9-]+", "[رمز تتبع محجوب]", value, flags=re.I)
    return value


def public_complaint(complaint):
    # Personal details, coordinates, tracking codes, attachments and authors are
    # excluded even if new fields are later added to the ORM or staff response.
    hidden = complaint.public_text_hidden
    return {
        "id": complaint.id,
        "public_text_hidden": hidden,
        "title": "نصوص الشكوى مخفية مؤقتًا للمراجعة" if hidden else public_text(complaint.title, complaint),
        "details": "" if hidden else public_text(complaint.details, complaint),
        "category": "" if hidden else public_text(complaint.category, complaint),
        "directorate_id": complaint.directorate_id,
        "status": complaint.status,
        "priority": complaint.priority,
        "progress": complaint.progress,
        "created_at": complaint.created_at,
        "resolution_report": "" if hidden else public_text(complaint.resolution_report, complaint),
        "notes": [] if hidden else [{"note": public_text(note.note, complaint), "created_at": note.created_at}
                  for note in sorted(complaint.notes, key=lambda n: n.id) if not note.is_internal],
    }
