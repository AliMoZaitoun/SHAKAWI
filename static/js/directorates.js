import { api } from "./api.js";
import { getUser } from "./auth.js";

const byId = (id) => document.getElementById(id);
let publicRows = [];
let adminRows = [];
let publicLoad = null;
let initialized = false;

export function getDirectorateLabel(id) {
  if (id === null || id === undefined || id === "") return "—";
  const item = [...adminRows, ...publicRows].find((row) => Number(row.id) === Number(id));
  return item?.hierarchy_path || item?.name || `مديرية رقم ${id}`;
}

function setSelectOptions(select, rows, placeholder) {
  if (!select) return;
  const previousValue = select.value;
  select.replaceChildren(new Option(placeholder, ""));
  rows.filter((item) => item.is_active).forEach((item) => {
    select.add(new Option(item.hierarchy_path || item.name, String(item.id)));
  });
  if ([...select.options].some((option) => option.value === previousValue)) {
    select.value = previousValue;
  }
}

function updatePublicSelects() {
  setSelectOptions(byId("comp-entity"), publicRows, "اختر المديرية");
  setSelectOptions(byId("public-directorate"), publicRows, "كل الجهات");
  setSelectOptions(byId("stats-directorate"), publicRows, "كل الجهات");
}

export async function loadPublicDirectorates(force = false) {
  if (!force && publicLoad) return publicLoad;
  publicLoad = api("/directorates").then((rows) => {
    publicRows = Array.isArray(rows) ? rows : [];
    updatePublicSelects();
    return publicRows;
  }).catch((error) => {
    publicLoad = null;
    throw error;
  });
  return publicLoad;
}

function canManageDirectorates() {
  return getUser()?.permissions?.["directorates.manage"]?.scope_type === "global";
}

function syncAdminTab() {
  const tab = byId("tab-directorates");
  if (!tab) return;
  const allowed = canManageDirectorates();
  tab.classList.toggle("visible", allowed);
  if (!allowed && byId("sec-directorates") && !byId("sec-directorates").classList.contains("hidden")) {
    window.switchTab("submit");
  }
}

function setListState(message, isError = false) {
  const state = byId("directorates-state");
  if (!state) return;
  state.textContent = message;
  state.dataset.kind = isError ? "error" : "info";
  state.classList.toggle("hidden", !message);
}

function setFormError(message = "") {
  const state = byId("directorate-form-state");
  state.textContent = message;
  state.classList.toggle("hidden", !message);
}

function resetForm() {
  byId("directorate-form").reset();
  byId("directorate-id").value = "";
  byId("directorate-active").checked = true;
  byId("directorate-save").textContent = "إضافة مديرية";
  byId("directorate-cancel").classList.add("hidden");
  setFormError();
  renderParentOptions();
}

function renderParentOptions(editingId = null, selectedParentId = null) {
  const select = byId("directorate-parent");
  if (!select) return;
  const descendants = new Set();
  if (editingId !== null) {
    const pending = [Number(editingId)];
    while (pending.length) {
      const parentId = pending.pop();
      adminRows.filter((item) => Number(item.parent_id) === parentId).forEach((child) => {
        if (!descendants.has(Number(child.id))) {
          descendants.add(Number(child.id));
          pending.push(Number(child.id));
        }
      });
    }
  }

  select.replaceChildren(new Option("بدون أب — مديرية رئيسية", ""));
  adminRows
    .filter((item) => Number(item.id) !== Number(editingId) && !descendants.has(Number(item.id)))
    .filter((item) => item.is_active || Number(item.id) === Number(selectedParentId))
    .forEach((item) => {
      const option = new Option(item.hierarchy_path || item.name, String(item.id));
      option.disabled = !item.is_active;
      select.add(option);
    });
  select.value = selectedParentId ? String(selectedParentId) : "";
}

function appendCell(row, value, className = "p-3") {
  const cell = document.createElement("td");
  cell.className = className;
  cell.textContent = value || "—";
  row.append(cell);
  return cell;
}

function actionButton(label, action, id, className = "secondary-button") {
  const button = document.createElement("button");
  button.type = "button";
  button.className = `${className} text-xs`;
  button.textContent = label;
  button.dataset.action = action;
  button.dataset.id = String(id);
  return button;
}

function renderAdminRows() {
  const body = byId("directorates-table-body");
  body.replaceChildren();
  if (!adminRows.length) {
    setListState("لا توجد مديريات بعد. أضف مديرية رئيسية للبدء.");
    return;
  }

  setListState();
  adminRows.forEach((item) => {
    const row = document.createElement("tr");
    row.dataset.id = String(item.id);
    const nameCell = document.createElement("td");
    nameCell.className = "p-3";
    const path = document.createElement("strong");
    path.textContent = item.hierarchy_path || item.name;
    nameCell.append(path);
    if (item.description) {
      const description = document.createElement("small");
      description.className = "block text-gray-500 mt-1";
      description.textContent = item.description;
      nameCell.append(description);
    }
    row.append(nameCell);
    appendCell(row, item.parent_name || "مديرية رئيسية");
    appendCell(row, item.location);
    appendCell(row, item.current_manager?.full_name);
    appendCell(row, item.is_active ? "مفعّلة" : "معطّلة");

    const actions = document.createElement("td");
    actions.className = "p-3";
    const buttons = document.createElement("div");
    buttons.className = "flex flex-wrap gap-2";
    buttons.append(actionButton("تعديل", "edit", item.id));
    buttons.append(actionButton(item.is_active ? "تعطيل" : "تفعيل", "toggle", item.id));
    buttons.append(actionButton("حذف", "delete", item.id, "danger-button"));
    actions.append(buttons);
    row.append(actions);
    body.append(row);
  });
}

async function loadAdminDirectorates() {
  if (!canManageDirectorates()) return;
  setListState("جارٍ تحميل المديريات…");
  try {
    adminRows = await api("/admin/directorates");
    adminRows = Array.isArray(adminRows) ? adminRows : [];
    renderParentOptions();
    renderAdminRows();
    await loadPublicDirectorates(true);
  } catch (error) {
    setListState(`تعذر تحميل المديريات: ${error.message}`, true);
  }
}

function directoratePayload() {
  const parentValue = byId("directorate-parent").value;
  return {
    name: byId("directorate-name").value.trim(),
    description: byId("directorate-description").value.trim(),
    location: byId("directorate-location").value.trim(),
    is_active: byId("directorate-active").checked,
    parent_id: parentValue ? Number(parentValue) : null,
  };
}

async function saveDirectorate(event) {
  event.preventDefault();
  if (!canManageDirectorates()) return;
  const id = byId("directorate-id").value;
  const button = byId("directorate-save");
  button.disabled = true;
  setFormError();
  try {
    await api(id ? `/admin/directorates/${id}` : "/admin/directorates", {
      method: id ? "PUT" : "POST",
      body: JSON.stringify(directoratePayload()),
    });
    resetForm();
    await loadAdminDirectorates();
    window.showNotice(id ? "تم تحديث المديرية." : "تمت إضافة المديرية.", "success");
  } catch (error) {
    setFormError(error.message);
  } finally {
    button.disabled = false;
  }
}

function beginEdit(id) {
  const item = adminRows.find((row) => Number(row.id) === Number(id));
  if (!item) return;
  byId("directorate-id").value = String(item.id);
  byId("directorate-name").value = item.name || "";
  byId("directorate-description").value = item.description || "";
  byId("directorate-location").value = item.location || "";
  byId("directorate-active").checked = Boolean(item.is_active);
  byId("directorate-save").textContent = "حفظ التعديلات";
  byId("directorate-cancel").classList.remove("hidden");
  renderParentOptions(item.id, item.parent_id);
  byId("directorate-name").focus();
}

async function toggleActive(id) {
  const item = adminRows.find((row) => Number(row.id) === Number(id));
  if (!item) return;
  try {
    await api(`/admin/directorates/${id}`, {
      method: "PUT",
      body: JSON.stringify({
        name: item.name,
        description: item.description || "",
        location: item.location || "",
        is_active: !item.is_active,
        parent_id: item.parent_id ?? null,
      }),
    });
    await loadAdminDirectorates();
  } catch (error) {
    setListState(`تعذر تغيير حالة المديرية: ${error.message}`, true);
  }
}

async function deleteDirectorate(id) {
  const item = adminRows.find((row) => Number(row.id) === Number(id));
  if (!item || !window.confirm(`هل تريد حذف «${item.name}»؟`)) return;
  try {
    await api(`/admin/directorates/${id}`, { method: "DELETE" });
    await loadAdminDirectorates();
  } catch (error) {
    setListState(`تعذر حذف المديرية: ${error.message}`, true);
  }
}

async function handleTableAction(event) {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const { action, id } = button.dataset;
  if (action === "edit") beginEdit(id);
  if (action === "toggle") await toggleActive(id);
  if (action === "delete") await deleteDirectorate(id);
}

export async function initDirectorates() {
  if (initialized) return;
  initialized = true;
  byId("directorate-form").addEventListener("submit", saveDirectorate);
  byId("directorates-table-body").addEventListener("click", handleTableAction);
  byId("directorate-cancel").addEventListener("click", resetForm);
  byId("tab-directorates").addEventListener("click", () => void loadAdminDirectorates());
  window.addEventListener("shakwa:auth", () => {
    syncAdminTab();
    void loadAdminDirectorates();
  });
  window.addEventListener("shakwa:logout", () => {
    syncAdminTab();
    adminRows = [];
    byId("directorates-table-body").replaceChildren();
    setListState("سجّل الدخول بحساب مخوّل لإدارة المديريات.");
    resetForm();
  });

  syncAdminTab();
  try {
    await loadPublicDirectorates();
  } catch (error) {
    setListState(`تعذر تحميل قائمة المديريات: ${error.message}`, true);
  }
  if (canManageDirectorates()) await loadAdminDirectorates();
}
