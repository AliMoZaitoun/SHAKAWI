import { api } from "./api.js";

const MAX_FILES = 5;
const MAX_FILE_BYTES = 10 * 1024 * 1024;
const ACCEPTED_TYPES = new Set(["image/jpeg", "image/png", "image/webp", "application/pdf"]);
const notificationLabels = {
  sent: "أُرسل إشعار تيليغرام", failed: "تعذر إرسال إشعار تيليغرام",
  not_linked: "لا يوجد حساب تيليغرام مرتبط؛ يبقى الطلب متاحًا في الموقع",
  not_configured: "البوت غير مضبوط؛ لم يُرسل إشعار، والطلب متاح في الموقع",
  not_requested: "لم يُرسل إشعار بعد"
};

const makeId = () => {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (char) => {
    const value = Math.floor(Math.random() * 16);
    return (char === "x" ? value : (value & 3) | 8).toString(16);
  });
};

function node(tag, className = "", value = "") {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (value) element.textContent = value;
  return element;
}

function dateLabel(value) {
  return value ? new Date(value).toLocaleString("ar") : "";
}

function sectionHeading(title, description) {
  const header = node("div", "evidence-heading");
  const titleEl = node("h3", "", title);
  titleEl.className = "text-base font-bold text-brand-dark";
  header.append(titleEl, node("p", "text-xs text-gray-600 mt-1", description));
  return header;
}

function safeFileLink(file) {
  const link = node("a", "safe-file evidence-file-link", file.name || file.file_type || "تنزيل المرفق");
  try {
    const url = new URL(file.file_url, window.location.origin);
    if (url.protocol === "https:" || url.protocol === "http:") {
      link.href = url.href;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
    } else {
      link.removeAttribute("href");
    }
  } catch {
    link.removeAttribute("href");
  }
  return link;
}

function renderTimeline(root, requests, staff, complaintId, onChange) {
  const timeline = root.querySelector("[data-evidence-timeline]");
  timeline.replaceChildren();
  if (!requests.length) {
    const empty = node("div", "evidence-empty", "لا توجد طلبات أدلة حتى الآن.");
    timeline.append(empty);
    return;
  }
  [...requests].sort((a, b) => new Date(a.created_at || 0) - new Date(b.created_at || 0)).forEach((request) => {
    const item = node("article", "evidence-request");
    item.dataset.requestId = request.id;
    const top = node("div", "evidence-request-top");
    const title = node("strong", "", request.status === "answered" ? "تم استلام الرد" : "بانتظار رد المواطن");
    title.className = `text-sm font-bold ${request.status === "answered" ? "text-brand-dark" : "text-amber-800"}`;
    top.append(title, node("time", "evidence-time", dateLabel(request.created_at)));
    item.append(top, node("p", "evidence-prompt", request.prompt || ""));
    const author = node("p", "evidence-author", request.author_name || "");
    if (request.author_name) item.append(author);

    if (request.notification_status) {
      const notification = node("p", `evidence-notification ${request.notification_status === "failed" ? "is-error" : ""}`,
        request.notification_error || notificationLabels[request.notification_status] || "حالة الإشعار غير معروفة");
      item.append(notification);
      if (staff && request.status === "pending" && request.notification_status !== "sent") {
        const retry = node("button", "secondary-button evidence-retry", "إعادة محاولة الإشعار");
        retry.type = "button";
        retry.dataset.testid = `evidence-retry-${request.id}`;
        retry.addEventListener("click", async () => {
          retry.disabled = true;
          retry.textContent = "جارٍ إعادة المحاولة";
          try {
            const result = await api(`/complaints/${encodeURIComponent(complaintId)}/evidence/${encodeURIComponent(request.id)}/retry`, { method: "POST" });
            request.notification_status = result.status;
            request.notification_error = result.status === "sent" ? "" : result.message;
            renderTimeline(root, requests, staff, complaintId, onChange);
            window.showNotice(result.message || "تم إرسال طلب إعادة المحاولة.", result.status === "failed" ? "info" : "success");
          } catch (error) {
            window.showNotice(`تعذرت إعادة محاولة الإشعار: ${error.message}`, "error");
          } finally {
            retry.disabled = false;
            retry.textContent = "إعادة محاولة الإشعار";
          }
        });
        item.append(retry);
      }
    }

    (request.replies || []).forEach((reply) => {
      const replyBox = node("div", "evidence-reply");
      const replyHeading = node("div", "evidence-reply-heading");
      replyHeading.append(node("strong", "", "رد المواطن"), node("time", "evidence-time", dateLabel(reply.created_at)));
      replyBox.append(replyHeading);
      if (reply.text) replyBox.append(node("p", "evidence-prompt", reply.text));
      if (reply.attachments?.length) {
        const files = node("div", "evidence-files");
        reply.attachments.forEach((file) => files.append(safeFileLink(file)));
        replyBox.append(files);
      }
      item.append(replyBox);
    });
    timeline.append(item);
  });
}

async function fetchEvidence(complaintId) {
  return api(`/complaints/${encodeURIComponent(complaintId)}/evidence`);
}

export function renderEvidence(complaint, root, staff = false, options = {}) {
  if (!root || !complaint?.id) return;
  root.replaceChildren();
  root.classList.add("evidence-root");
  const requests = Array.isArray(complaint.evidence_requests) ? [...complaint.evidence_requests] : [];
  complaint.evidence_requests = requests;
  const card = node("section", "evidence-card");
  card.dataset.testid = staff ? "staff-evidence" : "citizen-evidence";
  const timeline = node("div", "evidence-timeline");
  timeline.dataset.evidenceTimeline = "";
  card.append(sectionHeading(
    staff ? "طلبات الأدلة والردود" : "طلب أدلة إضافية",
    "طلبات الأدلة والردود خاصة، ولا تظهر ضمن الشكوى العامة."
  ));

  if (staff) {
    const form = node("form", "evidence-form");
    form.dataset.testid = "evidence-request-form";
    const label = node("label", "field-label", "ما المعلومات أو المستندات المطلوبة؟");
    label.htmlFor = "evidence-prompt";
    const prompt = node("textarea", "field");
    prompt.id = "evidence-prompt";
    prompt.dataset.testid = "evidence-prompt";
    prompt.rows = 3;
    prompt.maxLength = 4000;
    prompt.required = true;
    prompt.setAttribute("aria-describedby", "evidence-request-help");
    const help = node("p", "text-xs text-gray-500", "سيصل الطلب إلى المواطن إن كان لديه قناة إشعار مرتبطة.");
    help.id = "evidence-request-help";
    const submit = node("button", "primary-button", "طلب استكمال معلومات أو أدلة");
    submit.type = "submit";
    submit.dataset.testid = "evidence-request-submit";
    const status = node("p", "evidence-inline-status");
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    form.append(label, prompt, help, submit, status);
    let requestKey = makeId();
    let attemptedPrompt = "";
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const value = prompt.value.trim();
      if (!value) {
        prompt.focus();
        return;
      }
      submit.disabled = true;
      prompt.disabled = true;
      if (attemptedPrompt && attemptedPrompt !== value) requestKey = makeId();
      attemptedPrompt = value;
      submit.textContent = "جارٍ الإرسال";
      status.textContent = "";
      try {
        const result = await api(`/complaints/${encodeURIComponent(complaint.id)}/evidence`, {
          method: "POST",
          body: JSON.stringify({ prompt: value, submission_key: requestKey })
        });
        if (result.request && !requests.some((r) => r.id === result.request.id)) requests.push(result.request);
        prompt.value = "";
        prompt.disabled = false;
        requestKey = makeId(); attemptedPrompt = "";
        status.textContent = result.notification?.message || `تم تسجيل طلب الأدلة${result.notification?.status ? `؛ حالة الإشعار: ${result.notification.status}` : ""}.`;
        status.classList.toggle("is-error", result.notification?.status === "failed");
        renderTimeline(card, requests, staff, complaint.id, async () => {});
      } catch (error) {
        status.textContent = `تعذر تأكيد حفظ الطلب؛ أعد المحاولة بنفس المحتوى: ${error.message}`;
        if (error.status) prompt.disabled = false;
        status.classList.add("is-error");
      } finally {
        submit.disabled = false;
        submit.textContent = "طلب استكمال معلومات أو أدلة";
      }
    });
    card.append(form, timeline);

    const notesSection = node("section", "staff-notes-composer");
    notesSection.append(sectionHeading("إضافة ملاحظة", "اختر جمهور الملاحظة بوضوح. الملاحظات خاصة ما لم تُنشر صراحة."));
    const notesForm = node("form", "evidence-form");
    notesForm.dataset.testid = "complaint-note-form";
    const noteLabel = node("label", "field-label", "نص الملاحظة");
    noteLabel.htmlFor = "staff-note-text";
    const noteText = node("textarea", "field");
    noteText.id = "staff-note-text";
    noteText.dataset.testid = "staff-note-text";
    noteText.rows = 3;
    noteText.maxLength = 2000;
    noteText.required = true;
    const audienceLabel = node("label", "field-label", "الجمهور");
    audienceLabel.htmlFor = "staff-note-audience";
    const audience = node("select", "field");
    audience.id = "staff-note-audience";
    audience.dataset.testid = "staff-note-audience";
    [
      ["private", "ملاحظة خاصة للمواطن"],
      ["internal", "ملاحظة داخلية للموظفين"],
      ["public", "ملاحظة عامة منشورة"]
    ].forEach(([value, labelText]) => {
      const option = node("option", "", labelText);
      option.value = value;
      audience.append(option);
    });
    const publicConfirm = node("label", "evidence-public-confirm hidden");
    const confirmBox = document.createElement("input");
    confirmBox.type = "checkbox";
    confirmBox.dataset.testid = "public-note-confirm";
    publicConfirm.append(confirmBox, document.createTextNode(" أؤكد أن هذه الملاحظة مناسبة للنشر العام."));
    const publicBlocked = node("p", "evidence-inline-status is-error hidden", "لا يمكن نشر ملاحظة عامة في شكوى خاصة.");
    const audienceHint = node("p", "text-xs text-gray-500", "الملاحظات الداخلية لا تصل للمواطن. الملاحظات الخاصة تصل إليه في المتابعة فقط.");
    const noteSubmit = node("button", "primary-button", "حفظ الملاحظة");
    noteSubmit.type = "submit";
    noteSubmit.dataset.testid = "staff-note-submit";
    const noteStatus = node("p", "evidence-inline-status");
    noteStatus.setAttribute("role", "status");
    noteStatus.setAttribute("aria-live", "polite");
    const publicComplaint = complaint.is_public === true;
    const syncAudience = () => {
      const isPublic = audience.value === "public";
      publicConfirm.classList.toggle("hidden", !isPublic || !publicComplaint);
      publicBlocked.classList.toggle("hidden", !isPublic || publicComplaint);
      confirmBox.checked = false;
      audienceHint.textContent = isPublic ? (publicComplaint ? "سيتمكن الجميع من رؤية هذه الملاحظة." : "النشر العام متاح فقط إذا كانت الشكوى منشورة للعامة.") : "الملاحظات الداخلية لا تصل للمواطن. الملاحظات الخاصة تصل إليه في المتابعة فقط.";
    };
    audience.addEventListener("change", syncAudience);
    notesForm.append(noteLabel, noteText, audienceLabel, audience, publicConfirm, publicBlocked, audienceHint, noteSubmit, noteStatus);
    notesForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const note = noteText.value.trim();
      if (!note) return noteText.focus();
      const selectedAudience = audience.value;
      if (selectedAudience === "public" && !publicComplaint) {
        publicBlocked.classList.remove("hidden");
        return;
      }
      if (selectedAudience === "public" && (!confirmBox.checked || !window.confirm("هل تؤكد نشر هذه الملاحظة للعامة؟"))) return;
      noteSubmit.disabled = true;
      noteSubmit.textContent = "جارٍ الحفظ";
      noteStatus.textContent = "";
      try {
        const result = await api(`/complaints/${encodeURIComponent(complaint.id)}/notes`, {
          method: "POST",
          body: JSON.stringify({
            note,
            audience: selectedAudience,
            is_internal: selectedAudience === "internal"
          })
        });
        noteText.value = "";
        noteStatus.textContent = result.message || "تم حفظ الملاحظة.";
        await options.onNotesChanged?.(result);
      } catch (error) {
        noteStatus.textContent = `لم يتم حفظ الملاحظة: ${error.message}`;
        noteStatus.classList.add("is-error");
      } finally {
        noteSubmit.disabled = false;
        noteSubmit.textContent = "حفظ الملاحظة";
      }
    });
    notesSection.append(notesForm);
    root.append(card, notesSection);
  } else {
    const warning = node("p", "evidence-warning", "طلبات الأدلة والردود لا تُنشر. إذا لم تكن لديك قناة إشعار مرتبطة، تحقق من صفحة المتابعة دورياً.");
    card.append(warning, timeline);
    const fileProblem = (file, position) => {
      const extension = file.name.split(".").pop()?.toLowerCase();
      const typeOk = ACCEPTED_TYPES.has(file.type) || (!file.type && ["jpg", "jpeg", "png", "webp", "pdf"].includes(extension));
      if (position >= MAX_FILES) return "تجاوز الحد الأقصى البالغ 5 ملفات.";
      if (!typeOk) return "النوع غير مدعوم؛ اختر JPEG أو PNG أو WebP أو PDF.";
      if (!file.size) return "الملف فارغ.";
      if (file.size > MAX_FILE_BYTES) return "حجم الملف أكبر من 10 ميغابايت.";
      return "";
    };
    renderTimeline(card, requests, false, complaint.id, async () => {});
    requests.filter((request) => request.status === "pending").forEach((request) => {
      const replyForm = node("form", "evidence-reply-form");
      replyForm.className = "evidence-reply-form";
      replyForm.dataset.testid = "evidence-reply-form";
      replyForm.dataset.requestId = request.id;
      const promptInfo = node("div", "evidence-current-prompt");
      promptInfo.append(node("strong", "", "الرد على هذا الطلب"), node("p", "evidence-prompt", request.prompt || ""));
      const textClone = node("textarea", "field");
      textClone.id = `evidence-reply-text-${request.id}`;
      textClone.dataset.testid = "evidence-reply-text";
      textClone.rows = 3;
      textClone.maxLength = 10000;
      const labelClone = node("label", "field-label", "ردك");
      labelClone.htmlFor = textClone.id;
      const fileClone = node("input", "file-field");
      fileClone.id = `evidence-reply-files-${request.id}`;
      fileClone.dataset.testid = "evidence-reply-files";
      fileClone.type = "file";
      fileClone.multiple = true;
      fileClone.accept = ".jpg,.jpeg,.png,.webp,.pdf,image/jpeg,image/png,image/webp,application/pdf";
      const fileLabelClone = node("label", "field-label", "إرفاق ملفات");
      fileLabelClone.htmlFor = fileClone.id;
      const helpClone = node("p", "text-xs text-gray-500", "حتى 5 ملفات، بصيغة JPEG أو PNG أو WebP أو PDF، بحد أقصى 10 ميغابايت لكل ملف.");
      const listClone = node("ul", "evidence-selected-files");
      const statusClone = node("p", "evidence-inline-status");
      statusClone.dataset.testid = "evidence-reply-status";
      statusClone.setAttribute("role", "status");
      statusClone.setAttribute("aria-live", "polite");
      const submitClone = node("button", "primary-button", "إرسال الرد");
      submitClone.type = "submit";
      submitClone.dataset.testid = "evidence-reply-submit";
      const chosen = [];
      let locked = false;
      let key = makeId();
      const repaint = () => {
        listClone.replaceChildren();
        chosen.forEach((entry, index) => {
          entry.problem = fileProblem(entry.file, index);
          const row = node("li", `evidence-selected-file ${entry.problem ? "is-error" : ""}`);
          row.append(node("span", "", `${entry.file.name} — ${entry.problem || "جاهز للإرسال"}`));
          const remove = node("button", "evidence-remove-file", "إزالة");
          remove.type = "button";
          remove.setAttribute("aria-label", `إزالة الملف ${entry.file.name}`);
          remove.disabled = locked;
          remove.addEventListener("click", () => { chosen.splice(index, 1); repaint(); });
          row.append(remove);
          listClone.append(row);
        });
      };
      fileClone.addEventListener("change", () => {
        [...fileClone.files].forEach((file) => chosen.push({ file }));
        fileClone.value = "";
        repaint();
        statusClone.textContent = chosen.find((entry) => entry.problem)?.problem || "";
      });
      replyForm.append(promptInfo, labelClone, textClone, fileLabelClone, fileClone, helpClone, listClone, statusClone, submitClone);
      replyForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const text = textClone.value.trim();
        const invalidFile = chosen.find((entry) => entry.problem);
        if (!text && !chosen.length) {
          statusClone.textContent = "اكتب رداً أو أرفق ملفاً واحداً على الأقل.";
          statusClone.classList.add("is-error");
          return;
        }
        if (invalidFile) {
          statusClone.textContent = `${invalidFile.file.name}: ${invalidFile.problem}`;
          statusClone.classList.add("is-error");
          return;
        }
        submitClone.disabled = true;
        locked = true;
        textClone.disabled = true; fileClone.disabled = true; repaint();
        submitClone.textContent = "جارٍ رفع الرد";
        statusClone.textContent = "يتم إرسال الرد والمرفقات معاً.";
        statusClone.classList.remove("is-error");
        const body = new FormData();
        body.append("text", text);
        body.append("submission_key", key);
        chosen.forEach(({ file }) => body.append("files", file, file.name));
        let accepted = false;
        try {
          await api(`/complaints/${encodeURIComponent(complaint.id)}/evidence/${encodeURIComponent(request.id)}/reply`, { method: "POST", body });
          accepted = true;
        } catch (error) {
          statusClone.textContent = `تعذر تأكيد استلام الرد. بقي النص والملفات كما هي؛ أعد المحاولة دون تغييرها. ${error.message}`;
          if (error.status && error.status !== 409) {
            locked = false; textClone.disabled = false; fileClone.disabled = false; repaint();
          }
          statusClone.classList.add("is-error");
          submitClone.disabled = false;
          submitClone.textContent = "إرسال الرد";
          return;
        }
        try {
          const fresh = await fetchEvidence(complaint.id);
          requests.splice(0, requests.length, ...fresh);
          renderTimeline(card, requests, false, complaint.id, async () => {});
        } catch {
          statusClone.textContent = "تم استلام الرد، لكن تعذر تحديث سجل الطلبات. استخدم تحديث المتابعة لاحقاً.";
          statusClone.classList.add("is-error");
        }
        textClone.value = "";
        chosen.splice(0);
        repaint();
        key = makeId();
        if (!statusClone.classList.contains("is-error")) statusClone.textContent = "تم استلام الرد.";
        if (accepted) {
          textClone.disabled = true;
          fileClone.disabled = true;
          submitClone.disabled = true;
          submitClone.textContent = "تم استلام الرد";
        } else {
          submitClone.disabled = false;
          submitClone.textContent = "إرسال الرد";
        }
      });
      card.append(replyForm);
    });
    root.append(card);
  }

  if (staff) renderTimeline(card, requests, true, complaint.id, async (updated) => {
    try {
      const fresh = await fetchEvidence(complaint.id);
      requests.splice(0, requests.length, ...fresh);
    } catch {
      requests.splice(0, requests.length, ...updated);
    }
    renderTimeline(card, requests, true, complaint.id, async () => {});
  });
}
