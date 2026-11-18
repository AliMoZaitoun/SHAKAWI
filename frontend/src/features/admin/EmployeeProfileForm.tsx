import { useEffect, useRef, type Dispatch, type SetStateAction } from "react";
import { Check, UserRound, X } from "lucide-react";
import type { Directorate, Employee } from "../../shared/api/types";
import { UiText } from "../../shared/i18n/UiText";

export type EmployeeDraft = {
  first_name: string;
  last_name: string;
  phone: string;
  email: string;
  username: string;
  password: string;
  directorate_id: string;
  is_active: boolean;
};

export function EmployeeProfileForm({
  form,
  editing,
  directorates,
  requireDirectorate = false,
  busy,
  setForm,
  close,
  submit,
  tText,
  message,
  messageIsError,
}: {
  form: EmployeeDraft;
  editing: Employee | null;
  directorates: Directorate[];
  requireDirectorate?: boolean;
  busy: boolean;
  setForm: Dispatch<SetStateAction<EmployeeDraft>>;
  close: () => void;
  submit: (body: Record<string, unknown>) => Promise<void>;
  tText: (source: string) => string;
  message: string;
  messageIsError: boolean;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (dialog && !dialog.open) dialog.showModal();
  }, []);

  return (
    <dialog
      ref={dialogRef}
      className="employee-modal employee-profile-modal"
      aria-labelledby="employee-profile-title"
      onCancel={(event) => {
        event.preventDefault();
        close();
      }}
      onClick={(event) => {
        if (event.target === event.currentTarget) close();
      }}
    >
      <form
        className="employee-dialog-form"
        onSubmit={(event) => {
          event.preventDefault();
          const body = editing
            ? {
                first_name: form.first_name,
                last_name: form.last_name,
                phone: form.phone,
                email: form.email || null,
                directorate_id: form.directorate_id ? Number(form.directorate_id) : null,
                is_active: form.is_active,
              }
            : {
                first_name: form.first_name,
                last_name: form.last_name,
                phone: form.phone,
                email: form.email || null,
                username: form.username,
                password: form.password,
                directorate_id: form.directorate_id ? Number(form.directorate_id) : null,
              };
          void submit(body);
        }}
      >
        <header className="employee-dialog-header">
          <div className="employee-dialog-title">
            <span className="employee-dialog-icon">
              <UserRound size={18} />
            </span>
            <div>
              <span className="eyebrow">
                <UiText source={editing ? "ملف الموظف" : "حساب جديد"} />
              </span>
              <h2 id="employee-profile-title">
                <UiText source={editing ? "تعديل موظف" : "حساب موظف جديد"} />
              </h2>
            </div>
          </div>
          <button
            type="button"
            className="employee-icon-button"
            onClick={close}
            aria-label={tText("إغلاق")}
          >
            <X size={18} />
          </button>
        </header>

        <p className="employee-dialog-intro">
          {tText("بيانات الموظف ونطاقه التنظيمي الأساسي.")}
        </p>

        {message && (
          <div
            className={`employee-save-message ${messageIsError ? "error" : "success"}`}
            role={messageIsError ? "alert" : "status"}
          >
            {message}
          </div>
        )}

        <div className="employee-dialog-grid">
          {(["first_name", "last_name", "phone", "email"] as const).map((key, index) => (
            <label key={key}>
              {tText(
                {
                  first_name: "الاسم الأول",
                  last_name: "اسم العائلة",
                  phone: "الهاتف",
                  email: "البريد",
                }[key],
              )}
              {key === "email" && <span className="employee-optional">{tText("اختياري")}</span>}
              <input
                autoFocus={index === 0}
                className="field"
                type={key === "email" ? "email" : key === "phone" ? "tel" : "text"}
                required={key !== "email"}
                value={form[key]}
                onChange={(event) => setForm({ ...form, [key]: event.target.value })}
              />
            </label>
          ))}
          {!editing && (
            <>
              <label>
                {tText("اسم الدخول")}
                <input
                  required
                  autoComplete="username"
                  className="field"
                  value={form.username}
                  onChange={(event) => setForm({ ...form, username: event.target.value })}
                />
              </label>
              <label>
                {tText("كلمة مرور (12+)")}
                <input
                  required
                  minLength={12}
                  type="password"
                  autoComplete="new-password"
                  className="field"
                  value={form.password}
                  onChange={(event) => setForm({ ...form, password: event.target.value })}
                />
              </label>
            </>
          )}
          <label className="employee-dialog-wide">
            {tText("المديرية الأساسية")}
            <select
              className="field"
              required={requireDirectorate}
              value={form.directorate_id}
              onChange={(event) => setForm({ ...form, directorate_id: event.target.value })}
            >
              {!requireDirectorate && <option value="">{tText("بدون مديرية")}</option>}
              {directorates.map((directorate) => (
                <option key={directorate.id} value={directorate.id}>
                  {directorate.hierarchy_path ?? directorate.name}
                </option>
              ))}
            </select>
            <small>{tText("مسار الموظف التنظيمي الأساسي.")}</small>
          </label>
        </div>

        {editing && (
          <label className="employee-active-toggle">
            <span>
              <strong>{tText("الحساب نشط")}</strong>
              <small>{tText("يمكن للموظف استخدام حسابه في البوابة.")}</small>
            </span>
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(event) => setForm({ ...form, is_active: event.target.checked })}
            />
            <i aria-hidden="true" />
          </label>
        )}

        <footer className="employee-dialog-footer">
          <button type="button" className="btn ghost" onClick={close}>
            <UiText source="إغلاق" />
          </button>
          <button className="btn employee-save-button" disabled={busy}>
            <Check size={16} />
            <UiText source="حفظ الملف" />
          </button>
        </footer>
      </form>
    </dialog>
  );
}
