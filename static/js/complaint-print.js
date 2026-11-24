import { api } from "./api.js";
import { getUser } from "./auth.js";

const SECTIONS = [
  ["tracking_code", "رمز المتابعة", "Tracking code"],
  ["title", "عنوان الشكوى", "Complaint title"],
  ["details", "تفاصيل الشكوى", "Complaint details"],
  ["directorate", "الجهة المختصة", "Responsible directorate"],
  ["category", "التصنيف", "Category"],
  ["created_at", "تاريخ التقديم", "Submission date"],
  ["status", "الحالة", "Status"],
  ["progress", "تقدم المعالجة", "Processing progress"],
  ["resolution_report", "تقرير المعالجة", "Resolution report"],
  ["public_updates", "التحديثات", "Updates"],
  ["citizen_contact", "بيانات التواصل", "Contact details"],
];
const ALLOWED_SECTIONS = new Set(SECTIONS.map(([key]) => key));
const DEFAULT_SECTIONS = [
  "tracking_code", "title", "details", "directorate", "category",
  "created_at", "status", "progress", "resolution_report", "public_updates",
];
const DEFAULT_TITLES = { ar: "ملخص الشكوى", en: "Complaint summary" };
const STATUS = {
  ar: { PENDING: "جديدة", IN_PROGRESS: "قيد المعالجة", RESOLVED: "تمت المعالجة", REJECTED: "مرفوضة" },
  en: { PENDING: "New", IN_PROGRESS: "In progress", RESOLVED: "Resolved", REJECTED: "Rejected" },
};

function textElement(tag, className, text = "") {
  const element = document.createElement(tag);
  if (className) element.className = className;
  element.textContent = text;
  return element;
}

function isGlobalTemplateManager() {
  const scope = getUser()?.permissions?.["branding.manage"];
  return scope?.scope_type === "global" || scope?.directorate_ids === null;
}

function isTemplateSection(value) {
  return typeof value === "string" && ALLOWED_SECTIONS.has(value);
}

function formatDate(value, language) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleDateString(language === "en" ? "en" : "ar", {
    year: "numeric", month: "long", day: "numeric",
  });
}

function publicNotes(complaint) {
  return (complaint.notes || []).filter(
    (note) => !note.is_internal && note.audience !== "internal",
  );
}

function appendSection(content, key, heading, complaint, directorateName, language) {
  const section = textElement("section", "complaint-print-section");
  section.append(textElement("h2", "", heading));
  let value;
  if (key === "tracking_code") {
    value = textElement("p", "complaint-print-code", complaint.tracking_code || "—");
    value.dir = "ltr";
  } else if (key === "title") {
    value = textElement("p", "", complaint.title || "—");
  } else if (key === "details") {
    value = textElement("p", "complaint-print-preserve", complaint.details || "—");
  } else if (key === "directorate") {
    value = textElement("p", "", directorateName || "—");
  } else if (key === "category") {
    value = textElement("p", "", complaint.category || "—");
  } else if (key === "created_at") {
    value = textElement("p", "", formatDate(complaint.created_at, language));
  } else if (key === "status") {
    value = textElement("p", "", STATUS[language]?.[complaint.status] || complaint.status || "—");
  } else if (key === "progress") {
    const progress = Math.max(0, Math.min(100, Number(complaint.progress) || 0));
    value = textElement("p", "", `${progress}%`);
  } else if (key === "resolution_report") {
    if (!complaint.resolution_report?.trim()) return;
    value = textElement("p", "complaint-print-preserve", complaint.resolution_report);
  } else if (key === "public_updates") {
    const notes = publicNotes(complaint);
    if (!notes.length) return;
    const list = textElement("div", "complaint-print-updates");
    notes.forEach((note) => {
      const item = textElement("article", "complaint-print-update");
      item.append(textElement("p", "complaint-print-preserve", note.note || ""));
      item.append(textElement("time", "", formatDate(note.created_at, language)));
      list.append(item);
    });
    section.append(list);
    content.append(section);
    return;
  } else if (key === "citizen_contact") {
    if (!complaint.citizen) return;
    const name = `${complaint.citizen.first_name || ""} ${complaint.citizen.last_name || ""}`.trim();
    value = textElement("p", "complaint-print-preserve", [name, complaint.citizen.phone].filter(Boolean).join(" · ") || "—");
  } else {
    return;
  }
  section.append(value);
  content.append(section);
}

export async function openComplaintPrintPreview(complaint, audience, directorateName = "") {
  document.getElementById("complaint-print-dialog")?.remove();
  const language = document.documentElement.lang === "en" ? "en" : "ar";
  const rtl = language === "ar";
  let template;
  let branding;
  try {
    [template, branding] = await Promise.all([
      api("/print-template"),
      api("/branding"),
    ]);
  } catch (error) {
    window.showNotice?.(`تعذر تحميل إعدادات الطباعة: ${error.message}`, "error");
    return;
  }

  const titles = {
    ...DEFAULT_TITLES,
    ...(template?.titles && typeof template.titles === "object" ? template.titles : {}),
  };
  const defaults = Array.isArray(template?.default_sections)
    ? template.default_sections.filter(isTemplateSection)
    : DEFAULT_SECTIONS;
  let selected = new Set(defaults.length ? defaults : DEFAULT_SECTIONS);
  if (audience !== "staff") selected.delete("citizen_contact");
  let customLogo = "";
  let customLogoUrl = "";

  const dialog = document.createElement("dialog");
  dialog.id = "complaint-print-dialog";
  dialog.className = "complaint-print-dialog";
  dialog.dir = rtl ? "rtl" : "ltr";
  dialog.lang = language;
  dialog.setAttribute("aria-labelledby", "complaint-print-heading");

  const layout = textElement("div", "complaint-print-layout");
  const controls = textElement("aside", "complaint-print-controls");
  const header = textElement("header", "complaint-print-header");
  const heading = textElement("h2", "", rtl ? "إعداد ملخص للطباعة" : "Prepare a print summary");
  heading.id = "complaint-print-heading";
  const closeButton = textElement("button", "complaint-print-icon-button", "×");
  closeButton.type = "button";
  closeButton.setAttribute("aria-label", rtl ? "إغلاق" : "Close");
  header.append(heading, closeButton);

  const titleLabel = textElement("label", "complaint-print-label", rtl ? "عنوان الملخص" : "Summary title");
  const titleInput = document.createElement("input");
  titleInput.type = "text";
  titleInput.maxLength = 120;
  titleInput.className = "complaint-print-input";
  titleInput.value = titles[language] || DEFAULT_TITLES[language];
  titleLabel.htmlFor = "complaint-print-title";
  titleInput.id = "complaint-print-title";
  controls.append(titleLabel, titleInput);

  const sectionGroup = document.createElement("fieldset");
  sectionGroup.className = "complaint-print-section-options";
  sectionGroup.append(textElement("legend", "complaint-print-label", rtl ? "الأقسام" : "Sections"));
  for (const [key, arabic, english] of SECTIONS) {
    if (key === "citizen_contact" && audience !== "staff") continue;
    const label = textElement("label", "complaint-print-check");
    const input = document.createElement("input");
    input.type = "checkbox";
    input.value = key;
    input.checked = selected.has(key);
    const text = textElement("span", "", language === "en" ? english : arabic);
    label.append(input, text);
    sectionGroup.append(label);
    input.addEventListener("change", () => {
      if (input.checked) selected.add(key);
      else selected.delete(key);
      renderPreview();
    });
  }
  controls.append(sectionGroup);

  const logoGroup = textElement("section", "complaint-print-logo-controls");
  logoGroup.append(textElement("strong", "", rtl ? "شعار النسخة المطبوعة" : "Printed copy logo"));
  logoGroup.append(textElement("small", "", rtl ? "اختياري؛ يبقى الملف على جهازك فقط." : "Optional; the file stays on this device."));
  const logoInput = document.createElement("input");
  logoInput.type = "file";
  logoInput.accept = "image/png,image/jpeg,image/webp";
  logoInput.className = "complaint-print-visually-hidden";
  logoInput.id = "complaint-print-logo-input";
  const logoButton = textElement("label", "complaint-print-button-secondary", rtl ? "اختيار صورة" : "Choose an image");
  logoButton.htmlFor = logoInput.id;
  logoGroup.append(logoButton, logoInput);
  const logoMessage = textElement("p", "complaint-print-message");
  logoGroup.append(logoMessage);
  const resetLogoButton = textElement(
    "button",
    "complaint-print-button-secondary",
    rtl ? "استخدام شعار المنصة" : "Use platform logo",
  );
  resetLogoButton.type = "button";
  resetLogoButton.hidden = true;
  logoGroup.append(resetLogoButton);
  controls.append(logoGroup);

  const canSave = audience === "staff" && isGlobalTemplateManager();
  let saveButton = null;
  const saveMessage = textElement("p", "complaint-print-message");
  if (canSave) {
    const saveArea = textElement("div", "complaint-print-save-area");
    saveButton = textElement("button", "complaint-print-button-secondary", rtl ? "حفظ كإعداد افتراضي" : "Save as default");
    saveButton.type = "button";
    saveArea.append(saveButton, saveMessage);
    controls.append(saveArea);
  }

  const previewArea = textElement("main", "complaint-print-preview-area");
  const paper = textElement("article", "complaint-print-paper");
  paper.id = "complaint-print-paper";
  paper.dir = rtl ? "rtl" : "ltr";
  const paperHeader = textElement("header", "complaint-print-paper-header");
  const logoAndName = textElement("div", "complaint-print-paper-brand");
  const brandName = textElement("strong", "", rtl ? "خدمة الشكاوى" : "Complaints service");
  const brandSubtext = textElement("span", "", rtl ? "ملخص متابعة" : "Tracking summary");
  const brandText = textElement("div", "complaint-print-brand-text");
  brandText.append(brandName, brandSubtext);
  logoAndName.append(brandText);
  const documentDate = textElement("time", "complaint-print-document-date", formatDate(new Date().toISOString(), language));
  paperHeader.append(logoAndName, documentDate);
  const divider = textElement("div", "complaint-print-divider");
  const paperTitle = textElement("h1", "", titleInput.value || DEFAULT_TITLES[language]);
  const content = textElement("div", "complaint-print-content");
  const paperFooter = textElement("footer", "complaint-print-paper-footer");
  paperFooter.append(
    textElement("span", "", rtl ? "أُعد هذا الملخص من خدمة الشكاوى." : "Prepared by the complaints service."),
    textElement("span", "", rtl ? "للمتابعة، استخدم رمز المتابعة الخاص بك." : "Use your tracking code to follow this complaint."),
  );
  paper.append(paperHeader, divider, paperTitle, content, paperFooter);
  previewArea.append(paper);

  const footer = textElement("footer", "complaint-print-footer");
  footer.append(textElement(
    "p",
    "",
    rtl
      ? "تتضمن النسخة التحديثات غير الداخلية فقط، ولا تتضمن الملفات أو الملاحظات الداخلية."
      : "This copy includes non-internal updates only, and excludes files and internal notes.",
  ));
  const actions = textElement("div", "complaint-print-actions");
  const cancelButton = textElement("button", "complaint-print-button-secondary", rtl ? "إغلاق" : "Close");
  cancelButton.type = "button";
  const printButton = textElement("button", "complaint-print-button-primary", rtl ? "طباعة الملخص" : "Print summary");
  printButton.type = "button";
  actions.append(cancelButton, printButton);
  footer.append(actions);
  layout.append(controls, previewArea);
  dialog.append(header, layout, footer);
  document.body.append(dialog);

  function renderBrandLogo() {
    const old = logoAndName.querySelector(".complaint-print-logo");
    if (old) old.remove();
    const source = customLogoUrl || (branding?.logo_url
      ? `${branding.logo_url}${branding.logo_url.includes("?") ? "&" : "?"}v=${Number(branding.logo_version) || 0}`
      : "");
    if (source) {
      const image = document.createElement("img");
      image.className = "complaint-print-logo";
      image.alt = "";
      image.src = source;
      logoAndName.prepend(image);
      return;
    }
    const originalMark = document.getElementById("brand-logo-fallback");
    if (originalMark) {
      const mark = originalMark.cloneNode(true);
      mark.removeAttribute("id");
      mark.classList.add("complaint-print-logo");
      mark.removeAttribute("hidden");
      mark.setAttribute("aria-hidden", "true");
      logoAndName.prepend(mark);
    }
  }

  function renderPreview() {
    paperTitle.textContent = titleInput.value.trim() || DEFAULT_TITLES[language];
    content.replaceChildren();
    if (!selected.size) {
      content.append(textElement(
        "p", "complaint-print-empty",
        rtl ? "اختر قسمًا واحدًا على الأقل للمعاينة." : "Choose at least one section to preview.",
      ));
    } else {
      for (const [key, arabic, english] of SECTIONS) {
        if (!selected.has(key) || (key === "citizen_contact" && audience !== "staff")) continue;
        appendSection(content, key, language === "en" ? english : arabic, complaint, directorateName, language);
      }
    }
    printButton.disabled = selected.size === 0;
  }

  function closeDialog() {
    if (dialog.open) dialog.close();
  }

  titleInput.addEventListener("input", renderPreview);
  closeButton.addEventListener("click", closeDialog);
  cancelButton.addEventListener("click", closeDialog);
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) closeDialog();
  });
  dialog.addEventListener("close", () => {
    if (customLogoUrl) URL.revokeObjectURL(customLogoUrl);
    dialog.remove();
  }, { once: true });
  logoInput.addEventListener("change", () => {
    const file = logoInput.files?.[0];
    logoInput.value = "";
    logoMessage.textContent = "";
    if (!file) return;
    if (!["image/png", "image/jpeg", "image/webp"].includes(file.type)) {
      logoMessage.textContent = rtl ? "اختر ملف PNG أو JPEG أو WebP." : "Choose a PNG, JPEG, or WebP file.";
      return;
    }
    if (file.size > 2 * 1024 * 1024) {
      logoMessage.textContent = rtl ? "يجب ألا يتجاوز حجم الشعار 2 ميبيبايت." : "The logo must be 2 MiB or smaller.";
      return;
    }
    if (customLogoUrl) URL.revokeObjectURL(customLogoUrl);
    customLogo = file.name;
    customLogoUrl = URL.createObjectURL(file);
    resetLogoButton.hidden = false;
    logoMessage.textContent = `${rtl ? "شعار محلي:" : "Local logo:"} ${customLogo}`;
    renderBrandLogo();
  });
  resetLogoButton.addEventListener("click", () => {
    if (customLogoUrl) URL.revokeObjectURL(customLogoUrl);
    customLogoUrl = "";
    customLogo = "";
    resetLogoButton.hidden = true;
    logoMessage.textContent = "";
    renderBrandLogo();
  });
  printButton.addEventListener("click", () => window.print());
  saveButton?.addEventListener("click", async () => {
    if (!selected.size) {
      saveMessage.textContent = rtl ? "اختر قسمًا واحدًا على الأقل." : "Choose at least one section.";
      return;
    }
    saveButton.disabled = true;
    saveMessage.textContent = "";
    try {
      titles[language] = titleInput.value.trim() || DEFAULT_TITLES[language];
      await api("/admin/settings/print-template", {
        method: "PUT",
        body: { titles, default_sections: [...selected] },
      });
      saveMessage.textContent = rtl ? "تم حفظ الإعدادات الافتراضية." : "Default settings saved.";
    } catch (error) {
      saveMessage.textContent = error.message || (rtl ? "تعذر حفظ الإعدادات." : "Could not save settings.");
    } finally {
      saveButton.disabled = false;
    }
  });

  renderBrandLogo();
  renderPreview();
  dialog.showModal();
}
