import {
  ArrowLeft,
  ArrowRight,
  Eye,
  Headphones,
  LockKeyhole,
  Search,
  Send,
  ShieldCheck,
} from "lucide-react";
import { Link } from "react-router-dom";
import { useI18n } from "../../shared/i18n/I18n";
import "./HomePage.css";

function SyrianFlag() {
  return (
    <svg
      className="citizen-hero-flag"
      viewBox="0 0 180 126"
      role="img"
      aria-label="علم سوريا"
    >
      <path d="M28 10v103" fill="none" stroke="#4b4035" strokeWidth="4" />
      <path d="M34 20c42 2 80 13 132 17v58c-51-7-91-17-132-19z" fill="#fff" />
      <path d="M34 20c42 2 80 13 132 17v19c-51-7-91-15-132-17z" fill="#087a43" />
      <path d="M34 76c42 3 81 13 132 19V75c-51-7-91-16-132-17z" fill="#111" />
      <path
        d="M34 20c42 2 80 13 132 17v58c-51-7-91-17-132-19z"
        fill="none"
        stroke="#283128"
        strokeOpacity=".16"
        strokeWidth="1.5"
      />
      {[68, 99, 130].map((x) => (
        <path
          key={x}
          d={`M${x} 47l2.7 6.3 6.8.5-5.2 4.4 1.7 6.6-6-3.6-5.9 3.6 1.6-6.6-5.1-4.4 6.7-.5z`}
          fill="#ce1126"
          stroke="#ab1021"
          strokeWidth=".6"
        />
      ))}
    </svg>
  );
}

export function HomePage() {
  const { tText, lang } = useI18n();

  return (
    <div className="citizen-home">
      <section className="citizen-hero" aria-labelledby="citizen-home-title">
        <div className="citizen-hero-copy">
          <div className="citizen-hero-kicker">
            <span className="citizen-kicker-rule" aria-hidden="true" />
            {tText("منصة الشكاوى الحكومية الموحدة")}
          </div>
          <h1 id="citizen-home-title">
            {tText("صوتك مسموع، ومسار شكواك واضح")}
          </h1>
          <p className="citizen-hero-description">
            {tText(
              "قدّم شكوى بسهولة دون إنشاء حساب، واحتفظ برمز المتابعة لتعرف ما يحدث في كل خطوة.",
            )}
          </p>
          <div className="citizen-hero-actions">
            <Link className="citizen-action citizen-action-primary" to="/complaints/new">
              <span>{tText("تقديم شكوى")}</span>
              <Send size={19} aria-hidden="true" />
            </Link>
            <Link className="citizen-action citizen-action-secondary" to="/track">
              <span>{tText("متابعة شكوى")}</span>
              <Search size={20} aria-hidden="true" />
            </Link>
          </div>
          <div className="citizen-hero-assurance">
            <ShieldCheck size={17} aria-hidden="true" />
            <span>{tText("النشر العام اختياري ويحمي بياناتك الشخصية")}</span>
          </div>
        </div>

        <div className="citizen-hero-visual">
          <img
            className="citizen-hero-photo"
            src="/images/citizen-home-civic.jpg"
            alt={tText("مبنى خدمة عامة في سوريا")}
            fetchPriority="high"
          />
          <div className="citizen-image-wash" aria-hidden="true" />
          <div className="citizen-flag-wrap">
            <SyrianFlag />
          </div>
          <div className="citizen-photo-caption">
            <span className="citizen-photo-caption-icon">
              <ShieldCheck size={16} aria-hidden="true" />
            </span>
            <span>{tText("خدمة عامة متوفرة")}</span>
          </div>
          <span className="citizen-visual-accent" aria-hidden="true" />
        </div>
      </section>

      <Link className="citizen-transparency-link" to="/public">
        <span className="citizen-transparency-icon">
          <Headphones size={26} aria-hidden="true" />
        </span>
        <span className="citizen-transparency-copy">
          <strong>{tText("اطّلع على الشكاوى المنشورة")}</strong>
          <span>
            {tText(
              "تابع ما اختار المواطنون نشره واطّلع على تحديثاته، دون كشف هوياتهم أو مرفقاتهم.",
            )}
          </span>
        </span>
        <span className="citizen-transparency-arrow" aria-hidden="true">
          {lang === "ar" ? <ArrowLeft size={21} /> : <ArrowRight size={21} />}
        </span>
      </Link>

      <div className="citizen-privacy-note">
        <span className="citizen-privacy-icon">
          <LockKeyhole size={18} aria-hidden="true" />
        </span>
        <p>
          <strong>{tText("خصوصيتك محفوظة")}</strong>
          <span>
            {tText("معلوماتك الشخصية ومرفقاتك لا تظهر ضمن الشكاوى العامة.")}
          </span>
        </p>
      </div>
    </div>
  );
}
