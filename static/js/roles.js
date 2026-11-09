import { api } from "./api.js";
import { getUser } from "./auth.js";

const byId = (id) => document.getElementById(id);
let roles = [];
let permissions = [];
let languages = [];
let editingRoleCode = "";
let initialized = false;

function canManageRoles() {
  return getUser()?.permissions?.["rbac.manage"]?.scope_type === "global";
}

function syncAdminTab() {
  const tab = byId("tab-roles");
  if (!tab) return;
  const allowed = canManageRoles();
  tab.classList.toggle("visible", allowed);
  if (!allowed && byId("sec-roles") && !byId("sec-roles").classList.contains("hidden")) {
    window.switchTab("submit");
  }
}

function setState(message, isError = false) {
  const state = byId("roles-state");
  state.textContent = message;
  state.dataset.kind = isError ? "error" : "info";
  state.classList.toggle("hidden", !message);
}

function setFormState(message = "", isError = false) {
  const state = byId("role-form-state");
  state.textContent = message;
  state.classList.toggle("hidden", !message);
  state.classList.toggle("text-red-700", isError);
  state.classList.toggle("text-green-700", !isError);
}

function resetRoleForm() {
  byId("role-form").reset();
  byId("role-id").value = "";
  editingRoleCode = "";
  byId("role-code").disabled = false;
  byId("role-form-title").textContent = "إنشاء دور";
  byId("role-save").textContent = "إنشاء الدور";
  byId("role-cancel").classList.add("hidden");
  setFormState();
  renderPermissionChecks([]);
}

function renderPermissionChecks(selected = []) {
  const root = byId("role-permissions");
  root.replaceChildren();
  permissions.forEach((permission) => {
    const label = document.createElement("label");
    label.className = "flex gap-2 items-start bg-white border rounded-lg p-3 text-sm";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.value = permission.code;
    checkbox.checked = selected.includes(permission.code);
    checkbox.disabled = editingRoleCode === "system_admin";
    checkbox.className = "mt-1";
    const copy = document.createElement("span");
    const title = document.createElement("b");
    title.textContent = permission.name;
    const detail = document.createElement("small");
    detail.className = "block text-gray-500";
    detail.textContent = `${permission.code} · ${permission.description || ""}`;
    copy.append(title, detail);
    label.append(checkbox, copy);
    root.append(label);
  });
}

function renderRoles() {
  const root = byId("roles-list");
  root.replaceChildren();
  roles.forEach((role) => {
    const card = document.createElement("article");
    card.className = "border rounded-xl p-4";
    const heading = document.createElement("div");
    heading.className = "flex items-start justify-between gap-3";
    const title = document.createElement("h4");
    title.className = "font-bold text-brand-dark";
    title.textContent = role.name;
    const code = document.createElement("code");
    code.className = "text-xs bg-gray-100 rounded px-2 py-1";
    code.textContent = role.code;
    heading.append(title, code);
    const description = document.createElement("p");
    description.className = "text-sm text-gray-500 mt-2";
    description.textContent = role.description || "لا يوجد وصف.";
    const granted = document.createElement("p");
    granted.className = "text-xs text-gray-600 mt-2";
    granted.textContent = role.permissions.length
      ? role.permissions.map((codeValue) => permissions.find((item) => item.code === codeValue)?.name || codeValue).join(" · ")
      : "لا توجد صلاحيات مسندة";
    const actions = document.createElement("div");
    actions.className = "flex gap-2 mt-3";
    const edit = document.createElement("button");
    edit.type = "button";
    edit.className = "secondary-button text-xs";
    edit.textContent = "تعديل";
    edit.addEventListener("click", () => beginEdit(role));
    actions.append(edit);
    if (!role.is_system) {
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "secondary-button text-xs text-red-700";
      remove.textContent = "حذف";
      remove.addEventListener("click", () => void deleteRole(role));
      actions.append(remove);
    } else {
      const system = document.createElement("span");
      system.className = "text-xs text-gray-500 self-center";
      system.textContent = "دور نظامي";
      actions.append(system);
    }
    card.append(heading, description, granted, actions);
    root.append(card);
  });
  renderTranslationRecords();
}

function beginEdit(role) {
  byId("role-id").value = String(role.id);
  editingRoleCode = role.code;
  byId("role-code").value = role.code;
  byId("role-code").disabled = true;
  byId("role-name").value = role.name;
  byId("role-description").value = role.description || "";
  byId("role-form-title").textContent = `تعديل الدور: ${role.name}`;
  byId("role-save").textContent = "حفظ التعديلات";
  byId("role-cancel").classList.remove("hidden");
  setFormState();
  renderPermissionChecks(role.permissions);
  byId("role-form").scrollIntoView({ behavior: "smooth", block: "start" });
}

async function loadCatalog() {
  if (!canManageRoles()) {
    setState("تسجيل الدخول بحساب مخوّل لإدارة الأدوار والصلاحيات.");
    return;
  }
  setState("جارٍ تحميل الأدوار والصلاحيات…");
  try {
    const [roleRows, permissionRows, languageRows] = await Promise.all([
      api("/admin/roles"),
      api("/admin/permissions"),
      api("/admin/languages"),
    ]);
    roles = Array.isArray(roleRows) ? roleRows : [];
    permissions = Array.isArray(permissionRows) ? permissionRows : [];
    languages = Array.isArray(languageRows) ? languageRows : [];
    renderPermissionChecks([]);
    renderRoles();
    renderLanguages();
    setState("");
  } catch (error) {
    setState(`تعذر تحميل الأدوار والصلاحيات: ${error.message}`, true);
  }
}

function renderLanguages() {
  const select = byId("role-translation-language");
  const previous = select.value;
  select.replaceChildren(new Option("اختر اللغة", ""));
  languages.filter((language) => language.is_active).forEach((language) => {
    select.add(new Option(`${language.name} (${language.code})`, language.code));
  });
  if ([...select.options].some((option) => option.value === previous)) select.value = previous;
}

function renderTranslationRecords() {
  const entity = byId("role-translation-entity").value;
  const select = byId("role-translation-record");
  const previous = select.value;
  select.replaceChildren(new Option("اختر السجل", ""));
  const rows = entity === "roles"
    ? roles.map((role) => ({ id: String(role.id), name: role.name }))
    : permissions.map((permission) => ({ id: permission.code, name: permission.name }));
  rows.forEach((row) => select.add(new Option(row.name, row.id)));
  if ([...select.options].some((option) => option.value === previous)) select.value = previous;
  void loadSelectedTranslation();
}

async function loadSelectedTranslation() {
  const entity = byId("role-translation-entity").value;
  const recordId = byId("role-translation-record").value;
  const language = byId("role-translation-language").value;
  const form = byId("role-translation-form");
  const remove = byId("role-translation-delete");
  if (!recordId || !language) {
    form.classList.add("hidden");
    return;
  }
  form.classList.remove("hidden");
  remove.classList.toggle("hidden", language === "ar");
  byId("role-translation-name").value = "";
  byId("role-translation-description").value = "";
  try {
    const rows = await api(`/admin/translations/${entity}/${encodeURIComponent(recordId)}`);
    const translation = rows.find((row) => row.language_code === language);
    if (translation) {
      byId("role-translation-name").value = translation.name || "";
      byId("role-translation-description").value = translation.description || "";
    } else if (language === "ar") {
      const row = entity === "roles"
        ? roles.find((item) => String(item.id) === recordId)
        : permissions.find((item) => item.code === recordId);
      byId("role-translation-name").value = row?.name || "";
      byId("role-translation-description").value = row?.description || "";
    }
  } catch (error) {
    setState(`تعذر تحميل الترجمة: ${error.message}`, true);
  }
}

async function saveRole(event) {
  event.preventDefault();
  const id = byId("role-id").value;
  const permissionCodes = [...byId("role-permissions").querySelectorAll('input[type="checkbox"]:checked')]
    .map((input) => input.value);
  const payload = {
    name: byId("role-name").value.trim(),
    description: byId("role-description").value.trim(),
    permissions: permissionCodes,
  };
  if (!id) {
    payload.code = byId("role-code").value.trim();
  }
  byId("role-save").disabled = true;
  setFormState();
  try {
    await api(id ? `/admin/roles/${id}` : "/admin/roles", {
      method: id ? "PUT" : "POST",
      body: JSON.stringify(payload),
    });
    resetRoleForm();
    await loadCatalog();
    setState("تم حفظ الدور وتسجيل التغيير.");
  } catch (error) {
    setFormState(`تعذر حفظ الدور: ${error.message}`, true);
  } finally {
    byId("role-save").disabled = false;
  }
}

async function deleteRole(role) {
  if (!window.confirm(`هل تريد حذف الدور «${role.name}»؟ لا يمكن حذف دور نظامي أو دور مسند لموظف.`)) return;
  try {
    await api(`/admin/roles/${role.id}`, { method: "DELETE" });
    await loadCatalog();
    setState("تم حذف الدور.");
  } catch (error) {
    setState(`تعذر حذف الدور: ${error.message}`, true);
  }
}

async function saveTranslation(event) {
  event.preventDefault();
  const entity = byId("role-translation-entity").value;
  const recordId = byId("role-translation-record").value;
  const language = byId("role-translation-language").value;
  const name = byId("role-translation-name").value.trim();
  const description = byId("role-translation-description").value.trim();
  try {
    if (language === "ar") {
      if (entity === "roles") {
        const role = roles.find((item) => String(item.id) === recordId);
        await api(`/admin/roles/${recordId}`, {
          method: "PUT",
          body: JSON.stringify({ name, description, permissions: role.permissions }),
        });
      } else {
        await api(`/admin/permissions/${encodeURIComponent(recordId)}`, {
          method: "PATCH",
          body: JSON.stringify({ name, description }),
        });
      }
    } else {
      await api(`/admin/translations/${entity}/${encodeURIComponent(recordId)}/${language}`, {
        method: "PUT",
        body: JSON.stringify({ name, description }),
      });
    }
    await loadCatalog();
    await loadSelectedTranslation();
    setState("تم حفظ الترجمة.");
  } catch (error) {
    setState(`تعذر حفظ الترجمة: ${error.message}`, true);
  }
}

async function deleteTranslation() {
  const entity = byId("role-translation-entity").value;
  const recordId = byId("role-translation-record").value;
  const language = byId("role-translation-language").value;
  if (!recordId || !language || language === "ar" || !window.confirm("حذف الترجمة المحددة؟")) return;
  try {
    await api(`/admin/translations/${entity}/${encodeURIComponent(recordId)}/${language}`, {
      method: "DELETE",
    });
    await loadSelectedTranslation();
    setState("تم حذف الترجمة.");
  } catch (error) {
    setState(`تعذر حذف الترجمة: ${error.message}`, true);
  }
}

export async function initRoles() {
  if (initialized) return;
  initialized = true;
  byId("role-form").addEventListener("submit", saveRole);
  byId("role-cancel").addEventListener("click", resetRoleForm);
  byId("role-translation-entity").addEventListener("change", renderTranslationRecords);
  byId("role-translation-record").addEventListener("change", () => void loadSelectedTranslation());
  byId("role-translation-language").addEventListener("change", () => void loadSelectedTranslation());
  byId("role-translation-form").addEventListener("submit", saveTranslation);
  byId("role-translation-delete").addEventListener("click", () => void deleteTranslation());
  byId("tab-roles").addEventListener("click", () => void loadCatalog());
  window.addEventListener("shakwa:auth", () => {
    syncAdminTab();
    if (canManageRoles()) void loadCatalog();
  });
  window.addEventListener("shakwa:logout", () => {
    syncAdminTab();
    roles = [];
    permissions = [];
    byId("roles-list").replaceChildren();
    byId("role-permissions").replaceChildren();
    byId("role-translation-form").classList.add("hidden");
    resetRoleForm();
    setState("سجّل الدخول بحساب مخوّل لإدارة الأدوار والصلاحيات.");
  });
  syncAdminTab();
  if (canManageRoles()) await loadCatalog();
}
