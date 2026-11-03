import { api } from "./api.js";

let recoveryToken = null;
let trustedCitizenId = null;
let hasRecoveryKey = false;
let refreshSequence = 0;
let ownershipVersion = 0;
let keyIssuanceInProgress = false;
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
function clearIssuedKey() {
  for (const [outputId, actionsId] of [
    ["new-recovery-key", "owner-key-save-actions"],
    ["post-submit-recovery-key", "post-submit-key-save-actions"]
  ]) {
    byId(outputId).textContent = "";
    byId(outputId).classList.add("hidden");
    byId(actionsId).classList.add("hidden");
  }
}
function setPostSubmitAccessState() {
  const button = byId("post-submit-issue-recovery-key");
  const message = byId("post-submit-key-eligibility");
  if (trustedCitizenId) {
    button.classList.remove("hidden");
    message.textContent = hasRecoveryKey
      ? "جلستك موثوقة. يوجد مفتاح حالي؛ إصدار مفتاح جديد سيُبطل المفتاح السابق بعد تأكيدك."
      : "يظهر الإصدار للمواطن ذي الجلسة الموثوقة فقط. لا يمكن لرمز المتابعة وحده إصدار مفتاح استعادة.";
  } else {
    button.classList.add("hidden");
    message.textContent = "لإصدار مفتاح يلزم وجود جلسة مواطن موثوقة؛ رمز متابعة الشكوى وحده لا يمنح صلاحية استعادة الحساب.";
  }
}
function exposeKey(outputId, actionsId, key) {
  const output = byId(outputId);
  output.textContent = key;
  output.classList.remove("hidden");
  byId(actionsId).classList.remove("hidden");
}
async function issueRecoveryKey(outputId, actionsId) {
  if (keyIssuanceInProgress) return;
  keyIssuanceInProgress = true;
  const issueButtons = [byId("issue-recovery-key"), byId("post-submit-issue-recovery-key")];
  issueButtons.forEach((button) => { button.disabled = true; });
  try {
    if (!trustedCitizenId) throw new Error("إصدار المفتاح متاح فقط في جلسة مواطن موثوقة.");
    if (hasRecoveryKey && !window.confirm("لديك مفتاح استعادة صالح. إصدار مفتاح جديد سيُبطل المفتاح السابق. هل تريد الاستبدال؟")) return;
    const ownerAtStart = trustedCitizenId;
    const versionAtStart = ownershipVersion;
    const result = await post("key");
    if (trustedCitizenId !== ownerAtStart || ownershipVersion !== versionAtStart) return;
    hasRecoveryKey = true;
    clearIssuedKey();
    exposeKey(outputId, actionsId, result.key);
    setPostSubmitAccessState();
    await refreshCitizenAccess();
    window.showNotice("احفظ المفتاح الآن خارج المتصفح. لن يُعرض مرة ثانية؛ لا تشاركه.", "info");
  } finally {
    keyIssuanceInProgress = false;
    issueButtons.forEach((button) => { button.disabled = false; });
  }
}
async function copyKey(outputId) {
  const output = byId(outputId);
  const value = output.textContent.trim();
  if (!value) return;
  try {
    await navigator.clipboard.writeText(value);
    window.showNotice("تم نسخ المفتاح. احفظه في مكان خاص وآمن.", "success");
  } catch {
    output.focus();
    const selection = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(output);
    selection.removeAllRanges();
    selection.addRange(range);
    window.showNotice("تعذر النسخ تلقائيًا؛ تم تحديد المفتاح. انسخه يدويًا واحفظه بأمان.", "info");
  }
}
function downloadKey(outputId) {
  const value = byId(outputId).textContent.trim();
  if (!value) return;
  const blob = new Blob([`${value}\n`], {type: "text/plain;charset=utf-8"});
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "shakwa-recovery-key.txt";
  link.click();
  URL.revokeObjectURL(url);
  window.showNotice("تم تنزيل المفتاح. انقل الملف إلى مكان خاص وآمن ولا تشاركه.", "info");
}

export async function refreshCitizenAccess() {
  const sequence = ++refreshSequence;
  try {
    const { citizen, has_recovery_key: hasKey } = await api("/citizens/recovery/me");
    if (sequence !== refreshSequence) return Boolean(trustedCitizenId);
    if (trustedCitizenId !== citizen.id) {
      trustedCitizenId = citizen.id;
      ownershipVersion += 1;
      clearIssuedKey();
    }
    hasRecoveryKey = Boolean(hasKey);
    byId("owner-access").classList.remove("hidden");
    byId("access-state").textContent = `الوصول موثوق. ${citizen.telegram_id ? "تيليغرام مرتبط." : "تيليغرام غير مرتبط."} ${hasKey ? "يوجد مفتاح استعادة." : "لا يوجد مفتاح استعادة؛ يمكنك إصداره اختياريًا."}`;
    setPostSubmitAccessState();
    // Fill identity only from an authenticated response; never from typed claims.
    for (const field of ["first_name", "last_name", "phone", "national_id"]) {
      const id = {first_name: "c-first-name", last_name: "c-last-name",
        phone: "c-phone", national_id: "c-national-id"}[field];
      if (!byId(id).disabled) byId(id).value = citizen[field];
    }
    const ownerId = citizen.id;
    const complaints = await api(`/complaints/citizen/${ownerId}`);
    if (sequence !== refreshSequence || trustedCitizenId !== ownerId) return Boolean(trustedCitizenId);
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
    return true;
  } catch (error) {
    if (sequence !== refreshSequence) return Boolean(trustedCitizenId);
    if (error.status !== 403) throw error;
    trustedCitizenId = null;
    hasRecoveryKey = false;
    ownershipVersion += 1;
    clearIssuedKey();
    byId("owner-access").classList.add("hidden");
    byId("access-state").textContent = "لا توجد جلسة مواطن موثوقة في هذا المتصفح.";
    setPostSubmitAccessState();
    return false;
  }
}

export function initRecovery() {
  setPostSubmitAccessState();
  byId("open-citizen-access").addEventListener("click", () => {
    window.switchTab("submit");
    byId("citizen-access").open = true;
    byId("citizen-access").scrollIntoView({behavior: "smooth", block: "start"});
  });
  byId("restore-key-form").addEventListener("submit", run(async () => {
    await post("key/restore", {token: byId("recovery-key").value.trim()});
    byId("recovery-key").value = "";
    clearIssuedKey();
    hasRecoveryKey = false;
    await refreshCitizenAccess();
    window.showNotice("تمت الاستعادة. استُهلك المفتاح؛ يمكنك إصدار مفتاح جديد وحفظه.", "success");
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
  const issueFrom = (buttonId, outputId, actionsId) => {
    byId(buttonId).addEventListener("click", async (event) => {
      const button = event.currentTarget;
      if (button.disabled) return;
      button.disabled = true;
      try { await issueRecoveryKey(outputId, actionsId); }
      catch (error) { window.showNotice(error.message, "error"); }
      finally { button.disabled = false; }
    });
  };
  issueFrom("issue-recovery-key", "new-recovery-key", "owner-key-save-actions");
  issueFrom("post-submit-issue-recovery-key", "post-submit-recovery-key", "post-submit-key-save-actions");
  byId("copy-owner-recovery-key").addEventListener("click", () => copyKey("new-recovery-key"));
  byId("copy-post-submit-recovery-key").addEventListener("click", () => copyKey("post-submit-recovery-key"));
  byId("download-owner-recovery-key").addEventListener("click", () => downloadKey("new-recovery-key"));
  byId("download-post-submit-recovery-key").addEventListener("click", () => downloadKey("post-submit-recovery-key"));
  byId("issue-telegram-link").addEventListener("click", run(async () => {
    if (!byId("link-consent").checked) throw new Error("وافق على وسيلة الربط أولًا.");
    const result = await post("telegram/link");
    byId("link-command").textContent = `/link ${result.token}`;
  }));
  byId("refresh-owner-access").addEventListener("click", run(refreshCitizenAccess));
}
