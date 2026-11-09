import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../shared/api/client";
import { useDirectorates } from "../../shared/api/hooks";
import { useI18n } from "../../shared/i18n/I18n";
import { FormField as Field } from "../../shared/ui/FormField";
import { UiText } from "../../shared/i18n/UiText";
import { CitizenLoadError, PublicPageData, statusText } from "./shared";

export function PublicPage() {
  const { lang, tText } = useI18n();
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("");
  const [category, setCategory] = useState("");
  const [directorate, setDirectorate] = useState("");
  const directorates = useDirectorates(lang);
  const params = new URLSearchParams({ page: String(page), page_size: "12" });
  if (status) params.set("status", status);
  if (category) params.set("category", category);
  if (directorate) params.set("directorate_id", directorate);
  const query = useQuery({
    queryKey: ["public", params.toString(), lang],
    queryFn: () => api<PublicPageData>(`/complaints/public?${params}`, { language: lang }),
    retry: false,
  });

  return (
    <>
      <header style={{ marginBottom: 20 }}>
        <span className="eyebrow">OPEN RECORDS · PUBLIC VIEW</span>
        <h1 style={{ color: "var(--brand-dark)" }}>
          <UiText source="الشكاوى المنشورة" />
        </h1>
        <p className="muted">
          {tText(
            "يظهر فقط المحتوى العام المعتمد. لا تُعرض بيانات المواطنين أو رموز التتبع أو الملفات.",
          )}
        </p>
      </header>
      <div className="panel">
        <div className="form-grid">
          <Field label="الحالة">
            <select
              className="field"
              value={status}
              onChange={(event) => {
                setPage(1);
                setStatus(event.target.value);
              }}
            >
              <option value="">
                <UiText source="جميع الحالات" />
              </option>
              {["PENDING", "IN_PROGRESS", "RESOLVED", "REJECTED"].map((item) => (
                <option key={item} value={item}>
                  {statusText(item, lang)}
                </option>
              ))}
            </select>
          </Field>
          <Field label="التصنيف">
            <input
              className="field"
              value={category}
              onChange={(event) => {
                setPage(1);
                setCategory(event.target.value);
              }}
              placeholder={tText("اكتب التصنيف")}
            />
          </Field>
          <Field label="الجهة">
            <select
              className="field"
              value={directorate}
              onChange={(event) => {
                setPage(1);
                setDirectorate(event.target.value);
              }}
            >
              <option value="">
                <UiText source="كل الجهات" />
              </option>
              {directorates.data?.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.hierarchy_path ?? item.name}
                </option>
              ))}
            </select>
          </Field>
        </div>
        {query.isLoading ? (
          <div className="grid" style={{ marginTop: 18 }}>
            <div className="skeleton" />
            <div className="skeleton" />
          </div>
        ) : query.error ? (
          <CitizenLoadError
            message={tText("تعذر تحميل الشكاوى المنشورة.")}
            onRetry={() => void query.refetch()}
          />
        ) : query.data?.items.length ? (
          <>
            <div className="grid grid-two" style={{ marginTop: 18 }}>
              {query.data.items.map((item) => (
                <Link to={`/public/${item.id}`} className="panel" key={item.id}>
                  <div className="row" style={{ justifyContent: "space-between" }}>
                    <span className="badge">{statusText(item.status, lang)}</span>
                    <span className="muted">
                      {new Date(item.created_at).toLocaleDateString(lang)}
                    </span>
                  </div>
                  <h2 style={{ marginTop: 12 }}>{item.title}</h2>
                  <p className="muted">{item.details}</p>
                  <div className="row">
                    <span className="badge">{item.category}</span>
                    <span className="muted">
                      {tText("معرّف عام")} {item.id}
                    </span>
                  </div>
                </Link>
              ))}
            </div>
            <div className="row" style={{ justifyContent: "space-between", marginTop: 20 }}>
              <button
                className="btn secondary"
                disabled={page <= 1}
                onClick={() => setPage(page - 1)}
              >
                <UiText source="السابق" />
              </button>
              <span className="muted">
                {tText("صفحة")} {query.data.page} {tText("من")} {query.data.pages}
              </span>
              <button
                className="btn secondary"
                disabled={page >= query.data.pages}
                onClick={() => setPage(page + 1)}
              >
                <UiText source="التالي" />
              </button>
            </div>
          </>
        ) : (
          <div className="empty">
            <UiText source="لا توجد شكاوى منشورة ضمن هذه المعايير." />
          </div>
        )}
      </div>
    </>
  );
}
