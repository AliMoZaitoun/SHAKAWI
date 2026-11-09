import { useState } from "react";
import { api } from "../../shared/api/client";
import type { Permission, Role } from "../../shared/api/types";
import { useResource } from "../../shared/api/hooks";
import { useI18n } from "../../shared/i18n/I18n";
import { UiText } from "../../shared/i18n/UiText";
import { AdminAlert, AdminPage, useAdminSave } from "./AdminPage";
import { Link } from "react-router-dom";

export function RolesAdmin() {
  const { lang, tText } = useI18n();
  const roles = useResource<Role[]>("/admin/roles", lang);
  const permissions = useResource<Permission[]>("/admin/permissions", lang);
  const save = useAdminSave();
  const [editing, setEditing] = useState<Role | null>(null);
  const [form, setForm] = useState({
    code: "",
    name: "",
    description: "",
    permissions: [] as string[],
  });
  const [labels, setLabels] = useState<Record<string, { name: string; description: string }>>({});
  const [showForm, setShowForm] = useState(false);

  function start(role?: Role) {
    setEditing(role ?? null);
    setShowForm(true);
    setForm(
      role
        ? {
            code: role.code,
            name: role.name,
            description: role.description,
            permissions: role.permissions,
          }
        : { code: "", name: "", description: "", permissions: [] },
    );
  }

  return (
    <AdminPage
      title="الأدوار ومصفوفة الصلاحيات"
      subtitle="إنشاء الأدوار وتوزيع صلاحيات الخادم عليها. التغيير يُسجل في سجل التدقيق ويؤثر على الصلاحيات الفعلية."
    >
      <div className="status info">
        <UiText source="ترجمة أسماء الأدوار والصلاحيات لكل لغة تُدار من شاشة الترجمات." />{" "}
        <Link to="/employee/admin/translations" className="btn secondary">
          <UiText source="فتح إدارة الترجمات" />
        </Link>
      </div>
      <div className="grid grid-two">
        {roles.isLoading || permissions.isLoading ? (
          <div className="skeleton" />
        ) : roles.error || permissions.error ? (
          <div className="status error" role="alert">
            {tText("تعذر تحميل الكتالوج.")}
            <button
              className="btn secondary"
              onClick={() => {
                void roles.refetch();
                void permissions.refetch();
              }}
            >
              <UiText source="إعادة المحاولة" />
            </button>
          </div>
        ) : (
          roles.data?.map((role) => (
            <article className="panel" key={role.id}>
              <div className="row" style={{ justifyContent: "space-between" }}>
                <h3>{role.name}</h3>
                <span className="badge">{role.code}</span>
              </div>
              <p className="muted">{role.description}</p>
              <div className="muted">
                {role.permissions.length ? role.permissions.join(" · ") : tText("لا توجد صلاحيات")}
              </div>
              <button className="btn secondary" onClick={() => start(role)}>
                <UiText source="تعديل" />
              </button>
              {!role.is_system && (
                <button
                  className="btn danger"
                  onClick={() => {
                    if (window.confirm(tText("حذف الدور؟"))) {
                      void save.run(() => api(`/admin/roles/${role.id}`, { method: "DELETE" }));
                    }
                  }}
                >
                  <UiText source="حذف" />
                </button>
              )}
            </article>
          ))
        )}
      </div>
      <button className="btn" style={{ marginTop: 16 }} onClick={() => start()}>
        <UiText source="إنشاء دور" />
      </button>
      {showForm && (
        <form
          className="panel form-grid"
          onSubmit={(event) => {
            event.preventDefault();
            void save.run(() =>
              api(editing ? `/admin/roles/${editing.id}` : "/admin/roles", {
                method: editing ? "PUT" : "POST",
                body: editing
                  ? {
                      name: form.name,
                      description: form.description,
                      permissions: form.permissions,
                    }
                  : form,
              }),
            );
          }}
        >
          <h2 className="form-field full">
            <UiText source={editing ? "تعديل الدور" : "دور جديد"} />
          </h2>
          {!editing && (
            <label className="field-label">
              <UiText source="الرمز" />
              <input
                required
                pattern="[a-z][a-z0-9_]+"
                className="field"
                value={form.code}
                onChange={(event) => setForm({ ...form, code: event.target.value })}
              />
            </label>
          )}
          <label className="field-label">
            <UiText source="الاسم" />
            <input
              required
              minLength={2}
              className="field"
              value={form.name}
              onChange={(event) => setForm({ ...form, name: event.target.value })}
            />
          </label>
          <label className="field-label form-field full">
            <UiText source="الوصف" />
            <textarea
              className="field"
              value={form.description}
              onChange={(event) => setForm({ ...form, description: event.target.value })}
            />
          </label>
          <div className="form-field full">
            <h3>
              <UiText source="مصفوفة الصلاحيات المتاحة" />
            </h3>
            <div className="grid grid-two">
              {permissions.data?.map((permission) => (
                <label className="status info" key={permission.code}>
                  <input
                    type="checkbox"
                    checked={form.permissions.includes(permission.code)}
                    onChange={(event) =>
                      setForm({
                        ...form,
                        permissions: event.target.checked
                          ? [...form.permissions, permission.code]
                          : form.permissions.filter((code) => code !== permission.code),
                      })
                    }
                  />
                  <b>{permission.name}</b>
                  <div className="muted">
                    {permission.code} · {permission.description}
                  </div>
                </label>
              ))}
            </div>
          </div>
          <div className="row form-field full">
            <button className="btn" disabled={save.busy}>
              <UiText source="حفظ الدور" />
            </button>
            <button className="btn secondary" type="button" onClick={() => setShowForm(false)}>
              <UiText source="إلغاء" />
            </button>
          </div>
        </form>
      )}
      <section className="panel">
        <h2>
          <UiText source="كتالوج الصلاحيات" />
        </h2>
        {permissions.data?.map((permission) => (
          <form
            key={permission.code}
            className="row"
            onSubmit={(event) => {
              event.preventDefault();
              void save.run(() =>
                api(`/admin/permissions/${encodeURIComponent(permission.code)}`, {
                  method: "PATCH",
                  body: labels[permission.code] ?? {
                    name: permission.name,
                    description: permission.description,
                  },
                }),
              );
            }}
          >
            <code>{permission.code}</code>
            <input
              className="field"
              aria-label={tText("اسم الصلاحية")}
              value={labels[permission.code]?.name ?? permission.name}
              onChange={(event) =>
                setLabels({
                  ...labels,
                  [permission.code]: {
                    name: event.target.value,
                    description: labels[permission.code]?.description ?? permission.description,
                  },
                })
              }
            />
            <input
              className="field"
              aria-label={tText("وصف الصلاحية")}
              value={labels[permission.code]?.description ?? permission.description}
              onChange={(event) =>
                setLabels({
                  ...labels,
                  [permission.code]: {
                    name: labels[permission.code]?.name ?? permission.name,
                    description: event.target.value,
                  },
                })
              }
            />
            <button className="btn secondary">
              <UiText source="تحديث الاسم" />
            </button>
          </form>
        ))}
      </section>
      <AdminAlert text={save.message} />
    </AdminPage>
  );
}
