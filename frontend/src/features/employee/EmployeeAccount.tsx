import { useState } from "react";
import { api } from "../../shared/api/client";
import { useI18n } from "../../shared/i18n/I18n";
import { StaffGate } from "./StaffGate";

export function EmployeeAccount() {
  const { tText } = useI18n();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  return (
    <StaffGate required={null}>
      <div className="panel" style={{ maxWidth: 600 }}>
        <div className="eyebrow">ACCOUNT SECURITY</div>
        <h1>{tText("تغيير كلمة المرور")}</h1>
        <p className="muted">
          {tText("استخدم كلمة مرور من 12 محرفًا على الأقل. لا تحفظها في المتصفح.")}
        </p>
        <form
          onSubmit={async (event) => {
            event.preventDefault();
            if (next !== confirm) {
              setMessage(tText("كلمتا المرور غير متطابقتين."));
              return;
            }
            setBusy(true);
            try {
              await api("/auth/change-password", {
                method: "POST",
                body: { current_password: current, new_password: next },
              });
              setMessage(tText("تم تغيير كلمة المرور."));
              setCurrent("");
              setNext("");
              setConfirm("");
            } catch (cause) {
              setMessage(cause instanceof Error ? cause.message : tText("تعذر تغيير كلمة المرور"));
            } finally {
              setBusy(false);
            }
          }}
        >
          <label className="field-label">
            {tText("كلمة المرور الحالية")}
            <input
              className="field"
              type="password"
              autoComplete="current-password"
              required
              value={current}
              onChange={(event) => setCurrent(event.target.value)}
            />
          </label>
          <label className="field-label">
            {tText("كلمة المرور الجديدة")}
            <input
              className="field"
              type="password"
              minLength={12}
              autoComplete="new-password"
              required
              value={next}
              onChange={(event) => setNext(event.target.value)}
            />
          </label>
          <label className="field-label">
            {tText("تأكيد الجديدة")}
            <input
              className="field"
              type="password"
              minLength={12}
              autoComplete="new-password"
              required
              value={confirm}
              onChange={(event) => setConfirm(event.target.value)}
            />
          </label>
          <button className="btn" disabled={busy}>
            {tText("تحديث كلمة المرور")}
          </button>
        </form>
        {message && (
          <div role="status" className="status info">
            {message}
          </div>
        )}
      </div>
    </StaffGate>
  );
}
