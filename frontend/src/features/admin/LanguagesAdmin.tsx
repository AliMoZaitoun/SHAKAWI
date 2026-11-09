import { useState } from "react";
import { api } from "../../shared/api/client";
import type { Language } from "../../shared/api/types";
import { useResource } from "../../shared/api/hooks";
import { useI18n } from "../../shared/i18n/I18n";
import { UiText } from "../../shared/i18n/UiText";
import { AdminAlert, AdminPage, useAdminSave } from "./AdminPage";

export function LanguagesAdmin() {
  const { lang, tText } = useI18n();
  const languages = useResource<Language[]>("/admin/languages", lang);
  const save = useAdminSave();
  const [form, setForm] = useState({
    code: "",
    name: "",
    direction: "ltr" as "ltr" | "rtl",
    is_active: true,
  });
  const [editing, setEditing] = useState("");

  return (
    <AdminPage
      title="اللغات والترجمات"
      subtitle="إدارة اللغات النشطة والترجمات الاسمية. العربية لغة أساسية محمية."
    >
      <form
        className="form-grid"
        onSubmit={(event) => {
          event.preventDefault();
          void save.run(() =>
            api(editing ? `/admin/languages/${editing}` : "/admin/languages", {
              method: editing ? "PUT" : "POST",
              body: editing
                ? { name: form.name, direction: form.direction, is_active: form.is_active }
                : form,
            }),
          );
        }}
      >
        <label className="field-label">
          <UiText source="رمز اللغة" />
          <input
            className="field"
            required
            disabled={!!editing}
            value={form.code}
            onChange={(event) => setForm({ ...form, code: event.target.value })}
            placeholder="fr"
          />
        </label>
        <label className="field-label">
          <UiText source="الاسم" />
          <input
            className="field"
            required
            value={form.name}
            onChange={(event) => setForm({ ...form, name: event.target.value })}
          />
        </label>
        <label className="field-label">
          <UiText source="الاتجاه" />
          <select
            className="field"
            value={form.direction}
            onChange={(event) =>
              setForm({ ...form, direction: event.target.value as "rtl" | "ltr" })
            }
          >
            <option value="ltr">
              <UiText source="يسار إلى يمين" />
            </option>
            <option value="rtl">
              <UiText source="يمين إلى يسار" />
            </option>
          </select>
        </label>
        <label>
          <input
            type="checkbox"
            checked={form.is_active}
            onChange={(event) => setForm({ ...form, is_active: event.target.checked })}
          />{" "}
          <UiText source="مفعّلة" />
        </label>
        <button className="btn" disabled={save.busy}>
          <UiText source="حفظ اللغة" />
        </button>
        <button
          type="button"
          className="btn secondary"
          onClick={() => {
            setEditing("");
            setForm({ code: "", name: "", direction: "ltr", is_active: true });
          }}
        >
          <UiText source="لغة جديدة" />
        </button>
      </form>
      {languages.isLoading ? (
        <div className="skeleton" />
      ) : languages.error ? (
        <div className="status error" role="alert">
          {tText("تعذر تحميل اللغات")}
          <button className="btn secondary" onClick={() => void languages.refetch()}>
            <UiText source="إعادة المحاولة" />
          </button>
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                {["الرمز", "الاسم", "الاتجاه", "الحالة", "إجراء"].map((label) => (
                  <th key={label}>
                    <UiText source={label} />
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {languages.data?.map((language) => (
                <tr key={language.code}>
                  <td>{language.code}</td>
                  <td>{language.name}</td>
                  <td>{language.direction}</td>
                  <td>
                    <UiText source={language.is_active ? "مفعّلة" : "معطلة"} />
                  </td>
                  <td>
                    <button
                      className="btn secondary"
                      onClick={() => {
                        setEditing(language.code);
                        setForm({
                          code: language.code,
                          name: language.name,
                          direction: language.direction,
                          is_active: Boolean(language.is_active),
                        });
                      }}
                    >
                      <UiText source="تعديل" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="muted">
        {tText(
          "تعديل ترجمة الأدوار والمديريات والصلاحيات متاح في شاشة الأدوار والصلاحيات. تفضيل لغة الواجهة يُحفظ على هذا الجهاز فقط.",
        )}
      </p>
      <AdminAlert text={save.message} />
    </AdminPage>
  );
}
