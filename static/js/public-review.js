import { api } from "./api.js";

function node(tag, text = "") {
  const element = document.createElement(tag);
  element.textContent = text;
  return element;
}

export function reportForm(id, context = "public") {
  const form = node("form");
  form.className = "record-note mt-4";
  const label = node("label", "إبلاغ / اعتراض على نص عام أو قرار إخفائه");
  const reason = node("textarea");
  reason.id = `${context}-report-reason-${id}`;
  label.htmlFor = reason.id;
  reason.className = "field";
  reason.required = true; reason.minLength = 5; reason.maxLength = 2000;
  reason.placeholder = "وضّح موضع المشكلة دون تكرار بيانات حساسة. البلاغ خاص بفريق المراجعة.";
  const submit = node("button", "إرسال للمراجعة");
  submit.type = "submit"; submit.className = "secondary-button";
  const state = node("p"); state.setAttribute("role", "status");
  form.append(label, reason, submit, state);
  form.addEventListener("submit", async (event) => {
    event.preventDefault(); submit.disabled = true;
    try {
      const result = await api(`/complaints/public/${id}/reports`, {
        method: "POST", body: JSON.stringify({ reason: reason.value.trim() })
      });
      state.textContent = result.message; reason.value = "";
    } catch (error) { state.textContent = error.message; }
    finally { submit.disabled = false; }
  });
  return form;
}

export function renderOwnerReview(complaint, root) {
  root.replaceChildren();
  root.append(node("p", complaint.public_review?.message || ""));
  for (const review of complaint.public_review?.history || []) {
    root.append(node("p", `${review.message} السبب: ${review.reason} · ${new Date(review.created_at).toLocaleString("ar")}`));
  }
  if (complaint.is_public) root.append(reportForm(complaint.id, "owner"));
}

export function renderStaffReview(complaint, root, refresh) {
  root.replaceChildren();
  root.append(node("h4", "مراجعة النصوص العامة والبلاغات"));
  root.append(node("p", complaint.public_review?.message || ""));
  if (!complaint.is_public) return;
  const review = complaint.public_review || {};
  const reports = review.reports || [];
  root.append(node("p", `بلاغات بانتظار المراجعة: ${reports.filter((r) => !r.review_id).length}`));
  reports.forEach((report) => root.append(node("p",
    `${report.review_id ? "تمت المراجعة" : "بانتظار المراجعة"} · ${new Date(report.created_at).toLocaleString("ar")} · ${report.reason}`)));
  (review.history || []).forEach((entry) => root.append(node("p",
    `${entry.message} ${entry.reason} · ${entry.author_name} · ${new Date(entry.created_at).toLocaleString("ar")}`)));
  const form = node("form");
  const action = node("select"); action.className = "field"; action.setAttribute("aria-label", "قرار المراجعة");
  const choices = [
    [review.hidden ? "restore" : "hide", review.hidden ? "إعادة إظهار جميع النصوص بعد مراجعتها" : "إخفاء جميع النصوص مؤقتًا"],
    ["dismiss", "إنهاء مراجعة البلاغات دون تغيير العرض"]
  ];
  choices.forEach(([value, text]) => {
    const option = node("option", text); option.value = value; action.append(option);
  });
  const label = node("label", "سبب القرار — سيظهر لصاحب الشكوى، وليس للعامة");
  const reason = node("textarea"); reason.id = "review-decision-reason"; label.htmlFor = reason.id;
  reason.required = true; reason.minLength = 5; reason.maxLength = 2000; reason.className = "field";
  const warning = node("p", "إعادة الإظهار تنشر النصوص الأصلية كلها، بما فيها ملاحظات الحل. راجعها قبل التأكيد. لا يتغير اختيار المواطن للخصوصية.");
  const submit = node("button", "حفظ قرار المراجعة"); submit.type = "submit"; submit.className = "secondary-button";
  const state = node("p"); state.setAttribute("role", "status");
  form.append(action, label, reason, warning, submit, state); root.append(form);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (action.value === "restore" && !window.confirm("هل راجعت جميع النصوص وتؤكد خلوها من المعلومات الحساسة؟ ستظهر للعامة فورًا.")) return;
    submit.disabled = true;
    try {
      const result = await api(`/complaints/${complaint.id}/public-review`, {
        method: "POST", body: JSON.stringify({ action: action.value, reason: reason.value.trim() })
      });
      window.showNotice(`${result.message} — ${result.notification.message}`, "info");
      await refresh(complaint.id);
    } catch (error) { state.textContent = error.message; }
    finally { submit.disabled = false; }
  });
}
