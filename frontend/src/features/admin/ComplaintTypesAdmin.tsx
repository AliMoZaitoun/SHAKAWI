import { useState, type FormEvent } from "react";
import { Languages, Pencil, Plus, Tags } from "lucide-react";
import { api } from "../../shared/api/client";
import { useResource } from "../../shared/api/hooks";
import type { ComplaintType } from "../../shared/api/types";
import { formatDuration } from "../../shared/formatDuration";
import { useI18n } from "../../shared/i18n/I18n";
import { UiText } from "../../shared/i18n/UiText";
import { AdminAlert, AdminPage, useAdminSave } from "./AdminPage";
import { AdminDialog } from "./AdminDialog";
import "./admin-ui.css";

type DurationUnit = "minutes" | "hours" | "days" | "weeks";
type FormState = {
  name: string;
  description: string;
  amount: string;
  unit: DurationUnit;
  is_active: boolean;
};

const blank: FormState = {
  name: "",
  description: "",
  amount: "",
  unit: "days",
  is_active: true,
};
const unitMinutes: Record<DurationUnit, number> = {
  minutes: 1,
  hours: 60,
  days: 1440,
  weeks: 10080,
};

function initialForm(type?: ComplaintType): FormState {
  if (!type) return { ...blank };
  const minutes = type.sla_duration_minutes ?? 0;
  const unit: DurationUnit =
    minutes && minutes % 10080 === 0
      ? "weeks"
      : minutes && minutes % 1440 === 0
        ? "days"
        : minutes && minutes % 60 === 0
          ? "hours"
          : "minutes";
  return {
    name: type.name,
    description: type.description,
    amount: minutes ? String(minutes / unitMinutes[unit]) : "",
    unit,
    is_active: type.is_active,
  };
}

export function ComplaintTypesAdmin() {
  const { lang, tText } = useI18n();
  const query = useResource<ComplaintType[]>("/admin/complaint-types", lang);
  const save = useAdminSave();
  const [editing, setEditing] = useState<ComplaintType | null>(null);
  const [form, setForm] = useState<FormState>(blank);
  const [show, setShow] = useState(false);

  function begin(type?: ComplaintType) {
    setEditing(type ?? null);
    setForm(initialForm(type));
    setShow(true);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const duration =
      editing?.code === "other"
        ? null
        : form.amount
          ? Number(form.amount) * unitMinutes[form.unit]
          : null;
    if (
      editing?.code !== "other" &&
      form.is_active &&
      (!duration || !Number.isSafeInteger(duration) || duration > 5_256_000)
    ) {
      save.setMessage(tText("أدخل مهلة صحيحة لا تتجاوز عشر سنوات."));
      return;
    }
    const ok = await save.run(() =>
      api(editing ? `/admin/complaint-types/${editing.id}` : "/admin/complaint-types", {
        method: editing ? "PUT" : "POST",
        body: {
          name: form.name.trim(),
          description: form.description.trim(),
          sla_duration_minutes: duration,
          ...(editing ? { is_active: form.is_active } : {}),
        },
      }),
    );
    if (ok) setShow(false);
  }

  return (
    <AdminPage
      title="أنواع الشكاوى"
      required="complaint_types.manage"
      subtitle="أضف أنواعًا موحّدة، وحدد المدة التقديرية ووصفًا يساعد المواطن على إعداد شكواه."
      headerAction={
        <button className="btn" type="button" disabled={save.busy} onClick={() => begin()}>
          <Plus size={17} aria-hidden="true" />
          <UiText source="إضافة نوع" />
        </button>
      }
    >
      <p className="status info">
        <UiText source="تُحسب المدة بشكل متواصل من وقت تقديم الشكوى، لا كأيام دوام. نوع «أخرى» بلا مهلة." />
      </p>
      <div className="row" style={{ justifyContent: "flex-end", margin: "12px 0" }}>
        <a className="btn secondary" href="/employee/admin/translations">
          <Languages size={16} aria-hidden="true" />
          <UiText source="ترجمة أسماء الأنواع" />
        </a>
      </div>
      {query.isLoading ? (
        <div className="skeleton" />
      ) : query.error ? (
        <div className="status error" role="alert">
          {tText("تعذر تحميل أنواع الشكاوى.")}
          <button className="btn secondary" type="button" onClick={() => void query.refetch()}>
            <UiText source="إعادة المحاولة" />
          </button>
        </div>
      ) : query.data?.length ? (
        <>
          <div className="admin-role-meta muted">
            <span>
              <Tags size={15} aria-hidden="true" /> {query.data.length}{" "}
              <UiText source="نوع شكوى" />
            </span>
            <span>
              {query.data.filter((item) => item.is_active).length} <UiText source="نشط" />
            </span>
          </div>
          <div className="table-wrap" style={{ marginTop: 14 }}>
            <table>
              <thead>
                <tr>
                  {["النوع", "المدة التقديرية", "الحالة", "إجراء"].map((heading) => (
                    <th key={heading}>
                      <UiText source={heading} />
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {query.data.map((type) => (
                  <tr key={type.id}>
                    <td>
                      <b>{type.name}</b>
                      {type.description && <div className="muted">{type.description}</div>}
                    </td>
                    <td>
                      {type.code === "other"
                        ? tText("لا توجد مهلة")
                        : type.sla_duration_minutes
                          ? formatDuration(type.sla_duration_minutes, lang)
                          : tText("غير محددة بعد")}
                    </td>
                    <td>
                      <span className={`badge ${type.is_active ? "" : "red"}`}>
                        {tText(type.is_active ? "نشط" : "معطل")}
                      </span>
                    </td>
                    <td>
                      <button
                        className="admin-icon-button"
                        type="button"
                        title={tText("تعديل")}
                        aria-label={`${tText("تعديل")} ${type.name}`}
                        disabled={save.busy}
                        onClick={() => begin(type)}
                      >
                        <Pencil size={16} aria-hidden="true" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : (
        <div className="admin-empty">
          <Tags size={24} aria-hidden="true" />
          <p>
            <UiText source="لا توجد أنواع شكاوى بعد." />
          </p>
          <button className="btn" type="button" onClick={() => begin()}>
            <Plus size={17} aria-hidden="true" />
            <UiText source="إضافة نوع" />
          </button>
        </div>
      )}
      {!show && <AdminAlert text={save.message} isError={save.isError} />}
      {show && (
        <AdminDialog title={editing ? "تعديل نوع الشكوى" : "نوع شكوى جديد"} onClose={() => setShow(false)}>
          <form className="admin-dialog-form" onSubmit={(event) => void submit(event)}>
            <div className="form-grid">
              <label className="field-label full">
                <UiText source="الاسم بالعربية" />
                <input
                  className="field"
                  required
                  minLength={2}
                  maxLength={50}
                  value={form.name}
                  onChange={(event) => setForm({ ...form, name: event.target.value })}
                />
              </label>
              <label className="field-label full">
                <UiText source="وصف اختياري لمساعدة المواطن" />
                <textarea
                  className="field"
                  rows={3}
                  maxLength={4000}
                  value={form.description}
                  onChange={(event) => setForm({ ...form, description: event.target.value })}
                />
              </label>
              {editing?.code !== "other" && (
                <>
                  <label className="field-label">
                    <UiText source="المدة التقديرية" />
                    <input
                      className="field"
                      type="number"
                      min="1"
                      step="1"
                      required={form.is_active}
                      value={form.amount}
                      onChange={(event) => setForm({ ...form, amount: event.target.value })}
                    />
                  </label>
                  <label className="field-label">
                    <UiText source="وحدة المدة" />
                    <select
                      className="field"
                      value={form.unit}
                      onChange={(event) =>
                        setForm({ ...form, unit: event.target.value as DurationUnit })
                      }
                    >
                      <option value="minutes">{tText("دقائق")}</option>
                      <option value="hours">{tText("ساعات")}</option>
                      <option value="days">{tText("أيام متواصلة")}</option>
                      <option value="weeks">{tText("أسابيع متواصلة")}</option>
                    </select>
                  </label>
                </>
              )}
            </div>
            {editing && (
              <label className="row">
                <input
                  type="checkbox"
                  disabled={editing.code === "other"}
                  checked={form.is_active}
                  onChange={(event) => setForm({ ...form, is_active: event.target.checked })}
                />
                <UiText source="نشط ومتاح للمواطن" />
              </label>
            )}
            <AdminAlert text={save.message} isError={save.isError} />
            <div className="admin-dialog-footer">
              <button className="btn" disabled={save.busy}>
                {save.busy ? <UiText source="جارٍ الحفظ…" /> : <UiText source="حفظ" />}
              </button>
              <button
                type="button"
                className="btn secondary"
                disabled={save.busy}
                onClick={() => setShow(false)}
              >
                <UiText source="إلغاء" />
              </button>
            </div>
          </form>
        </AdminDialog>
      )}
    </AdminPage>
  );
}
