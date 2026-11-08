import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { LogOut, RefreshCw } from "lucide-react";
import { api } from "../../shared/api/client";
import { useSession } from "../../shared/api/hooks";
import type { Complaint } from "../../shared/api/types";
import { useI18n } from "../../shared/i18n/I18n";
import { UiText } from "../../shared/i18n/UiText";
import { StaffGate } from "./StaffGate";
import { complaintStatusLabel, hasGlobalPermission, hasPermission } from "./permissions";

export function EmployeeHome() {
  const session = useSession();
  const { tText } = useI18n();

  return (
    <StaffGate>
      <div className="side-layout">
        <aside className="side-nav panel">
          <div className="eyebrow">{session.data?.full_name}</div>
          <Link to="/employee/complaints"><UiText source="سجل الشكاوى" /></Link>
          {hasPermission(session.data, "reports.view") && (
            <Link to="/employee/statistics"><UiText source="الإحصائيات" /></Link>
          )}
          <Link to="/employee/account"><UiText source="الحساب" /></Link>
          {hasGlobalPermission(session.data, "directorates.manage") && (
            <Link to="/employee/admin/directorates"><UiText source="المديريات" /></Link>
          )}
          {hasGlobalPermission(session.data, "employees.manage") && (
            <Link to="/employee/admin/employees"><UiText source="الموظفون" /></Link>
          )}
          {hasGlobalPermission(session.data, "rbac.manage") && (
            <>
              <Link to="/employee/admin/roles"><UiText source="الأدوار والصلاحيات" /></Link>
              <Link to="/employee/admin/languages"><UiText source="اللغات" /></Link>
              <Link to="/employee/admin/translations"><UiText source="الترجمات" /></Link>
            </>
          )}
          {hasGlobalPermission(session.data, "audit.view") && (
            <Link to="/employee/admin/audit"><UiText source="سجل التدقيق" /></Link>
          )}
          <button
            className="btn ghost"
            onClick={async () => {
              await api("/auth/logout", { method: "POST" });
              window.location.assign("/");
            }}
          >
            <LogOut size={15} />
            <UiText source="تسجيل الخروج" />
          </button>
        </aside>
        <div className="panel">
          <div className="eyebrow">DIRECTORATE DESK</div>
          <h1>{tText("سجل الشكاوى")}</h1>
          <ComplaintList />
        </div>
      </div>
    </StaffGate>
  );
}

function ComplaintList() {
  const { lang, tText } = useI18n();
  const query = useQuery({
    queryKey: ["employee-complaints"],
    queryFn: () => api<Complaint[]>("/complaints/"),
    retry: false,
  });
  const [search, setSearch] = useState("");

  if (query.isLoading) return <div className="skeleton" />;
  if (query.error) {
    return (
      <div className="status error" role="alert">
        {query.error instanceof Error ? query.error.message : tText("تعذر تحميل البيانات.")}
        <button type="button" className="btn secondary" onClick={() => void query.refetch()}>
          <RefreshCw size={15} />
          {tText("إعادة المحاولة")}
        </button>
      </div>
    );
  }

  const rows = (query.data ?? []).filter((complaint) =>
    `${complaint.title} ${complaint.tracking_code} ${complaint.category}`
      .toLowerCase()
      .includes(search.toLowerCase()),
  );

  return (
    <>
      <div className="row">
        <label className="field-label" style={{ flex: 1 }}>
          {tText("بحث")}
          <input
            className="field"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder={tText("العنوان أو الرمز أو التصنيف")}
          />
        </label>
        <button className="btn secondary" onClick={() => void query.refetch()}>
          <RefreshCw size={15} />
          {tText("تحديث")}
        </button>
      </div>
      {!rows.length ? (
        <div className="empty">{tText("لا توجد شكاوى في النطاق أو لا تطابق البحث.")}</div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>{tText("الرمز")}</th>
                <th>{tText("العنوان")}</th>
                <th>{tText("التصنيف")}</th>
                <th>{tText("الحالة")}</th>
                <th>{tText("التقدم")}</th>
                <th>{tText("تاريخ الإنشاء")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((complaint) => (
                <tr key={complaint.id}>
                  <td className="code">{complaint.tracking_code}</td>
                  <td>
                    <Link to={`/employee/complaints/${complaint.id}`}>
                      <b>{complaint.title}</b>
                    </Link>
                  </td>
                  <td>{complaint.category}</td>
                  <td><span className="badge">{complaintStatusLabel(complaint.status, lang)}</span></td>
                  <td>{complaint.progress}%</td>
                  <td>{new Date(complaint.created_at).toLocaleDateString(lang)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
