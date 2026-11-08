import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { useSession } from "../../shared/api/hooks";
import { useI18n } from "../../shared/i18n/I18n";

export function StaffGate({
  children,
  required = "complaints.view",
  globalOnly = false,
}: {
  children: ReactNode;
  required?: string | null;
  globalOnly?: boolean;
}) {
  const session = useSession();
  const { tText } = useI18n();

  if (session.isLoading) return <div className="skeleton" />;

  if (session.error) {
    return (
      <div className="panel">
        <h2>{tText("يلزم تسجيل الدخول")}</h2>
        <p className="muted">{tText("تعذر قراءة جلسة الموظف. المحتوى العام يظل متاحًا.")}</p>
        <Link to="/employee/login" className="btn">
          {tText("دخول الموظفين")}
        </Link>
      </div>
    );
  }

  const scope = required ? session.data?.permissions?.[required] : null;
  const denied =
    required &&
    (!scope ||
      (globalOnly
        ? scope.directorate_ids !== null
        : scope.directorate_ids !== null && scope.directorate_ids.length === 0));

  if (denied) {
    return (
      <div className="panel">
        <div className="eyebrow">403 · FORBIDDEN</div>
        <h1>{tText("لا تملك صلاحية هذه الصفحة")}</h1>
        <p className="muted">
          {tText("الصلاحية والنطاق يحددهما الخادم. اطلب من مدير النظام مراجعة إسنادك.")}
        </p>
        <Link to="/employee/complaints" className="btn secondary">
          {tText("العودة إلى بوابة الموظفين")}
        </Link>
      </div>
    );
  }

  return <>{children}</>;
}
