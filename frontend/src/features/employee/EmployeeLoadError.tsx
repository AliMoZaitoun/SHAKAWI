import { RefreshCw } from "lucide-react";
import { ApiError } from "../../shared/api/client";
import { useI18n } from "../../shared/i18n/I18n";

export function EmployeeLoadError({
  error,
  retry,
}: {
  error: unknown;
  retry: () => void;
}) {
  const { tText } = useI18n();
  return (
    <div className="status error" role="alert">
      {error instanceof ApiError ? error.message : tText("تعذر تحميل البيانات.")}
      <button type="button" className="btn secondary" onClick={retry}>
        <RefreshCw size={15} />
        {tText("إعادة المحاولة")}
      </button>
    </div>
  );
}
