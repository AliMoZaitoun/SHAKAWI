import { useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { api, ApiError } from "../../shared/api/client";
import type { Complaint, EvidenceRequest } from "../../shared/api/types";
import { useI18n } from "../../shared/i18n/I18n";
import { UiText } from "../../shared/i18n/UiText";
import { CitizenLoadError, statusText } from "./shared";

export function TrackPage() {
  const { tText } = useI18n();
  const [code, setCode] = useState("");
  const [active, setActive] = useState("");
  const query = useQuery({
    queryKey: ["track", active],
    queryFn: () => api<Complaint>(`/complaints/track/${encodeURIComponent(active)}`),
    enabled: !!active,
    retry: false,
  });

  return (
    <div className="panel" style={{ maxWidth: 840, margin: "auto" }}>
      <span className="eyebrow">PRIVATE TRACKING</span>
      <h1 style={{ color: "var(--brand-dark)" }}>
        <UiText source="متابعة شكوى" />
      </h1>
      <p className="muted">
        {tText("رمز المتابعة السري يمنح وصولًا لهذه الشكوى فقط. لا تحفظه على جهاز مشترك.")}
      </p>
      <form
        className="row"
        onSubmit={(event) => {
          event.preventDefault();
          setActive(code.trim());
        }}
      >
        <input
          aria-label={tText("رمز المتابعة")}
          className="field code"
          dir="ltr"
          required
          value={code}
          onChange={(event) => setCode(event.target.value)}
          placeholder="CMP-…"
        />
        <button className="btn">
          <Search size={16} />
          <UiText source="استعلام" />
        </button>
      </form>
      {query.isLoading && (
        <div className="skeleton" style={{ marginTop: 20 }} aria-label={tText("تحميل")} />
      )}
      {query.error && (
        <CitizenLoadError
          message={
            query.error instanceof ApiError
              ? query.error.message
              : tText("لم يتم العثور على الشكوى.")
          }
          onRetry={() => void query.refetch()}
        />
      )}
      {query.data && <TrackCard complaint={query.data} />}
    </div>
  );
}

function TrackCard({ complaint }: { complaint: Complaint }) {
  const { lang, tText } = useI18n();
  const [reply, setReply] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const submissionKey = useRef(crypto.randomUUID());
  const evidence = useQuery({
    queryKey: ["evidence", complaint.id],
    queryFn: () => api<EvidenceRequest[]>(`/complaints/${complaint.id}/evidence`),
    enabled: false,
    retry: false,
  });

  async function sendReply(event: React.FormEvent<HTMLFormElement>, requestId: number) {
    event.preventDefault();
    if (!reply.trim() && files.length === 0) {
      setNotice(tText("أضف نصًا للرد أو أرفق ملفًا واحدًا على الأقل."));
      return;
    }
    const invalidFile = files.find(
      (file) =>
        file.size > 10 * 1024 * 1024 ||
        !(file.type.startsWith("image/") || file.type === "application/pdf"),
    );
    if (files.length > 5 || invalidFile) {
      setNotice(tText("اختر حتى خمسة ملفات صور أو PDF، بحد أقصى 10 ميبيبايت لكل ملف."));
      return;
    }
    setBusy(true);
    setNotice("");
    try {
      const data = new FormData();
      data.append("text", reply);
      data.append("submission_key", submissionKey.current);
      files.forEach((file) => data.append("files", file));
      await api(`/complaints/${complaint.id}/evidence/${requestId}/reply`, {
        method: "POST",
        body: data,
      });
      setReply("");
      setFiles([]);
      submissionKey.current = crypto.randomUUID();
      setNotice(tText("تم استلام الرد."));
      await evidence.refetch();
    } catch (error) {
      setNotice(
        error instanceof Error
          ? error.message
          : tText("تعذر إرسال الرد. بقي النص والملفات محفوظة لإعادة المحاولة."),
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel" style={{ marginTop: 20 }}>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <span className="badge">{statusText(complaint.status, lang)}</span>
        <span className="code">{complaint.tracking_code}</span>
      </div>
      <h2 style={{ marginTop: 18 }}>{complaint.title}</h2>
      <p className="muted">{complaint.details}</p>
      <div className="row">
        <span className="badge">{complaint.category}</span>
        <span className="muted">{new Date(complaint.created_at).toLocaleDateString(lang)}</span>
      </div>
      <div style={{ marginTop: 20 }}>
        <div className="row" style={{ justifyContent: "space-between" }}>
          <b>{tText("تقدم المعالجة")}</b>
          <b>{complaint.progress}%</b>
        </div>
        <div className="progress">
          <span style={{ width: `${complaint.progress}%` }} />
        </div>
      </div>
      {complaint.resolution_report && (
        <div className="status success">
          <b>{tText("تقرير المعالجة")}</b>
          <br />
          {complaint.resolution_report}
        </div>
      )}
      {complaint.notes?.length > 0 && (
        <div>
          <h3>{tText("التحديثات")}</h3>
          {complaint.notes
            .filter((note) => !note.is_internal)
            .map((note) => (
              <div className="status info" key={note.id}>
                {note.note}
                <small className="muted"> · {new Date(note.created_at).toLocaleString(lang)}</small>
              </div>
            ))}
        </div>
      )}
      <div className="panel" style={{ marginTop: 18, background: "#fafbf8" }}>
        <h3>
          <UiText source="استكمال الأدلة" />
        </h3>
        <p className="muted">
          {tText(
            "يمكنك الرد على طلبات الأدلة وإرفاق صور أو PDF (حتى خمسة ملفات). لا يفتح الرمز ملفات الهوية.",
          )}
        </p>
        <button type="button" className="btn secondary" onClick={() => void evidence.refetch()}>
          <UiText source="تحميل طلبات الأدلة" />
        </button>
        {evidence.isLoading && <div className="skeleton" aria-label={tText("تحميل")} />}
        {evidence.error && (
          <div role="alert" className="status error">
            {tText("تعذر تحميل طلبات الأدلة.")}
          </div>
        )}
        {evidence.data?.length === 0 && (
          <div className="empty">{tText("لا توجد طلبات استكمال حتى الآن.")}</div>
        )}
        {evidence.data?.map((request) => (
          <article className="status info" key={request.id}>
            <p>{request.prompt}</p>
            <span className="badge">{request.status}</span>
            {request.replies.map((item) => (
              <div className="status success" key={item.id}>
                {item.text}
                {item.attachments.map((file) => (
                  <a
                    key={file.id}
                    href={file.file_url}
                    target="_blank"
                    rel="noreferrer"
                    className="badge"
                  >
                    {tText("ملف مرفق")}
                  </a>
                ))}
              </div>
            ))}
            {request.status === "pending" && (
              <form onSubmit={(event) => void sendReply(event, request.id)}>
                <label className="field-label">
                  {tText("الرد")}
                  <textarea
                    className="field"
                    value={reply}
                    onChange={(event) => setReply(event.target.value)}
                  />
                </label>
                <label className="field-label">
                  {tText("إرفاق صور أو PDF")}
                  <input
                    type="file"
                    multiple
                    accept="image/*,.pdf"
                    onChange={(event) => setFiles(Array.from(event.target.files ?? []).slice(0, 5))}
                  />
                </label>
                <p className="muted">
                  {tText("حد أقصى خمسة ملفات؛ النص والملفات يبقيان عند فشل الإرسال.")}
                </p>
                <button className="btn" disabled={busy}>
                  {busy ? <UiText source="جارٍ الإرسال…" /> : <UiText source="إرسال الرد" />}
                </button>
              </form>
            )}
          </article>
        ))}
        {notice && (
          <div role="status" className="status info">
            {notice}
          </div>
        )}
      </div>
    </section>
  );
}
