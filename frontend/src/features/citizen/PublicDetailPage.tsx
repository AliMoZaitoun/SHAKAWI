import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";
import { api } from "../../shared/api/client";
import { useI18n } from "../../shared/i18n/I18n";
import { UiText } from "../../shared/i18n/UiText";
import { CitizenLoadError, PanelLoading, PublicComplaint, statusText } from "./shared";

export function PublicDetailPage() {
  const { id } = useParams();
  const { lang, tText } = useI18n();
  const query = useQuery({
    queryKey: ["public-detail", id, lang],
    queryFn: () => api<PublicComplaint>(`/complaints/public/${id}`, { language: lang }),
    enabled: !!id,
    retry: false,
  });
  const [reason, setReason] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  if (query.isLoading) return <PanelLoading />;
  if (query.error) {
    return (
      <CitizenLoadError
        message={tText("تعذر العثور على الشكوى العامة.")}
        onRetry={() => void query.refetch()}
      />
    );
  }
  const complaint = query.data;
  if (!complaint) return null;

  return (
    <>
      <Link className="btn secondary" to="/public">
        <ArrowRight size={16} /><UiText source="العودة للقائمة" />
      </Link>
      <article className="panel" style={{ marginTop: 16 }}>
        <div className="eyebrow">PUBLIC COMPLAINT · #{complaint.id}</div>
        <div className="row" style={{ justifyContent: "space-between", marginTop: 12 }}>
          <h1>{complaint.title}</h1>
          <span className="badge">{statusText(complaint.status, lang)}</span>
        </div>
        <p className="muted">
          {complaint.public_text_hidden
            ? tText("النص مخفي مؤقتًا للمراجعة.")
            : complaint.details}
        </p>
        <div className="row">
          <span className="badge">{complaint.category}</span>
          <span className="muted">{new Date(complaint.created_at).toLocaleDateString(lang)}</span>
        </div>
        {complaint.resolution_report && <div className="status success">{complaint.resolution_report}</div>}
        {complaint.notes?.map((note, index) => (
          <div key={index} className="status info">{note.note}</div>
        ))}
        <hr style={{ border: 0, borderTop: "1px solid var(--line)", margin: "24px 0" }} />
        <h3><UiText source="الإبلاغ عن محتوى عام" /></h3>
        <p className="muted"><UiText source="البلاغ لا يخفي المحتوى تلقائيًا. يراجعه موظف مخوّل." /></p>
        <form
          onSubmit={async (event) => {
            event.preventDefault();
            setBusy(true);
            try {
              const result = await api<{ message: string }>(`/complaints/public/${complaint.id}/reports`, {
                method: "POST",
                body: { reason },
              });
              setNotice(result.message);
              setReason("");
            } catch (error) {
              setNotice(error instanceof Error ? error.message : tText("تعذر إرسال البلاغ"));
            } finally {
              setBusy(false);
            }
          }}
        >
          <label className="field-label">
            {tText("اشرح سبب البلاغ")}
            <textarea
              className="field"
              required
              minLength={5}
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            />
          </label>
          <button className="btn danger" disabled={busy}><UiText source="إرسال بلاغ" /></button>
        </form>
        {notice && <div role="status" className="status info">{notice}</div>}
      </article>
    </>
  );
}
