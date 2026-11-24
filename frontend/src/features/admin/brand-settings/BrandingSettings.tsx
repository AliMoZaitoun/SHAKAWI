import { useEffect, useMemo, useRef, useState, type ChangeEvent, type CSSProperties } from "react";
import { Check, ImagePlus, Palette, RotateCcw, Save, ShieldCheck, Upload, X } from "lucide-react";
import { api } from "../../../shared/api/client";
import { useResource } from "../../../shared/api/hooks";
import { useI18n } from "../../../shared/i18n/I18n";
import { UiText } from "../../../shared/i18n/UiText";
import { readableForeground } from "../../../shared/branding/Branding";
import { AdminAlert, AdminPage, useAdminSave } from "../AdminPage";
import "./branding-settings.css";

type BrandColors = {
  brand_dark: string;
  brand_primary: string;
  brand_light: string;
  brand_accent: string;
  brand_gold: string;
  brand_bg: string;
  brand_card: string;
  sidebar_item_bg: string;
};

type BrandingSettingsResponse = {
  colors: BrandColors;
  logo_url: string | null;
  logo_version: number;
  updated_at: string | null;
};

type ColorField = {
  key: keyof BrandColors;
  label: string;
  description: string;
};

const DEFAULT_COLORS: BrandColors = {
  brand_dark: "#3B4B32",
  brand_primary: "#4A5D3F",
  brand_light: "#657B57",
  brand_accent: "#B88D4B",
  brand_gold: "#D4A860",
  brand_bg: "#F7F8F4",
  brand_card: "#FFFFFF",
  sidebar_item_bg: "#EDF1E8",
};
const COLOR_FIELDS: ColorField[] = [
  { key: "brand_dark", label: "اللون الداكن", description: "العناوين ونص روابط الشريط الجانبي" },
  { key: "brand_primary", label: "اللون الأساسي", description: "الأزرار والإجراءات الرئيسية" },
  { key: "brand_light", label: "اللون الفاتح", description: "التفاصيل والعناصر المساندة" },
  { key: "brand_accent", label: "لون التمييز", description: "خط تحديد العنصر النشط والإشارات" },
  { key: "brand_gold", label: "اللون الذهبي", description: "التأكيدات البصرية" },
  { key: "brand_bg", label: "خلفية الصفحة", description: "المساحة المحيطة بالمحتوى" },
  { key: "brand_card", label: "خلفية البطاقة", description: "البطاقات وخلفية الشريط الجانبي" },
  { key: "sidebar_item_bg", label: "خلفية أزرار الشريط الجانبي", description: "خلفية الرابط النشط وعند المرور عليه" },
];
const HEX_COLOR = /^#[0-9a-fA-F]{6}$/;
const MAX_LOGO_BYTES = 2 * 1024 * 1024;

function isBrandColors(value: BrandColors): boolean {
  return COLOR_FIELDS.every(({ key }) => HEX_COLOR.test(value[key]));
}

function luminance(hex: string): number {
  const channels = hex.slice(1).match(/.{2}/g)?.map((channel) => Number.parseInt(channel, 16) / 255) ?? [];
  const linear = channels.map((channel) =>
    channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4,
  );
  return 0.2126 * (linear[0] ?? 0) + 0.7152 * (linear[1] ?? 0) + 0.0722 * (linear[2] ?? 0);
}

function contrastRatio(first: string, second: string): number {
  const values = [luminance(first), luminance(second)].sort((a, b) => b - a);
  return (values[0] + 0.05) / (values[1] + 0.05);
}

function accentInk(accent: string, surface: string): string {
  if (!HEX_COLOR.test(accent) || !HEX_COLOR.test(surface)) return "#283128";
  if (contrastRatio(accent, surface) >= 4.5) return accent;
  const source = accent.slice(1).match(/.{2}/g)?.map((channel) => Number.parseInt(channel, 16)) ?? [];
  for (let amount = 0.04; amount <= 1; amount += 0.04) {
    const candidate = `#${source
      .map((channel) => Math.round(channel * (1 - amount)).toString(16).padStart(2, "0"))
      .join("")}`;
    if (contrastRatio(candidate, surface) >= 4.5) return candidate;
  }
  return "#283128";
}

function ContrastCheck({
  foreground,
  background,
  label,
  foregroundLabel,
  passLabel,
  failLabel,
}: {
  foreground: string;
  background: string;
  label: string;
  foregroundLabel: string;
  passLabel: string;
  failLabel: string;
}) {
  const ratio = contrastRatio(foreground, background);
  const passes = ratio >= 4.5;
  return (
    <div className={`branding-contrast-check ${passes ? "is-pass" : "is-fail"}`}>
      <span className="branding-contrast-icon" aria-hidden="true">
        {passes ? <Check size={14} /> : <X size={14} />}
      </span>
      <span className="branding-contrast-copy">
        <strong>{label}</strong>
        <small>{foregroundLabel} · {ratio.toFixed(2)}:1</small>
      </span>
      <span className="branding-contrast-result">{passes ? passLabel : failLabel}</span>
    </div>
  );
}

export function BrandingSettings() {
  const { lang, tText } = useI18n();
  const query = useResource<BrandingSettingsResponse>("/admin/settings/branding", lang);
  const save = useAdminSave();
  const [colors, setColors] = useState<BrandColors>(DEFAULT_COLORS);
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [logoPreview, setLogoPreview] = useState<string | null>(null);
  const [logoError, setLogoError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Partial<Record<keyof BrandColors, string>>>({});
  const [hasLocalEdits, setHasLocalEdits] = useState(false);
  const [resetLogoOnSave, setResetLogoOnSave] = useState(false);
  const objectUrlRef = useRef<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (query.data && !hasLocalEdits) setColors(query.data.colors);
  }, [query.data, hasLocalEdits]);

  useEffect(
    () => () => {
      if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
    },
    [],
  );

  const contrastIssues = useMemo(() => {
    const issues: string[] = [];
    if (HEX_COLOR.test(colors.brand_dark) && contrastRatio("#FFFFFF", colors.brand_dark) < 4.5) {
      issues.push("اللون الداكن مع النص الأبيض يحتاج تباينًا 4.5:1 على الأقل.");
    }
    if (HEX_COLOR.test(colors.brand_primary) && contrastRatio("#FFFFFF", colors.brand_primary) < 4.5) {
      issues.push("اللون الأساسي مع النص الأبيض يحتاج تباينًا 4.5:1 على الأقل.");
    }
    if (HEX_COLOR.test(colors.brand_bg) && contrastRatio("#283128", colors.brand_bg) < 4.5) {
      issues.push("خلفية الصفحة داكنة على النص؛ اختر درجة أفتح حتى يبقى النص مقروءًا.");
    }
    if (HEX_COLOR.test(colors.brand_card) && contrastRatio("#283128", colors.brand_card) < 4.5) {
      issues.push("خلفية البطاقة داكنة على النص؛ اختر درجة أفتح حتى يبقى النص مقروءًا.");
    }
    return issues;
  }, [colors]);
  const validColorFormats = useMemo(() => isBrandColors(colors), [colors]);
  const isValid = validColorFormats && contrastIssues.length === 0;
  const changedColors = useMemo(
    () => query.data && COLOR_FIELDS.some(({ key }) => colors[key].toUpperCase() !== query.data?.colors[key].toUpperCase()),
    [colors, query.data],
  );
  const hasChanges = Boolean(changedColors || logoFile || resetLogoOnSave);
  const previewStyles = {
    "--preview-dark": colors.brand_dark,
    "--preview-primary": colors.brand_primary,
    "--preview-light": colors.brand_light,
    "--preview-accent": colors.brand_accent,
    "--preview-accent-ink": accentInk(colors.brand_accent, colors.brand_bg),
    "--preview-gold": colors.brand_gold,
    "--preview-bg": colors.brand_bg,
    "--preview-card": colors.brand_card,
    "--preview-sidebar-item-bg": colors.sidebar_item_bg,
    "--preview-sidebar-item-ink": readableForeground(
      HEX_COLOR.test(colors.sidebar_item_bg) ? colors.sidebar_item_bg : DEFAULT_COLORS.sidebar_item_bg,
    ),
  } as CSSProperties;

  function updateColor(key: keyof BrandColors, value: string) {
    setHasLocalEdits(true);
    setColors((current) => ({ ...current, [key]: value }));
    setFieldErrors((current) => ({
      ...current,
      [key]: HEX_COLOR.test(value) ? undefined : tText("أدخل رمز لون بصيغة #RRGGBB."),
    }));
  }

  function selectLogo(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setLogoError("");
    const supportedTypes = ["image/png", "image/jpeg", "image/webp"];
    if (!supportedTypes.includes(file.type)) {
      setLogoError(tText("اختر ملف PNG أو JPEG أو WebP."));
      event.target.value = "";
      return;
    }
    if (file.size > MAX_LOGO_BYTES) {
      setLogoError(tText("حجم الشعار يتجاوز الحد الأقصى البالغ 2 ميغابايت."));
      event.target.value = "";
      return;
    }
    if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
    const localUrl = URL.createObjectURL(file);
    objectUrlRef.current = localUrl;
    setLogoPreview(localUrl);
    setLogoFile(file);
    setResetLogoOnSave(false);
    setHasLocalEdits(true);
  }

  function clearLocalLogo() {
    if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
    objectUrlRef.current = null;
    setLogoPreview(null);
    setLogoFile(null);
    setResetLogoOnSave(false);
    if (fileInputRef.current) fileInputRef.current.value = "";
    setLogoError("");
    setHasLocalEdits(true);
  }

  async function submitChanges() {
    const errors: Partial<Record<keyof BrandColors, string>> = {};
    COLOR_FIELDS.forEach(({ key }) => {
      if (!HEX_COLOR.test(colors[key])) errors[key] = tText("أدخل رمز لون بصيغة #RRGGBB.");
    });
    setFieldErrors(errors);
    if (Object.keys(errors).length) {
      save.setMessage(tText("راجع رموز الألوان غير الصالحة قبل الحفظ."));
      return;
    }
    if (!hasChanges) return;

    let latestResponse = query.data;
    const ok = await save.run(async () => {
      if (changedColors) {
        latestResponse = await api<BrandingSettingsResponse>("/admin/settings/branding", {
          method: "PUT",
          language: lang,
          body: { colors },
        });
      }
      if (logoFile) {
        const body = new FormData();
        body.append("file", logoFile);
        latestResponse = await api<BrandingSettingsResponse>("/admin/settings/branding/logo", {
          method: "POST",
          language: lang,
          body,
        });
      }
      if (resetLogoOnSave) {
        latestResponse = await api<BrandingSettingsResponse>("/admin/settings/branding/logo", {
          method: "DELETE",
          language: lang,
        });
      }
      return latestResponse;
    });

    if (ok && latestResponse) {
      setColors(latestResponse.colors);
      setLogoFile(null);
      setResetLogoOnSave(false);
      if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
      objectUrlRef.current = null;
      setLogoPreview(null);
      setHasLocalEdits(false);
      setLogoError("");
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  function resetLogo() {
    if (resetLogoOnSave) {
      setResetLogoOnSave(false);
      setHasLocalEdits(true);
      return;
    }
    setLogoError("");
    if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
    objectUrlRef.current = null;
    setLogoPreview(null);
    setLogoFile(null);
    setResetLogoOnSave(Boolean(query.data?.logo_url));
    if (fileInputRef.current) fileInputRef.current.value = "";
    setHasLocalEdits(true);
  }

  function restoreDefaultColors() {
    setColors({ ...DEFAULT_COLORS });
    setHasLocalEdits(true);
    setFieldErrors({});
    save.setMessage("");
  }

  return (
    <AdminPage
      title="هوية الخدمة"
      subtitle="اضبط الشعار والألوان التي تظهر للمواطنين، ثم راجع المعاينة قبل حفظ التغييرات."
      required="branding.manage"
      className="branding-admin"
    >
      {query.isLoading ? (
        <div className="branding-loading" aria-label={tText("جارٍ تحميل إعدادات الهوية")}>
          <div className="branding-skeleton branding-skeleton-title" />
          <div className="branding-skeleton" />
          <div className="branding-skeleton branding-skeleton-preview" />
        </div>
      ) : query.error || !query.data ? (
        <div className="branding-load-error" role="alert">
          <ShieldCheck size={24} aria-hidden="true" />
          <div>
            <strong><UiText source="تعذر تحميل إعدادات الهوية." /></strong>
            <p><UiText source="تحقق من اتصالك ثم أعد المحاولة." /></p>
          </div>
          <button className="btn secondary" type="button" onClick={() => void query.refetch()}>
            <UiText source="إعادة المحاولة" />
          </button>
        </div>
      ) : (
        <>
          <div className="branding-topline">
            <span className="branding-live-indicator"><i aria-hidden="true" /> <UiText source="إعدادات الهوية العامة" /></span>
            <span className="branding-version">
              <UiText source="نسخة الشعار" /> <bdi>{query.data.logo_version}</bdi>
            </span>
          </div>

          <section className="branding-section branding-logo-section" aria-labelledby="branding-logo-heading">
            <div className="branding-section-heading">
              <span className="branding-section-icon"><ImagePlus size={19} aria-hidden="true" /></span>
              <div>
                <h2 id="branding-logo-heading"><UiText source="شعار الخدمة" /></h2>
                <p><UiText source="اختر علامة واضحة تعمل جيدًا على الخلفيات الفاتحة." /></p>
              </div>
            </div>
            <div className="branding-logo-layout">
              <div className="branding-logo-tile" aria-label={tText("معاينة الشعار")}>
                {logoPreview || (query.data.logo_url && !resetLogoOnSave) ? (
                  <img src={logoPreview ?? query.data.logo_url ?? undefined} alt={tText("معاينة شعار الخدمة")} />
                ) : (
                  <div className="branding-built-in-mark" aria-hidden="true">
                    <span />
                    <span />
                    <span />
                  </div>
                )}
                {logoPreview && <span className="branding-preview-tag"><UiText source="معاينة محلية" /></span>}
              </div>
              <div className="branding-logo-controls">
                <p className="branding-helper"><UiText source="الملفات المدعومة: PNG وJPEG وWebP. الحد الأقصى 2 ميغابايت." /></p>
                <input
                  ref={fileInputRef}
                  className="branding-file-input"
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  aria-label={tText("اختيار ملف شعار")}
                  onChange={selectLogo}
                />
                <div className="branding-logo-actions">
                  <button className="btn secondary" type="button" onClick={() => fileInputRef.current?.click()} disabled={save.busy}>
                    <Upload size={16} aria-hidden="true" />
                    <UiText source="اختيار شعار" />
                  </button>
                  {(logoPreview || query.data.logo_url) && (
                    <button className="btn ghost" type="button" onClick={resetLogo} disabled={save.busy}>
                      <RotateCcw size={15} aria-hidden="true" />
                      <UiText source={resetLogoOnSave ? "إلغاء استعادة الشعار" : "استعادة الشعار المدمج"} />
                    </button>
                  )}
                  {logoFile && (
                    <button className="branding-remove-selection" type="button" onClick={clearLocalLogo}>
                      <X size={14} aria-hidden="true" /><UiText source="إلغاء الاختيار" />
                    </button>
                  )}
                </div>
                {logoFile && <p className="branding-selected-file"><bdi>{logoFile.name}</bdi> · <UiText source="لن يُرفع حتى تحفظ التغييرات." /></p>}
                {logoError && <p className="branding-inline-error" role="alert">{logoError}</p>}
              </div>
            </div>
          </section>

          <section className="branding-section" aria-labelledby="branding-colors-heading">
            <div className="branding-section-heading branding-colors-heading">
              <span className="branding-section-icon"><Palette size={19} aria-hidden="true" /></span>
              <div>
                <h2 id="branding-colors-heading"><UiText source="لوحة الألوان" /></h2>
                <p><UiText source="ثمانية ألوان واضحة الأدوار تحافظ على اتساق الهوية في جميع صفحات الخدمة." /></p>
              </div>
              <button type="button" className="branding-reset-colors" onClick={restoreDefaultColors} disabled={save.busy}>
                <RotateCcw size={14} aria-hidden="true" />
                <UiText source="استعادة الألوان الافتراضية" />
              </button>
            </div>
            <div className="branding-color-grid">
              {COLOR_FIELDS.map(({ key, label, description }, index) => {
                const invalid = Boolean(fieldErrors[key]) || (colors[key].length > 0 && !HEX_COLOR.test(colors[key]));
                return (
                  <div className={`branding-color-field ${invalid ? "has-error" : ""}`} key={key}>
                    <div className="branding-color-field-title">
                      <span className="branding-color-index">{String(index + 1).padStart(2, "0")}</span>
                      <label htmlFor={`branding-${key}`}><UiText source={label} /></label>
                    </div>
                    <p><UiText source={description} /></p>
                    <div className="branding-color-input-wrap">
                      <input
                        aria-label={`${tText("اختيار")} ${tText(label)}`}
                        className="branding-native-picker"
                        type="color"
                        value={HEX_COLOR.test(colors[key]) ? colors[key] : DEFAULT_COLORS[key]}
                        onChange={(event) => updateColor(key, event.target.value.toUpperCase())}
                      />
                      <input
                        id={`branding-${key}`}
                        className="branding-hex-input"
                        type="text"
                        inputMode="text"
                        autoCapitalize="characters"
                        spellCheck={false}
                        value={colors[key]}
                        aria-invalid={invalid}
                        aria-describedby={invalid ? `branding-${key}-error` : undefined}
                        onChange={(event) => updateColor(key, event.target.value.toUpperCase())}
                      />
                    </div>
                    {invalid && <small className="branding-field-error" id={`branding-${key}-error`}>{fieldErrors[key] ?? tText("أدخل رمز لون بصيغة #RRGGBB.")}</small>}
                  </div>
                );
              })}
            </div>
            <section className="branding-sidebar-guide" aria-labelledby="branding-sidebar-guide-heading" style={previewStyles}>
              <div className="branding-sidebar-guide-copy">
                <strong id="branding-sidebar-guide-heading"><UiText source="معاينة ألوان الشريط الجانبي" /></strong>
                <p><UiText source="خلفية الشريط من لون البطاقة، وخلفية الزر النشط من لون أزرار الشريط، وخط التحديد من لون التمييز." /></p>
              </div>
              <nav className="branding-sidebar-sample" aria-label={tText("معاينة الشريط الجانبي")}>
                <span className="branding-sidebar-sample-link"><UiText source="سجل الشكاوى" /></span>
                <span className="branding-sidebar-sample-link active"><UiText source="الإحصائيات" /></span>
                <span className="branding-sidebar-sample-link"><UiText source="إدارة الموظفين" /></span>
              </nav>
            </section>
          </section>

          <section className="branding-preview-section" aria-labelledby="branding-preview-heading" style={previewStyles}>
            <div className="branding-preview-head">
              <div>
                <span className="branding-preview-eyebrow"><UiText source="معاينة قبل النشر" /></span>
                <h2 id="branding-preview-heading"><UiText source="هكذا ستبدو الهوية للمواطن" /></h2>
              </div>
              <span className="branding-preview-badge"><UiText source="معاينة فقط" /></span>
            </div>
            <div className="branding-mock-page">
              <div className="branding-mock-nav">
                <div className="branding-mock-brand">
                  <div className="branding-mock-mark">
                    {logoPreview || (query.data.logo_url && !resetLogoOnSave)
                      ? <img src={logoPreview ?? query.data.logo_url ?? undefined} alt="" />
                      : <span className="branding-mini-mark" aria-hidden="true"><i /><i /><i /></span>}
                  </div>
                  <div><strong><UiText source="خدمة الشكاوى العامة" /></strong><small><UiText source="صوتك يصل، ونتابع معك" /></small></div>
                </div>
                <span className="branding-mock-nav-label"><UiText source="الشفافية العامة" /></span>
              </div>
              <div className="branding-mock-content">
                <span className="branding-mock-kicker"><UiText source="خدمة عامة موثوقة" /></span>
                <h3><UiText source="كل شكوى تستحق أن تُسمع." /></h3>
                <p><UiText source="قدّم شكواك وتابع خطوات معالجتها بوضوح." /></p>
                <button type="button" className="branding-mock-button"><UiText source="تقديم شكوى" /></button>
                <div className="branding-mock-status">
                  <span className="branding-mock-status-dot" />
                  <span><strong><UiText source="قيد المتابعة" /></strong><small><UiText source="تحديثات واضحة في كل خطوة" /></small></span>
                  <span className="branding-mock-status-accent" />
                </div>
              </div>
            </div>
            <div className="branding-contrast">
              <div className="branding-contrast-heading">
                <ShieldCheck size={17} aria-hidden="true" />
                <strong><UiText source="فحوصات وضوح النص" /></strong>
                <span><UiText source="المعيار: 4.5:1" /></span>
              </div>
              <div className="branding-contrast-grid">
                <ContrastCheck foreground="#FFFFFF" background={colors.brand_dark} label={tText("زر أساسي")} foregroundLabel={tText("نص أبيض / داكن")} passLabel={tText("مقروء")} failLabel={tText("يحتاج تحسينًا")} />
                <ContrastCheck foreground="#FFFFFF" background={colors.brand_primary} label={tText("زر رئيسي")} foregroundLabel={tText("نص أبيض / أساسي")} passLabel={tText("مقروء")} failLabel={tText("يحتاج تحسينًا")} />
                <ContrastCheck foreground="#283128" background={colors.brand_bg} label={tText("خلفية الصفحة")} foregroundLabel={tText("نص داكن / خلفية")} passLabel={tText("مقروء")} failLabel={tText("يحتاج تحسينًا")} />
                <ContrastCheck foreground="#283128" background={colors.brand_card} label={tText("خلفية البطاقة")} foregroundLabel={tText("نص داكن / بطاقة")} passLabel={tText("مقروء")} failLabel={tText("يحتاج تحسينًا")} />
              </div>
            </div>
          </section>

          <div className="branding-savebar">
            <div className="branding-save-meta">
              {query.data.updated_at && (
                <span><UiText source="آخر تحديث" /> · <time dateTime={query.data.updated_at}>{new Intl.DateTimeFormat(lang === "ar" ? "ar" : "en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(query.data.updated_at))}</time></span>
              )}
              {hasChanges && <span className="branding-unsaved"><i aria-hidden="true" /><UiText source="تغييرات غير محفوظة" /></span>}
            </div>
            <div className="branding-save-actions">
              <AdminAlert text={save.message} isError={save.isError} />
              {hasChanges && !isValid && (
                <div className="branding-save-warning" role="alert">
                  <strong><UiText source="تعذّر الحفظ للأسباب التالية:" /></strong>
                  {!validColorFormats ? (
                    <p><UiText source="أدخل جميع الألوان بصيغة #RRGGBB." /></p>
                  ) : (
                    <ul>
                      {contrastIssues.map((issue) => <li key={issue}><UiText source={issue} /></li>)}
                    </ul>
                  )}
                </div>
              )}
              <button className="btn branding-save-button" type="button" onClick={() => void submitChanges()} disabled={save.busy || !hasChanges || !isValid}>
                <Save size={16} aria-hidden="true" />
                {save.busy ? <UiText source="جارٍ الحفظ…" /> : <UiText source="حفظ التغييرات" />}
              </button>
            </div>
          </div>
        </>
      )}
    </AdminPage>
  );
}
