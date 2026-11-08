import type { ReactNode } from "react";
import { useI18n } from "../i18n/I18n";

type FormFieldProps = {
  label: string;
  children: ReactNode;
  full?: boolean;
};

export function FormField({ label, children, full = false }: FormFieldProps) {
  const { tText } = useI18n();
  return (
    <label className={`form-field ${full ? "full" : ""}`}>
      <span className="field-label">{tText(label)}</span>
      {children}
    </label>
  );
}
