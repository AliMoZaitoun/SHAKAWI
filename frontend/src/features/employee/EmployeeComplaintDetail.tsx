import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { api } from "../../shared/api/client";
import { useResource, useSession } from "../../shared/api/hooks";
import type { Complaint, Directorate, HistoryEvent, Page, SessionEmployee } from "../../shared/api/types";
import { useI18n } from "../../shared/i18n/I18n";
import { UiText } from "../../shared/i18n/UiText";
import { NotesPanel } from "./NotesPanel";
import { EmployeeLoadError } from "./EmployeeLoadError";
import { StaffGate } from "./StaffGate";
import { complaintStatusLabel, hasPermission } from "./permissions";

export function EmployeeComplaintDetail() {
  const { id } = useParams();
  const session = useSession();
  return (
    <StaffGate>
      <ComplaintDetail id={id ?? ""} session={session.data} />
    </StaffGate>
  );
}

function ComplaintDetail({ id, session }: { id: string; session?: SessionEmployee }) {
  const { lang, tText } = useI18n();
  const cache = useQueryClient();
  const complaintQuery = useQuery({
    queryKey: ["employee-complaint", id],
    queryFn: () => api<Complaint>(`/complaints/${id}`),
    enabled: !!id,
    retry: false,
  });
  const history = useQuery({
    queryKey: ["complaint-history", id],
    queryFn: () => api<HistoryEvent[] | Page<HistoryEvent>>(`/complaints/${id}/history`),
    enabled: !!complaintQuery.data,
    retry: false,
  });
  const [form, setForm] = useState({ status: "", progress: "", resolution_report: "", reason: "" });
  const [note, setNote] = useState("");
  const [audience, setAudience] = useState<"internal" | "private" | "public">("internal");
  const [transferId, setTransferId] = useState("");
  const [transferReason, setTransferReason] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const directorates = useResource<Directorate[]>("/directorates", lang);

  if (complaintQuery.isLoading) return <div className="skeleton" />;
  if (complaintQuery.error) {
    return (
      <EmployeeLoadError
        error={complaintQuery.error}
        retry={() => void complaintQuery.refetch()}
      />
    );
  }
  const complaint = complaintQuery.data;
  if (!complaint) return null;

  async function mutate(action: () => Promise<unknown>) {
    setBusy(true);
    setMessage("");
    try {
      await action();
      await cache.invalidateQueries({ queryKey: ["employee-complaint", id] });
      setMessage(tText("تم حفظ التغيير."));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : tText("تعذر حفظ التغيير"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Link className="btn secondary" to="/employee/complaints">
        <ArrowLeft size={15} />
        <UiText source="سجل الشكاوى" />
      </Link>
      {(hasPermission(session, "evidence.read", complaint.directorate_id) ||
        hasPermission(session, "evidence.request", complaint.directorate_id) ||
        hasPermission(session, "public.review", complaint.directorate_id)) && (
        <Link className="btn secondary" to={`/employee/complaints/${id}/tools`}>
          <UiText source="الأدلة ومراجعة النشر" />
        </Link>
      )}
      <div className="grid grid-two" style={{ marginTop: 16, alignItems: "start" }}>
        <section className="panel">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <span className="badge">{complaintStatusLabel(complaint.status, lang)}</span>
            <span className="code">{complaint.tracking_code}</span>
          </div>
          <h1>{complaint.title}</h1>
          <p className="muted">{complaint.details}</p>
          <div className="row">
            <span className="badge">{complaint.category}</span>
            <span className="badge">{complaint.priority}</span>
            <span className="badge">
              <UiText source={complaint.is_public ? "عامة" : "خاصة"} />
            </span>
          </div>
          <h3 style={{ marginTop: 24 }}><UiText source="معالجة الشكوى" /></h3>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void mutate(() =>
                api(`/complaints/${id}/status?new_status=${form.status || complaint.status}`, {
                  method: "PATCH",
                  body: {
                    progress: Number(form.progress || complaint.progress),
                    resolution_report: form.resolution_report || complaint.resolution_report,
                    reason: form.reason,
                  },
                }),
              );
            }}
          >
            <label className="field-label">
              <UiText source="الحالة" />
              <select
                className="field"
                value={form.status || complaint.status}
                onChange={(event) => setForm({ ...form, status: event.target.value })}
              >
                {["PENDING", "IN_PROGRESS", "RESOLVED", "REJECTED"].map((status) => (
                  <option key={status} value={status}>{complaintStatusLabel(status, lang)}</option>
                ))}
              </select>
            </label>
            <label className="field-label">
              <UiText source="نسبة التقدم" />
              <input
                type="number"
                min="0"
                max="100"
                className="field"
                value={form.progress || complaint.progress}
                onChange={(event) => setForm({ ...form, progress: event.target.value })}
              />
            </label>
            <label className="field-label">
              <UiText source="تقرير الحل" />
              <textarea
                className="field"
                value={form.resolution_report || complaint.resolution_report}
                onChange={(event) => setForm({ ...form, resolution_report: event.target.value })}
              />
            </label>
            <label className="field-label">
              <UiText source="سبب التحديث (اختياري)" />
              <input
                className="field"
                value={form.reason}
                onChange={(event) => setForm({ ...form, reason: event.target.value })}
              />
            </label>
            <button
              className="btn"
              disabled={busy || !hasPermission(session, "complaints.update", complaint.directorate_id)}
            >
              <UiText source="حفظ المعالجة" />
            </button>
          </form>
          <hr />
          <h3><UiText source="إضافة ملاحظة" /></h3>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void mutate(() =>
                api(`/complaints/${id}/notes`, { method: "POST", body: { note, audience } }).then(
                  () => setNote(""),
                ),
              );
            }}
          >
            <label className="field-label">
              <UiText source="ملاحظة" />
              <textarea
                required
                minLength={2}
                className="field"
                value={note}
                onChange={(event) => setNote(event.target.value)}
              />
            </label>
            <label className="field-label">
              <UiText source="الجمهور" />
              <select
                className="field"
                value={audience}
                onChange={(event) => setAudience(event.target.value as typeof audience)}
              >
                <option value="internal"><UiText source="داخلية للفريق" /></option>
                <option value="private"><UiText source="للمواطن بشكل خاص" /></option>
                <option value="public"><UiText source="تحديث عام" /></option>
              </select>
            </label>
            <button
              className="btn secondary"
              disabled={busy || !hasPermission(session, "complaints.notes.create", complaint.directorate_id)}
            >
              <UiText source="إضافة ملاحظة" />
            </button>
          </form>
          <NotesPanel complaint={complaint} session={session} />
          <h3><UiText source="سجل الأحداث" /></h3>
          {history.isLoading ? (
            <div className="skeleton" />
          ) : history.error ? (
            <EmployeeLoadError error={history.error} retry={() => void history.refetch()} />
          ) : null}
          {(Array.isArray(history.data) ? history.data : (history.data?.items ?? [])).map((event) => (
            <div className="status info" key={event.id}>
              {event.event} · {new Date(event.created_at).toLocaleString(lang)}
            </div>
          ))}
        </section>
        <section className="panel">
          <h2><UiText source="نقل الشكوى" /></h2>
          <p className="muted">{tText("يتطلب صلاحية النقل في نطاق المديريتين.")}</p>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void mutate(() =>
                api(`/complaints/${id}/transfer`, {
                  method: "POST",
                  body: { directorate_id: Number(transferId), reason: transferReason },
                }),
              );
            }}
          >
            <label className="field-label">
              <UiText source="المديرية الهدف" />
              <select
                className="field"
                required
                value={transferId}
                onChange={(event) => setTransferId(event.target.value)}
              >
                <option value=""><UiText source="اختر جهة" /></option>
                {directorates.data?.map((directorate) => (
                  <option key={directorate.id} value={directorate.id}>{directorate.name}</option>
                ))}
              </select>
            </label>
            <label className="field-label">
              <UiText source="سبب النقل" />
              <textarea
                required
                minLength={5}
                className="field"
                value={transferReason}
                onChange={(event) => setTransferReason(event.target.value)}
              />
            </label>
            <button
              className="btn"
              disabled={
                busy ||
                !hasPermission(session, "complaints.transfer", complaint.directorate_id) ||
                !hasPermission(session, "complaints.transfer", Number(transferId) || undefined)
              }
            >
              <UiText source="نقل" />
            </button>
          </form>
          <h2 style={{ marginTop: 24 }}><UiText source="الملفات المرفقة" /></h2>
          {complaint.attachments?.map((file) => (
            <a className="badge" key={file.id} href={file.file_url} target="_blank" rel="noreferrer">
              {file.name || tText("فتح ملف")}
            </a>
          ))}
          <h2 style={{ marginTop: 24 }}><UiText source="الأدلة" /></h2>
          <p className="muted">
            {tText("يمكن إدارة طلبات الأدلة من متابعة المواطن. عناصر الملفات لا تُعرض هنا دون الصلاحيات اللازمة.")}
          </p>
          {message && <div className="status info" role="status">{message}</div>}
        </section>
      </div>
    </>
  );
}
