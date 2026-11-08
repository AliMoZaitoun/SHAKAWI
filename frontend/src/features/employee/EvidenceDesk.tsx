import { useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api } from "../../shared/api/client";
import { StaffGate } from "./StaffGate";
import { useSession } from "../../shared/api/hooks";
import type { Complaint, EvidenceRequest, SessionEmployee } from "../../shared/api/types";

type Props = { complaint: Complaint; session?: SessionEmployee };

function allowed(session: SessionEmployee | undefined, permission: string, directorateId: number) {
  const scope = session?.permissions?.[permission];
  return Boolean(
    scope && (scope.directorate_ids === null || scope.directorate_ids.includes(directorateId)),
  );
}

export function EvidenceDesk({ complaint, session }: Props) {
  const queryClient = useQueryClient();
  const [prompt, setPrompt] = useState("");
  const submissionKey = useRef(crypto.randomUUID());
  const [notice, setNotice] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);
  const canRead = allowed(session, "evidence.read", complaint.directorate_id);
  const canRequest = allowed(session, "evidence.request", complaint.directorate_id);
  const canRetry = allowed(session, "notifications.retry", complaint.directorate_id);
  const requests = useQuery({
    queryKey: ["evidence", complaint.id],
    queryFn: () => api<EvidenceRequest[]>(`/complaints/${complaint.id}/evidence`),
    enabled: canRead,
    retry: false,
  });

  async function createRequest(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setNotice("");
    setBusyId(-1);
    try {
      const result = await api<{
        request: EvidenceRequest;
        notification: { status: string; message: string };
      }>(`/complaints/${complaint.id}/evidence`, {
        method: "POST",
        body: { prompt, submission_key: submissionKey.current },
      });
      setPrompt("");
      submissionKey.current = crypto.randomUUID();
      setNotice(`${result.notification.status}: ${result.notification.message}`);
      await queryClient.invalidateQueries({ queryKey: ["evidence", complaint.id] });
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "تعذر إنشاء الطلب.");
    } finally {
      setBusyId(null);
    }
  }

  async function retry(requestId: number) {
    setBusyId(requestId);
    setNotice("");
    try {
      const result = await api<{ status: string; message: string }>(
        `/complaints/${complaint.id}/evidence/${requestId}/retry`,
        { method: "POST", body: {} },
      );
      setNotice(`${result.status}: ${result.message}`);
      await queryClient.invalidateQueries({ queryKey: ["evidence", complaint.id] });
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "تعذرت إعادة المحاولة.");
    } finally {
      setBusyId(null);
    }
  }

  if (!canRead && !canRequest) {
    return <p className="muted">لا تتوفر صلاحية إدارة الأدلة ضمن نطاق هذه المديرية.</p>;
  }
  return (
    <section aria-labelledby="evidence-title">
      <h2 id="evidence-title">طلبات استكمال الأدلة</h2>
      {canRequest && (
        <form onSubmit={(event) => void createRequest(event)}>
          <label className="field-label">
            المطلوب من المواطن
            <textarea
              className="field"
              required
              minLength={1}
              maxLength={4000}
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
            />
          </label>
          <button className="btn" disabled={busyId !== null}>
            إرسال طلب استكمال
          </button>
        </form>
      )}
      {requests.isLoading && <div className="skeleton" aria-label="تحميل طلبات الأدلة" />}
      {requests.error && (
        <div className="status error" role="alert">
          تعذر تحميل الطلبات.
          <button className="btn secondary" onClick={() => void requests.refetch()}>
            إعادة المحاولة
          </button>
        </div>
      )}
      {requests.data?.length === 0 && <div className="empty">لا توجد طلبات أدلة.</div>}
      {requests.data?.map((request) => (
        <article className="status info" key={request.id}>
          <p>{request.prompt}</p>
          <div className="row">
            <span className="badge">{request.status}</span>
            <span className="badge">{request.notification_status ?? "not_requested"}</span>
          </div>
          {request.notification_error && <p className="muted">{request.notification_error}</p>}
          {request.notification_status !== "sent" && canRetry && request.status === "pending" && (
            <button
              className="btn secondary"
              disabled={busyId === request.id}
              onClick={() => void retry(request.id)}
            >
              إعادة محاولة الإشعار
            </button>
          )}
          {request.replies.map((reply) => (
            <div className="panel" key={reply.id}>
              <p>{reply.text}</p>
              <span className="muted">{new Date(reply.created_at).toLocaleString("ar")}</span>
              <div className="row">
                {reply.attachments.map((file) => (
                  <a
                    className="badge"
                    key={file.id}
                    href={file.file_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {file.name ?? "فتح ملف مرفق"}
                  </a>
                ))}
              </div>
            </div>
          ))}
        </article>
      ))}
      {notice && (
        <div className="status info" role="status">
          {notice}
        </div>
      )}
    </section>
  );
}

export function ComplaintToolsPage() {
  const { id = "" } = useParams();
  const session = useSession();
  const complaint = useQuery({
    queryKey: ["employee-complaint", id],
    queryFn: () => api<Complaint>(`/complaints/${id}`),
    enabled: Boolean(id),
    retry: false,
  });
  return (
    <StaffGate>
      <Link className="btn secondary" to={`/employee/complaints/${id}`}>
        العودة إلى معالجة الشكوى
      </Link>
      {complaint.isLoading && <div className="skeleton" />}
      {complaint.error && (
        <div className="status error" role="alert">
          تعذر تحميل الشكوى.
          <button className="btn secondary" onClick={() => void complaint.refetch()}>
            إعادة المحاولة
          </button>
        </div>
      )}
      {complaint.data && (
        <div className="grid grid-two" style={{ marginTop: 18, alignItems: "start" }}>
          <div className="panel">
            <div className="eyebrow">COMPLAINT TOOLS</div>
            <h1>{complaint.data.title}</h1>
            <EvidenceDesk complaint={complaint.data} session={session.data} />
          </div>
          <PublicReview complaint={complaint.data} session={session.data} />
        </div>
      )}
    </StaffGate>
  );
}

function PublicReview({ complaint, session }: Props) {
  const [reason, setReason] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const scope = session?.permissions?.["public.review"];
  const canReview = Boolean(
    scope &&
    (scope.directorate_ids === null || scope.directorate_ids.includes(complaint.directorate_id)),
  );
  if (!complaint.is_public)
    return (
      <section className="panel">
        <h2>مراجعة النشر العام</h2>
        <p className="muted">هذه الشكوى خاصة؛ لا يمكن مراجعة نص عام.</p>
      </section>
    );

  async function review(action: "hide" | "restore" | "dismiss") {
    if (action === "restore" && !window.confirm("تأكيد إعادة إظهار نص الشكوى للعامة؟")) return;
    setBusy(true);
    setMessage("");
    try {
      const result = await api<{
        message: string;
        notification: { status: string; message: string };
      }>(`/complaints/${complaint.id}/public-review`, { method: "POST", body: { action, reason } });
      setMessage(`${result.message} · إشعار صاحب الشكوى: ${result.notification.status}`);
      setReason("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "تعذرت مراجعة المحتوى.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel">
      <div className="eyebrow">PUBLIC SAFETY REVIEW</div>
      <h2>مراجعة النص العام</h2>
      <p className="muted">
        البلاغات لا تخفي المحتوى تلقائيًا. سجّل سببًا لا يقل عن خمسة أحرف للقرار.
      </p>
      <p className="badge">
        {complaint.public_review.hidden ? "النص مخفي مؤقتًا" : "النص ظاهر للعامة"}
      </p>
      {complaint.public_review.reports?.map((report) => (
        <div className="status info" key={report.id}>
          <b>بلاغ وارد</b> · {report.reason}
          <p className="muted">{new Date(report.created_at).toLocaleString("ar")}</p>
        </div>
      ))}
      <label className="field-label">
        سبب القرار
        <textarea
          className="field"
          required
          minLength={5}
          value={reason}
          onChange={(event) => setReason(event.target.value)}
        />
      </label>
      <div className="row">
        {!complaint.public_review.hidden && (
          <button
            className="btn danger"
            disabled={!canReview || busy}
            onClick={() => void review("hide")}
          >
            إخفاء مؤقت
          </button>
        )}
        {complaint.public_review.hidden && (
          <button
            className="btn"
            disabled={!canReview || busy}
            onClick={() => void review("restore")}
          >
            إعادة النشر
          </button>
        )}
        <button
          className="btn secondary"
          disabled={!canReview || busy}
          onClick={() => void review("dismiss")}
        >
          إغلاق البلاغات
        </button>
      </div>
      {!canReview && <p className="muted">لا تملك صلاحية مراجعة النشر ضمن هذا النطاق.</p>}
      {message && (
        <div className="status info" role="status">
          {message}
        </div>
      )}
    </section>
  );
}
