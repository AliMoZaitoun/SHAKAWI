import { useMemo, useState } from "react";
import { KeyRound, Pencil, Plus, Search, ShieldCheck, Trash2, UsersRound } from "lucide-react";
import { Link } from "react-router-dom";
import { api } from "../../shared/api/client";
import type { Permission, Role } from "../../shared/api/types";
import { useResource } from "../../shared/api/hooks";
import { useI18n } from "../../shared/i18n/I18n";
import { UiText } from "../../shared/i18n/UiText";
import { AdminAlert, AdminPage, useAdminSave } from "./AdminPage";
import { AdminDialog } from "./AdminDialog";
import "./admin-ui.css";

type RoleForm = {
  code: string;
  name: string;
  description: string;
  permissions: string[];
};

const PAGE_SIZE = 6;
const PERMISSION_PAGE_SIZE = 10;

export function RolesAdmin() {
  const { lang, tText } = useI18n();
  const [activeSection, setActiveSection] = useState<"roles" | "permissions">("roles");
  const roles = useResource<Role[]>("/admin/roles", lang);
  const permissions = useResource<Permission[]>("/admin/permissions", lang);
  const arabicPermissions = useResource<Permission[]>(
    "/admin/permissions",
    "ar",
    activeSection === "permissions",
  );
  const save = useAdminSave();
  const [editingRole, setEditingRole] = useState<Role | null>(null);
  const [roleForm, setRoleForm] = useState<RoleForm>({
    code: "",
    name: "",
    description: "",
    permissions: [],
  });
  const [editingPermission, setEditingPermission] = useState<Permission | null>(null);
  const [permissionForm, setPermissionForm] = useState({ name: "", description: "" });
  const [roleSearch, setRoleSearch] = useState("");
  const [permissionSearch, setPermissionSearch] = useState("");
  const [permissionEditError, setPermissionEditError] = useState("");
  const [rolePage, setRolePage] = useState(1);
  const [permissionPage, setPermissionPage] = useState(1);
  const [showRoleDialog, setShowRoleDialog] = useState(false);

  const filteredRoles = useMemo(() => {
    const term = roleSearch.trim().toLocaleLowerCase();
    return (roles.data ?? []).filter(
      (role) =>
        !term ||
        [role.name, role.description, role.code].some((value) =>
          value.toLocaleLowerCase().includes(term),
        ),
    );
  }, [roleSearch, roles.data]);

  const filteredPermissions = useMemo(() => {
    const term = permissionSearch.trim().toLocaleLowerCase();
    return (permissions.data ?? []).filter(
      (permission) =>
        !term ||
        [permission.code, permission.name, permission.description].some((value) =>
          value.toLocaleLowerCase().includes(term),
        ),
    );
  }, [permissionSearch, permissions.data]);

  const rolePageCount = Math.max(1, Math.ceil(filteredRoles.length / PAGE_SIZE));
  const permissionPageCount = Math.max(
    1,
    Math.ceil(filteredPermissions.length / PERMISSION_PAGE_SIZE),
  );
  const visibleRoles = filteredRoles.slice((rolePage - 1) * PAGE_SIZE, rolePage * PAGE_SIZE);
  const visiblePermissions = filteredPermissions.slice(
    (permissionPage - 1) * PERMISSION_PAGE_SIZE,
    permissionPage * PERMISSION_PAGE_SIZE,
  );

  function startRole(role?: Role) {
    setEditingRole(role ?? null);
    setRoleForm(
      role
        ? {
            code: role.code,
            name: role.name,
            description: role.description,
            permissions: [...role.permissions],
          }
        : { code: "", name: "", description: "", permissions: [] },
    );
    save.setMessage("");
    setShowRoleDialog(true);
  }

  function startPermission(permission: Permission) {
    const arabicPermission = arabicPermissions.data?.find((item) => item.code === permission.code);
    if (!arabicPermission) {
      setPermissionEditError(tText("تعذر تحميل بيانات الصلاحية العربية."));
      return;
    }
    setPermissionEditError("");
    setEditingPermission(arabicPermission);
    setPermissionForm({ name: arabicPermission.name, description: arabicPermission.description });
    save.setMessage("");
  }

  async function submitRole(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const succeeded = await save.run(() =>
      api(editingRole ? `/admin/roles/${editingRole.id}` : "/admin/roles", {
        method: editingRole ? "PUT" : "POST",
        body: editingRole
          ? {
              name: roleForm.name,
              description: roleForm.description,
              permissions: roleForm.permissions,
            }
          : roleForm,
      }),
    );
    if (succeeded) setShowRoleDialog(false);
  }

  async function submitPermission(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editingPermission) return;
    const succeeded = await save.run(() =>
      api(`/admin/permissions/${encodeURIComponent(editingPermission.code)}`, {
        method: "PATCH",
        body: permissionForm,
      }),
    );
    if (succeeded) setEditingPermission(null);
  }

  const headerAction =
    activeSection === "roles" ? (
      <button className="btn" type="button" disabled={save.busy} onClick={() => startRole()}>
        <Plus size={17} aria-hidden="true" />
        <UiText source="إنشاء دور" />
      </button>
    ) : null;

  return (
    <AdminPage
      title="الأدوار ومصفوفة الصلاحيات"
      subtitle="إنشاء الأدوار وتوزيع صلاحيات الخادم عليها، مع الحفاظ على الصلاحيات الفعلية ونطاقات الوصول."
      headerAction={headerAction}
    >
      <div className="admin-tabs" role="tablist" aria-label={tText("إدارة الأدوار والصلاحيات")}>
        <button
          className="admin-tab"
          type="button"
          role="tab"
          aria-selected={activeSection === "roles"}
          onClick={() => setActiveSection("roles")}
        >
          <ShieldCheck size={16} aria-hidden="true" />
          <UiText source="الأدوار" />
          <span className="admin-tab-count">{roles.data?.length ?? 0}</span>
        </button>
        <button
          className="admin-tab"
          type="button"
          role="tab"
          aria-selected={activeSection === "permissions"}
          onClick={() => setActiveSection("permissions")}
        >
          <KeyRound size={16} aria-hidden="true" />
          <UiText source="الصلاحيات" />
          <span className="admin-tab-count">{permissions.data?.length ?? 0}</span>
        </button>
      </div>

      {roles.isLoading ||
      permissions.isLoading ||
      (activeSection === "permissions" && arabicPermissions.isLoading) ? (
        <div className="skeleton" style={{ marginTop: 18 }} />
      ) : roles.error || permissions.error || (activeSection === "permissions" && arabicPermissions.error) ? (
        <div className="status error" role="alert">
          {tText("تعذر تحميل الكتالوج.")}
          <button
            className="btn secondary"
            type="button"
            onClick={() => {
              void roles.refetch();
              void permissions.refetch();
              if (activeSection === "permissions") void arabicPermissions.refetch();
            }}
          >
            <UiText source="إعادة المحاولة" />
          </button>
        </div>
      ) : activeSection === "roles" ? (
        <section role="tabpanel" aria-label={tText("الأدوار")}>
          <div className="status info">
            <UiText source="ترجمة أسماء الأدوار والصلاحيات لكل لغة تُدار من شاشة الترجمات." />{" "}
            <Link to="/employee/admin/translations" className="btn secondary">
              <UiText source="فتح إدارة الترجمات" />
            </Link>
          </div>
          <div className="admin-toolbar">
            <label className="sr-only" htmlFor="role-search">
              {tText("ابحث عن دور")}
            </label>
            <input
              id="role-search"
              className="field"
              type="search"
              placeholder={tText("ابحث عن دور")}
              value={roleSearch}
              onChange={(event) => {
                setRoleSearch(event.target.value);
                setRolePage(1);
              }}
            />
            <span className="muted">
              <UsersRound size={15} aria-hidden="true" /> {filteredRoles.length}{" "}
              <UiText source="دور" />
            </span>
          </div>
          {filteredRoles.length ? (
            <>
              <div className="admin-card-grid">
                {visibleRoles.map((role) => {
                  const permissionNames = role.permissions.map(
                    (code) => permissions.data?.find((item) => item.code === code)?.name ?? code,
                  );
                  return (
                    <article className="panel admin-role-card" key={role.id}>
                      <div className="admin-role-heading">
                        <h3>{role.name}</h3>
                        <span className="badge">{role.code}</span>
                      </div>
                      <p className="muted">{role.description || tText("لا يوجد وصف.")}</p>
                      <div className="admin-permission-chips">
                        {permissionNames.length ? (
                          <>
                            {permissionNames.slice(0, 4).map((name) => (
                              <span className="admin-permission-chip" key={name}>
                                {name}
                              </span>
                            ))}
                            {permissionNames.length > 4 && (
                              <span className="admin-permission-chip">
                                +{permissionNames.length - 4}
                              </span>
                            )}
                          </>
                        ) : (
                          <span className="muted">{tText("لا توجد صلاحيات")}</span>
                        )}
                      </div>
                      <div className="admin-row-actions">
                        <button
                          className="btn secondary"
                          type="button"
                          onClick={() => startRole(role)}
                        >
                          <Pencil size={15} aria-hidden="true" />
                          <UiText source="تعديل" />
                        </button>
                        {!role.is_system && (
                          <button
                            className="admin-icon-button danger"
                            type="button"
                            title={tText("حذف")}
                            aria-label={`${tText("حذف")} ${role.name}`}
                            disabled={save.busy}
                            onClick={() => {
                              if (window.confirm(tText("حذف الدور؟"))) {
                                void save.run(() =>
                                  api(`/admin/roles/${role.id}`, { method: "DELETE" }),
                                );
                              }
                            }}
                          >
                            <Trash2 size={16} aria-hidden="true" />
                          </button>
                        )}
                      </div>
                    </article>
                  );
                })}
              </div>
              <Pagination
                current={rolePage}
                total={rolePageCount}
                onChange={setRolePage}
                tText={tText}
              />
            </>
          ) : (
            <div className="admin-empty">
              <ShieldCheck size={24} aria-hidden="true" />
              <p>{roleSearch ? tText("لا توجد نتائج مطابقة.") : tText("لا توجد أدوار بعد.")}</p>
              {!roleSearch && (
                <button className="btn" type="button" onClick={() => startRole()}>
                  <Plus size={17} aria-hidden="true" />
                  <UiText source="إنشاء دور" />
                </button>
              )}
            </div>
          )}
        </section>
      ) : (
        <section role="tabpanel" aria-label={tText("الصلاحيات")}>
          <div className="admin-toolbar">
            <label className="sr-only" htmlFor="permission-search">
              {tText("ابحث عن صلاحية")}
            </label>
            <div style={{ position: "relative", flex: "1 1 300px" }}>
              <Search
                size={16}
                aria-hidden="true"
                style={{
                  position: "absolute",
                  top: "50%",
                  insetInlineStart: 13,
                  transform: "translateY(-50%)",
                  color: "var(--muted)",
                }}
              />
              <input
                id="permission-search"
                className="field"
                style={{ paddingInlineStart: 38 }}
                type="search"
                placeholder={tText("ابحث عن صلاحية")}
                value={permissionSearch}
                onChange={(event) => {
                  setPermissionSearch(event.target.value);
                  setPermissionPage(1);
                }}
              />
            </div>
            <span className="muted">
              {filteredPermissions.length} <UiText source="صلاحية" />
            </span>
          </div>
          {filteredPermissions.length ? (
            <>
              <div className="admin-permission-list">
                {visiblePermissions.map((permission) => (
                  <article className="admin-permission-row" key={permission.code}>
                    <code>{permission.code}</code>
                    <span className="admin-permission-description">
                      <strong>{permission.name}</strong>
                      {permission.description && <span> · {permission.description}</span>}
                    </span>
                    <button
                      className="btn secondary"
                      type="button"
                      disabled={arabicPermissions.isLoading || !!arabicPermissions.error}
                      onClick={() => startPermission(permission)}
                    >
                      <Pencil size={15} aria-hidden="true" />
                      <UiText source="تعديل" />
                    </button>
                  </article>
                ))}
              </div>
              <Pagination
                current={permissionPage}
                total={permissionPageCount}
                onChange={setPermissionPage}
                tText={tText}
              />
            </>
          ) : (
            <div className="admin-empty">{tText("لا توجد نتائج مطابقة.")}</div>
          )}
        </section>
      )}

      {!showRoleDialog && !editingPermission && (
        <AdminAlert text={save.message} isError={save.isError} />
      )}

      {showRoleDialog && (
        <AdminDialog
          title={editingRole ? "تعديل الدور" : "دور جديد"}
          className="admin-dialog-wide"
          onClose={() => setShowRoleDialog(false)}
        >
          <form className="admin-dialog-form" onSubmit={(event) => void submitRole(event)}>
            {!editingRole && (
              <label className="field-label">
                <UiText source="الرمز" />
                <input
                  required
                  pattern="[a-z][a-z0-9_]+"
                  className="field"
                  value={roleForm.code}
                  onChange={(event) => setRoleForm({ ...roleForm, code: event.target.value })}
                />
              </label>
            )}
            <label className="field-label">
              <UiText source="الاسم" />
              <input
                required
                minLength={2}
                className="field"
                value={roleForm.name}
                onChange={(event) => setRoleForm({ ...roleForm, name: event.target.value })}
              />
            </label>
            <label className="field-label">
              <UiText source="الوصف" />
              <textarea
                className="field"
                value={roleForm.description}
                onChange={(event) => setRoleForm({ ...roleForm, description: event.target.value })}
              />
            </label>
            <div>
              <div className="admin-role-meta" style={{ marginBottom: 9 }}>
                <h3>
                  <UiText source="مصفوفة الصلاحيات المتاحة" />
                </h3>
                <span className="badge">{roleForm.permissions.length}</span>
              </div>
              {editingRole?.code === "system_admin" && (
                <p className="muted admin-dialog-intro">
                  <UiText source="صلاحيات مدير النظام محمية ولا يمكن تعديلها." />
                </p>
              )}
              <div className="admin-permission-options">
                {permissions.data?.map((permission) => (
                  <label className="admin-permission-option" key={permission.code}>
                    <input
                      type="checkbox"
                      checked={roleForm.permissions.includes(permission.code)}
                      disabled={editingRole?.code === "system_admin"}
                      onChange={(event) =>
                        setRoleForm({
                          ...roleForm,
                          permissions: event.target.checked
                            ? [...roleForm.permissions, permission.code]
                            : roleForm.permissions.filter((code) => code !== permission.code),
                        })
                      }
                    />
                    <span>
                      <strong>{permission.name}</strong>
                      <small>
                        {permission.code}
                        {permission.description ? ` · ${permission.description}` : ""}
                      </small>
                    </span>
                  </label>
                ))}
              </div>
            </div>
            <AdminAlert text={save.message} isError={save.isError} />
            <div className="admin-dialog-footer">
              <button className="btn" disabled={save.busy}>
                <UiText source="حفظ الدور" />
              </button>
              <button
                className="btn secondary"
                type="button"
                disabled={save.busy}
                onClick={() => setShowRoleDialog(false)}
              >
                <UiText source="إلغاء" />
              </button>
            </div>
          </form>
        </AdminDialog>
      )}

      {permissionEditError && (
        <div className="status error" role="alert">
          {permissionEditError}
        </div>
      )}

      {editingPermission && (
        <AdminDialog
          title="تعديل الصلاحية"
          onClose={() => setEditingPermission(null)}
        >
          <p className="admin-dialog-intro muted">
            <UiText source="تعديل الاسم هنا يغيّر الترجمة العربية الأساسية. لإدارة اللغات الأخرى استخدم الترجمات." />
            <br />
            <code>{editingPermission.code}</code>
          </p>
          <form className="admin-dialog-form" onSubmit={(event) => void submitPermission(event)}>
            <label className="field-label">
              <UiText source="اسم الصلاحية بالعربية" />
              <input
                className="field"
                required
                value={permissionForm.name}
                onChange={(event) =>
                  setPermissionForm({ ...permissionForm, name: event.target.value })
                }
              />
            </label>
            <label className="field-label">
              <UiText source="وصف الصلاحية بالعربية" />
              <textarea
                className="field"
                value={permissionForm.description}
                onChange={(event) =>
                  setPermissionForm({ ...permissionForm, description: event.target.value })
                }
              />
            </label>
            <AdminAlert text={save.message} isError={save.isError} />
            <div className="admin-dialog-footer">
              <button className="btn" disabled={save.busy}>
                <UiText source="تحديث الاسم" />
              </button>
              <button
                className="btn secondary"
                type="button"
                disabled={save.busy}
                onClick={() => setEditingPermission(null)}
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

function Pagination({
  current,
  total,
  onChange,
  tText,
}: {
  current: number;
  total: number;
  onChange: (page: number) => void;
  tText: (source: string) => string;
}) {
  if (total <= 1) return null;
  return (
    <nav className="admin-pagination" aria-label={tText("التنقل بين الصفحات")}>
      <button
        className="btn secondary"
        type="button"
        disabled={current <= 1}
        onClick={() => onChange(current - 1)}
      >
        <UiText source="السابق" />
      </button>
      <span className="admin-pagination-label">
        {current} / {total}
      </span>
      <button
        className="btn secondary"
        type="button"
        disabled={current >= total}
        onClick={() => onChange(current + 1)}
      >
        <UiText source="التالي" />
      </button>
    </nav>
  );
}
