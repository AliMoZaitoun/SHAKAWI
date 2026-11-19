import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  BadgeCheck,
  Building2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Plus,
  Search,
  Shield,
  UsersRound,
} from "lucide-react";
import { api } from "../../shared/api/client";
import type { Directorate, Employee, Page, Role } from "../../shared/api/types";
import { useResource, useSession } from "../../shared/api/hooks";
import { useI18n } from "../../shared/i18n/I18n";
import { UiText } from "../../shared/i18n/UiText";
import { AdminAlert, AdminPage, useAdminSave } from "./AdminPage";
import { EmployeeProfileForm, type EmployeeDraft } from "./EmployeeProfileForm";
import { EmployeeRoleAssignmentDialog } from "./EmployeeRoleAssignmentDialog";
import { hasGlobalPermission } from "../employee/permissions";
import "./employees-admin.css";

const PAGE_SIZE = 20;
const blankEmployee: EmployeeDraft = {
  first_name: "",
  last_name: "",
  phone: "",
  email: "",
  username: "",
  password: "",
  directorate_id: "",
  is_active: true,
};

type StatusFilter = "all" | "active" | "inactive";

export function EmployeesAdmin() {
  const { lang, tText } = useI18n();
  const session = useSession();
  const canAssignRoles = hasGlobalPermission(session.data, "rbac.manage");
  const employeeScope = session.data?.permissions?.["employees.manage"]?.directorate_ids;
  const canManageGlobally = employeeScope === null;
  const [page, setPage] = useState(1);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [directorateFilter, setDirectorateFilter] = useState("all");
  const employees = useQuery({
    queryKey: ["admin-employees", page, lang],
    queryFn: () =>
      api<Page<Employee>>(`/admin/employees?page=${page}&page_size=${PAGE_SIZE}`, {
        language: lang,
      }),
    retry: false,
  });
  const roles = useResource<Role[]>("/admin/roles", lang, canAssignRoles);
  const directorates = useResource<Directorate[]>("/admin/employees/directorates", lang);
  const manageableDirectorates = (directorates.data ?? []).filter(
    (item) => canManageGlobally || (employeeScope?.includes(item.id) ?? false),
  );
  const employeeItems = employees.data?.items ?? [];
  const save = useAdminSave();
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<Employee | null>(null);
  const [form, setForm] = useState<EmployeeDraft>({ ...blankEmployee });
  const [roleEmployeeId, setRoleEmployeeId] = useState<number | null>(null);

  const getDirectorateLabel = (id: number) => {
    const item = manageableDirectorates.find((directorate) => directorate.id === id);
    return item?.hierarchy_path ?? item?.name ?? `#${id}`;
  };

  const normalizedQuery = query.trim().toLocaleLowerCase(lang);
  const filteredEmployees = useMemo(
    () =>
      employeeItems.filter((employee) => {
        const name = employee.needs_profile_completion
          ? tText("يحتاج استكمال الملف")
          : `${employee.first_name ?? ""} ${employee.last_name ?? ""}`;
        const directorate = employee.directorate_id
          ? getDirectorateLabel(employee.directorate_id)
          : tText("بدون مديرية");
        const searchText = [
          name,
          employee.username,
          employee.phone ?? "",
          employee.email ?? "",
          directorate,
        ]
          .join(" ")
          .toLocaleLowerCase(lang);
        const matchesStatus =
          statusFilter === "all" ||
          (statusFilter === "active" ? employee.is_active : !employee.is_active);
        const matchesDirectorate =
          directorateFilter === "all" ||
          String(employee.directorate_id ?? "") === directorateFilter;
        return (
          (!normalizedQuery || searchText.includes(normalizedQuery)) &&
          matchesStatus &&
          matchesDirectorate
        );
      }),
    [
      employeeItems,
      directorateFilter,
      getDirectorateLabel,
      lang,
      normalizedQuery,
      statusFilter,
      tText,
    ],
  );

  const activeCount = employeeItems.filter((employee) => employee.is_active).length;
  const assignedCount = employeeItems.filter(
    (employee) => employee.role_assignments.length > 0,
  ).length;
  const roleEmployee = employeeItems.find((employee) => employee.id === roleEmployeeId) ?? null;

  function start(employee?: Employee) {
    setSaveMessage("");
    setEditing(employee ?? null);
    setShowForm(true);
    setForm(
      employee
        ? {
            first_name: employee.first_name ?? "",
            last_name: employee.last_name ?? "",
            phone: employee.phone ?? "",
            email: employee.email ?? "",
            username: employee.username,
            password: "",
            directorate_id: employee.directorate_id ? String(employee.directorate_id) : "",
            is_active: employee.is_active,
          }
        : { ...blankEmployee },
    );
  }

  function setSaveMessage(message: string) {
    save.setMessage(message);
  }

  function openRoleAssignments(employee: Employee) {
    setSaveMessage("");
    setRoleEmployeeId(employee.id);
  }

  function assignRole(body: {
    role_id: number;
    scope_type: "global" | "directorate";
    directorate_id: number | null;
  }) {
    if (roleEmployeeId === null) return;
    void save.run(() =>
      api(`/admin/employees/${roleEmployeeId}/roles`, {
        method: "POST",
        body,
      }),
    );
  }

  function removeRole(assignmentId: number) {
    if (!roleEmployeeId || !window.confirm(tText("إلغاء هذا الإسناد؟"))) return;
    void save.run(() =>
      api(`/admin/employees/${roleEmployeeId}/roles/${assignmentId}`, {
        method: "DELETE",
      }),
    );
  }

  return (
    <AdminPage
      title="إدارة الموظفين"
      required="employees.manage"
      globalOnly={false}
      className="employee-admin-panel"
      subtitle="لا تُستكمل الحسابات القديمة بتخمين بيانات. الإسناد الجديد لا يمنح صلاحيات حتى يُعيّن دور ونطاق."
      headerAction={
        <button className="btn employee-add-button" onClick={() => start()}>
          <Plus size={17} />
          <UiText source="إضافة موظف" />
        </button>
      }
    >
      {!canManageGlobally && (
        <div className="status info employee-scope-notice" role="status">
          {tText("يمكنك إدارة موظفي مديريتك والمديريات التابعة لها فقط. إسناد الأدوار والصلاحيات متاح للإدارة العامة.")}
        </div>
      )}

      <div className="employee-admin-summary" aria-label={tText("ملخص الموظفين")}>
        <div className="employee-summary-item">
          <span className="employee-summary-icon">
            <UsersRound size={17} />
          </span>
          <span className="employee-summary-copy">
            <strong>{employees.data?.total ?? 0}</strong>
            <span>{tText("إجمالي الموظفين")}</span>
          </span>
        </div>
        <div className="employee-summary-item">
          <span className="employee-summary-icon active">
            <BadgeCheck size={17} />
          </span>
          <span className="employee-summary-copy">
            <strong>{activeCount}</strong>
            <span>{tText("نشطون في هذه الصفحة")}</span>
          </span>
        </div>
        <div className="employee-summary-item">
          <span className="employee-summary-icon roles">
            <Shield size={17} />
          </span>
          <span className="employee-summary-copy">
            <strong>{assignedCount}</strong>
            <span>{tText("لديهم دور مسند في هذه الصفحة")}</span>
          </span>
        </div>
        <div className="employee-scope-summary">
          <Building2 size={16} />
          <span>{tText("المديريات ضمن النطاق")}</span>
          <strong>{manageableDirectorates.length}</strong>
        </div>
      </div>

      <section className="employee-directory">
        <header className="employee-directory-heading">
          <div>
            <h2>{tText("دليل الموظفين")}</h2>
            <p>{tText("ابحث ضمن الموظفين الظاهرين، وراجع كل دور مع نطاقه التنظيمي.")}</p>
          </div>
          <span className="employee-record-count">
            {filteredEmployees.length} {tText("من")} {employeeItems.length}
          </span>
        </header>

        <div className="employee-filter-bar">
          <label className="employee-search">
            <Search size={17} aria-hidden="true" />
            <span className="sr-only">{tText("البحث ضمن الموظفين الظاهرين")}</span>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={tText("ابحث بالاسم أو اسم الدخول أو الهاتف")}
            />
          </label>
          <label className="employee-filter">
            <Shield size={15} aria-hidden="true" />
            <span className="sr-only">{tText("تصفية حسب الحالة")}</span>
            <select
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value as StatusFilter)}
            >
              <option value="all">{tText("كل الحالات")}</option>
              <option value="active">{tText("نشط")}</option>
              <option value="inactive">{tText("معطل")}</option>
            </select>
            <ChevronDown size={14} aria-hidden="true" />
          </label>
          <label className="employee-filter employee-directorate-filter">
            <Building2 size={15} aria-hidden="true" />
            <span className="sr-only">{tText("تصفية حسب المديرية")}</span>
            <select
              value={directorateFilter}
              onChange={(event) => setDirectorateFilter(event.target.value)}
            >
              <option value="all">{tText("كل المديريات")}</option>
              {manageableDirectorates.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.hierarchy_path ?? item.name}
                </option>
              ))}
            </select>
            <ChevronDown size={14} aria-hidden="true" />
          </label>
        </div>
        <p className="employee-search-hint">{tText("يُطبق البحث والتصفية على الصفحة الحالية.")}</p>

        {employees.isLoading ? (
          <div className="skeleton employee-directory-loading" role="status">
            {tText("جارٍ التحميل")}
          </div>
        ) : employees.error ? (
          <div className="status error employee-directory-error" role="alert">
            <span>{tText("تعذر تحميل الموظفين.")}</span>
            <button onClick={() => void employees.refetch()} className="btn secondary">
              <UiText source="إعادة المحاولة" />
            </button>
          </div>
        ) : (
          <>
            <div className="employee-directory-list" role="list">
              <div className="employee-directory-labels" aria-hidden="true">
                <span>{tText("الموظف")}</span>
                <span>{tText("المديرية الأساسية")}</span>
                <span>{tText("الأدوار والنطاق")}</span>
                <span>{tText("الحالة")}</span>
                <span>{tText("إجراء")}</span>
              </div>
              {filteredEmployees.map((employee) => {
                const fullName = employee.needs_profile_completion
                  ? tText("يحتاج استكمال الملف")
                  : [employee.first_name, employee.last_name].filter(Boolean).join(" ") || "—";
                return (
                  <article className="employee-directory-row" role="listitem" key={employee.id}>
                    <div className="employee-directory-identity">
                      <span className="employee-directory-avatar" aria-hidden="true">
                        {(employee.first_name ?? employee.username).slice(0, 1)}
                      </span>
                      <span className="employee-directory-person">
                        <strong>{fullName}</strong>
                        <span className="employee-username" dir="ltr">
                          @{employee.username}
                        </span>
                        <span className="employee-contact">
                          {employee.phone ?? tText("لا يوجد هاتف")}
                          {employee.email ? ` · ${employee.email}` : ""}
                        </span>
                      </span>
                    </div>

                    <div className="employee-directory-branch">
                      <Building2 size={15} aria-hidden="true" />
                      <span>
                        {employee.directorate_id
                          ? getDirectorateLabel(employee.directorate_id)
                          : tText("بدون مديرية")}
                      </span>
                    </div>

                    <div className="employee-directory-roles">
                      {employee.role_assignments.length ? (
                        <div className="employee-role-chips">
                          {employee.role_assignments.map((assignment) => {
                            const roleName =
                              roles.data?.find((role) => role.id === assignment.role_id)?.name ??
                              `${tText("دور")} #${assignment.role_id}`;
                            const scopeLabel =
                              assignment.scope_type === "global"
                                ? tText("عام")
                                : assignment.directorate_id
                                  ? getDirectorateLabel(assignment.directorate_id)
                                  : tText("مديرية");
                            return (
                              <span className="employee-role-chip" key={assignment.id}>
                                <strong>{roleName}</strong>
                                <small>{scopeLabel}</small>
                              </span>
                            );
                          })}
                        </div>
                      ) : (
                        <span className="employee-no-role">{tText("لا أدوار")}</span>
                      )}
                      {canAssignRoles && (
                        <button
                          type="button"
                          className="employee-assign-link"
                          onClick={() => openRoleAssignments(employee)}
                        >
                          <Plus size={14} />
                          {tText("إدارة الأدوار")}
                        </button>
                      )}
                    </div>

                    <div>
                      <span
                        className={`employee-status-pill ${employee.is_active ? "active" : "inactive"}`}
                      >
                        <i aria-hidden="true" />
                        {tText(employee.is_active ? "نشط" : "معطل")}
                      </span>
                    </div>

                    <div className="employee-directory-actions">
                      <button
                        type="button"
                        className="employee-edit-button"
                        onClick={() => start(employee)}
                      >
                        <UiText source="تعديل" />
                      </button>
                    </div>
                  </article>
                );
              })}
              {!filteredEmployees.length && (
                <div className="employee-directory-empty">
                  <span className="employee-empty-icon">
                    <Search size={21} />
                  </span>
                  <strong>
                    {employeeItems.length
                      ? tText("لا توجد نتائج مطابقة")
                      : tText("لا يوجد موظفون ضمن نطاقك.")}
                  </strong>
                  <p>
                    {employeeItems.length
                      ? tText("جرّب تغيير كلمات البحث أو عوامل التصفية.")
                      : tText("ستظهر حسابات الموظفين هنا بعد إنشائها.")}
                  </p>
                  {(query || statusFilter !== "all" || directorateFilter !== "all") && (
                    <button
                      type="button"
                      onClick={() => {
                        setQuery("");
                        setStatusFilter("all");
                        setDirectorateFilter("all");
                      }}
                    >
                      {tText("مسح عوامل التصفية")}
                    </button>
                  )}
                </div>
              )}
            </div>
            <footer className="employee-directory-footer">
              <span>
                {tText("عرض")} <strong>{filteredEmployees.length}</strong> {tText("من")}{" "}
                <strong>{employeeItems.length}</strong> {tText("موظفين")}
              </span>
              <div className="employee-page-controls">
                <button
                  type="button"
                  disabled={page <= 1}
                  onClick={() => setPage((current) => current - 1)}
                  aria-label={tText("السابق")}
                >
                  <ChevronRight size={16} />
                </button>
                <span>{page}</span>
                <button
                  type="button"
                  disabled={page * PAGE_SIZE >= (employees.data?.total ?? 0)}
                  onClick={() => setPage((current) => current + 1)}
                  aria-label={tText("التالي")}
                >
                  <ChevronLeft size={16} />
                </button>
              </div>
            </footer>
          </>
        )}
      </section>

      {!showForm && !roleEmployee && <AdminAlert text={save.message} />}
      {showForm && (
        <EmployeeProfileForm
          form={form}
          editing={editing}
          directorates={manageableDirectorates}
          requireDirectorate={!canManageGlobally}
          busy={save.busy}
          setForm={setForm}
          close={() => setShowForm(false)}
          submit={async (body) => {
            await save.run(() =>
              api(editing ? `/admin/employees/${editing.id}` : "/admin/employees", {
                method: editing ? "PUT" : "POST",
                body,
              }),
            );
          }}
          tText={tText}
          message={save.message}
          messageIsError={save.isError}
        />
      )}
      {canAssignRoles && roleEmployee && (
        <EmployeeRoleAssignmentDialog
          employee={roleEmployee}
          roles={roles.data ?? []}
          directorates={manageableDirectorates}
          rolesLoading={roles.isLoading}
          rolesFailed={!!roles.error}
          busy={save.busy}
          message={save.message}
          messageIsError={save.isError}
          getDirectorateLabel={getDirectorateLabel}
          onClose={() => setRoleEmployeeId(null)}
          onAssign={assignRole}
          onRemove={removeRole}
          tText={tText}
        />
      )}
    </AdminPage>
  );
}
