"""Private moderation records: never pass these to the public serializer."""

ACTION_LABELS = {
    "hide": "أُخفيت النصوص العامة مؤقتًا لحماية الخصوصية. الشكوى لم تُحذف وتستمر معالجتها.",
    "restore": "أُعيد إظهار النصوص العامة بعد المراجعة.",
    "dismiss": "اكتملت مراجعة البلاغات دون تغيير حالة عرض النصوص.",
}


def review_data(complaint, staff=False):
    reviews = sorted(complaint.public_reviews, key=lambda row: row.id)
    data = {
        "hidden": complaint.public_text_hidden,
        "message": (
            "نصوص شكواك العامة مخفية مؤقتًا لحماية الخصوصية؛ لم تُحذف الشكوى وتستمر معالجتها."
            if complaint.public_text_hidden else
            "شكواك منشورة فورًا وفق اختيارك، مع إمكانية الإبلاغ ومراجعة النصوص."
        ) if complaint.is_public else "شكواك خاصة ولا تظهر للعامة.",
        "history": [
            {"id": row.id, "action": row.action, "reason": row.reason,
             "message": ACTION_LABELS[row.action], "created_at": row.created_at,
             **({"author_id": row.author_id,
                 "author_name": row.author.full_name if row.author else "موظف",
                 "notification_status": row.notification_status} if staff else {})}
            for row in reviews
        ],
    }
    if staff:
        data["reports"] = [
            {"id": row.id, "reason": row.reason, "created_at": row.created_at,
             "review_id": row.review_id}
            for row in sorted(complaint.public_reports, key=lambda row: row.id)
        ]
    return data
