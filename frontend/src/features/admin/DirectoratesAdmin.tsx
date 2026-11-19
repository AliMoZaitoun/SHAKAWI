import { useState } from "react";
import { Building2, Pencil, Plus, Trash2 } from "lucide-react";
import { ApiError, api } from "../../shared/api/client";
import type { Directorate } from "../../shared/api/types";
import { useResource } from "../../shared/api/hooks";
import { useI18n } from "../../shared/i18n/I18n";
import { UiText } from "../../shared/i18n/UiText";
import { AdminAlert, AdminPage, useAdminSave } from "./AdminPage";
import { AdminDialog } from "./AdminDialog";
import "./admin-ui.css";

type DirectorateForm = {
  name: string;
  description: string;
  location: string;
  is_active: boolean;
  parent_id: string;
};

const blankForm: DirectorateForm = {
  name: "",
  description: "",
  location: "",
  is_active: true,
  parent_id: "",
};

export function DirectoratesAdmin() {
  const { lang, tText } = useI18n();
  const query = useResource<Directorate[]>("/admin/directorates", lang);
  const save = useAdminSave();
  const [editing, setEditing] = useState<Directorate | null>(null);
  const [form, setForm] = useState<DirectorateForm>(blankForm);
  const [show, setShow] = useState(false);

  function begin(directorate?: Directorate) {
    setEditing(directorate ?? null);
    setForm(
      directorate
        ? {
            name: directorate.name,
            description: directorate.description,
            location: directorate.location,
            is_active: directorate.is_active,
            parent_id: directorate.parent_id ? String(directorate.parent_id) : "",
          }
        : { ...blankForm },
    );
    setShow(true);
  }

  function descendantsOf(rootId: number) {
    const descendants = new Set([rootId]);
    let foundNew = true;
    while (foundNew) {
      foundNew = false;
      for (const item of query.data ?? []) {
        if (item.parent_id && descendants.has(item.parent_id) && !descendants.has(item.id)) {
          descendants.add(item.id);
          foundNew = true;
        }
      }
    }
    return descendants;
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const succeeded = await save.run(() =>
      api(editing ? `/admin/directorates/${editing.id}` : "/admin/directorates", {
        method: editing ? "PUT" : "POST",
        body: {
          ...form,
          parent_id: form.parent_id ? Number(form.parent_id) : null,
        },
      }),
    );
    if (succeeded) setShow(false);
  }

  async function remove(directorate: Directorate) {
    if (!window.confirm(tText("هل تريد حذف هذه المديرية؟"))) return;
    await save.run(async () => {
      try {
        await api(`/admin/directorates/${directorate.id}`, { method: "DELETE" });
      } catch (error) {
        if (
          error instanceof ApiError &&
          error.status === 409 &&
          window.confirm(tText("المديرية مستخدمة. هل تريد تعطيلها بدلًا من ذلك؟"))
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
  }

  return (
    <AdminPage
      title="إدارة المديريات"
      required="directorates.manage"
      subtitle="إنشاء وتعديل المديريات. عند وجود شكاوى مرتبطة، عطّل المديرية بدل حذفها."
      headerAction={
        <button className="btn" type="button" disabled={save.busy} onClick={() => begin()}>
          <Plus size={17} aria-hidden="true" />
          <UiText source="إضافة مديرية" />
        </button>
      }
    >
      {query.isLoading ? (
        <div className="skeleton" />
      ) : query.error ? (
        <div className="status error" role="alert">
          {tText("تعذر تحميل المديريات")}
          <button className="btn secondary" type="button" onClick={() => void query.refetch()}>
            <UiText source="إعادة المحاولة" />
          </button>
        </div>
      ) : query.data?.length ? (
        <>
          <div className="admin-role-meta muted">
            <span>
              <Building2 size={15} aria-hidden="true" /> {query.data.length}{" "}
              <UiText source="مديرية" />
            </span>
            <span>
              {query.data.filter((item) => item.is_active).length} <UiText source="نشطة" />
            </span>
          </div>
          <div className="table-wrap" style={{ marginTop: 14 }}>
            <table>
              <thead>
                <tr>
                  {["المديرية", "المديرية الأب", "الموقع", "الحالة", "المدير الحالي", "إجراء"].map(
                    (heading) => (
                      <th key={heading}>
                        <UiText source={heading} />
                      </th>
                    ),
                  )}
                </tr>
              </thead>
              <tbody>
                {query.data.map((directorate) => (
                  <tr key={directorate.id}>
                    <td>
                      <b>{directorate.hierarchy_path ?? directorate.name}</b>
                      {directorate.description && <div className="muted">{directorate.description}</div>}
                    </td>
                    <td>{directorate.parent_name ?? tText("بدون مديرية أب")}</td>
                    <td>{directorate.location || "—"}</td>
                    <td>
                      <span className={`badge ${directorate.is_active ? "" : "red"}`}>
                        {tText(directorate.is_active ? "نشطة" : "معطلة")}
                      </span>
                    </td>
                    <td>{directorate.current_manager?.full_name ?? tText("غير معيّن")}</td>
                    <td>
                      <div className="admin-row-actions">
                        <button
                          className="admin-icon-button"
                          type="button"
                          title={tText("تعديل")}
                          aria-label={`${tText("تعديل")} ${directorate.name}`}
                          disabled={save.busy}
                          onClick={() => begin(directorate)}
                        >
                          <Pencil size={16} aria-hidden="true" />
                        </button>
                        <button
                          className="admin-icon-button danger"
                          type="button"
                          title={tText("حذف / تعطيل")}
                          aria-label={`${tText("حذف / تعطيل")} ${directorate.name}`}
                          disabled={save.busy}
                          onClick={() => void remove(directorate)}
                        >
                          <Trash2 size={16} aria-hidden="true" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : (
        <div className="admin-empty">
          <Building2 size={24} aria-hidden="true" />
          <p>
            <UiText source="لا توجد مديريات بعد." />
          </p>
          <button className="btn" type="button" onClick={() => begin()}>
            <Plus size={17} aria-hidden="true" />
            <UiText source="إضافة مديرية" />
          </button>
        </div>
      )}
      {!show && <AdminAlert text={save.message} isError={save.isError} />}
      {show && (
        <AdminDialog
          title={editing ? "تعديل مديرية" : "مديرية جديدة"}
          onClose={() => setShow(false)}
        >
          <p className="muted admin-dialog-intro">
            <UiText source="المديرية الأعلى تشمل المديريات التابعة في نطاق صلاحياتها." />
          </p>
          <form className="admin-dialog-form" onSubmit={(event) => void submit(event)}>
            <div className="form-grid">
              {(["name", "description", "location"] as const).map((key) => (
                <label key={key} className="field-label">
                  <UiText
                    source={{ name: "الاسم", description: "الوصف", location: "الموقع" }[key]}
                  />
                  <input
                    required={key === "name"}
                    className="field"
                    value={form[key]}
                    onChange={(event) => setForm({ ...form, [key]: event.target.value })}
                  />
                </label>
              ))}
              <label className="field-label">
                <UiText source="المديرية الأب" />
                <select
                  className="field"
                  value={form.parent_id}
                  onChange={(event) => setForm({ ...form, parent_id: event.target.value })}
                >
                  <option value="">{tText("بدون مديرية أب")}</option>
                  {(query.data ?? [])
                    .filter((item) => !editing || !descendantsOf(editing.id).has(item.id))
                    .map((item) => (
                      <option
                        key={item.id}
                        value={item.id}
                        disabled={!item.is_active && editing?.parent_id !== item.id}
                      >
                        {item.hierarchy_path ?? item.name}
                      </option>
                    ))}
                </select>
              </label>
            </div>
            <label className="row">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(event) => setForm({ ...form, is_active: event.target.checked })}
              />
              <UiText source="نشطة" />
            </label>
            <AdminAlert text={save.message} isError={save.isError} />
            <div className="admin-dialog-footer">
              <button className="btn" disabled={save.busy}>
                <UiText source="حفظ" />
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
