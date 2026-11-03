import { api } from "./api.js";

let currentUser = null;
let authConfigured = null;
let unauthorizedHandler = () => {};

export function setUnauthorizedHandler(handler) { unauthorizedHandler = handler; }
export function getUser() { return currentUser; }
export function isStaff() { return Boolean(currentUser); }
export function maySeeDirectorate(directorateId) {
  return currentUser?.role === "governor" || (currentUser?.role === "employee" && Number(directorateId) === 2);
}

export async function loadAuthState() {
  try { currentUser = await api("/auth/me"); }
  catch (error) { currentUser = null; if (error.status !== 401) throw error; }
  try { authConfigured = (await api("/auth/config"))?.configured === true; }
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
    const logout = document.createElement("button");
    logout.type = "button"; logout.className = "text-xs font-bold text-brand-dark px-3 py-2 rounded-lg border border-gray-200 hover:bg-gray-50";
    logout.textContent = "تسجيل الخروج"; logout.addEventListener("click", logoutUser);
    root.append(identity, logout);
  } else {
    document.querySelectorAll(".staff-tab").forEach((tab) => tab.classList.remove("visible"));
    const login = document.createElement("button");
    login.type = "button"; login.className = "text-xs font-bold text-brand-dark px-3 py-2 rounded-lg border border-gray-200 hover:bg-gray-50";
    login.textContent = "دخول الموظفين"; login.addEventListener("click", openLogin);
    root.append(login);
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
  catch (error) { if (error.status !== 401) { unauthorizedHandler(error); return; } }
  currentUser = null;
  renderAuthControls();
  window.dispatchEvent(new CustomEvent("shakwa:logout"));
}
