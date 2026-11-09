import { Link } from "react-router-dom";
import { ArrowLeft, LockKeyhole } from "lucide-react";
import { useI18n } from "../../shared/i18n/I18n";

export function HomePage() {
  const { tText } = useI18n();
  return (
    <>
      <section className="hero">
        <div className="hero-kicker">{tText("منصة الشكاوى الحكومية الموحدة")}</div>
        <h1>{tText("صوتك مسموع. ومسار شكواك واضح.")}</h1>
        <p>
          {tText(
            "قدّم شكواك دون إنشاء حساب. احتفظ برمز المتابعة السري، وتابع خطوات المعالجة، أو اطّلع على ما اختار المواطنون نشره.",
          )}
        </p>
        <div className="row">
          <Link className="btn gold" to="/complaints/new">
            {tText("تقديم شكوى")} <ArrowLeft size={16} />
          </Link>
          <Link className="btn secondary" to="/track">
            {tText("متابعة شكوى")}
          </Link>
        </div>
      </section>
      <div className="grid grid-two">
        <Link className="panel" to="/complaints/new">
          <span className="eyebrow">01 / START</span>
          <h2>{tText("ابدأ بشكوى جديدة")}</h2>
          <p className="muted">
            {tText("بياناتك الخاصة تبقى خارج العرض العام. النشر اختياري بالكامل.")}
          </p>
        </Link>
        <Link className="panel" to="/public">
          <span className="eyebrow">02 / OPEN RECORD</span>
          <h2>{tText("اطّلع على الشكاوى المنشورة")}</h2>
          <p className="muted">{tText("شفافية بلا كشف للهويات أو رموز المتابعة أو المرفقات.")}</p>
        </Link>
      </div>
      <div
        className="panel"
        style={{ marginTop: 18, display: "flex", gap: 14, alignItems: "flex-start" }}
      >
        <span className="empty-icon">
          <LockKeyhole size={21} />
        </span>
        <div>
          <h3>{tText("رمز المتابعة يخص شكوى واحدة")}</h3>
          <p className="muted">
            {tText("لا يمنح الرمز وصولًا إلى سجل المواطن أو بقية شكاواه. لا تحفظه في جهاز مشترك.")}
          </p>
        </div>
      </div>
    </>
  );
}
