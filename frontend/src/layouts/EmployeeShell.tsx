import { Link, Outlet } from "react-router-dom";
import { Languages, MessageSquareText } from "lucide-react";
import { useI18n } from "../shared/i18n/I18n";

export function EmployeeShell() {
  const { lang, setLang } = useI18n();

  return (
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
              aria-label={lang === "ar" ? "Switch language to English" : "تغيير اللغة إلى العربية"}
            >
              <Languages size={16} />
              {lang === "ar" ? "English" : "العربية"}
            </button>
          </div>
        </div>
      </header>
      <main className="shell main">
        <Outlet />
      </main>
      <footer className="footer">
        <div className="shell">
          SHAKWA — {lang === "ar" ? "بوابة الموظفين" : "Staff portal"}
        </div>
      </footer>
    </div>
  );
}
