import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "../../shared/api/client";
import type { Complaint, SessionEmployee } from "../../shared/api/types";

export function NotesPanel({
  complaint,
  session,
}: {
  complaint: Complaint;
  session?: SessionEmployee;
}) {
  const [busyNote, setBusyNote] = useState<number | null>(null);
  const [message, setMessage] = useState("");
  const queryClient = useQueryClient();
  const retryScope = session?.permissions?.["notifications.retry"];
  const canRetry = Boolean(
    retryScope &&
    (retryScope.directorate_ids === null ||
      retryScope.directorate_ids.includes(complaint.directorate_id)),
  );

  async function retry(noteId: number) {
    setBusyNote(noteId);
    setMessage("");
    try {
      const result = await api<{ notification_status: string; notification_error?: string | null }>(
        `/complaints/${complaint.id}/notes/${noteId}/retry`,
        { method: "POST", body: {} },
      );
      setMessage(`Notification: ${result.notification_status}`);
      await queryClient.invalidateQueries({
        queryKey: ["employee-complaint", String(complaint.id)],
      });
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Notification retry failed.");
    } finally {
      setBusyNote(null);
    }
  }

  return (
    <section aria-labelledby="staff-notes-title">
      <h3 id="staff-notes-title">ملاحظات وإشعارات المواطن</h3>
      {complaint.notes.length === 0 && <div className="empty">لا توجد ملاحظات مسجلة.</div>}
      {complaint.notes.map((note) => (
        <article className="status info" key={note.id}>
          <p>{note.note}</p>
          <div className="row">
            <span className="badge">{note.audience}</span>
            {note.author_name && <span className="muted">{note.author_name}</span>}
            {note.notification_status && <span className="badge">{note.notification_status}</span>}
          </div>
          {note.notification_error && <p className="muted">{note.notification_error}</p>}
          {canRetry && note.notification_status && note.notification_status !== "sent" && (
            <button
              type="button"
              className="btn secondary"
              disabled={busyNote !== null}
              onClick={() => void retry(note.id)}
            >
              {busyNote === note.id ? "جارٍ الإرسال…" : "إعادة محاولة الإشعار"}
            </button>
          )}
        </article>
      ))}
      {message && (
        <div className="status info" role="status">
          {message}
        </div>
      )}
    </section>
  );
}
