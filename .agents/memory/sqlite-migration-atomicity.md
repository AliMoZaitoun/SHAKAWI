---
name: SQLite migration atomicity
description: Why database migration rollback needs an explicit SQLite transaction.
---

لا تفترض أن engine.begin وحده يجعل DDL في SQLite قابلاً للرجوع في بيئة Python؛ وضع sqlite3 القديم قد يؤخر BEGIN حتى أول عملية DML.

**Why:** ترحيل الجداول والهوية والمرفقات يجب أن يتراجع بالكامل عند الفشل، لا أن يترك مخططاً نصف منقول. حُسم هذا الشرط باختبار فشل متعمد وسط ترحيل مع التأكد من رجوع المخطط والبيانات.

**How to apply:** حافظ على معاملة SQLite صريحة قبل أول DDL عند تعديل نقطة الترحيل، واختبر فشل الترحيل لا نجاحه فقط. لا تستخدم executescript الذي قد ينهي المعاملة ضمناً، ولا تخلط ترحيلات بدء تشغيل مستقلة مع Alembic.
