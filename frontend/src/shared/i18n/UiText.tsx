import { useI18n } from "./I18n";

type UiTextProps = { source: string };

/** Translate known interface copy only. Never pass API or citizen-provided text here. */
export function UiText({ source }: UiTextProps) {
  const { tText } = useI18n();
  return <>{tText(source)}</>;
}
