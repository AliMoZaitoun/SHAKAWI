import { complaintStatusLabel } from "./permissions";

type DailyPoint = { date: string; count: number };
type TrendPoint = { label: string; title: string; count: number };

export function DailyChart({ data, lang }: { data: TrendPoint[]; lang: string }) {
  if (!data.length || data.every((point) => point.count === 0)) {
    return <EmptyBreakdown lang={lang} />;
  }

  const width = Math.max(640, data.length * 31 + 48);
  const height = 240;
  const padding = { top: 20, right: 15, bottom: 44, left: 38 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;
  const max = Math.max(...data.map((item) => item.count), 1);
  const step = chartWidth / data.length;
  const barWidth = Math.min(18, step * 0.64);
  const tickStep = Math.max(1, Math.ceil(data.length / 8));
  const axisLabels = new Set<number>();

  return (
    <div
      className="statistics-chart-shell"
      role="img"
      aria-label={label(lang, "مخطط أعمدة لحجم الشكاوى", "Complaint volume bar chart")}
    >
      <svg
        className="statistics-chart"
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
      >
        {[0, 0.5, 1].map((fraction) => {
          const y = padding.top + chartHeight * fraction;
          const value = Math.round(max * (1 - fraction));
          const showLabel = !axisLabels.has(value);
          axisLabels.add(value);
          return (
            <g key={fraction}>
              <line
                className="chart-gridline"
                x1={padding.left}
                x2={width - padding.right}
                y1={y}
                y2={y}
              />
              {showLabel && (
                <text x={padding.left - 8} y={y + 4} textAnchor="end">
                  {formatNumber(value, lang)}
                </text>
              )}
            </g>
          );
        })}
        {data.map((point, index) => {
          const barHeight = (point.count / max) * chartHeight;
          const x = padding.left + index * step + (step - barWidth) / 2;
          const y = padding.top + chartHeight - barHeight;
          return (
            <g key={`${point.title}-${index}`}>
              <title>{`${point.title}: ${formatNumber(point.count, lang)}`}</title>
              <rect
                className="chart-bar"
                x={x}
                y={y}
                width={barWidth}
                height={Math.max(1, barHeight)}
                rx="3"
              />
              {(index % tickStep === 0 || index === data.length - 1) && (
                <text x={x + barWidth / 2} y={height - 12} textAnchor="middle">
                  {point.label}
                </text>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

export function StatusDonut({
  data,
  total,
  lang,
}: {
  data: [string, number][];
  total: number;
  lang: string;
}) {
  const radius = 62;
  const circumference = 2 * Math.PI * radius;
  const segments = data.filter(([, count]) => count > 0);
  let offset = 0;

  return (
    <div className="statistics-status-chart">
      <figure
        className="statistics-donut"
        role="img"
        aria-label={label(
          lang,
          "مخطط دائري يوضح توزيع الشكاوى حسب الحالة",
          "Donut chart of complaints by status",
        )}
      >
        <svg viewBox="0 0 180 180" aria-hidden="true">
          <circle
            className="statistics-donut-track"
            cx="90"
            cy="90"
            r={radius}
            fill="none"
            strokeWidth="19"
          />
          {segments.map(([status, count]) => {
            const length = (count / total) * circumference;
            const circle = (
              <circle
                key={status}
                className="statistics-donut-segment"
                cx="90"
                cy="90"
                r={radius}
                fill="none"
                stroke={statusColor(status)}
                strokeWidth="19"
                strokeDasharray={`${length} ${circumference - length}`}
                strokeDashoffset={-offset}
                transform="rotate(-90 90 90)"
              />
            );
            offset += length;
            return circle;
          })}
        </svg>
        <div className="statistics-donut-center">
          <strong>{formatNumber(total, lang)}</strong>
          <span>{label(lang, "شكوى", "complaints")}</span>
        </div>
      </figure>
      <div className="statistics-status-legend">
        {data.map(([status, count]) => (
          <div className="statistics-status-row" key={status}>
            <span className="statistics-status-name">
              <span
                className="statistics-status-dot"
                style={{ backgroundColor: statusColor(status) }}
              />
              {complaintStatusLabel(status, lang)}
            </span>
            <span className="statistics-status-count">{formatNumber(count, lang)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function HorizontalBars({ items, lang }: { items: [string, number][]; lang: string }) {
  const max = Math.max(...items.map(([, value]) => value), 1);
  return (
    <div className="statistics-bar-list">
      {items.map(([name, count]) => (
        <div className="statistics-bar-row" key={name} title={`${name}: ${count}`}>
          <span className="statistics-bar-label">{name}</span>
          <span className="statistics-bar-track">
            <span
              className="statistics-bar-fill"
              style={{ width: `${Math.max(1, (count / max) * 100)}%` }}
            />
          </span>
          <span className="statistics-bar-count">{formatNumber(count, lang)}</span>
        </div>
      ))}
    </div>
  );
}

export function EmptyBreakdown({ lang }: { lang: string }) {
  return (
    <div className="statistics-empty">
      <strong>{label(lang, "لا توجد بيانات للعرض", "Nothing to display")}</strong>
      <span>
        {label(
          lang,
          "لا تتوفر قيم ضمن النتائج الحالية.",
          "No values are available for the current results.",
        )}
      </span>
    </div>
  );
}

export function makeDailyBuckets(rows: DailyPoint[], lang: string) {
  const dateCount = rows.length;
  const granularity = dateCount <= 14 ? "day" : dateCount <= 180 ? "week" : "month";
  const buckets: { start: string; end: string; count: number }[] = [];
  if (granularity === "month") {
    const byMonth = new Map<string, (typeof buckets)[number]>();
    for (const row of rows) {
      const month = row.date.slice(0, 7);
      const bucket = byMonth.get(month);
      if (bucket) {
        bucket.end = row.date;
        bucket.count += row.count;
      } else {
        byMonth.set(month, { start: row.date, end: row.date, count: row.count });
      }
    }
    buckets.push(...byMonth.values());
  } else {
    const bucketSize = granularity === "day" ? 1 : 7;
    for (let i = 0; i < rows.length; i += bucketSize) {
      const slice = rows.slice(i, i + bucketSize);
      buckets.push({
        start: slice[0].date,
        end: slice[slice.length - 1].date,
        count: slice.reduce((sum, row) => sum + row.count, 0),
      });
    }
  }

  return {
    granularity,
    data: buckets.map((bucket) => ({
      count: bucket.count,
      title:
        bucket.start === bucket.end
          ? formatDate(bucket.start, lang)
          : `${formatDate(bucket.start, lang)} – ${formatDate(bucket.end, lang)}`,
      label:
        granularity === "month"
          ? new Intl.DateTimeFormat(lang === "en" ? "en" : "ar", {
              month: "short",
              year: "2-digit",
            }).format(new Date(`${bucket.start}T12:00:00`))
          : formatDate(bucket.start, lang, true),
    })),
  };
}

export function trendDescription(granularity: string, lang: string) {
  const descriptions: Record<string, [string, string]> = {
    day: ["عدد الشكاوى حسب اليوم", "Daily complaint count"],
    week: ["إجمالي الشكاوى لكل ٧ أيام", "Complaint totals in 7-day periods"],
    month: ["إجمالي الشكاوى لكل شهر", "Monthly complaint totals"],
  };
  return descriptions[granularity]?.[lang === "en" ? 1 : 0] ?? descriptions.day[0];
}

function statusColor(status: string) {
  const colors: Record<string, string> = {
    PENDING: "#4a5d3f",
    IN_PROGRESS: "#b88d4b",
    RESOLVED: "#728964",
    REJECTED: "#aa6559",
  };
  return colors[status] ?? "#8d9787";
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

function formatNumber(value: number, lang: string) {
  return new Intl.NumberFormat(lang === "en" ? "en" : "ar").format(value);
}

function label(lang: string, arabic: string, english: string) {
  return lang === "en" ? english : arabic;
}
