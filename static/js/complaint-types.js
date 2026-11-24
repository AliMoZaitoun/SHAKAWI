import { api } from "./api.js";

export let complaintTypes = [];

const byId = (id) => document.getElementById(id);
const durationUnits = [
  { factor: 10080, unit: "week" },
  { factor: 1440, unit: "day" },
  { factor: 60, unit: "hour" },
];

export function formatComplaintDuration(minutes) {
  const match = durationUnits.find(({ factor }) => minutes >= factor && minutes % factor === 0);
  const unit = match?.unit || "minute";
  const value = match ? minutes / match.factor : minutes;
  return new Intl.NumberFormat("ar", { style: "unit", unit, unitDisplay: "long" }).format(value);
}

function renderSelectedType() {
  const root = byId("comp-type-meta");
  if (!root) return;
  root.replaceChildren();
  const type = complaintTypes.find((item) => String(item.id) === byId("comp-type").value);
  if (!type) return;
  if (type.description) {
    const description = document.createElement("p");
    description.textContent = type.description;
    root.append(description);
  }
  const estimate = document.createElement("p");
  estimate.className = "mt-1 font-semibold";
  estimate.textContent = type.code === "other"
    ? "لا توجد مهلة تقديرية لهذا النوع."
    : type.sla_duration_minutes
      ? `المدة التقديرية: ${formatComplaintDuration(type.sla_duration_minutes)} (متواصلة من وقت التقديم)`
      : "المدة التقديرية لم تُحدد لهذا النوع بعد.";
  root.append(estimate);
}

export async function initComplaintTypes() {
  const result = await api("/complaint-types?lang=ar");
  if (!Array.isArray(result)) throw new Error("ردّ أنواع الشكاوى غير صالح");
  complaintTypes = result;

  const submission = byId("comp-type");
  const selected = submission.value;
  submission.replaceChildren(new Option("اختر نوع الشكوى", ""));
  complaintTypes.forEach((type) => submission.add(new Option(type.name, String(type.id))));
  if (complaintTypes.some((type) => String(type.id) === selected)) submission.value = selected;
  submission.addEventListener("change", renderSelectedType);
  renderSelectedType();

  const publicFilter = byId("public-category");
  if (publicFilter) {
    const previous = publicFilter.value;
    publicFilter.replaceChildren(new Option("كل التصنيفات", ""));
    complaintTypes.forEach((type) => publicFilter.add(new Option(type.name, type.name)));
    if ([...publicFilter.options].some((option) => option.value === previous)) {
      publicFilter.value = previous;
    }
  }
  return complaintTypes;
}

export function findComplaintType(id) {
  return complaintTypes.find((type) => String(type.id) === String(id));
}
