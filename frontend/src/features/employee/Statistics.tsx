import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../shared/api/client";
import { useResource, useSession } from "../../shared/api/hooks";
import type { Directorate } from "../../shared/api/types";
import { useI18n } from "../../shared/i18n/I18n";
import { EmployeeLoadError } from "./EmployeeLoadError";
import { StaffGate } from "./StaffGate";
import { hasPermission } from "./permissions";
import {
  DailyChart,
  EmptyBreakdown,
  HorizontalBars,
  makeDailyBuckets,
  StatusDonut,
  trendDescription,
} from "./StatisticsCharts";
import "./Statistics.css";

type Analytics = {
  total: number;
  counts_by_status: Record<string, number>;
  counts_by_category: { label: string; count: number }[];
  counts_by_priority: Record<string, number>;
  daily: { date: string; count: number }[];
  resolution_rate: number;
  average_progress: number;
  scope: { role: string; directorate_id: number | null };
  filters: { start_date: string; end_date: string; directorate_id: number | null };
  definitions: Record<string, string>;
};

export function Statistics() {
  const { lang, tText } = useI18n();
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [directorate, setDirectorate] = useState("");
  const [query, setQuery] = useState("");
  const [period, setPeriod] = useState("30");
  const [customDates, setCustomDates] = useState(false);
  const session = useSession();
  const directorates = useResource<Directorate[]>("/directorates", lang);
  const analytics = useQuery({
    queryKey: ["analytics", query, lang],
    queryFn: () => api<Analytics>(`/analytics${query ? `?${query}` : ""}`, { language: lang }),
    enabled: hasPermission(session.data, "reports.view"),
    retry: false,
  });

  return (
    <StaffGate required="reports.view">
      <div className="statistics-page">
        <header className="statistics-heading">
          <div>
            <div className="eyebrow">{label(lang, "لوحة الأداء", "SERVICE PERFORMANCE")}</div>
            <h1>{tText("إحصائيات الشكاوى")}</h1>
            <p className="muted">
              {tText("أرقام فعلية ضمن نطاق الصلاحية، حسب تاريخ تقديم الشكوى.")}
            </p>
          </div>
          {analytics.data && (
            <div className="statistics-period-note" dir="auto">
              {formatDateRange(
                analytics.data.filters.start_date,
                analytics.data.filters.end_date,
                lang,
              )}
            </div>
          )}
        </header>

        <form
          className="statistics-filters"
          onSubmit={(event) => {
            event.preventDefault();
            const params = new URLSearchParams();
            if (from) params.set("start_date", from);
            if (to) params.set("end_date", to);
            if (directorate) params.set("directorate_id", directorate);
            setPeriod("");
            setQuery(params.toString());
          }}
        >
          <div className="statistics-filter-top">
            <div>
              <strong>{label(lang, "الفترة الزمنية", "Reporting period")}</strong>
              <span>
                {label(
                  lang,
                  "عرض سريع للفترة أو تحديد تواريخ مخصصة",
                  "Choose a preset or set exact dates",
                )}
              </span>
            </div>
            <div
              className="statistics-range-tabs"
              role="group"
              aria-label={label(lang, "الفترة", "Period")}
            >
              {[
                ["7", label(lang, "٧ أيام", "7 days")],
                ["30", label(lang, "٣٠ يومًا", "30 days")],
                ["90", label(lang, "٩٠ يومًا", "90 days")],
                ["366", label(lang, "سنة", "1 year")],
              ].map(([days, caption]) => (
                <button
                  className="statistics-range-button"
                  type="button"
                  key={days}
                  aria-pressed={period === days}
                  onClick={() => {
                    const range = getRange(Number(days));
                    setPeriod(days);
                    setFrom(range.start);
                    setTo(range.end);
                    const params = new URLSearchParams({
                      start_date: range.start,
                      end_date: range.end,
                    });
                    if (directorate) params.set("directorate_id", directorate);
                    setQuery(params.toString());
                  }}
                >
                  {caption}
                </button>
              ))}
              <button
                className="statistics-custom-toggle"
                type="button"
                aria-expanded={customDates}
                onClick={() => setCustomDates((value) => !value)}
              >
                {customDates
                  ? label(lang, "إخفاء التواريخ", "Hide dates")
                  : label(lang, "تاريخ مخصص", "Custom dates")}
              </button>
            </div>
          </div>

          {hasPermission(session.data, "reports.view") && (
            <label className="field-label">
              {tText("المديرية")}
              <select
                className="field"
                value={directorate}
                onChange={(event) => {
                  const selected = event.target.value;
                  setDirectorate(selected);
                  const params = new URLSearchParams();
                  if (from) params.set("start_date", from);
                  if (to) params.set("end_date", to);
                  if (selected) params.set("directorate_id", selected);
                  setQuery(params.toString());
                }}
              >
                <option value="">{tText("وفق نطاقي")}</option>
                {directorates.data?.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.hierarchy_path ?? item.name}
                  </option>
                ))}
              </select>
            </label>
          )}

          {customDates && (
            <div className="statistics-filter-controls">
              <label className="field-label">
                {tText("من تاريخ")}
                <input
                  className="field"
                  type="date"
                  value={from}
                  max={to || undefined}
                  onChange={(e) => {
                    setFrom(e.target.value);
                    setPeriod("");
                  }}
                />
              </label>
              <label className="field-label">
                {tText("إلى تاريخ")}
                <input
                  className="field"
                  type="date"
                  value={to}
                  min={from || undefined}
                  onChange={(e) => {
                    setTo(e.target.value);
                    setPeriod("");
                  }}
                />
              </label>
              <button
                className="btn"
                disabled={!from || !to || from > to || dateDistance(from, to) > 366}
              >
                {tText("تطبيق")}
              </button>
              {from && to && dateDistance(from, to) > 366 && (
                <p className="status error" style={{ gridColumn: "1 / -1", margin: 0 }}>
                  {label(
                    lang,
                    "يجب ألا تتجاوز المدة بين التاريخين ٣٦٦ يومًا.",
                    "The span between dates must be no more than 366 days.",
                  )}
                </p>
              )}
            </div>
          )}
        </form>

        {analytics.isLoading ? (
          <div className="statistics-loading-grid" aria-label={tText("جارٍ التحميل")}>
            <div className="statistics-summary">
              <div className="skeleton" />
              <div className="skeleton" />
              <div className="skeleton" />
            </div>
            <div className="skeleton" />
            <div className="skeleton" />
          </div>
        ) : analytics.error ? (
          <EmployeeLoadError error={analytics.error} retry={() => void analytics.refetch()} />
        ) : analytics.data ? (
          <AnalyticsResults data={analytics.data} lang={lang} tText={tText} />
        ) : null}
      </div>
    </StaffGate>
  );
}

function AnalyticsResults({
  data,
  lang,
  tText,
}: {
  data: Analytics;
  lang: string;
  tText: (text: string) => string;
}) {
  const chart = useMemo(() => makeDailyBuckets(data.daily, lang), [data.daily, lang]);
  const categories = data.counts_by_category;
  const priorities = Object.entries(data.counts_by_priority);
  const statuses = Object.entries(data.counts_by_status);

  return (
    <div className="statistics-page">
      {data.total === 0 ? (
        <div className="statistics-empty">
          <strong>
            {label(lang, "لا توجد شكاوى في هذه الفترة", "No complaints in this period")}
          </strong>
          <span>
            {label(
              lang,
              "جرّب فترة زمنية أخرى أو وسّع نطاق البحث.",
              "Try another reporting period or a wider scope.",
            )}
          </span>
        </div>
      ) : (
        <>
          <section
            className="statistics-summary"
            aria-label={label(lang, "ملخص المؤشرات", "Key measures")}
          >
            <MetricCard
              primary
              title={tText("إجمالي الشكاوى")}
              value={formatNumber(data.total, lang)}
              foot={label(lang, "ضمن الفترة المحددة", "In selected period")}
            />
            <MetricCard
              title={tText("معدل الحل")}
              value={`${formatPercent(data.resolution_rate, lang)}%`}
              foot={label(lang, "من إجمالي الشكاوى", "Of all complaints")}
            />
            <MetricCard
              title={tText("متوسط التقدم")}
              value={`${formatPercent(data.average_progress, lang)}%`}
              foot={label(lang, "متوسط تقدير تقدم المعالجة", "Average reported progress")}
            />
          </section>

          <section className="statistics-section">
            <SectionHeading
              title={label(lang, "حجم الشكاوى عبر الزمن", "Complaint volume over time")}
              subtitle={trendDescription(chart.granularity, lang)}
            />
            <DailyChart data={chart.data} lang={lang} />
          </section>

          <div className="statistics-analytics-grid">
            <section className="statistics-section">
              <SectionHeading
                title={tText("حسب التصنيف")}
                subtitle={label(
                  lang,
                  "توزيع الشكاوى حسب التصنيف",
                  "Breakdown of complaints by category",
                )}
              />
              {categories.length ? (
                <HorizontalBars
                  items={categories.map((item) => [item.label, item.count])}
                  lang={lang}
                />
              ) : (
                <EmptyBreakdown lang={lang} />
              )}
            </section>
            <section className="statistics-section">
              <SectionHeading
                title={tText("حسب الأولوية")}
                subtitle={label(lang, "عدد الشكاوى في كل مستوى", "Complaint count at each level")}
              />
              {priorities.length ? (
                <HorizontalBars
                  items={priorities.map(([name, count]) => [priorityLabel(name, lang), count])}
                  lang={lang}
                />
              ) : (
                <EmptyBreakdown lang={lang} />
              )}
            </section>
          </div>

          <section className="statistics-section">
            <SectionHeading
              title={label(lang, "حالة الشكاوى", "Complaint status")}
              subtitle={label(
                lang,
                "توزيع الحالات ضمن النتائج الحالية",
                "Status mix for the current results",
              )}
            />
            <StatusDonut data={statuses} total={data.total} lang={lang} />
          </section>
        </>
      )}

      {Object.keys(data.definitions).length > 0 && (
        <details className="statistics-definitions">
          <summary>{tText("تعريفات المؤشرات")}</summary>
          <div className="statistics-definition-list">
            {Object.entries(data.definitions).map(([key, value]) => (
              <div className="statistics-definition" key={key}>
                <strong>{definitionLabel(key, lang)}</strong>
                <p>{definitionText(value, key, lang)}</p>
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}

function MetricCard({
  title,
  value,
  foot,
  primary = false,
}: {
  title: string;
  value: string;
  foot: string;
  primary?: boolean;
}) {
  return (
    <div className={`statistics-metric${primary ? " primary" : ""}`}>
      <span className="statistics-metric-label">{title}</span>
      <strong className="statistics-metric-value">{value}</strong>
      <span className="statistics-metric-foot">{foot}</span>
    </div>
  );
}

function SectionHeading({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div className="statistics-section-header">
      <div>
        <h2>{title}</h2>
        <p className="muted">{subtitle}</p>
      </div>
    </div>
  );
}

function formatDate(value: string, lang: string, compact = false) {
  const date = new Date(`${value}T12:00:00`);
  return new Intl.DateTimeFormat(
    lang === "en" ? "en" : "ar",
    compact
      ? { month: "short", day: "numeric" }
      : { year: "numeric", month: "short", day: "numeric" },
  ).format(date);
}

function formatDateRange(start: string, end: string, lang: string) {
  return `${formatDate(start, lang)} – ${formatDate(end, lang)}`;
}

function getRange(days: number) {
  const end = new Date();
  const start = new Date(end);
  start.setDate(start.getDate() - days + 1);
  return { start: localDate(start), end: localDate(end) };
}

function localDate(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function dateDistance(start: string, end: string) {
  return Math.floor((Date.parse(`${end}T00:00:00Z`) - Date.parse(`${start}T00:00:00Z`)) / 86400000);
}

function formatNumber(value: number, lang: string) {
  return new Intl.NumberFormat(lang === "en" ? "en" : "ar").format(value);
}

function formatPercent(value: number, lang: string) {
  return new Intl.NumberFormat(lang === "en" ? "en" : "ar", { maximumFractionDigits: 2 }).format(
    value,
  );
}

function priorityLabel(priority: string, lang: string) {
  const names: Record<string, [string, string]> = {
    LOW: ["منخفضة", "Low"],
    MEDIUM: ["متوسطة", "Medium"],
    HIGH: ["عالية", "High"],
    URGENT: ["عاجلة", "Urgent"],
  };
  return names[priority]?.[lang === "en" ? 1 : 0] ?? priority;
}

function definitionLabel(key: string, lang: string) {
  const names: Record<string, [string, string]> = {
    resolution_rate: ["معدل الحل", "Resolution rate"],
    average_progress: ["متوسط التقدم", "Average progress"],
    dates: ["التواريخ", "Dates"],
  };
  return names[key]?.[lang === "en" ? 1 : 0] ?? key;
}

function definitionText(value: string, key: string, lang: string) {
  if (lang !== "en") return value;
  const translations: Record<string, string> = {
    resolution_rate:
      "Resolved complaints ÷ all complaints in the period × 100; rejected complaints remain in the total.",
    average_progress:
      "Average staff estimate of processing progress; this is not the share of resolved complaints.",
    dates: "Filtered by complaint submission date in UTC; the start and end dates are inclusive.",
  };
  return translations[key] ?? value;
}

function label(lang: string, arabic: string, english: string) {
  return lang === "en" ? english : arabic;
}
