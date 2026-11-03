import { complaintDownloadUrl } from "./api.js";
import { complaints, loadComplaints, updateComplaintStatus, retryNotification, statusLabels, priorityLabels, entityLabel } from "./complaints.js";
import { logoutUser } from "./auth.js";

const byId = (id) => document.getElementById(id);
let previousStatus = null;

function attachmentLink(file) {
  const link = document.createElement("a");
  link.className = "safe-file"; link.href = complaintDownloadUrl(file.id); link.target = "_blank"; link.rel = "noopener";
  const icon = document.createElement("i"); icon.className = "fa-solid fa-file-arrow-down";
  link.append(icon, document.createTextNode(file.file_type || "تنزيل المرفق")); return link;
}
function renderHistory(complaint) {
  const root = byId("p-notes-history"); root.replaceChildren();
  (complaint.notes || []).forEach((note) => {
    const item = document.createElement("div"); item.className = "record-note";
    const title = document.createElement("strong"); title.textContent = note.is_internal ? "ملاحظة داخلية" : "ملاحظة عامة";
    const content = document.createElement("p"); content.textContent = note.note || "";
    const time = document.createElement("time"); time.textContent = `${note.author_name || ""}${note.created_at ? ` · ${new Date(note.created_at).toLocaleString("ar")}` : ""}`;
    item.append(title, content, time); root.append(item);
    if (note.notification_status === "failed") {
      const retry = document.createElement("button"); retry.type = "button"; retry.className = "text-xs text-brand-accent font-bold mt-2"; retry.textContent = "إعادة محاولة الإشعار";
      retry.addEventListener("click", async () => {
        try {
          const result = await retryNotification(complaint.id, note.id);
          window.showNotice(
            result.message || "تم إرسال طلب إعادة المحاولة.",
            result.status === "sent" ? "success" : "info"
          );
          await loadComplaints(); populateProcessDropdown(complaint.id);
        } catch (error) { window.showNotice(error.message, "error"); }
      });
      item.append(retry);
    }
  });
}
export function updateSliderProgress(value) {
  const n = Number(value); byId("p-progress-text").textContent = `${n}%`;
  byId("p-progress").style.background = `linear-gradient(to left,#B88D4B ${n}%,#E5E7EB ${n}%)`;
}
export function toggleResolutionFields() {
  const resolved = byId("p-status").value === "RESOLVED";
  const slider = byId("p-progress");
  const nextStatus = byId("p-status").value;
  if (previousStatus === "RESOLVED" && !resolved) {
    slider.value = "0";
    updateSliderProgress(0);
  }
  slider.max = resolved ? "100" : "99";
  slider.disabled = resolved;
  if (resolved) {
    slider.value = "100";
    updateSliderProgress(100);
  }
  previousStatus = nextStatus;
  byId("resolution-fields").classList.toggle("hidden", !resolved);
}
export function populateProcessDropdown(selectedId = null) {
  const select = byId("process-select-id"); select.replaceChildren();
  const active = complaints.filter((item) => item.status !== "RESOLVED");
  if (selectedId && !active.some((item) => String(item.id) === String(selectedId))) {
    const previous = complaints.find((item) => String(item.id) === String(selectedId));
    if (previous) active.unshift(previous);
  }
  if (!active.length) {
    const opt = document.createElement("option"); opt.value = ""; opt.textContent = "لا توجد شكاوى متاحة للمعالجة"; select.append(opt);
    byId("processing-card").classList.add("opacity-50"); return;
  }
  byId("processing-card").classList.remove("opacity-50");
  active.forEach((item) => {
    const opt = document.createElement("option"); opt.value = item.id;
    opt.textContent = `[${item.tracking_code || item.id}] ${item.title || ""} (${statusLabels[item.status] || item.status})`;
    select.append(opt);
  });
  if (selectedId) select.value = selectedId;
  loadComplaintForProcessing();
}
export function loadComplaintForProcessing() {
  const id = byId("process-select-id").value;
  const complaint = complaints.find((item) => String(item.id) === String(id));
  if (!complaint) return;
  byId("p-title").textContent = complaint.title || "";
  byId("p-code-badge").textContent = complaint.tracking_code || String(complaint.id);
  byId("p-details").textContent = complaint.details || "";
  byId("p-citizen").textContent = complaint.citizen ? `${complaint.citizen.first_name || ""} ${complaint.citizen.last_name || ""}`.trim() : "";
  byId("p-phone").textContent = complaint.citizen?.phone || "";
  byId("p-entity").textContent = entityLabel(complaint.directorate_id);
  byId("p-date").textContent = complaint.created_at ? new Date(complaint.created_at).toLocaleDateString("ar") : "";
  const files = byId("p-attachments-container"); files.replaceChildren();
  (complaint.attachments || []).forEach((file) => files.append(attachmentLink(file)));
  byId("p-status").value = complaint.status || "PENDING";
  previousStatus = complaint.status || "PENDING";
  byId("p-priority").value = complaint.priority || "MEDIUM";
  const resolved = complaint.status === "RESOLVED";
  const progress = resolved ? 100 : Math.max(0, Math.min(99, Number(complaint.progress) || 0));
  byId("p-progress").max = resolved ? "100" : "99";
  byId("p-progress").disabled = resolved;
  byId("p-progress").value = progress; updateSliderProgress(progress);
  byId("p-employee-note").value = "";
  byId("p-report").value = complaint.resolution_report || "";
  renderHistory(complaint); toggleResolutionFields();
}
export async function saveComplaintProcessing() {
  const id = byId("process-select-id").value;
  if (!id) return window.showNotice("اختر شكوى أولاً.", "error");
  const note = byId("p-employee-note").value.trim();
  const status = byId("p-status").value;
  const button = byId("save-processing"); button.disabled = true;
  const payload = {
    ...(note ? { admin_notes: note } : {}),
    resolution_report: byId("p-report").value.trim(),
    progress: Number(byId("p-progress").value),
    priority: byId("p-priority").value
  };
  try {
    const result = await updateComplaintStatus(id, status, payload);
    byId("p-employee-note").value = "";
    const notify = result.notification;
    const notifyText = notify?.message || (notify?.status ? `حالة الإشعار: ${notify.status}` : "");
    window.showNotice([result.message, notifyText].filter(Boolean).join(" — ") || "تم حفظ التحديث.", notify?.status === "failed" ? "info" : "success");
    await loadComplaints(); populateProcessDropdown(id);
  } catch (error) {
    if (error.status === 401) await logoutUser();
    else window.showNotice(`لم يتم حفظ التحديث: ${error.message}`, "error");
  }
  finally { button.disabled = false; }
}
