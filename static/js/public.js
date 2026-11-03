import { api } from "./api.js";

const byId = (id) => document.getElementById(id);
const statusLabels = { PENDING: "جديدة", IN_PROGRESS: "جاري العمل", RESOLVED: "تمت المعالجة", REJECTED: "مرفوضة" };
const priorityLabels = { LOW: "منخفضة", MEDIUM: "عادية", HIGH: "عالية", URGENT: "مستعجلة" };
const directorateLabel = (id) => Number(id) === 1 ? "المحافظة" : Number(id) === 2 ? "مديرية الخدمات الفنية" : "—";
let page = 1;
let pages = 1;
let requestToken = 0;

function dateLabel(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleDateString("ar");
}
function setState(message, kind = "info") {
  const state = byId("public-state");
  state.textContent = message;
  state.classList.remove("hidden");
  state.dataset.kind = kind;
}
function makeCard(item) {
  const card = document.createElement("article");
  card.className = "public-card";
  const title = document.createElement("h3");
  title.className = "font-bold text-brand-dark text-lg";
  title.textContent = item.title || "شكوى منشورة";
  const meta = document.createElement("div");
  meta.className = "public-meta mt-2";
  [item.category || "—", directorateLabel(item.directorate_id), statusLabels[item.status] || item.status || "—", priorityLabels[item.priority] || item.priority || "—", dateLabel(item.created_at)].forEach((label) => {
    const pill = document.createElement("span");
    pill.className = "public-pill";
    pill.textContent = label;
    meta.append(pill);
  });
  const details = document.createElement("p");
  details.className = "text-sm text-gray-600 mt-3 leading-relaxed";
  details.textContent = item.details || "";
  const progress = document.createElement("p");
  progress.className = "text-xs text-gray-500 mt-3";
  progress.textContent = `الإنجاز التقديري: ${Math.max(0, Math.min(100, Number(item.progress) || 0))}%`;
  const open = document.createElement("button");
  open.type = "button";
  open.className = "text-brand-accent font-bold text-sm mt-3";
  open.textContent = "عرض التفاصيل والملاحظات";
  open.addEventListener("click", () => openPublicComplaint(item.id, true));
  card.append(title, meta, details, progress, open);
  return card;
}
function renderList(items) {
  const root = byId("public-list");
  root.replaceChildren();
  items.forEach((item) => root.append(makeCard(item)));
  byId("public-page-label").textContent = pages > 0 ? `الصفحة ${page} من ${pages}` : "";
  byId("public-prev").disabled = page <= 1;
  byId("public-next").disabled = page >= pages;
}
export async function loadPublicComplaints() {
  const token = ++requestToken;
  page = Math.max(1, page);
  byId("public-detail").classList.add("hidden");
  const list = byId("public-list");
  list.replaceChildren();
  for (let index = 0; index < 4; index += 1) {
    const skeleton = document.createElement("div");
    skeleton.className = "skeleton-card";
    skeleton.setAttribute("aria-hidden", "true");
    list.append(skeleton);
  }
  setState("جارٍ تحميل الشكاوى المنشورة…");
  const params = new URLSearchParams({ page: String(page), page_size: "12" });
  const category = byId("public-category").value;
  const status = byId("public-status").value;
  const directorate = byId("public-directorate").value;
  if (category) params.set("category", category);
  if (status) params.set("status", status);
  if (directorate) params.set("directorate_id", directorate);
  try {
    const result = await api(`/complaints/public?${params.toString()}`);
    if (token !== requestToken) return;
    const items = Array.isArray(result.items) ? result.items : [];
    pages = Math.max(1, Number(result.pages) || 1);
    page = Number(result.page) || page;
    byId("public-list").replaceChildren(...items.map(makeCard));
    byId("public-state").classList.toggle("hidden", items.length > 0);
    if (!items.length) setState(Number(result.total) ? "لا توجد شكاوى في هذه الصفحة." : "لا توجد شكاوى منشورة تطابق الفلاتر.");
    renderList(items);
  } catch (error) {
    if (token !== requestToken) return;
    byId("public-list").replaceChildren();
    setState(`تعذر تحميل الشكاوى: ${error.message}`, "error");
    const retry = document.createElement("button");
    retry.type = "button"; retry.className = "text-brand-accent font-bold mt-2"; retry.textContent = "إعادة المحاولة";
    retry.addEventListener("click", loadPublicComplaints);
    byId("public-state").append(document.createElement("br"), retry);
  }
}
export function changePublicPage(delta) {
  page = Math.min(pages, Math.max(1, page + delta));
  loadPublicComplaints();
}
function renderDetail(item) {
  const root = byId("public-detail");
  root.replaceChildren();
  const heading = document.createElement("h3");
  heading.className = "text-xl font-bold text-brand-dark";
  heading.textContent = item.title || "تفاصيل الشكوى";
  const meta = document.createElement("p");
  meta.className = "public-meta mt-2";
  meta.textContent = `${item.category || "—"} · ${directorateLabel(item.directorate_id)} · ${statusLabels[item.status] || item.status || "—"} · ${priorityLabels[item.priority] || item.priority || "—"} · ${dateLabel(item.created_at)}`;
  const details = document.createElement("p");
  details.className = "mt-4 text-sm leading-7 whitespace-pre-wrap";
  details.textContent = item.details || "";
  const progress = document.createElement("p");
  progress.className = "text-sm font-bold text-brand-dark mt-4";
  progress.textContent = `الإنجاز التقديري: ${Math.max(0, Math.min(100, Number(item.progress) || 0))}%`;
  root.append(heading, meta, details, progress);
  if (item.resolution_report) {
    const report = document.createElement("section");
    report.className = "mt-4 bg-green-50 border border-green-200 rounded-lg p-4";
    const reportTitle = document.createElement("h4");
    reportTitle.className = "font-bold text-green-900";
    reportTitle.textContent = "نتيجة المعالجة";
    const reportText = document.createElement("p");
    reportText.className = "text-sm text-green-900 mt-2 whitespace-pre-wrap";
    reportText.textContent = item.resolution_report;
    report.append(reportTitle, reportText);
    root.append(report);
  }
  const notesTitle = document.createElement("h4");
  notesTitle.className = "font-bold mt-5 mb-2";
  notesTitle.textContent = "الملاحظات العامة";
  const notes = document.createElement("div");
  notes.className = "space-y-2";
  (Array.isArray(item.notes) ? item.notes : []).filter((note) => note && note.is_internal !== true).forEach((note) => {
    const block = document.createElement("div");
    block.className = "public-note";
    const text = document.createElement("p");
    text.textContent = note.note || "";
    const time = document.createElement("time");
    time.className = "text-xs text-gray-500 block mt-2";
    time.textContent = dateLabel(note.created_at);
    block.append(text, time);
    notes.append(block);
  });
  if (!notes.childElementCount) {
    const empty = document.createElement("p");
    empty.className = "text-sm text-gray-500";
    empty.textContent = "لا توجد ملاحظات عامة حتى الآن.";
    notes.append(empty);
  }
  const actions = document.createElement("div");
  actions.className = "flex gap-3 mt-5";
  const share = document.createElement("button");
  share.type = "button"; share.className = "secondary-button"; share.textContent = "نسخ رابط المشاركة";
  share.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(`${location.origin}${location.pathname}#public-${encodeURIComponent(item.id)}`);
      window.showNotice("تم نسخ رابط الشكوى العامة.", "success");
    } catch { window.showNotice("تعذر نسخ الرابط. يمكنك نسخه من شريط العنوان.", "error"); }
  });
  const close = document.createElement("button");
  close.type = "button"; close.className = "secondary-button"; close.textContent = "إغلاق التفاصيل";
  close.addEventListener("click", () => {
    history.replaceState(null, "", `${location.pathname}${location.search}#public`);
    root.classList.add("hidden");
  });
  actions.append(share, close);
  root.append(notesTitle, notes, actions);
  root.classList.remove("hidden");
  root.scrollIntoView({ behavior: "smooth", block: "start" });
}
export async function openPublicComplaint(id, updateHash = false) {
  const root = byId("public-detail");
  root.classList.remove("hidden");
  root.textContent = "جارٍ تحميل التفاصيل العامة…";
  if (updateHash) history.pushState(null, "", `${location.pathname}${location.search}#public-${encodeURIComponent(id)}`);
  try {
    const item = await api(`/complaints/public/${encodeURIComponent(id)}`);
    renderDetail(item);
  } catch (error) {
    root.replaceChildren();
    const message = document.createElement("p");
    message.className = "state-panel";
    message.textContent = error.status === 404 ? "هذه الشكوى غير منشورة أو لم تعد متاحة." : `تعذر تحميل التفاصيل: ${error.message}`;
    root.append(message);
  }
}
export function handlePublicHash() {
  const hash = decodeURIComponent(location.hash.slice(1));
  if (hash === "public") {
    window.switchTab("public");
  } else if (hash.startsWith("public-")) {
    window.switchTab("public");
    openPublicComplaint(hash.slice(7), false);
  }
}
export function initPublicBrowse() {
  ["public-category", "public-status", "public-directorate"].forEach((id) => byId(id).addEventListener("change", () => {
    page = 1;
    loadPublicComplaints();
  }));
  window.addEventListener("popstate", () => {
    if (location.hash.startsWith("#public")) handlePublicHash();
  });
}
