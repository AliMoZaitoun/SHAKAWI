import type { Dispatch, SetStateAction } from "react";
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
  busy,
  setForm,
  close,
  submit,
  tText,
}: {
  form: EmployeeDraft;
  editing: Employee | null;
  directorates: Directorate[];
  busy: boolean;
  setForm: Dispatch<SetStateAction<EmployeeDraft>>;
  close: () => void;
  submit: (body: Record<string, unknown>) => Promise<void>;
  tText: (source: string) => string;
}) {
  return (
    <form
      className="panel form-grid"
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
      <h2 className="form-field full">
        <UiText source={editing ? "تعديل موظف" : "حساب موظف جديد"} />
      </h2>
      {(["first_name", "last_name", "phone", "email"] as const).map((key) => (
        <label key={key} className="field-label">
          {tText(
            {
              first_name: "الاسم الأول",
              last_name: "اسم العائلة",
              phone: "الهاتف",
              email: "البريد",
            }[key],
          )}
          <input
            className="field"
            required={key !== "email"}
            value={form[key]}
            onChange={(event) => setForm({ ...form, [key]: event.target.value })}
          />
        </label>
      ))}
      {!editing && (
        <>
          <label className="field-label">
            {tText("اسم الدخول")}
            <input
              required
              className="field"
              value={form.username}
              onChange={(event) => setForm({ ...form, username: event.target.value })}
            />
          </label>
          <label className="field-label">
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
      <label className="field-label">
        {tText("المديرية الأساسية")}
        <select
          className="field"
          value={form.directorate_id}
          onChange={(event) => setForm({ ...form, directorate_id: event.target.value })}
        >
          <option value="">{tText("بدون مديرية")}</option>
          {directorates.map((directorate) => (
            <option key={directorate.id} value={directorate.id}>
              {directorate.hierarchy_path ?? directorate.name}
            </option>
          ))}
        </select>
      </label>
      {editing && (
        <label>
          <input
            type="checkbox"
            checked={form.is_active}
            onChange={(event) => setForm({ ...form, is_active: event.target.checked })}
          />{" "}
          {tText("نشط")}
        </label>
      )}
      <div className="row form-field full">
        <button className="btn" disabled={busy}>
          <UiText source="حفظ الملف" />
        </button>
        <button type="button" className="btn secondary" onClick={close}>
          <UiText source="إغلاق" />
        </button>
      </div>
    </form>
  );
}
