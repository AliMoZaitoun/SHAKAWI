import { loadAuthState, isStaff, loginUser, setUnauthorizedHandler, logoutUser } from "./auth.js";
import { complaints, loadComplaints, createCitizen, uploadCitizenIdentity, createComplaint, uploadComplaintAttachment, statusLabels, priorityLabels } from "./complaints.js";
import { searchComplaint, copyComplaintLink, checkUrlForCode } from "./tracking.js";
import { populateProcessDropdown, loadComplaintForProcessing, saveComplaintProcessing, toggleResolutionFields, updateSliderProgress } from "./processing.js";

let pendingSubmission = null;
let submissionInProgress = false;

function fileFingerprint(file) {
  if (!file) return "";
  return [file.name, file.size, file.lastModified, file.type].join(":");
}

function readSubmissionDraft() {
  return {
    citizen: {
      first_name: document.getElementById("c-first-name").value.trim(),
      last_name: document.getElementById("c-last-name").value.trim(),
      phone: document.getElementById("c-phone").value.trim(),
      national_id: document.getElementById("c-national-id").value.trim()
    },
    identity: document.getElementById("c-id-card").files[0] || null,
    title: document.getElementById("comp-title").value.trim(),
    details: document.getElementById("comp-details").value.trim(),
    directorateId: Number(document.getElementById("comp-entity").value),
    category: document.getElementById("comp-type").value,
    attachments: [...document.getElementById("comp-attachments").files]
  };
}

function sameDraft(first, second) {
  return JSON.stringify({
    ...first,
    identity: fileFingerprint(first.identity),
    attachments: first.attachments.map(fileFingerprint)
  }) === JSON.stringify({
    ...second,
    identity: fileFingerprint(second.identity),
    attachments: second.attachments.map(fileFingerprint)
  });
}

function lockSubmissionDraft(locked) {
  [
    "c-first-name",
    "c-last-name",
    "c-phone",
    "c-national-id",
    "c-id-card",
    "comp-title",
    "comp-details",
    "comp-entity",
    "comp-type",
    "comp-attachments"
  ].forEach((id) => {
    document.getElementById(id).disabled = locked;
  });
  document.querySelectorAll("#form-step-1 button, #form-step-2 button").forEach((button) => {
    if (button.id !== "submit-complaint") button.disabled = locked;
  });
  const submitButton = document.getElementById("submit-complaint");
  submitButton.textContent = locked ? "متابعة رفع المرفقات" : "إرسال الشكوى";
}
window.showNotice = (message, type = "info") => {
  const notice = document.getElementById("notice");
  notice.textContent = message; notice.className = `notice ${type}`; notice.classList.remove("hidden");
  window.clearTimeout(window.noticeTimer); window.noticeTimer = window.setTimeout(() => notice.classList.add("hidden"), 8500);
};
window.switchTab = (name) => {
  if (["list", "process"].includes(name) && !isStaff()) { window.showNotice("تسجيل الدخول مطلوب للوصول إلى لوحة الموظفين.", "info"); document.getElementById("login-dialog").showModal(); return; }
  document.querySelectorAll(".tab-content").forEach((element) => element.classList.add("hidden"));
  document.querySelectorAll(".tab-btn").forEach((element) => element.classList.remove("active"));
  document.getElementById(`sec-${name}`).classList.remove("hidden");
  document.getElementById(`tab-${name}`).classList.add("active");
  if (name === "list") refreshStaffData();
  if (name === "process") refreshStaffData();
};
window.validatePhoneRealtime = (input) => document.getElementById("phone-error").classList.toggle("hidden", !input.value || /^09\d{8}$/.test(input.value.trim()));
window.validateNationalIdRealtime = (input) => document.getElementById("nid-error").classList.toggle("hidden", !input.value || /^\d{11}$/.test(input.value.trim()));
window.goToStep2 = () => {
  const first = document.getElementById("c-first-name").value.trim();
  const last = document.getElementById("c-last-name").value.trim();
  const phone = document.getElementById("c-phone").value.trim();
  const nationalId = document.getElementById("c-national-id").value.trim();
  if (first.length < 2 || first.length > 50 || last.length < 2 || last.length > 50) return window.showNotice("يرجى إدخال الاسم الأول واسم العائلة (2–50 حرفاً لكل منهما).", "error");
  if (!/^09\d{8}$/.test(phone)) return window.showNotice("يجب أن يتكون رقم الموبايل من 10 أرقام ويبدأ بـ 09.", "error");
  if (!/^\d{11}$/.test(nationalId)) return window.showNotice("يجب أن يتكون الرقم الوطني من 11 رقماً.", "error");
  if (!document.getElementById("c-id-card").files[0]) return window.showNotice("يرجى إرفاق صورة الهوية الشخصية.", "error");
  document.getElementById("circle-step-1").classList.replace("active", "completed");
  document.getElementById("circle-step-1").textContent = "✓";
  document.getElementById("circle-step-2").classList.add("active");
  document.getElementById("line-step").classList.replace("bg-gray-300", "bg-brand-dark");
  document.getElementById("form-step-1").classList.add("hidden");
  document.getElementById("form-step-2").classList.remove("hidden");
  document.getElementById("summary-citizen-name").textContent = `${first} ${last} (${phone})`;
};
window.goToStep1 = () => {
  document.getElementById("circle-step-1").classList.remove("completed"); document.getElementById("circle-step-1").classList.add("active"); document.getElementById("circle-step-1").textContent = "1";
  document.getElementById("circle-step-2").classList.remove("active");
  document.getElementById("line-step").classList.replace("bg-brand-dark", "bg-gray-300");
  document.getElementById("form-step-2").classList.add("hidden"); document.getElementById("form-step-1").classList.remove("hidden");
};
window.submitComplaintForm = async () => {
  if (submissionInProgress) return;
  const currentDraft = readSubmissionDraft();
  if (pendingSubmission?.complaint && !sameDraft(pendingSubmission.draft, currentDraft)) {
    lockSubmissionDraft(true);
    return window.showNotice("تم تسجيل الشكوى بالفعل. لا يمكن تغيير بياناتها؛ استخدم متابعة رفع المرفقات لإكمال الطلب نفسه.", "error");
  }
  if (pendingSubmission && !pendingSubmission.complaint && !sameDraft(pendingSubmission.draft, currentDraft)) {
    pendingSubmission = null;
    lockSubmissionDraft(false);
    window.showNotice("تم تغيير البيانات قبل إنشاء الشكوى؛ ستبدأ محاولة جديدة ببيانات المواطن الحالية.", "info");
  }
  const draft = pendingSubmission?.draft || currentDraft;
  if (draft.citizen.first_name.length < 2 || draft.citizen.first_name.length > 50 ||
      draft.citizen.last_name.length < 2 || draft.citizen.last_name.length > 50) {
    return window.showNotice("يرجى إدخال الاسم الأول واسم العائلة (2–50 حرفاً لكل منهما).", "error");
  }
  if (!/^09\d{8}$/.test(draft.citizen.phone)) {
    return window.showNotice("يجب أن يتكون رقم الموبايل من 10 أرقام ويبدأ بـ 09.", "error");
  }
  if (!/^\d{11}$/.test(draft.citizen.national_id)) {
    return window.showNotice("يجب أن يتكون الرقم الوطني من 11 رقماً.", "error");
  }
  if (!draft.identity) return window.showNotice("يرجى إرفاق صورة الهوية الشخصية.", "error");
  if (draft.title.length < 5) return window.showNotice("عنوان الشكوى يجب ألا يقل عن 5 أحرف.", "error");
  if (draft.details.length < 10) return window.showNotice("تفاصيل الشكوى يجب ألا تقل عن 10 أحرف.", "error");
  const button = document.getElementById("submit-complaint");
  button.disabled = true;
  submissionInProgress = true;
  if (!pendingSubmission) {
    pendingSubmission = {
      draft,
      citizen: null,
      identityUploaded: false,
      complaint: null,
      uploadedAttachments: 0
    };
  }
  const submission = pendingSubmission;
  try {
    if (!submission.citizen) {
      submission.citizen = await createCitizen(submission.draft.citizen);
    }
    if (!submission.identityUploaded) {
      await uploadCitizenIdentity(submission.citizen.id, submission.draft.identity);
      submission.identityUploaded = true;
    }
    if (!submission.complaint) {
      submission.complaint = await createComplaint({
        citizen_id: submission.citizen.id,
        directorate_id: submission.draft.directorateId,
        title: submission.draft.title,
        details: submission.draft.details,
        category: submission.draft.category,
        priority: "MEDIUM"
      });
      lockSubmissionDraft(true);
    }
    while (submission.uploadedAttachments < submission.draft.attachments.length) {
      await uploadComplaintAttachment(
        submission.complaint.id,
        submission.draft.attachments[submission.uploadedAttachments]
      );
      submission.uploadedAttachments += 1;
    }
    const trackingCode = submission.complaint.tracking_code || "";
    resetForm();
    document.getElementById("search-code-input").value = trackingCode;
    window.showNotice(`تم حفظ الشكوى ومرفقاتها. رمز المتابعة: ${trackingCode}`, "success");
    window.switchTab("view");
    if (document.getElementById("search-code-input").value) await searchComplaint();
  } catch (error) {
    const code = submission.complaint?.tracking_code
      ? ` رمز الشكوى المسجلة: ${submission.complaint.tracking_code}. اضغط «متابعة رفع المرفقات» لإكمال الطلب نفسه.`
      : "";
    window.showNotice(`لم يكتمل حفظ الطلب: ${error.message}.${code} لم يتم مسح البيانات المدخلة.`, "error");
  } finally {
    submissionInProgress = false;
    button.disabled = false;
  }
};
function resetForm() {
  ["c-first-name","c-last-name","c-phone","c-national-id","c-id-card","comp-title","comp-details","comp-attachments"].forEach((id) => { document.getElementById(id).value = ""; });
  document.getElementById("comp-entity").value = "2";
  document.getElementById("comp-type").value = "عامة";
  pendingSubmission = null;
  lockSubmissionDraft(false);
  window.goToStep1();
}
function renderComplaintsTable() {
  const tbody = document.getElementById("complaints-table-body"); tbody.replaceChildren();
  const status = document.getElementById("filter-status").value;
  const priority = document.getElementById("filter-priority").value;
  const type = document.getElementById("filter-type").value;
  const filtered = complaints.filter((item) => (status === "الكل" || item.status === status) && (priority === "الكل" || item.priority === priority) && (type === "الكل" || item.category === type));
  document.getElementById("total-count").textContent = filtered.length;
  if (!filtered.length) { const row = tbody.insertRow(); const cell = row.insertCell(); cell.colSpan = 8; cell.className = "text-center py-8 text-gray-400"; cell.textContent = "لا توجد شكاوى مطابقة للفلترة الحالية."; return; }
  filtered.forEach((item) => {
    const row = tbody.insertRow(); row.className = "hover:bg-gray-50";
    const values = [item.tracking_code || item.id,item.title,`${item.citizen?.first_name || ""} ${item.citizen?.last_name || ""}`.trim(),item.category || "—",priorityLabels[item.priority] || item.priority || "—",statusLabels[item.status] || item.status || "—",`${Number(item.progress) || 0}%`];
    values.forEach((value) => { const cell = row.insertCell(); cell.className = "p-3"; cell.textContent = value; });
    const action = row.insertCell(); action.className = "p-3 text-center";
    const button = document.createElement("button"); button.className = "bg-brand-accent text-white text-xs font-bold px-3 py-1.5 rounded"; button.textContent = "معالجة الشكوى";
    button.addEventListener("click", () => { window.switchTab("process"); populateProcessDropdown(item.id); }); action.append(button);
  });
}
window.renderComplaintsTable = renderComplaintsTable;
window.loadComplaintForProcessing = loadComplaintForProcessing;
window.toggleResolutionFields = toggleResolutionFields;
window.updateSliderProgress = updateSliderProgress;
window.saveComplaintProcessing = saveComplaintProcessing;
window.searchComplaint = searchComplaint;
window.copyComplaintLink = copyComplaintLink;
window.checkUrlForCode = checkUrlForCode;
async function refreshStaffData() {
  if (!isStaff()) return;
  try { await loadComplaints(); renderComplaintsTable(); populateProcessDropdown(); }
  catch (error) {
    if (error.status === 401) { await logoutUser(); window.showNotice("انتهت جلسة الدخول. سجل الدخول مجدداً.", "error"); }
    else window.showNotice(`تعذر تحميل سجل الشكاوى: ${error.message}`, "error");
  }
}
setUnauthorizedHandler((error) => window.showNotice(error.message, "error"));
window.addEventListener("shakwa:complaints", () => { renderComplaintsTable(); });
window.addEventListener("shakwa:auth", () => { window.showNotice("تم تسجيل الدخول.", "success"); window.switchTab("list"); });
window.addEventListener("shakwa:logout", () => {
  document.querySelectorAll(".staff-tab").forEach((tab) => tab.classList.remove("visible"));
  document.getElementById("complaints-table-body").replaceChildren();
  document.getElementById("total-count").textContent = "0";
  if (["list","process"].includes(location.hash.replace("#",""))) window.switchTab("submit");
  else { document.querySelectorAll(".tab-content").forEach((section) => section.classList.add("hidden")); document.getElementById("sec-submit").classList.remove("hidden"); }
  window.showNotice("تم تسجيل الخروج.", "info");
});
document.getElementById("login-form").addEventListener("submit", loginUser);
document.getElementById("close-login").addEventListener("click", () => document.getElementById("login-dialog").close());
document.getElementById("c-phone").addEventListener("input", (event) => window.validatePhoneRealtime(event.currentTarget));
document.getElementById("c-national-id").addEventListener("input", (event) => { event.currentTarget.value = event.currentTarget.value.replace(/\D/g, "").slice(0,11); window.validateNationalIdRealtime(event.currentTarget); });
document.getElementById("search-code-input").addEventListener("keydown", (event) => { if (event.key === "Enter") searchComplaint(); });
document.addEventListener("DOMContentLoaded", async () => {
  try { await loadAuthState(); }
  catch (error) { window.showNotice(`تعذر التحقق من جلسة الموظف: ${error.message}`, "error"); }
  checkUrlForCode();
});
