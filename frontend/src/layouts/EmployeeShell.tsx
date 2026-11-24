import { NavLink, Link, Outlet } from "react-router-dom";
import {
  BarChart3,
  Building2,
  ClipboardList,
  History,
  Languages,
  LogOut,
  MessageSquareText,
  Shield,
  Settings2,
  Tags,
  UserRound,
  UsersRound,
  type LucideIcon,
} from "lucide-react";
import { useI18n } from "../shared/i18n/I18n";
import { api } from "../shared/api/client";
import { useSession } from "../shared/api/hooks";
import { hasGlobalPermission, hasPermission } from "../features/employee/permissions";
import { StaffGate } from "../features/employee/StaffGate";

function EmployeeNavLink({
  to,
  label,
  icon: Icon,
}: {
  to: string;
  label: string;
  icon: LucideIcon;
}) {
  return (
    <NavLink to={to} className={({ isActive }) => `employee-nav-link${isActive ? " active" : ""}`}>
      <Icon size={17} aria-hidden="true" />
      <span>{label}</span>
    </NavLink>
  );
}

export function EmployeeShell() {
  const { lang, setLang, tText } = useI18n();
  const session = useSession();

  return (
    <StaffGate required={null}>
      <div className="employee-portal">
        <header className="topbar">
          <div className="shell">
            <div className="topbar-inner">
              <Link to="/employee/complaints" className="brand">
                <span className="brand-mark">
                  <MessageSquareText size={22} />
                </span>
                <span>
                  شكوى
                  <small>{lang === "ar" ? "بوابة الموظفين" : "Staff portal"}</small>
                </span>
              </Link>
              <button
                className="btn ghost"
                type="button"
                onClick={() => setLang(lang === "ar" ? "en" : "ar")}
                aria-label={
                  lang === "ar" ? "Switch language to English" : "تغيير اللغة إلى العربية"
                }
              >
                <Languages size={16} />
                {lang === "ar" ? "English" : "العربية"}
              </button>
            </div>
          </div>
        </header>
        <main className="shell main">
          <div className="employee-workspace">
            <aside className="employee-sidebar panel">
              <div className="employee-sidebar-user">
                <span className="eyebrow">{lang === "ar" ? "الحساب النشط" : "Active account"}</span>
                <strong>{session.data?.full_name}</strong>
              </div>
              <nav
                className="employee-nav"
                aria-label={lang === "ar" ? "التنقل الرئيسي للموظفين" : "Main employee navigation"}
              >
                {hasPermission(session.data, "complaints.view") && (
                  <EmployeeNavLink
                    to="/employee/complaints"
                    label={tText("سجل الشكاوى")}
                    icon={ClipboardList}
                  />
                )}
                {hasPermission(session.data, "reports.view") && (
                  <EmployeeNavLink
                    to="/employee/statistics"
                    label={tText("الإحصائيات")}
                    icon={BarChart3}
                  />
                )}
                <EmployeeNavLink to="/employee/account" label={tText("الحساب")} icon={UserRound} />
                {hasGlobalPermission(session.data, "directorates.manage") && (
                  <EmployeeNavLink
                    to="/employee/admin/directorates"
                    label={tText("المديريات")}
                    icon={Building2}
                  />
                )}
                {hasGlobalPermission(session.data, "complaint_types.manage") && (
                  <EmployeeNavLink
                    to="/employee/admin/complaint-types"
                    label={tText("أنواع الشكاوى")}
                    icon={Tags}
                  />
                )}
                {hasGlobalPermission(session.data, "files.manage") && (
                  <EmployeeNavLink
                    to="/employee/admin/settings/files"
                    label={tText("حدود الملفات والاحتفاظ")}
                    icon={Settings2}
                  />
                )}
                {hasPermission(session.data, "employees.manage") && (
                  <EmployeeNavLink
                    to="/employee/admin/employees"
                    label={tText("الموظفون")}
                    icon={UsersRound}
                  />
                )}
                {hasGlobalPermission(session.data, "rbac.manage") && (
                  <>
                    <EmployeeNavLink
                      to="/employee/admin/roles"
                      label={tText("الأدوار والصلاحيات")}
                      icon={Shield}
                    />
                    <EmployeeNavLink
                      to="/employee/admin/languages"
                      label={tText("اللغات")}
                      icon={Languages}
                    />
                    <EmployeeNavLink
                      to="/employee/admin/translations"
                      label={tText("الترجمات")}
                      icon={MessageSquareText}
                    />
                  </>
                )}
                {hasGlobalPermission(session.data, "audit.view") && (
                  <EmployeeNavLink
                    to="/employee/admin/audit"
                    label={tText("سجل التدقيق")}
                    icon={History}
                  />
                )}
              </nav>
              <button
                className="btn ghost employee-logout"
                type="button"
                onClick={async () => {
                  await api("/auth/logout", { method: "POST" });
                  window.location.assign("/");
                }}
              >
                <LogOut size={16} />
                {tText("تسجيل الخروج")}
              </button>
            </aside>
            <div className="employee-page-content">
              <Outlet />
            </div>
          </div>
        </main>
        <footer className="footer">
          <div className="shell">SHAKWA — {lang === "ar" ? "بوابة الموظفين" : "Staff portal"}</div>
        </footer>
      </div>
    </StaffGate>
  );
}
