import { Link, NavLink, Outlet } from "react-router-dom";
import { Languages, ShieldCheck } from "lucide-react";
import { useI18n } from "../shared/i18n/I18n";
import { BrandMark } from "../shared/branding/Branding";
import "./Shell.css";

export function Shell() {
  const { lang, t, tText, setLang } = useI18n();
  return (
    <div className="citizen-site">
      <header className="topbar">
        <div className="shell">
          <div className="topbar-inner citizen-topbar-inner">
            <Link to="/" className="brand citizen-brand">
              <span className="brand-mark">
                <BrandMark />
              </span>
              <span>
                شكوى{" "}
                <small>{lang === "ar" ? "منصة الشكاوى الحكومية" : "GOVERNMENT COMPLAINTS"}</small>
              </span>
            </Link>
            <span className="badge citizen-service-badge">
              <span className="citizen-service-icon">
                <ShieldCheck size={14} />
              </span>
              {tText("خدمة عامة متوفرة")}
            </span>
            <button
              className="btn ghost citizen-language-switch"
              type="button"
              onClick={() => setLang(lang === "ar" ? "en" : "ar")}
              aria-label={t("language")}
            >
              <Languages size={16} />
              {t("language")}
            </button>
          </div>
          <nav
            className="nav citizen-nav"
            aria-label={lang === "ar" ? "التنقل الرئيسي" : "Main navigation"}
          >
            <NavLink to="/" end>
              {t("home")}
            </NavLink>
            <NavLink to="/complaints/new">{t("submit")}</NavLink>
            <NavLink to="/track">{t("track")}</NavLink>
            <NavLink to="/public">{t("public")}</NavLink>
            <NavLink to="/access">{lang === "ar" ? "استعادة الوصول" : "Recover access"}</NavLink>
          </nav>
        </div>
      </header>
      <main className="shell main citizen-main">
        <Outlet />
      </main>
      <footer className="footer citizen-footer">
        <div className="shell">
          <span className="citizen-footer-rule" aria-hidden="true" />
          <span>
            SHAKWA — {lang === "ar" ? "منصة الشكاوى الحكومية" : "Government complaints service"}
          </span>
          <span className="citizen-footer-rule" aria-hidden="true" />
        </div>
      </footer>
    </div>
  );
}
