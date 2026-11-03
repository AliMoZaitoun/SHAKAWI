import { api } from "./api.js";
import { getUser, logoutUser } from "./auth.js";

const byId = (id) => document.getElementById(id);
const statusNames = { PENDING: "جديدة", IN_PROGRESS: "جاري العمل", RESOLVED: "تمت المعالجة", REJECTED: "مرفوضة" };
const priorityNames = { LOW: "منخفضة", MEDIUM: "عادية", HIGH: "عالية", URGENT: "مستعجلة" };
let loading = false;
let requestEpoch = 0;

function formatDateInput(date) {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 10);
}
function setState(message, error = false) {
  const state = byId("stats-state");
  state.textContent = message;
  if (!error && message.includes("جارٍ")) {
    for (let index = 0; index < 3; index += 1) {
      const skeleton = document.createElement("div");
      skeleton.className = "skeleton-line";
      skeleton.setAttribute("aria-hidden", "true");
      state.append(skeleton);
    }
  }
  state.classList.remove("hidden");
  state.dataset.error = String(error);
  byId("stats-results").classList.add("hidden");
}
function table(headers, rows, emptyMessage) {
  const wrapper = document.createElement("div");
  wrapper.className = "overflow-x-auto border border-gray-100 rounded-lg";
  const element = document.createElement("table");
  element.className = "stats-table";
  const head = document.createElement("thead");
  const headRow = document.createElement("tr");
  headers.forEach((label) => { const th = document.createElement("th"); th.scope = "col"; th.textContent = label; headRow.append(th); });
  head.append(headRow);
  const body = document.createElement("tbody");
  if (rows.length) {
    rows.forEach((values) => {
      const row = document.createElement("tr");
      values.forEach((value) => { const cell = document.createElement("td"); cell.textContent = String(value ?? "—"); row.append(cell); });
      body.append(row);
    });
  } else {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = headers.length;
    cell.className = "text-center text-gray-500";
    cell.textContent = emptyMessage;
    row.append(cell); body.append(row);
  }
  element.append(head, body); wrapper.append(element);
  return wrapper;
}
function render(data) {
  const counts = data.counts_by_status || {};
  const summaries = [
    ["إجمالي الشكاوى", Number(data.total) || 0],
    ["نسبة الشكاوى المحلولة", `${Number(data.resolution_rate) || 0}%`],
    ["متوسط الإنجاز المقدر", `${Number(data.average_progress) || 0}%`]
  ];
  const summaryRoot = byId("stats-summary");
  summaryRoot.replaceChildren();
  summaries.forEach(([label, value]) => {
    const card = document.createElement("div"); card.className = "stats-summary";
    const title = document.createElement("p"); title.className = "text-xs text-gray-600"; title.textContent = label;
    const number = document.createElement("p"); number.className = "text-2xl font-bold text-brand-dark mt-1"; number.textContent = String(value);
    card.append(title, number); summaryRoot.append(card);
  });
  byId("stats-status").replaceChildren(table(["الحالة", "العدد"], Object.entries(statusNames).map(([key, label]) => [label, Number(counts[key]) || 0]), "لا توجد بيانات للحالات."));
  byId("stats-category").replaceChildren(table(["التصنيف", "العدد"], (data.counts_by_category || []).map((item) => [item.label || "غير محدد", Number(item.count) || 0]), "لا توجد بيانات للتصنيفات."));
  byId("stats-priority").replaceChildren(table(["الأولوية", "العدد"], Object.entries(priorityNames).map(([key, label]) => [label, Number((data.counts_by_priority || {})[key]) || 0]), "لا توجد بيانات للأولويات."));
  byId("stats-daily").replaceChildren(table(["التاريخ", "عدد الشكاوى"], (data.daily || []).map((item) => [item.date || "—", Number(item.count) || 0]), "لا توجد بيانات يومية للفترة المحددة."));
  const role = data.scope?.role === "governor" ? "المحافظة" : "مديرية الخدمات الفنية";
  byId("stats-scope").textContent = `نطاق البيانات: ${role}${data.filters?.directorate_id ? ` · الجهة رقم ${data.filters.directorate_id}` : ""} · من ${data.filters?.start_date || "—"} إلى ${data.filters?.end_date || "—"}.`;
  const definitions = data.definitions || {};
  byId("stats-definitions").textContent = [
    definitions.resolution_rate || "نسبة المعالجة = عدد الشكاوى المعالجة ÷ إجمالي الشكاوى × 100.",
    definitions.average_progress || "متوسط الإنجاز تقدير الموظفين لنسبة تقدم معالجة الشكاوى، وليس قياساً آلياً مستقلاً.",
    definitions.dates || "الفترة محددة بالتاريخين المدخلين."
  ].join(" ");
  byId("stats-state").classList.add("hidden");
  byId("stats-results").classList.remove("hidden");
}
export function initStatistics() {
  const now = new Date();
  const start = new Date(now); start.setDate(start.getDate() - 29);
  byId("stats-start").value = formatDateInput(start);
  byId("stats-end").value = formatDateInput(now);
}
export function clearStatistics() {
  requestEpoch += 1;
  loading = false;
  byId("stats-directorate").value = "";
  byId("stats-directorate").disabled = false;
  byId("stats-load").disabled = false;
  byId("stats-results").classList.add("hidden");
  byId("stats-summary").replaceChildren();
  ["stats-status", "stats-category", "stats-priority", "stats-daily"].forEach((id) => byId(id).replaceChildren());
  setState("تسجيل الدخول مطلوب لعرض الإحصائيات.");
}
export async function loadStatistics() {
  if (loading) return;
  const user = getUser();
  if (!user) return;
  const start = byId("stats-start").value;
  const end = byId("stats-end").value;
  if (!start || !end || start > end) return setState("أدخل تاريخ بداية ونهاية صحيحين.", true);
  const directorateFilter = byId("stats-directorate");
  if (user.role === "employee") {
    directorateFilter.value = String(user.directorate_id ?? "");
    directorateFilter.disabled = true;
  } else {
    directorateFilter.disabled = false;
  }
  const params = new URLSearchParams({ start_date: start, end_date: end });
  if (directorateFilter.value) params.set("directorate_id", directorateFilter.value);
  const button = byId("stats-load");
  const epoch = ++requestEpoch;
  loading = true; button.disabled = true;
  setState("جارٍ تحميل الإحصائيات…");
  try {
    const data = await api(`/analytics?${params.toString()}`);
    if (epoch !== requestEpoch || !getUser()) return;
    render(data);
  } catch (error) {
    if (epoch !== requestEpoch || !getUser()) return;
    if (error.status === 401) {
      await logoutUser();
      return;
    }
    setState(`تعذر تحميل الإحصائيات: ${error.message}`, true);
    const retry = document.createElement("button");
    retry.type = "button"; retry.className = "text-brand-accent font-bold mt-2"; retry.textContent = "إعادة المحاولة";
    retry.addEventListener("click", loadStatistics);
    byId("stats-state").append(document.createElement("br"), retry);
  } finally {
    if (epoch === requestEpoch) { loading = false; button.disabled = false; }
  }
}
