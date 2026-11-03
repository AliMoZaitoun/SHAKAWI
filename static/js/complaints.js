import { api, postFile } from "./api.js";
import { getUser, maySeeDirectorate } from "./auth.js";

export let complaints = [];
export let activeComplaint = null;
export const statusLabels = { PENDING: "جديدة", IN_PROGRESS: "جاري العمل", RESOLVED: "تمت المعالجة", REJECTED: "مرفوضة" };
export const priorityLabels = { MEDIUM: "عادي", URGENT: "مستعجل" };
export const entityLabel = (id) => Number(id) === 1 ? "المحافظة" : "مديرية الخدمات الفنية";

export async function loadComplaints() {
  const result = await api("/complaints/");
  const user = getUser();
  complaints = user?.role === "employee" ? result.filter((complaint) => maySeeDirectorate(complaint.directorate_id)) : result;
  window.dispatchEvent(new CustomEvent("shakwa:complaints"));
  return complaints;
}
export async function createCitizen(payload) {
  return api("/citizens/", { method: "POST", body: JSON.stringify(payload) });
}
export async function uploadCitizenIdentity(id, file) {
  return postFile(`/citizens/${encodeURIComponent(id)}/id-image/`, file);
}
export async function createComplaint(payload) {
  return api("/complaints/", { method: "POST", body: JSON.stringify(payload) });
}
export async function uploadComplaintAttachment(id, file) {
  return postFile(`/complaints/${encodeURIComponent(id)}/attachments/`, file);
}
export async function updateComplaintStatus(id, status, body) {
  const query = new URLSearchParams({ new_status: status });
  return api(`/complaints/${encodeURIComponent(id)}/status?${query}`, { method: "PATCH", body: JSON.stringify(body) });
}
export async function addPublicNote(id, note) {
  return api(`/complaints/${encodeURIComponent(id)}/notes`, { method: "POST", body: JSON.stringify({ note, is_internal: false }) });
}
export async function retryNotification(complaintId, noteId) {
  return api(`/complaints/${encodeURIComponent(complaintId)}/notes/${encodeURIComponent(noteId)}/retry`, { method: "POST" });
}
export function findComplaintById(id) {
  return complaints.find((complaint) => String(complaint.id) === String(id));
}
export function setActiveComplaint(complaint) { activeComplaint = complaint; }
