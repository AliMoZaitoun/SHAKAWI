import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../shared/api/client";
import type { AuditEvent, Page } from "../../shared/api/types";
import { useI18n } from "../../shared/i18n/I18n";
import { UiText } from "../../shared/i18n/UiText";
import { AdminPage } from "./AdminPage";

export function AuditAdmin() {
  const { lang, tText } = useI18n();
  const [page, setPage] = useState(1);
  const [action, setAction] = useState("");
  const [entity, setEntity] = useState("");
  const params = new URLSearchParams({ page: String(page), page_size: "25" });
  if (action) params.set("action", action);
  if (entity) params.set("entity_type", entity);
  const audit = useQuery({
    queryKey: ["audit", params.toString(), lang],
    queryFn: () => api<Page<AuditEvent>>(`/admin/audit-events?${params}`, { language: lang }),
    retry: false,
  });

  return (
    <AdminPage
      title="سجل التدقيق"
      required="audit.view"
      subtitle="سجل قراءة فقط للأحداث الإدارية. القيم الحساسة لا تُعرض ولا يوجد تعديل أو حذف."
    >
      <div className="form-grid">
        <label className="field-label">
          {tText("العملية")}
          <input
            className="field"
            value={action}
            onChange={(event) => {
              setPage(1);
              setAction(event.target.value);
            }}
          />
        </label>
        <label className="field-label">
          {tText("نوع الكيان")}
          <input
            className="field"
            value={entity}
            onChange={(event) => {
              setPage(1);
              setEntity(event.target.value);
            }}
          />
        </label>
      </div>
      {audit.isLoading ? (
        <div className="skeleton" />
      ) : audit.error ? (
        <div className="status error" role="alert">
          {tText("تعذر تحميل سجل التدقيق.")}
          <button className="btn secondary" onClick={() => void audit.refetch()}>
            <UiText source="إعادة المحاولة" />
          </button>
        </div>
      ) : !audit.data?.items.length ? (
        <div className="empty">
          <UiText source="لا توجد أحداث مطابقة." />
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                {["الوقت", "الفاعل", "العملية", "الكيان", "المعرّف", "المصدر", "معرّف الطلب"].map(
                  (label) => (
                    <th key={label}>
                      <UiText source={label} />
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody>
              {audit.data.items.map((event) => (
                <tr key={event.id}>
                  <td>{new Date(event.created_at).toLocaleString(lang)}</td>
                  <td>{event.actor_user_id ?? tText("نظام")}</td>
                  <td>{event.action}</td>
                  <td>{event.entity_type}</td>
                  <td>{event.entity_id}</td>
                  <td>{event.source}</td>
                  <td className="code">{event.request_id}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="row">
        <button className="btn secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}>
          <UiText source="السابق" />
        </button>
        <span className="muted">
          {tText("صفحة")} {audit.data?.page} · {audit.data?.total} {tText("حدث")}
        </span>
        <button
          className="btn secondary"
          disabled={page * 25 >= (audit.data?.total ?? 0)}
          onClick={() => setPage(page + 1)}
        >
          <UiText source="التالي" />
        </button>
      </div>
    </AdminPage>
  );
}
