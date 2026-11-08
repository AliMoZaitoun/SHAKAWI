import { useI18n } from "../../shared/i18n/I18n";
import type { Page } from "../../shared/api/types";

export type PublicComplaint = {
  id: number;
  public_text_hidden: boolean;
  title: string;
  details: string;
  category: string;
  directorate_id: number;
  status: string;
  priority: string;
  progress: number;
  created_at: string;
  resolution_report: string;
  notes: { note: string; created_at: string }[];
};

export type PublicPageData = Page<PublicComplaint> & { page_size: number; pages: number };

export function statusText(status: string, lang: string): string {
  const labels =
    lang === "ar"
      ? { PENDING: "جديدة", IN_PROGRESS: "قيد المعالجة", RESOLVED: "تمت المعالجة", REJECTED: "مرفوضة" }
      : { PENDING: "New", IN_PROGRESS: "In progress", RESOLVED: "Resolved", REJECTED: "Rejected" };
  return labels[status as keyof typeof labels] ?? status;
}

export function CitizenLoadError({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  const { tText } = useI18n();
  return (
    <div role="alert" className="status error">
      {message}{" "}
      <button className="btn secondary" onClick={onRetry} type="button">
        {tText("إعادة المحاولة")}
      </button>
    </div>
  );
}

export function PanelLoading() {
  return (
    <div className="grid">
      <div className="skeleton" />
      <div className="skeleton" />
    </div>
  );
}

