import type { SessionEmployee } from "../../shared/api/types";

export function hasPermission(
  session: SessionEmployee | undefined,
  code: string,
  directorateId?: number,
): boolean {
  const scope = session?.permissions?.[code];
  if (!scope) return false;
  if (scope.directorate_ids === null) return true;
  if (directorateId === undefined) return scope.directorate_ids.length > 0;
  return scope.directorate_ids.includes(directorateId);
}

export function hasGlobalPermission(session: SessionEmployee | undefined, code: string): boolean {
  return session?.permissions?.[code]?.directorate_ids === null;
}

export function complaintStatusLabel(status: string, language = "ar"): string {
  const labels =
    language === "en"
      ? {
          PENDING: "New",
          IN_PROGRESS: "In progress",
          RESOLVED: "Resolved",
          REJECTED: "Rejected",
        }
      : {
          PENDING: "جديدة",
          IN_PROGRESS: "قيد المعالجة",
          RESOLVED: "تمت المعالجة",
          REJECTED: "مرفوضة",
        };
  return labels[status as keyof typeof labels] ?? status;
}
