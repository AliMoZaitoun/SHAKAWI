export function formatDuration(minutes: number, language: string): string {
  const units: { value: number; unit: Intl.NumberFormatOptions["unit"] }[] = [
    { value: 10080, unit: "week" },
    { value: 1440, unit: "day" },
    { value: 60, unit: "hour" },
  ];
  const match = units.find(({ value }) => minutes >= value && minutes % value === 0);
  const unit = match?.unit ?? "minute";
  const value = match ? minutes / match.value : minutes;
  return new Intl.NumberFormat(language, { style: "unit", unit, unitDisplay: "long" }).format(
    value,
  );
}
