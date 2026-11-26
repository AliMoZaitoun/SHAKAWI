import {
  ArrowLeft,
  ArrowRight,
  Eye,
  LockKeyhole,
  Search,
  Send,
  ShieldCheck,
} from "lucide-react";
import { Link } from "react-router-dom";
import { useI18n } from "../../shared/i18n/I18n";
import "./HomePage.css";

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
            <span>{tText("صوتك مسموع")}</span>
            <span>{tText("ومسار شكواك واضح")}</span>
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
            src="/static/images/citizen-home-syria-flag.jpg"
            alt={tText("علم سوريا يرفرف فوق مبنى خدمة عامة")}
            fetchPriority="high"
          />
          <div className="citizen-image-wash" aria-hidden="true" />
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
          <Eye size={26} aria-hidden="true" />
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
