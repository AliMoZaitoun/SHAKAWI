import { useEffect, useId, useMemo, useRef, useState } from "react";
import {
  Check,
  FileText,
  Printer,
  RotateCcw,
  Save,
  Upload,
  X,
} from "lucide-react";
import { api } from "../../../shared/api/client";
import { useResource } from "../../../shared/api/hooks";
import type { Complaint, Directorate } from "../../../shared/api/types";
import { BrandMark, useBranding } from "../../../shared/branding/Branding";
import { useI18n } from "../../../shared/i18n/I18n";
import "./ComplaintPrintPreview.css";

export type ComplaintPrintSection =
  | "tracking_code"
  | "title"
  | "details"
  | "directorate"
  | "category"
  | "created_at"
  | "status"
  | "progress"
  | "resolution_report"
  | "public_updates"
  | "citizen_contact";

type PrintTemplate = {
  titles: Record<string, string>;
  default_sections: string[];
};

type Props = {
  complaint: Complaint;
  audience: "staff" | "citizen";
  canSaveDefaults?: boolean;
};

const SECTION_IDS: ComplaintPrintSection[] = [
  "tracking_code",
  "title",
  "details",
  "directorate",
  "category",
  "created_at",
  "status",
  "progress",
  "resolution_report",
  "public_updates",
  "citizen_contact",
];

const FALLBACK_SECTIONS: ComplaintPrintSection[] = [
  "tracking_code",
  "title",
  "details",
  "directorate",
  "category",
  "created_at",
  "status",
  "progress",
  "resolution_report",
  "public_updates",
];

const SECTION_LABELS: Record<ComplaintPrintSection, string> = {
  tracking_code: "رمز المتابعة",
  title: "عنوان الشكوى",
  details: "تفاصيل الشكوى",
  directorate: "الجهة المختصة",
  category: "التصنيف",
  created_at: "تاريخ التقديم",
  status: "الحالة",
  progress: "تقدم المعالجة",
  resolution_report: "تقرير المعالجة",
  public_updates: "التحديثات العامة",
  citizen_contact: "بيانات التواصل",
};

function isSection(value: string): value is ComplaintPrintSection {
  return SECTION_IDS.includes(value as ComplaintPrintSection);
}

function safeDate(value: string, lang: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  try {
    return new Intl.DateTimeFormat(lang === "ar" ? "ar" : "en", {
      dateStyle: "long",
    }).format(date);
  } catch {
    return date.toLocaleDateString();
  }
}

function statusLabel(status: Complaint["status"], tText: (source: string) => string) {
  const labels: Record<Complaint["status"], string> = {
    PENDING: "جديدة",
    IN_PROGRESS: "قيد المعالجة",
    RESOLVED: "تمت المعالجة",
    REJECTED: "مرفوضة",
  };
  return tText(labels[status] ?? status);
}

export function ComplaintPrintPreview({
  complaint,
  audience,
  canSaveDefaults = false,
}: Props) {
  const { lang, tText } = useI18n();
  const branding = useBranding();
  const directorates = useResource<Directorate[]>("/directorates", lang);
  const dialogId = useId();
  const titleInputId = useId();
  const logoInputId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);
  const initializedTemplate = useRef(false);
  const [isOpen, setIsOpen] = useState(false);
  const [template, setTemplate] = useState<PrintTemplate>({
    titles: {},
    default_sections: FALLBACK_SECTIONS,
  });
  const [selectedSections, setSelectedSections] =
    useState<ComplaintPrintSection[]>(FALLBACK_SECTIONS);
  const [titleOverride, setTitleOverride] = useState("");
  const [customLogoUrl, setCustomLogoUrl] = useState("");
  const [logoNotice, setLogoNotice] = useState("");
  const [saveNotice, setSaveNotice] = useState("");
  const [savingDefaults, setSavingDefaults] = useState(false);

  const direction = lang === "ar" ? "rtl" : "ltr";
  const filteredNotes = useMemo(
    () =>
      (complaint.notes ?? []).filter(
        (note) => !note.is_internal && note.audience !== "internal",
      ),
    [complaint.notes],
  );
  const directorateName =
    directorates.data?.find((item) => item.id === complaint.directorate_id)?.hierarchy_path ??
    directorates.data?.find((item) => item.id === complaint.directorate_id)?.name ??
    "";
  const printableSections = useMemo(
    () =>
      selectedSections.filter(
        (section) => section !== "citizen_contact" || audience === "staff",
      ),
    [audience, selectedSections],
  );
  const logoSource = customLogoUrl || branding?.logo_url || "";
  const effectiveTitle =
    titleOverride.trim() ||
    template.titles[lang] ||
    template.titles.en ||
    tText("ملخص الشكوى");

  useEffect(() => {
    let mounted = true;
    api<PrintTemplate>("/print-template", { language: lang })
      .then((result) => {
        if (!mounted) return;
        const safeSections = Array.isArray(result.default_sections)
          ? result.default_sections.filter(isSection)
          : FALLBACK_SECTIONS;
        const safeTitles =
          result.titles && typeof result.titles === "object" ? result.titles : {};
        setTemplate({ titles: safeTitles, default_sections: safeSections });
        if (!initializedTemplate.current) {
          const initial = safeSections.length ? safeSections : FALLBACK_SECTIONS;
          setSelectedSections(
            audience === "citizen"
              ? initial.filter((section) => section !== "citizen_contact")
              : initial,
          );
          initializedTemplate.current = true;
        }
      })
      .catch(() => {
        if (!initializedTemplate.current) {
          setSelectedSections(
            audience === "citizen"
              ? FALLBACK_SECTIONS.filter((section) => section !== "citizen_contact")
              : FALLBACK_SECTIONS,
          );
          initializedTemplate.current = true;
        }
      });
    return () => {
      mounted = false;
    };
  }, [audience, lang]);

  useEffect(() => {
    return () => {
      if (customLogoUrl) URL.revokeObjectURL(customLogoUrl);
    };
  }, [customLogoUrl]);

  useEffect(() => {
    if (!isOpen) return;
    previousFocus.current = document.activeElement as HTMLElement | null;
    closeRef.current?.focus();

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        setIsOpen(false);
      }
      if (event.key !== "Tab" || !dialogRef.current) return;
      const focusable = Array.from(
        dialogRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), input:not([disabled]), [href], [tabindex]:not([tabindex="-1"])',
        ),
      ).filter((element) => element.offsetParent !== null);
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      previousFocus.current?.focus();
    };
  }, [isOpen]);

  function openDialog() {
    setIsOpen(true);
    setSaveNotice("");
    setLogoNotice("");
  }

  function toggleSection(section: ComplaintPrintSection) {
    if (section === "citizen_contact" && audience === "citizen") return;
    setSelectedSections((current) =>
      current.includes(section)
        ? current.filter((item) => item !== section)
        : [...current, section],
    );
  }

  function handleLogoSelection(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    setLogoNotice("");
    if (!file) return;
    const allowedTypes = ["image/png", "image/jpeg", "image/webp"];
    if (!allowedTypes.includes(file.type)) {
      setLogoNotice(tText("اختر ملف PNG أو JPEG أو WebP."));
      return;
    }
    if (file.size > 2 * 1024 * 1024) {
      setLogoNotice(tText("يجب ألا يتجاوز حجم الشعار 2 ميبيبايت."));
      return;
    }
    setCustomLogoUrl(URL.createObjectURL(file));
  }

  async function saveDefaults() {
    setSavingDefaults(true);
    setSaveNotice("");
    try {
      const titles = { ...template.titles, [lang]: effectiveTitle };
      await api("/admin/settings/print-template", {
        method: "PUT",
        language: lang,
        body: {
          titles,
          default_sections: selectedSections,
        },
      });
      setTemplate((current) => ({ ...current, titles }));
      setTitleOverride("");
      setSaveNotice(tText("تم حفظ الإعدادات الافتراضية."));
    } catch (error) {
      setSaveNotice(
        error instanceof Error
          ? error.message
          : tText("تعذر حفظ الإعدادات الافتراضية."),
      );
    } finally {
      setSavingDefaults(false);
    }
  }

  function sectionLabel(section: ComplaintPrintSection) {
    return tText(SECTION_LABELS[section]);
  }

  function renderSection(section: ComplaintPrintSection) {
    const heading = sectionLabel(section);
    switch (section) {
      case "tracking_code":
        return (
          <section className="cpp-print-section cpp-code-section" key={section}>
            <h2>{heading}</h2>
            <p className="cpp-tracking-code" dir="ltr">
              {complaint.tracking_code}
            </p>
          </section>
        );
      case "title":
        return (
          <section className="cpp-print-section" key={section}>
            <h2>{heading}</h2>
            <p>{complaint.title || "—"}</p>
          </section>
        );
      case "details":
        return (
          <section className="cpp-print-section" key={section}>
            <h2>{heading}</h2>
            <p className="cpp-preserve-lines">{complaint.details || "—"}</p>
          </section>
        );
      case "directorate":
        return (
          <section className="cpp-print-section" key={section}>
            <h2>{heading}</h2>
            <p>{directorateName || "—"}</p>
          </section>
        );
      case "category":
        return (
          <section className="cpp-print-section" key={section}>
            <h2>{heading}</h2>
            <p>{complaint.category || "—"}</p>
          </section>
        );
      case "created_at":
        return (
          <section className="cpp-print-section" key={section}>
            <h2>{heading}</h2>
            <p>{safeDate(complaint.created_at, lang)}</p>
          </section>
        );
      case "status":
        return (
          <section className="cpp-print-section" key={section}>
            <h2>{heading}</h2>
            <p>{statusLabel(complaint.status, tText)}</p>
          </section>
        );
      case "progress":
        return (
          <section className="cpp-print-section" key={section}>
            <h2>{heading}</h2>
            <p>{`${Math.max(0, Math.min(100, Number(complaint.progress) || 0))}%`}</p>
          </section>
        );
      case "resolution_report":
        if (!complaint.resolution_report?.trim()) return null;
        return (
          <section className="cpp-print-section" key={section}>
            <h2>{heading}</h2>
            <p className="cpp-preserve-lines">{complaint.resolution_report}</p>
          </section>
        );
      case "public_updates":
        if (!filteredNotes.length) return null;
        return (
          <section className="cpp-print-section" key={section}>
            <h2>{heading}</h2>
            <div className="cpp-updates">
              {filteredNotes.map((note) => (
                <article className="cpp-update" key={note.id}>
                  <p className="cpp-preserve-lines">{note.note}</p>
                  <time>{safeDate(note.created_at, lang)}</time>
                </article>
              ))}
            </div>
          </section>
        );
      case "citizen_contact": {
        if (audience !== "staff") return null;
        const citizenName = [
          complaint.citizen?.first_name,
          complaint.citizen?.last_name,
        ].filter(Boolean).join(" ");
        return (
          <section className="cpp-print-section" key={section}>
            <h2>{heading}</h2>
            <p className="cpp-preserve-lines">
              {[citizenName, complaint.citizen?.phone].filter(Boolean).join("\n") || "—"}
            </p>
          </section>
        );
      }
    }
  }

  return (
    <div className="cpp-root" dir={direction}>
      <button className="cpp-open-button" type="button" onClick={openDialog}>
        <Printer size={17} aria-hidden="true" />
        <span>{tText("معاينة وطباعة")}</span>
      </button>

      {isOpen && (
        <div
          className="cpp-backdrop"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) setIsOpen(false);
          }}
        >
          <div
            aria-labelledby={`${dialogId}-heading`}
            aria-modal="true"
            className="cpp-dialog"
            id={dialogId}
            ref={dialogRef}
            role="dialog"
          >
            <header className="cpp-dialog-header">
              <div className="cpp-dialog-title">
                <span className="cpp-dialog-icon">
                  <FileText size={19} aria-hidden="true" />
                </span>
                <div>
                  <h2 id={`${dialogId}-heading`}>{tText("إعداد ملخص للطباعة")}</h2>
                  <p>{tText("اختر ما تريد تضمينه في نسخة واضحة قابلة للمشاركة.")}</p>
                </div>
              </div>
              <button
                aria-label={tText("إغلاق")}
                className="cpp-icon-button"
                onClick={() => setIsOpen(false)}
                ref={closeRef}
                type="button"
              >
                <X size={19} aria-hidden="true" />
              </button>
            </header>

            <div className="cpp-dialog-body">
              <aside className="cpp-controls" aria-label={tText("إعدادات المعاينة")}>
                <label className="cpp-field-label" htmlFor={titleInputId}>
                  {tText("عنوان الملخص")}
                </label>
                <input
                  className="cpp-text-input"
                  id={titleInputId}
                  maxLength={120}
                  onChange={(event) => setTitleOverride(event.target.value)}
                  placeholder={template.titles[lang] || tText("ملخص الشكوى")}
                  value={titleOverride}
                />

                <fieldset className="cpp-section-fieldset">
                  <legend>{tText("الأقسام")}</legend>
                  <div className="cpp-section-list">
                    {SECTION_IDS.filter(
                      (section) => section !== "citizen_contact" || audience === "staff",
                    ).map((section) => (
                      <label className="cpp-check-row" key={section}>
                        <input
                          checked={selectedSections.includes(section)}
                          onChange={() => toggleSection(section)}
                          type="checkbox"
                        />
                        <span className="cpp-checkmark" aria-hidden="true">
                          <Check size={13} />
                        </span>
                        <span>{sectionLabel(section)}</span>
                      </label>
                    ))}
                  </div>
                </fieldset>

                <div className="cpp-logo-control">
                  <div className="cpp-logo-copy">
                    <strong>{tText("شعار النسخة المطبوعة")}</strong>
                    <span>{tText("اختياري · يبقى هذا الملف على جهازك فقط")}</span>
                  </div>
                  <label className="cpp-upload-button" htmlFor={logoInputId}>
                    <Upload size={15} aria-hidden="true" />
                    {tText("اختيار صورة")}
                  </label>
                  <input
                    accept="image/png,image/jpeg,image/webp"
                    className="cpp-visually-hidden"
                    id={logoInputId}
                    onChange={handleLogoSelection}
                    type="file"
                  />
                  {logoSource && (
                    <div className="cpp-logo-preview">
                      <img src={logoSource} alt={tText("معاينة الشعار")} />
                      {customLogoUrl && (
                        <button
                          className="cpp-clear-logo"
                          onClick={() => setCustomLogoUrl("")}
                          type="button"
                        >
                          <RotateCcw size={14} aria-hidden="true" />
                          {tText("استخدام شعار المنصة")}
                        </button>
                      )}
                    </div>
                  )}
                  {logoNotice && (
                    <p className="cpp-inline-notice" role="alert">
                      {logoNotice}
                    </p>
                  )}
                </div>

                {canSaveDefaults && (
                  <div className="cpp-default-save">
                    <button
                      className="cpp-save-button"
                      disabled={savingDefaults || selectedSections.length === 0}
                      onClick={() => void saveDefaults()}
                      type="button"
                    >
                      <Save size={16} aria-hidden="true" />
                      {savingDefaults
                        ? tText("جارٍ الحفظ…")
                        : tText("حفظ اختيارات الأقسام كافتراضي")}
                    </button>
                    {saveNotice && (
                      <p className="cpp-inline-notice" role="status">
                        {saveNotice}
                      </p>
                    )}
                  </div>
                )}
              </aside>

              <main className="cpp-preview-area">
                <div className="cpp-preview-caption">
                  <span>{tText("معاينة النسخة")}</span>
                  <span>{tText("نسخة للمشاركة")}</span>
                </div>
                <article className="cpp-print-sheet" dir={direction}>
                  <header className="cpp-document-header">
                    <div className="cpp-document-brand">
                      {logoSource ? (
                        <img className="cpp-document-logo" src={logoSource} alt="" />
                      ) : (
                      <span className="cpp-document-mark">
                        <BrandMark size={22} />
                      </span>
                      )}
                      <div>
                        <strong>{tText("خدمة الشكاوى")}</strong>
                        <span>{tText("ملخص متابعة")}</span>
                      </div>
                    </div>
                    <span className="cpp-document-date">{safeDate(new Date().toISOString(), lang)}</span>
                  </header>
                  <div className="cpp-document-rule" />
                  <h1>{effectiveTitle}</h1>
                  <div className="cpp-document-content">
                    {printableSections.map(renderSection)}
                    {printableSections.length === 0 && (
                      <p className="cpp-no-sections">{tText("اختر قسمًا واحدًا على الأقل للمعاينة.")}</p>
                    )}
                  </div>
                  <footer className="cpp-document-footer">
                    <span>{tText("أُعد هذا الملخص من خدمة الشكاوى.")}</span>
                    <span>{tText("للمتابعة، استخدم رمز المتابعة الخاص بك.")}</span>
                  </footer>
                </article>
              </main>
            </div>

            <footer className="cpp-dialog-footer">
              <p>{tText("تتضمن النسخة التحديثات العامة فقط، ولا تتضمن الملاحظات الداخلية أو الملفات.")}</p>
              <div className="cpp-actions">
                <button
                  className="cpp-cancel-button"
                  onClick={() => setIsOpen(false)}
                  type="button"
                >
                  {tText("إغلاق")}
                </button>
                <button
                  className="cpp-print-button"
                  disabled={!printableSections.length}
                  onClick={() => window.print()}
                  type="button"
                >
                  <Printer size={16} aria-hidden="true" />
                  {tText("طباعة الملخص")}
                </button>
              </div>
            </footer>
          </div>
        </div>
      )}
    </div>
  );
}

export default ComplaintPrintPreview;
