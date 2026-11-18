import { useEffect, useRef, useState, type FormEvent } from "react";
import { Building2, Check, ChevronDown, Globe2, Plus, Shield, UserRound, X } from "lucide-react";
import type { Directorate, Employee, Role } from "../../shared/api/types";
import { UiText } from "../../shared/i18n/UiText";

type RoleAssignmentBody = {
  role_id: number;
  scope_type: "global" | "directorate";
  directorate_id: number | null;
};

export function EmployeeRoleAssignmentDialog({
  employee,
  roles,
  directorates,
  rolesLoading,
  rolesFailed,
  busy,
  message,
  messageIsError,
  getDirectorateLabel,
  onClose,
  onAssign,
  onRemove,
  tText,
}: {
  employee: Employee;
  roles: Role[];
  directorates: Directorate[];
  rolesLoading: boolean;
  rolesFailed: boolean;
  busy: boolean;
  message: string;
  messageIsError: boolean;
  getDirectorateLabel: (id: number) => string;
  onClose: () => void;
  onAssign: (body: RoleAssignmentBody) => void;
  onRemove: (assignmentId: number) => void;
  tText: (source: string) => string;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [roleId, setRoleId] = useState("");
  const [scopeType, setScopeType] = useState<"global" | "directorate">("directorate");
  const [directorateId, setDirectorateId] = useState(
    employee.directorate_id ? String(employee.directorate_id) : "",
  );
  const employeeName = [employee.first_name, employee.last_name].filter(Boolean).join(" ");

  useEffect(() => {
    const dialog = dialogRef.current;
    if (dialog && !dialog.open) dialog.showModal();
  }, []);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!roleId || (scopeType === "directorate" && !directorateId)) return;
    onAssign({
      role_id: Number(roleId),
      scope_type: scopeType,
      directorate_id: scopeType === "global" ? null : Number(directorateId),
    });
  }

  return (
    <dialog
      ref={dialogRef}
      className="employee-modal employee-role-modal"
      aria-labelledby="employee-roles-title"
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section className="employee-dialog-content">
        <header className="employee-dialog-header">
          <div className="employee-dialog-title">
            <span className="employee-dialog-icon employee-role-icon">
              <Shield size={18} />
            </span>
            <div>
              <span className="eyebrow">
                <UiText source="المسؤوليات والنطاق" />
              </span>
              <h2 id="employee-roles-title">
                <UiText source="أدوار الموظف" />
              </h2>
            </div>
          </div>
          <button
            type="button"
            className="employee-icon-button"
            onClick={onClose}
            aria-label={tText("إغلاق")}
          >
            <X size={18} />
          </button>
        </header>

        <div className="employee-target">
          <span className="employee-dialog-icon">
            <UserRound size={17} />
          </span>
          <div>
            <strong>{employeeName || tText("يحتاج استكمال الملف")}</strong>
            <span>@{employee.username}</span>
          </div>
          <span className="employee-target-directorate">
            <Building2 size={14} />
            {employee.directorate_id
              ? getDirectorateLabel(employee.directorate_id)
              : tText("بدون مديرية")}
          </span>
        </div>

        {message && (
          <div
            className={`employee-save-message ${messageIsError ? "error" : "success"}`}
            role={messageIsError ? "alert" : "status"}
          >
            {message}
          </div>
        )}
        {rolesFailed && (
          <div className="status error" role="alert">
            {tText("تعذر تحميل الأدوار.")}
          </div>
        )}

        <div className="employee-assignment-heading">
          <strong>{tText("الإسنادات الحالية")}</strong>
          <span>{employee.role_assignments.length}</span>
        </div>
        <div className="employee-assignment-list">
          {employee.role_assignments.length ? (
            employee.role_assignments.map((assignment) => {
              const roleName =
                roles.find((role) => role.id === assignment.role_id)?.name ??
                `${tText("دور")} #${assignment.role_id}`;
              const scopeLabel =
                assignment.scope_type === "global"
                  ? tText("عام")
                  : assignment.directorate_id
                    ? getDirectorateLabel(assignment.directorate_id)
                    : tText("مديرية");
              return (
                <div className="employee-assignment-item" key={assignment.id}>
                  <span className="employee-assignment-mark">
                    {assignment.scope_type === "global" ? <Globe2 size={15} /> : <Building2 size={15} />}
                  </span>
                  <div>
                    <strong>{roleName}</strong>
                    <span>
                      {assignment.scope_type === "global"
                        ? tText("نطاق عام")
                        : `${tText("مديرية")} · ${scopeLabel}`}
                    </span>
                  </div>
                  <button
                    type="button"
                    className="employee-remove-assignment"
                    onClick={() => onRemove(assignment.id)}
                    disabled={busy}
                  >
                    <UiText source="إزالة" />
                  </button>
                </div>
              );
            })
          ) : (
            <div className="employee-no-assignments">{tText("لا توجد أدوار مسندة لهذا الحساب.")}</div>
          )}
        </div>

        <form className="employee-role-form" onSubmit={submit}>
          <h3>{tText("إسناد دور جديد")}</h3>
          {rolesLoading ? (
            <div className="status info" role="status">
              {tText("جارٍ تحميل الأدوار")}
            </div>
          ) : (
            <label>
              {tText("الدور")}
              <span className="employee-select-wrap">
                <select
                  required
                  value={roleId}
                  onChange={(event) => setRoleId(event.target.value)}
                  disabled={rolesFailed || !roles.length}
                >
                  <option value="">{tText("اختر دورًا")}</option>
                  {roles.map((role) => (
                    <option value={role.id} key={role.id}>
                      {role.name}
                    </option>
                  ))}
                </select>
                <ChevronDown size={15} />
              </span>
            </label>
          )}
          <label>
            {tText("نطاق الإسناد")}
            <span className="employee-select-wrap">
              <select
                value={scopeType}
                onChange={(event) =>
                  setScopeType(event.target.value as "global" | "directorate")
                }
              >
                <option value="directorate">{tText("مديرية محددة")}</option>
                <option value="global">{tText("عام")}</option>
              </select>
              <ChevronDown size={15} />
            </span>
          </label>
          {scopeType === "directorate" && (
            <label>
              {tText("المديرية")}
              <span className="employee-select-wrap">
                <select
                  required
                  value={directorateId}
                  onChange={(event) => setDirectorateId(event.target.value)}
                >
                  <option value="">{tText("اختر مديرية")}</option>
                  {directorates.map((directorate) => (
                    <option key={directorate.id} value={directorate.id}>
                      {directorate.hierarchy_path ?? directorate.name}
                    </option>
                  ))}
                </select>
                <ChevronDown size={15} />
              </span>
            </label>
          )}
          <div className="employee-scope-hint">
            <Shield size={14} />
            <span>{tText("سيظهر النطاق بوضوح مع الدور بعد الإسناد.")}</span>
          </div>
          <footer className="employee-dialog-footer">
            <button type="button" className="btn ghost" onClick={onClose}>
              <UiText source="إغلاق" />
            </button>
            <button
              className="btn employee-save-button"
              type="submit"
              disabled={busy || rolesLoading || rolesFailed || !roleId}
            >
              <Check size={16} />
              <UiText source="إسناد دور" />
            </button>
          </footer>
        </form>
      </section>
    </dialog>
  );
}
