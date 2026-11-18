import { useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { StaffGate } from "../employee/StaffGate";
import { useI18n } from "../../shared/i18n/I18n";

export function AdminPage({
  title,
  subtitle,
  children,
  required = "rbac.manage",
  globalOnly = true,
  headerAction,
  className,
}: {
  title: string;
  subtitle: string;
  children: ReactNode;
  required?: string;
  globalOnly?: boolean;
  headerAction?: ReactNode;
  className?: string;
}) {
  const { tText } = useI18n();
  return (
    <StaffGate required={required} globalOnly={globalOnly}>
      <div className={["panel", className].filter(Boolean).join(" ")}>
        {headerAction ? (
          <div className="admin-page-heading">
            <div>
              <span className="eyebrow">SYSTEM ADMINISTRATION</span>
              <h1>{tText(title)}</h1>
              <p className="muted">{tText(subtitle)}</p>
            </div>
            {headerAction}
          </div>
        ) : (
          <>
            <span className="eyebrow">SYSTEM ADMINISTRATION</span>
            <h1>{tText(title)}</h1>
            <p className="muted">{tText(subtitle)}</p>
          </>
        )}
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
  const [message, setMessageState] = useState("");
  const [isError, setIsError] = useState(false);

  function setMessage(value: string) {
    setMessageState(value);
    setIsError(false);
  }

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setMessageState("");
    setIsError(false);
    try {
      await action();
      await cache.invalidateQueries();
      setMessageState(tText("تم حفظ التغيير."));
    } catch (error) {
      setMessageState(error instanceof Error ? error.message : tText("تعذر حفظ التغيير"));
      setIsError(true);
    } finally {
      setBusy(false);
    }
  }

  return { busy, message, isError, run, setMessage };
}
