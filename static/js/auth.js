import { api } from "./api.js";

let currentUser = null;
let authConfigured = null;
let demoMode = false;
let unauthorizedHandler = () => {};

export function setUnauthorizedHandler(handler) { unauthorizedHandler = handler; }
export function getUser() { return currentUser; }
export function isStaff() { return Boolean(currentUser); }
export function maySeeDirectorate(directorateId) {
  const grant = currentUser?.permissions?.["complaints.view"];
  if (grant?.scope_type === "global" || currentUser?.role === "governor") return true;
  if (Array.isArray(grant?.directorate_ids)) {
    return grant.directorate_ids.includes(Number(directorateId));
  }
  return currentUser?.role === "employee"
    && Number(directorateId) === Number(currentUser.directorate_id);
}

export async function loadAuthState() {
  try { currentUser = await api("/auth/me"); }
  catch (error) { currentUser = null; if (error.status !== 401) throw error; }
  try {
    const config = await api("/auth/config");
    authConfigured = config?.configured === true;
    demoMode = config?.demo_mode === true;
  }
  catch { authConfigured = null; }
  renderAuthControls();
  return currentUser;
}

export function renderAuthControls() {
  const root = document.getElementById("auth-controls");
  if (!root) return;
  root.replaceChildren();
  if (currentUser) {
    document.querySelectorAll(".staff-tab").forEach((tab) => tab.classList.add("visible"));
    const identity = document.createElement("span");
    identity.className = "hidden md:inline text-xs text-gray-600";
    identity.textContent = `${currentUser.full_name} · ${currentUser.role === "governor" ? "المحافظة" : "موظف"}`;
    const changePassword = document.createElement("button");
    changePassword.type = "button";
    changePassword.className = "text-xs font-bold text-brand-dark px-3 py-2 rounded-lg border border-gray-200 hover:bg-gray-50";
    changePassword.textContent = "تغيير كلمة المرور";
    changePassword.addEventListener("click", openPasswordDialog);
    const logout = document.createElement("button");
    logout.type = "button"; logout.className = "text-xs font-bold text-brand-dark px-3 py-2 rounded-lg border border-gray-200 hover:bg-gray-50";
    logout.textContent = "تسجيل الخروج"; logout.addEventListener("click", logoutUser);
    root.append(identity, changePassword, logout);
    if (demoMode || currentUser.is_demo) {
      const warning = document.createElement("p");
      warning.className = "text-xs text-amber-900 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2";
      warning.textContent = "تنبيه: الحسابات التجريبية ما زالت مفعلة. غيّر كلمة المرور من إجراء «تغيير كلمة المرور» بعد الدخول.";
      warning.setAttribute("role", "status");
      root.append(warning);
    }
  } else {
    document.querySelectorAll(".staff-tab").forEach((tab) => tab.classList.remove("visible"));
    const login = document.createElement("button");
    login.type = "button"; login.className = "text-xs font-bold text-brand-dark px-3 py-2 rounded-lg border border-gray-200 hover:bg-gray-50";
    login.textContent = "دخول الموظفين"; login.addEventListener("click", openLogin);
    root.append(login);
    if (demoMode) {
      const warning = document.createElement("p");
      warning.className = "text-xs text-amber-900 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2";
      warning.textContent = "حسابات تجريبية مفعّلة. على الموظف تغيير كلمة المرور من إجراء الحساب بعد تسجيل الدخول.";
      warning.setAttribute("role", "status");
      root.append(warning);
    }
  }
}

function openPasswordDialog() {
  document.getElementById("password-error").classList.add("hidden");
  document.getElementById("password-form").reset();
  document.getElementById("password-dialog").showModal();
  document.getElementById("current-password").focus();
}

export async function changePassword(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector('[type="submit"]');
  const errorBox = document.getElementById("password-error");
  const current = document.getElementById("current-password").value;
  const next = document.getElementById("new-password").value;
  errorBox.classList.add("hidden");
  if (next.length < 12 || next.length > 256) {
    errorBox.textContent = "يجب أن تتكون كلمة المرور الجديدة من 12 إلى 256 حرفاً.";
    errorBox.classList.remove("hidden");
    return;
  }
  button.disabled = true;
  try {
    currentUser = await api("/auth/change-password", { method: "POST", body: JSON.stringify({
      current_password: current,
      new_password: next
    }) });
    renderAuthControls();
    document.getElementById("password-dialog").close();
    form.reset();
    window.showNotice("تم تغيير كلمة المرور بنجاح. جلستك الحالية ما زالت صالحة.", "success");
    window.dispatchEvent(new CustomEvent("shakwa:password-changed", { detail: currentUser }));
  } catch (error) {
    if (error.status === 401) {
      document.getElementById("password-dialog").close();
      form.reset();
      await logoutUser();
      window.showNotice("انتهت جلسة الدخول. سجل الدخول مجدداً.", "error");
      return;
    }
    errorBox.textContent = error.message;
    errorBox.classList.remove("hidden");
  } finally {
    button.disabled = false;
  }
}

export function openLogin() {
  const dialog = document.getElementById("login-dialog");
  document.getElementById("login-error").classList.add("hidden");
  document.getElementById("login-config-warning").classList.toggle("hidden", authConfigured !== false);
  dialog.showModal();
}

export async function loginUser(event) {
  event.preventDefault();
  const button = event.currentTarget.querySelector('[type="submit"]');
  const errorBox = document.getElementById("login-error");
  button.disabled = true; errorBox.classList.add("hidden");
  try {
    currentUser = await api("/auth/login", { method: "POST", body: JSON.stringify({
      username: document.getElementById("login-username").value.trim(),
      password: document.getElementById("login-password").value
    }) });
    document.getElementById("login-password").value = "";
    document.getElementById("login-dialog").close();
    renderAuthControls();
    window.dispatchEvent(new CustomEvent("shakwa:auth", { detail: currentUser }));
  } catch (error) {
    errorBox.textContent = error.message; errorBox.classList.remove("hidden");
  } finally { button.disabled = false; }
}

export async function logoutUser() {
  try { await api("/auth/logout", { method: "POST" }); }
  catch (error) {
    if (error.status !== 401) {
      unauthorizedHandler(new Error("تعذر تسجيل الخروج. ما زالت الجلسة نشطة؛ تحقق من الاتصال وحاول مجددًا."));
      return false;
    }
  }
  currentUser = null;
  renderAuthControls();
  window.dispatchEvent(new CustomEvent("shakwa:logout"));
  return true;
}
