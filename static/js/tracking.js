import { api } from "./api.js";
import { renderOwnerReview } from "./public-review.js";
import { entityLabel, priorityLabels, statusLabels } from "./complaints.js";

function text(id, value) { document.getElementById(id).textContent = value ?? ""; }
function renderNotes(notes = []) {
  const box = document.getElementById("v-notes-history");
  box.replaceChildren();
  notes.filter((note) => !note.is_internal).forEach((note) => {
    const item = document.createElement("div"); item.className = "record-note";
    item.textContent = note.note || "";
    const time = document.createElement("time");
    time.textContent = note.created_at ? new Date(note.created_at).toLocaleString("ar") : "";
    item.append(time); box.append(item);
  });
  document.getElementById("v-note-box").classList.toggle("hidden", box.childElementCount === 0);
}
export async function searchComplaint() {
  const code = document.getElementById("search-code-input").value.trim();
  if (!code) return window.showNotice("يرجى إدخال رمز المتابعة.", "error");
  const button = document.getElementById("track-button");
  button.disabled = true;
  const card = document.getElementById("view-card");
  const notFound = document.getElementById("view-not-found");
  card.classList.add("hidden"); notFound.classList.add("hidden");
  try {
    const complaint = await api(`/complaints/track/${encodeURIComponent(code)}`);
    const status = complaint.status || "PENDING";
    const progress = Math.max(0, Math.min(100, Number(complaint.progress) || 0));
    text("v-code", complaint.tracking_code || code);
    text("v-title", complaint.title);
    text("v-details", complaint.details);
    text("v-entity", entityLabel(complaint.directorate_id));
    text("v-date", complaint.created_at ? new Date(complaint.created_at).toLocaleDateString("ar") : "");
    text("v-type", `شكوى ${complaint.category || "عامة"}`);
    text("v-priority", priorityLabels[complaint.priority] || complaint.priority || "");
    text("v-status-badge", statusLabels[status] || status);
    text("v-progress-num", `${progress}%`);
    document.getElementById("v-progress-bar").style.width = `${progress}%`;
    const files = document.getElementById("v-attachments-container"); files.replaceChildren();
    (complaint.attachments || []).forEach((file) => {
      const item = document.createElement("span"); item.className = "safe-file";
      const icon = document.createElement("i"); icon.className = "fa-solid fa-paperclip";
      item.append(icon, document.createTextNode(file.file_type || "مرفق"));
      files.append(item);
    });
    renderNotes(complaint.notes || []);
    let review = document.getElementById("v-public-review");
    if (!review) {
      review = document.createElement("section"); review.id = "v-public-review";
      review.className = "record-note mt-4"; card.append(review);
    }
    renderOwnerReview(complaint, review);
    const report = complaint.resolution_report || "";
    text("v-report", report);
    document.getElementById("v-resolution-box").classList.toggle("hidden", status !== "RESOLVED" || !report);
    card.classList.remove("hidden");
  } catch (error) {
    notFound.textContent = error.status === 404 ? "لم يتم العثور على شكوى بهذا الرمز. تحقق من الرمز وحاول مجدداً." : `تعذر جلب بيانات المتابعة: ${error.message}`;
    notFound.classList.remove("hidden");
  } finally { button.disabled = false; }
}
export async function copyComplaintLink() {
  const code = document.getElementById("v-code").textContent;
  const url = new URL("/", window.location.origin); url.searchParams.set("code", code);
  try { await navigator.clipboard.writeText(url.href); window.showNotice("تم نسخ رابط المتابعة.", "success"); }
  catch { window.showNotice(url.href, "info"); }
}
export function checkUrlForCode() {
  const code = new URLSearchParams(window.location.search).get("code");
  if (code) { document.getElementById("search-code-input").value = code; window.switchTab("view"); searchComplaint(); }
}
