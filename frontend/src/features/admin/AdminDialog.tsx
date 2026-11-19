import { useEffect, useRef, type ReactNode } from "react";
import { X } from "lucide-react";
import { useI18n } from "../../shared/i18n/I18n";

export function AdminDialog({
  title,
  eyebrow = "SYSTEM ADMINISTRATION",
  children,
  onClose,
  className = "",
}: {
  title: string;
  eyebrow?: string;
  children: ReactNode;
  onClose: () => void;
  className?: string;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const { tText } = useI18n();

  useEffect(() => {
    dialogRef.current?.showModal();
  }, []);

  return (
    <dialog
      ref={dialogRef}
      className={`admin-dialog ${className}`}
      aria-label={tText(title)}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClose={onClose}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="admin-dialog-inner">
        <header className="admin-dialog-header">
          <div>
            <span className="eyebrow">{eyebrow}</span>
            <h2>{tText(title)}</h2>
          </div>
          <button
            type="button"
            className="admin-dialog-close"
            aria-label={tText("إغلاق")}
            onClick={onClose}
          >
            <X size={18} aria-hidden="true" />
          </button>
        </header>
        {children}
      </div>
    </dialog>
  );
}
