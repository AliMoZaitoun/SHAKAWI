import { api } from "./api.js";
import { getUser } from "./auth.js";
import { formatComplaintDuration } from "./complaint-types.js";

const byId = (id) => document.getElementById(id);
const durationFactors = { minutes: 1, hours: 60, days: 1440, weeks: 10080 };
let types = [];

function canManage() {
  return getUser()?.permissions?.["complaint_types.manage"]?.scope_type === "global";
}

function setState(message, error = false) {
  const root = byId("complaint-types-state");
  root.textContent = message;
  root.dataset.kind = error ? "error" : "info";
  root.classList.toggle("hidden", !message);
}

function setFormState(message = "", error = false) {
  const root = byId("complaint-type-form-state");
  root.textContent = message;
  root.classList.toggle("hidden", !message);
  root.classList.toggle("text-red-700", error);
  root.classList.toggle("text-green-700", !error);
}

function render() {
  const root = byId("complaint-types-table-body");
  root.replaceChildren();
  types.forEach((type) => {
    const row = document.createElement("tr");
    const info = document.createElement("td");
    info.className = "p-3";
    const name = document.createElement("b");
    name.textContent = type.name;
    const description = document.createElement("p");
    description.className = "text-gray-500 mt-1";
    description.textContent = type.description || "—";
    info.append(name, description);
    const sla = document.createElement("td");
    sla.className = "p-3";
    sla.textContent = type.code === "other"
      ? "لا توجد مهلة"
      : type.sla_duration_minutes
        ? formatComplaintDuration(type.sla_duration_minutes)
        : "غير محددة بعد";
    const status = document.createElement("td");
    status.className = "p-3";
    status.textContent = type.is_active ? "نشط" : "معطل";
    const actions = document.createElement("td");
    actions.className = "p-3";
    const edit = document.createElement("button");
    edit.type = "button";
    edit.className = "secondary-button text-xs";
    edit.textContent = "تعديل";
    edit.addEventListener("click", () => beginEdit(type));
    actions.append(edit);
    row.append(info, sla, status, actions);
    root.append(row);
  });
}

function openDialog(type = null) {
  const form = byId("complaint-type-form");
  form.reset();
  byId("complaint-type-id").value = type ? String(type.id) : "";
  byId("complaint-type-name").value = type?.name || "";
  byId("complaint-type-description").value = type?.description || "";
  byId("complaint-type-active").checked = type ? type.is_active : true;
  byId("complaint-type-dialog-title").textContent = type ? "تعديل نوع الشكوى" : "نوع شكوى جديد";
  const minutes = type?.sla_duration_minutes || 0;
  const unit = minutes && minutes % 10080 === 0
    ? "weeks"
    : minutes && minutes % 1440 === 0
      ? "days"
      : minutes && minutes % 60 === 0
        ? "hours"
        : "minutes";
  byId("complaint-type-amount").value = minutes ? String(minutes / durationFactors[unit]) : "";
  byId("complaint-type-unit").value = unit;
  const isOther = type?.code === "other";
  byId("complaint-type-sla-fields").classList.toggle("hidden", isOther);
  byId("complaint-type-amount").required = !isOther && (!type || type.is_active);
  byId("complaint-type-active").disabled = isOther;
  setFormState();
  byId("complaint-type-dialog").showModal();
}

function beginEdit(type) {
  openDialog(type);
}

async function loadAdminTypes() {
  if (!canManage()) {
    setState("تسجيل الدخول بحساب يملك صلاحية إدارة أنواع الشكاوى.");
    return;
  }
  setState("جارٍ تحميل أنواع الشكاوى…");
  try {
    const result = await api("/admin/complaint-types");
    types = Array.isArray(result) ? result : [];
    render();
    setState("");
  } catch (error) {
    setState(`تعذر تحميل أنواع الشكاوى: ${error.message}`, true);
  }
}

async function saveType(event) {
  event.preventDefault();
  const id = byId("complaint-type-id").value;
  const current = types.find((item) => String(item.id) === id);
  const other = current?.code === "other";
  const amount = Number(byId("complaint-type-amount").value);
  const unit = byId("complaint-type-unit").value;
  const duration = other ? null : amount * (durationFactors[unit] || 1);
  if (!other && byId("complaint-type-active").checked &&
      (!Number.isSafeInteger(duration) || duration < 1 || duration > 5256000)) {
    setFormState("أدخل مدة صحيحة لا تتجاوز عشر سنوات.", true);
    return;
  }
  byId("complaint-type-save").disabled = true;
  setFormState();
  try {
    await api(id ? `/admin/complaint-types/${id}` : "/admin/complaint-types", {
      method: id ? "PUT" : "POST",
      body: JSON.stringify({
        name: byId("complaint-type-name").value.trim(),
        description: byId("complaint-type-description").value.trim(),
        sla_duration_minutes: duration,
        ...(id ? { is_active: byId("complaint-type-active").checked } : {}),
      }),
    });
    byId("complaint-type-dialog").close();
    await loadAdminTypes();
    setState("تم حفظ نوع الشكوى.");
  } catch (error) {
    setFormState(`تعذر الحفظ: ${error.message}`, true);
  } finally {
    byId("complaint-type-save").disabled = false;
  }
}

let initialized = false;
export async function initComplaintTypesAdmin() {
  if (!initialized) {
    initialized = true;
    byId("complaint-type-add").addEventListener("click", () => openDialog());
    byId("complaint-type-form").addEventListener("submit", saveType);
    byId("complaint-type-close").addEventListener("click", () => byId("complaint-type-dialog").close());
    byId("complaint-type-cancel").addEventListener("click", () => byId("complaint-type-dialog").close());
    byId("tab-complaint-types").addEventListener("click", () => void loadAdminTypes());
    window.addEventListener("shakwa:auth", () => void loadAdminTypes());
    window.addEventListener("shakwa:logout", () => {
      types = [];
      byId("complaint-types-table-body").replaceChildren();
      setState("سجّل الدخول بحساب مخوّل لإدارة أنواع الشكاوى.");
    });
  }
  if (canManage()) await loadAdminTypes();
}
