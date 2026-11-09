import { useState } from "react";
import { ApiError, api } from "../../shared/api/client";
import type { Directorate } from "../../shared/api/types";
import { useResource } from "../../shared/api/hooks";
import { useI18n } from "../../shared/i18n/I18n";
import { UiText } from "../../shared/i18n/UiText";
import { AdminAlert, AdminPage, useAdminSave } from "./AdminPage";

export function DirectoratesAdmin() {
  const { lang, tText } = useI18n();
  const query = useResource<Directorate[]>("/admin/directorates", lang);
  const save = useAdminSave();
  const [editing, setEditing] = useState<Directorate | null>(null);
  const [form, setForm] = useState({ name: "", description: "", location: "", is_active: true });
  const [show, setShow] = useState(false);

  function begin(directorate?: Directorate) {
    setEditing(directorate ?? null);
    setShow(true);
    setForm(
      directorate
        ? {
            name: directorate.name,
            description: directorate.description,
            location: directorate.location,
            is_active: directorate.is_active,
          }
        : { name: "", description: "", location: "", is_active: true },
    );
  }

  return (
    <AdminPage
      title="إدارة المديريات"
      required="directorates.manage"
      subtitle="إنشاء وتعديل المديريات. عند وجود شكاوى مرتبطة، عطّل المديرية بدل حذفها."
    >
      <button className="btn" onClick={() => begin()}>
        <UiText source="إضافة مديرية" />
      </button>
      {query.isLoading ? (
        <div className="skeleton" />
      ) : query.error ? (
        <div className="status error" role="alert">
          {tText("تعذر تحميل المديريات")}
          <button className="btn secondary" onClick={() => void query.refetch()}>
            <UiText source="إعادة المحاولة" />
          </button>
        </div>
      ) : (
        <div className="table-wrap" style={{ marginTop: 16 }}>
          <table>
            <thead>
              <tr>
                {["المديرية", "الموقع", "الحالة", "المدير الحالي", "إجراء"].map((heading) => (
                  <th key={heading}>
                    <UiText source={heading} />
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {query.data?.map((directorate) => (
                <tr key={directorate.id}>
                  <td>
                    <b>{directorate.name}</b>
                    <div className="muted">{directorate.description}</div>
                  </td>
                  <td>{directorate.location}</td>
                  <td>
                    <UiText source={directorate.is_active ? "نشطة" : "معطلة"} />
                  </td>
                  <td>{directorate.current_manager?.full_name ?? tText("غير معيّن")}</td>
                  <td>
                    <button className="btn secondary" onClick={() => begin(directorate)}>
                      <UiText source="تعديل" />
                    </button>
                    <button
                      className="btn danger"
                      onClick={() => {
                        if (!window.confirm(tText("هل تريد حذف هذه المديرية؟"))) return;
                        void save.run(async () => {
                          try {
                            await api(`/admin/directorates/${directorate.id}`, {
                              method: "DELETE",
                            });
                          } catch (error) {
                            if (
                              error instanceof ApiError &&
                              error.status === 409 &&
                              window.confirm(
                                tText("المديرية مستخدمة. هل تريد تعطيلها بدلًا من ذلك؟"),
                              )
                            ) {
                              await api(`/admin/directorates/${directorate.id}`, {
                                method: "PUT",
                                body: { ...directorate, is_active: false },
                              });
                              return;
                            }
                            throw error;
                          }
                        });
                      }}
                    >
                      <UiText source="حذف / تعطيل" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {show && (
        <form
          className="form-grid panel"
          onSubmit={(event) => {
            event.preventDefault();
            void save.run(() =>
              api(editing ? `/admin/directorates/${editing.id}` : "/admin/directorates", {
                method: editing ? "PUT" : "POST",
                body: form,
              }),
            );
          }}
        >
          <h2 className="form-field full">
            <UiText source={editing ? "تعديل مديرية" : "مديرية جديدة"} />
          </h2>
          {(["name", "description", "location"] as const).map((key) => (
            <label key={key} className="field-label">
              <UiText source={{ name: "الاسم", description: "الوصف", location: "الموقع" }[key]} />
              <input
                required={key === "name"}
                className="field"
                value={form[key]}
                onChange={(event) => setForm({ ...form, [key]: event.target.value })}
              />
            </label>
          ))}
          <label>
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(event) => setForm({ ...form, is_active: event.target.checked })}
            />{" "}
            <UiText source="نشطة" />
          </label>
          <div className="row form-field full">
            <button className="btn" disabled={save.busy}>
              <UiText source="حفظ" />
            </button>
            <button type="button" className="btn secondary" onClick={() => setShow(false)}>
              <UiText source="إلغاء" />
            </button>
          </div>
        </form>
      )}
      <AdminAlert text={save.message} />
    </AdminPage>
  );
}
