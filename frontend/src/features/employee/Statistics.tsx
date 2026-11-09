import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../shared/api/client";
import { useResource, useSession } from "../../shared/api/hooks";
import type { Directorate } from "../../shared/api/types";
import { useI18n } from "../../shared/i18n/I18n";
import { EmployeeLoadError } from "./EmployeeLoadError";
import { StaffGate } from "./StaffGate";
import { complaintStatusLabel, hasPermission } from "./permissions";

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
      <div className="panel">
        <div className="eyebrow">SERVICE INTELLIGENCE</div>
        <h1>{tText("إحصائيات الشكاوى")}</h1>
        <p className="muted">{tText("أرقام فعلية ضمن نطاق الصلاحية، حسب تاريخ تقديم الشكوى.")}</p>
        <form
          className="form-grid"
          onSubmit={(event) => {
            event.preventDefault();
            const params = new URLSearchParams();
            if (from) params.set("start_date", from);
            if (to) params.set("end_date", to);
            if (directorate) params.set("directorate_id", directorate);
            setQuery(params.toString());
          }}
        >
          <label className="field-label">
            {tText("من تاريخ")}
            <input
              className="field"
              type="date"
              value={from}
              onChange={(e) => setFrom(e.target.value)}
            />
          </label>
          <label className="field-label">
            {tText("إلى تاريخ")}
            <input
              className="field"
              type="date"
              value={to}
              onChange={(e) => setTo(e.target.value)}
            />
          </label>
          {hasPermission(session.data, "reports.view") && (
            <label className="field-label">
              {tText("المديرية")}
              <select
                className="field"
                value={directorate}
                onChange={(event) => setDirectorate(event.target.value)}
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
          <button className="btn">{tText("تطبيق")}</button>
        </form>
        {analytics.isLoading ? (
          <div className="skeleton" />
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
  const metrics: [string, number | string][] = [
    [tText("إجمالي الشكاوى"), data.total],
    [tText("معدل الحل"), `${data.resolution_rate}%`],
    [tText("متوسط التقدم"), `${data.average_progress}%`],
    ...Object.entries(data.counts_by_status).map(([status, count]): [string, string | number] => [
      complaintStatusLabel(status, lang),
      count,
    ]),
  ];

  return (
    <>
      <div className="grid grid-two" style={{ marginTop: 18 }}>
        {metrics.map(([label, value]) => (
          <div className="panel" key={label}>
            <span className="eyebrow">MEASURE</span>
            <h2>{value}</h2>
            <span className="muted">{label}</span>
          </div>
        ))}
      </div>
      <AnalyticsTable
        title="حسب التصنيف"
        headers={["التصنيف", "العدد"]}
        rows={data.counts_by_category.map(({ label, count }) => [label, count])}
        tText={tText}
      />
      <AnalyticsTable
        title="حسب الأولوية"
        headers={["الأولوية", "العدد"]}
        rows={Object.entries(data.counts_by_priority)}
        tText={tText}
      />
      <AnalyticsTable
        title="الاستلام اليومي"
        headers={["التاريخ", "عدد الشكاوى"]}
        rows={data.daily.map(({ date, count }) => [date, count])}
        tText={tText}
      />
      <h2>{tText("تعريفات المؤشرات")}</h2>
      {Object.entries(data.definitions).map(([key, value]) => (
        <p className="muted" key={key}>
          {key}: {value}
        </p>
      ))}
    </>
  );
}

function AnalyticsTable({
  title,
  headers,
  rows,
  tText,
}: {
  title: string;
  headers: [string, string];
  rows: [string, number | string][];
  tText: (text: string) => string;
}) {
  return (
    <>
      <h2>{tText(title)}</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              {headers.map((header) => (
                <th key={header}>{tText(header)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map(([label, count]) => (
              <tr key={label}>
                <td>{label}</td>
                <td>{count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
