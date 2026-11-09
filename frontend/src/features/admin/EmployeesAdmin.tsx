import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../shared/api/client";
import type { Directorate, Employee, Page, Role } from "../../shared/api/types";
import { useResource } from "../../shared/api/hooks";
import { useI18n } from "../../shared/i18n/I18n";
import { UiText } from "../../shared/i18n/UiText";
import { AdminAlert, AdminPage, useAdminSave } from "./AdminPage";
import { EmployeeProfileForm, type EmployeeDraft } from "./EmployeeProfileForm";

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
const blankAssignment = { role_id: "", scope_type: "directorate", directorate_id: "" };

export function EmployeesAdmin() {
  const { lang, tText } = useI18n();
  const [page, setPage] = useState(1);
  const employees = useQuery({
    queryKey: ["admin-employees", page, lang],
    queryFn: () =>
      api<Page<Employee>>(`/admin/employees?page=${page}&page_size=20`, { language: lang }),
    retry: false,
  });
  const roles = useResource<Role[]>("/admin/roles", lang);
  const directorates = useResource<Directorate[]>("/admin/directorates", lang);
  const save = useAdminSave();
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<Employee | null>(null);
  const [form, setForm] = useState<EmployeeDraft>({ ...blankEmployee });
  const [assignment, setAssignment] = useState({ ...blankAssignment });

  function start(employee?: Employee) {
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

  return (
    <AdminPage
      title="إدارة الموظفين"
      required="employees.manage"
      subtitle="لا تُستكمل الحسابات القديمة بتخمين بيانات. الإسناد الجديد لا يمنح صلاحيات حتى يُعيّن دور ونطاق."
    >
      <button className="btn" onClick={() => start()}>
        <UiText source="إضافة موظف" />
      </button>
      {employees.isLoading ? (
        <div className="skeleton" />
      ) : employees.error ? (
        <div className="status error" role="alert">
          {tText("تعذر تحميل الموظفين.")}
          <button onClick={() => void employees.refetch()} className="btn secondary">
            <UiText source="إعادة المحاولة" />
          </button>
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                {["الموظف", "اسم الدخول", "المديرية", "الحالة", "الأدوار والنطاق", "إجراء"].map(
                  (label) => (
                    <th key={label}>
                      <UiText source={label} />
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody>
              {employees.data?.items.map((employee) => (
                <tr key={employee.id}>
                  <td>
                    {employee.needs_profile_completion ? (
                      <UiText source="يحتاج استكمال الملف" />
                    ) : (
                      `${employee.first_name ?? ""} ${employee.last_name ?? ""}`
                    )}
                    <div className="muted">{employee.phone ?? tText("لا يوجد هاتف")}</div>
                  </td>
                  <td>{employee.username}</td>
                  <td>
                    {directorates.data?.find((item) => item.id === employee.directorate_id)?.name ??
                      "—"}
                  </td>
                  <td>
                    <UiText source={employee.is_active ? "نشط" : "معطل"} />
                  </td>
                  <td>
                    {employee.role_assignments
                      .map((item) => {
                        const roleName = roles.data?.find((role) => role.id === item.role_id)?.name;
                        const scopeName =
                          item.scope_type === "global" ? tText("عام") : tText("مديرية");
                        return `${roleName ?? item.role_id} · ${scopeName}${item.directorate_id ? ` #${item.directorate_id}` : ""}`;
                      })
                      .join("، ") || tText("لا أدوار")}
                  </td>
                  <td>
                    <button className="btn secondary" onClick={() => start(employee)}>
                      <UiText source="تعديل" />
                    </button>
                    <form
                      onSubmit={(event) => {
                        event.preventDefault();
                        void save.run(() =>
                          api(`/admin/employees/${employee.id}/roles`, {
                            method: "POST",
                            body: {
                              role_id: Number(assignment.role_id),
                              scope_type: assignment.scope_type,
                              directorate_id:
                                assignment.scope_type === "global"
                                  ? null
                                  : Number(assignment.directorate_id),
                            },
                          }),
                        );
                      }}
                    >
                      <label className="field-label">
                        <UiText source="الدور" />
                        <select
                          className="field"
                          value={assignment.role_id}
                          onChange={(event) =>
                            setAssignment({ ...assignment, role_id: event.target.value })
                          }
                          required
                        >
                          <option value="">{tText("اختر دورًا")}</option>
                          {roles.data?.map((role) => (
                            <option value={role.id} key={role.id}>
                              {role.name}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label className="field-label">
                        <UiText source="النطاق" />
                        <select
                          className="field"
                          value={assignment.scope_type}
                          onChange={(event) =>
                            setAssignment({ ...assignment, scope_type: event.target.value })
                          }
                        >
                          <option value="directorate">{tText("مديرية")}</option>
                          <option value="global">{tText("عام")}</option>
                        </select>
                      </label>
                      {assignment.scope_type === "directorate" && (
                        <label className="field-label">
                          <UiText source="المديرية" />
                          <select
                            className="field"
                            value={assignment.directorate_id}
                            onChange={(event) =>
                              setAssignment({ ...assignment, directorate_id: event.target.value })
                            }
                            required
                          >
                            <option value="">{tText("اختر مديرية")}</option>
                            {directorates.data?.map((item) => (
                              <option key={item.id} value={item.id}>
                                {item.name}
                              </option>
                            ))}
                          </select>
                        </label>
                      )}
                      <button className="btn secondary" disabled={!assignment.role_id}>
                        <UiText source="إسناد دور" />
                      </button>
                    </form>
                    {employee.role_assignments.map((item) => (
                      <button
                        key={item.id}
                        className="btn danger"
                        onClick={() => {
                          if (window.confirm(tText("إلغاء هذا الإسناد؟"))) {
                            void save.run(() =>
                              api(`/admin/employees/${employee.id}/roles/${item.id}`, {
                                method: "DELETE",
                              }),
                            );
                          }
                        }}
                      >
                        {tText("إلغاء")}{" "}
                        {roles.data?.find((role) => role.id === item.role_id)?.name ?? item.role_id}
                      </button>
                    ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {showForm && (
        <EmployeeProfileForm
          form={form}
          editing={editing}
          directorates={directorates.data ?? []}
          busy={save.busy}
          setForm={setForm}
          close={() => setShowForm(false)}
          submit={(body) =>
            save.run(() =>
              api(editing ? `/admin/employees/${editing.id}` : "/admin/employees", {
                method: editing ? "PUT" : "POST",
                body,
              }),
            )
          }
          tText={tText}
        />
      )}
      <div className="row">
        <button disabled={page <= 1} className="btn secondary" onClick={() => setPage(page - 1)}>
          <UiText source="السابق" />
        </button>
        <span className="muted">
          {tText("صفحة")} {employees.data?.page} · {employees.data?.total} {tText("موظفًا")}
        </span>
        <button
          disabled={page * 20 >= (employees.data?.total ?? 0)}
          className="btn secondary"
          onClick={() => setPage(page + 1)}
        >
          <UiText source="التالي" />
        </button>
      </div>
      <AdminAlert text={save.message} />
    </AdminPage>
  );
}
