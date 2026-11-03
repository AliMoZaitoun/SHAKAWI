import { api } from "./api.js";

let recoveryToken = null;
const byId = (id) => document.getElementById(id);
const post = (path, body = {}) => api(`/citizens/recovery/${path}`, {
  method: "POST", body: JSON.stringify(body)
});
const run = (action) => async (event) => {
  event.preventDefault();
  const button = event.submitter || event.currentTarget;
  button.disabled = true;
  try { await action(); }
  catch (error) { window.showNotice(error.message, "error"); }
  finally { button.disabled = false; }
};

export async function refreshCitizenAccess() {
  try {
    const { citizen, has_recovery_key: hasKey } = await api("/citizens/recovery/me");
    byId("owner-access").classList.remove("hidden");
    byId("access-state").textContent = `الوصول موثوق. ${citizen.telegram_id ? "تيليغرام مرتبط." : "تيليغرام غير مرتبط."} ${hasKey ? "يوجد مفتاح استعادة." : "لا يوجد مفتاح استعادة؛ يُنصح بإصداره الآن."}`;
    // Fill identity only from an authenticated response; never from typed claims.
    for (const field of ["first_name", "last_name", "phone", "national_id"]) {
      const id = {first_name: "c-first-name", last_name: "c-last-name",
        phone: "c-phone", national_id: "c-national-id"}[field];
      if (!byId(id).disabled) byId(id).value = citizen[field];
    }
    const complaints = await api(`/complaints/citizen/${citizen.id}`);
    const container = byId("citizen-complaints");
    container.replaceChildren();
    const heading = document.createElement("p");
    heading.textContent = complaints.length ? "شكاواك — اضغط لعرض التفاصيل:" : "لا توجد شكاوى مسجلة بعد.";
    container.append(heading);
    for (const item of complaints) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "block border rounded px-3 py-2";
      button.textContent = `${item.title} — ${item.tracking_code}`;
      button.addEventListener("click", () => {
        byId("search-code-input").value = item.tracking_code;
        window.switchTab("view");
        window.searchComplaint();
      });
      container.append(button);
    }
  } catch (error) {
    if (error.status !== 403) throw error;
    byId("owner-access").classList.add("hidden");
    byId("access-state").textContent = "لا توجد جلسة مواطن موثوقة في هذا المتصفح.";
  }
}

export function initRecovery() {
  byId("restore-key-form").addEventListener("submit", run(async () => {
    await post("key/restore", {token: byId("recovery-key").value.trim()});
    byId("recovery-key").value = "";
    await refreshCitizenAccess();
    window.showNotice("تمت الاستعادة. استُهلك المفتاح؛ أصدر مفتاحًا جديدًا واحفظه.", "success");
  }));
  byId("restore-telegram-form").addEventListener("submit", run(async () => {
    const telegramId = Number(byId("recovery-telegram").value);
    if (!Number.isSafeInteger(telegramId) || telegramId <= 0) throw new Error("أدخل معرّف تيليغرام رقميًا صحيحًا.");
    const result = await post("telegram/start", {telegram_id: telegramId, consent: byId("recovery-consent").checked});
    recoveryToken = result.token;
    byId("recovery-command").textContent = `/recover ${result.token}`;
    byId("recovery-pending").classList.remove("hidden");
  }));
  byId("finish-recovery").addEventListener("click", run(async () => {
    await post("telegram/finish", {token: recoveryToken});
    recoveryToken = null;
    byId("recovery-command").textContent = "";
    byId("recovery-pending").classList.add("hidden");
    await refreshCitizenAccess();
    window.showNotice("تمت استعادة الوصول إلى شكاواك.", "success");
  }));
  byId("issue-recovery-key").addEventListener("click", run(async () => {
    const result = await post("key");
    byId("new-recovery-key").textContent = result.key;
    await refreshCitizenAccess();
    window.showNotice("احفظ المفتاح الآن خارج المتصفح. لن يُعرض مرة ثانية.", "info");
  }));
  byId("issue-telegram-link").addEventListener("click", run(async () => {
    if (!byId("link-consent").checked) throw new Error("وافق على وسيلة الربط أولًا.");
    const result = await post("telegram/link");
    byId("link-command").textContent = `/link ${result.token}`;
  }));
  byId("refresh-owner-access").addEventListener("click", run(refreshCitizenAccess));
}
