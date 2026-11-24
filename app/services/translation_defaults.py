"""English labels for built-in capabilities, not translations of citizen content."""
ENGLISH_ROLES = {
    "system_admin": "System administrator",
    "governor": "Governor", "technical_assistant": "Technical assistant",
    "complaint_receiver": "Complaint receiver", "branch_manager": "Branch manager",
    "legacy_department_staff": "Department staff (legacy access)",
}
ENGLISH_PERMISSIONS = {
    "complaints.view": "View complaints", "complaints.update": "Update complaints",
    "complaints.resolve": "Resolve complaints", "complaints.files.read": "Download complaint attachments",
    "complaints.notes.create": "Add complaint notes", "notifications.retry": "Retry notifications",
    "evidence.request": "Request additional evidence", "evidence.read": "Read evidence correspondence",
    "evidence.files.read": "Download evidence files", "public.review": "Review public text reports",
    "reports.view": "View complaint statistics", "rbac.manage": "Manage roles and permissions",
    "employees.manage": "Manage employee accounts", "directorates.manage": "Manage directorates",
    "audit.view": "View system audit log", "files.identity.read": "Read identity documents",
    "complaints.transfer": "Transfer complaints between directorates",
    "complaint_types.manage": "Manage complaint types",
    "files.manage": "Manage file limits and retention",
    "branding.manage": "Manage site branding",
}

ENGLISH_COMPLAINT_TYPES = {
    "roads": "Roads",
    "building_violations": "Building violations",
    "excavations": "Excavations",
    "road_opening": "Road openings",
    "service_outage": "Service outage",
    "technical_issue": "Technical issue",
    "administrative_complaint": "Administrative complaint",
    "other": "Other",
}
