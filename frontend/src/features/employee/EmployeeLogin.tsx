import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { LockKeyhole, RefreshCw } from "lucide-react";
import { api } from "../../shared/api/client";
import { useI18n } from "../../shared/i18n/I18n";

export function EmployeeLogin() {
  const { tText } = useI18n();
  const nav = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const authConfig = useQuery({
    queryKey: ["auth-config"],
    queryFn: () => api<{ configured: boolean; demo_mode: boolean }>("/auth/config"),
    retry: false,
  });

  return (
    <div className="panel" style={{ maxWidth: 470, margin: "35px auto" }}>
      <div className="empty-icon">
        <LockKeyhole />
      </div>
      <div className="eyebrow">STAFF ACCESS</div>
      <h1>{tText("دخول الموظفين")}</h1>
      <p className="muted">
        {tText("الدخول عبر جلسة آمنة بملفات الارتباط. لا تحفظ كلمة المرور في هذا الجهاز.")}
      </p>
      {authConfig.isLoading && <div className="skeleton" aria-label={tText("جارٍ التحميل")} />}
      {authConfig.error && (
        <div className="status error" role="alert">
          {authConfig.error instanceof Error ? authConfig.error.message : tText("تعذر تحميل البيانات.")}
          <button
            type="button"
            className="btn secondary"
            onClick={() => void authConfig.refetch()}
          >
            <RefreshCw size={15} />
            {tText("إعادة المحاولة")}
          </button>
        </div>
      )}
      {authConfig.data?.demo_mode && (
        <div className="status info">
          {tText("وضع تجريبي مفعّل؛ استخدم بيانات دخول معتمدة من المسؤول.")}
        </div>
      )}
      {authConfig.data?.configured === false && (
        <div className="status error">{tText("لم يتم إعداد الدخول للموظفين.")}</div>
      )}
      <form
        onSubmit={async (event) => {
          event.preventDefault();
          setBusy(true);
          setError("");
          try {
            await api("/auth/login", { method: "POST", body: { username, password } });
            nav("/employee/complaints");
          } catch (cause) {
            setError(cause instanceof Error ? cause.message : tText("تعذر تسجيل الدخول"));
          } finally {
            setBusy(false);
            setPassword("");
          }
        }}
      >
        <label className="field-label">
          {tText("اسم المستخدم")}
          <input
            className="field"
            required
            autoComplete="username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
          />
        </label>
        <label className="field-label">
          {tText("كلمة المرور")}
          <input
            className="field"
            type="password"
            required
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>
        {error && (
          <div role="alert" className="status error">
            {error}
          </div>
        )}
        <button
          className="btn"
          disabled={busy || authConfig.isLoading || authConfig.data?.configured === false}
        >
          {busy ? tText("جارٍ التحقق…") : tText("دخول آمن")}
        </button>
      </form>
    </div>
  );
}
