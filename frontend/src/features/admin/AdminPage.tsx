import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { StaffGate } from "../employee/StaffGate";
import { useI18n } from "../../shared/i18n/I18n";

export function AdminPage({
  title,
  subtitle,
  children,
  required = "rbac.manage",
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
  required?: string;
}) {
  const { tText } = useI18n();
  return (
    <StaffGate required={required} globalOnly>
      <div className="panel">
        <span className="eyebrow">SYSTEM ADMINISTRATION</span>
        <h1>{tText(title)}</h1>
        <p className="muted">{tText(subtitle)}</p>
        {children}
      </div>
    </StaffGate>
  );
}

export function AdminAlert({ text }: { text: string }) {
  return text ? (
    <div className="status info" role="status">
      {text}
    </div>
  ) : null;
}

export function useAdminSave() {
  const cache = useQueryClient();
  const { tText } = useI18n();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setMessage("");
    try {
      await action();
      await cache.invalidateQueries();
      setMessage(tText("تم حفظ التغيير."));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : tText("تعذر حفظ التغيير"));
    } finally {
      setBusy(false);
    }
  }

  return { busy, message, run, setMessage };
}
