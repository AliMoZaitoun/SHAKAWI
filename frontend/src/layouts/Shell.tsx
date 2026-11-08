import { Link, NavLink, Outlet } from "react-router-dom";
import { Languages, MessageSquareText, ShieldCheck } from "lucide-react";
import { useI18n } from "../shared/i18n/I18n";

export function Shell() {
  const { lang, t, setLang } = useI18n();
  return (
    <div>
      <header className="topbar">
        <div className="shell">
          <div className="topbar-inner">
            <Link to="/" className="brand">
              <span className="brand-mark">
                <MessageSquareText size={22} />
              </span>
              <span>
                شكوى <small>SHAKWA · صوتك يصل</small>
              </span>
            </Link>
            <div className="row">
              <span className="badge">
                <ShieldCheck size={14} />
                {lang === "ar" ? "خدمة عامة موثوقة" : "Public service"}
              </span>
              <button
                className="btn ghost"
                type="button"
                onClick={() => setLang(lang === "ar" ? "en" : "ar")}
                aria-label={t("language")}
              >
                <Languages size={16} />
                {t("language")}
              </button>
            </div>
          </div>
          <nav className="nav" aria-label={lang === "ar" ? "التنقل الرئيسي" : "Main navigation"}>
            <NavLink to="/" end>
              {t("home")}
            </NavLink>
            <NavLink to="/complaints/new">{t("submit")}</NavLink>
            <NavLink to="/track">{t("track")}</NavLink>
            <NavLink to="/public">{t("public")}</NavLink>
            <NavLink to="/access">{lang === "ar" ? "استعادة الوصول" : "Recover access"}</NavLink>
            <NavLink to="/employee/complaints">{t("staff")}</NavLink>
          </nav>
        </div>
      </header>
      <main className="shell main">
        <Outlet />
      </main>
      <footer className="footer">
        <div className="shell row" style={{ justifyContent: "space-between" }}>
          <span>
            SHAKWA — {lang === "ar" ? "منصة الشكاوى الحكومية" : "Government complaints service"}
          </span>
          <a href="/legacy">{lang === "ar" ? "الواجهة الاحتياطية" : "Legacy backup interface"}</a>
          <Link to="/employee/login">{t("login")}</Link>
        </div>
      </footer>
    </div>
  );
}
