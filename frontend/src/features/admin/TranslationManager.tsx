import { useEffect, useRef, useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Languages, Save, Trash2 } from "lucide-react";
import { api } from "../../shared/api/client";
import { useResource } from "../../shared/api/hooks";
import { useI18n } from "../../shared/i18n/I18n";
import type { Directorate, Language, Permission, Role, Translation } from "../../shared/api/types";
import { UiText } from "../../shared/i18n/UiText";
import { AdminAlert } from "./AdminPage";
import "./admin-ui.css";

type Entity = "roles" | "permissions" | "directorates";
type TranslationForm = { name: string; description: string; location: string };
const emptyTranslation: TranslationForm = { name: "", description: "", location: "" };

export function TranslationManager() {
  const { lang, tText } = useI18n();
  const roles = useResource<Role[]>("/admin/roles", lang);
  const permissions = useResource<Permission[]>("/admin/permissions", lang);
  const directorates = useResource<Directorate[]>("/admin/directorates", lang);
  const languages = useResource<Language[]>("/admin/languages", lang);
  const [entity, setEntity] = useState<Entity>("roles");
  const [recordId, setRecordId] = useState("");
  const [languageCode, setLanguageCode] = useState("");
  const [form, setForm] = useState<TranslationForm>(emptyTranslation);
  const [message, setMessage] = useState("");
  const [isError, setIsError] = useState(false);
  const [busy, setBusy] = useState(false);
  const queryClient = useQueryClient();
  const hydratedTarget = useRef("");

  const resources = [roles, permissions, directorates, languages];
  const listsLoading = resources.some((resource) => resource.isLoading);
  const listsError = resources.find((resource) => resource.error)?.error;
  const records: { id: string; label: string }[] =
    entity === "roles"
      ? (roles.data ?? []).map((role) => ({ id: String(role.id), label: role.name }))
      : entity === "permissions"
        ? (permissions.data ?? []).map((item) => ({ id: item.code, label: item.name }))
        : (directorates.data ?? []).map((item) => ({
            id: String(item.id),
            label: item.hierarchy_path ?? item.name,
          }));
  const translationsKey = ["translations", entity, recordId] as const;
  const query = useQuery({
    queryKey: translationsKey,
    queryFn: () =>
      api<Translation[]>(`/admin/translations/${entity}/${encodeURIComponent(recordId)}`),
    enabled: Boolean(recordId),
    retry: false,
  });
  const selectedTarget = recordId && languageCode ? `${entity}:${recordId}:${languageCode}` : "";
  const activeTranslation = query.data?.find((item) => item.language_code === languageCode);
  const otherLanguages = (languages.data ?? []).filter(
    (language) => language.code !== "ar" && language.is_active !== false,
  );

  useEffect(() => {
    if (!selectedTarget || query.isLoading || hydratedTarget.current === selectedTarget) return;
    const translation = query.data?.find((item) => item.language_code === languageCode);
    setForm({
      name: translation?.name ?? "",
      description: translation?.description ?? "",
      location: translation?.location ?? "",
    });
    hydratedTarget.current = selectedTarget;
  }, [languageCode, query.data, query.isLoading, selectedTarget]);

  function resetSelection(next: { entity?: Entity; recordId?: string; languageCode?: string }) {
    hydratedTarget.current = "";
    setForm(emptyTranslation);
    setMessage("");
    setIsError(false);
    if (next.entity !== undefined) setEntity(next.entity);
    if (next.recordId !== undefined) setRecordId(next.recordId);
    if (next.languageCode !== undefined) setLanguageCode(next.languageCode);
  }

  function setResult(text: string, error = false) {
    setMessage(text);
    setIsError(error);
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!recordId || !languageCode) return;
    setBusy(true);
    setResult("");
    try {
      const saved = await api<Translation>(
        `/admin/translations/${entity}/${encodeURIComponent(recordId)}/${languageCode}`,
        {
          method: "PUT",
          body: entity === "directorates" ? form : { name: form.name, description: form.description },
        },
      );
      queryClient.setQueryData<Translation[]>(translationsKey, (current = []) => [
        ...current.filter((item) => item.language_code !== languageCode),
        saved,
      ]);
      hydratedTarget.current = selectedTarget;
      setForm({
        name: saved.name,
        description: saved.description,
        location: saved.location ?? "",
      });
      setResult(tText("حُفظت الترجمة."));
    } catch (error) {
      setResult(error instanceof Error ? error.message : tText("تعذر حفظ الترجمة."), true);
    } finally {
      setBusy(false);
    }
  }

  async function removeTranslation() {
    if (!activeTranslation || !window.confirm(tText("حذف هذه الترجمة؟"))) return;
    setBusy(true);
    setResult("");
    try {
      await api(
        `/admin/translations/${entity}/${encodeURIComponent(recordId)}/${languageCode}`,
        { method: "DELETE" },
      );
      queryClient.setQueryData<Translation[]>(translationsKey, (current = []) =>
        current.filter((item) => item.language_code !== languageCode),
      );
      hydratedTarget.current = selectedTarget;
      setForm(emptyTranslation);
      setResult(tText("حُذفت الترجمة."));
    } catch (error) {
      setResult(error instanceof Error ? error.message : tText("تعذر حذف الترجمة."), true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel" aria-labelledby="translation-heading">
      <div className="eyebrow">{tText("إدارة السجلات المترجمة")}</div>
      <h2 id="translation-heading">{tText("إدارة الترجمات")}</h2>
      <p className="muted">
        {tText("العربية أساسية ولا يمكن حذف ترجمتها. اختر سجلًا ولغة لعرض القيمة الحالية أو حفظ ترجمة جديدة.")}
      </p>
      <div className="admin-translation-controls">
        <label className="field-label">
          {tText("نوع السجل")}
          <select
            className="field"
            value={entity}
            disabled={listsLoading || busy}
            onChange={(event) => resetSelection({ entity: event.target.value as Entity, recordId: "", languageCode: "" })}
          >
            <option value="roles">{tText("الأدوار")}</option>
            <option value="permissions">{tText("الصلاحيات")}</option>
            <option value="directorates">{tText("المديريات")}</option>
          </select>
        </label>
        <label className="field-label">
          {tText("السجل")}
          <select
            className="field"
            value={recordId}
            disabled={listsLoading || !!listsError || !records.length || busy}
            onChange={(event) => resetSelection({ recordId: event.target.value })}
          >
            <option value="">{tText("اختر سجلًا")}</option>
            {records.map((record) => (
              <option value={record.id} key={record.id}>
                {record.label}
              </option>
            ))}
          </select>
        </label>
        <label className="field-label">
          {tText("اللغة")}
          <select
            className="field"
            value={languageCode}
            disabled={!recordId || listsLoading || !!listsError || busy}
            onChange={(event) => resetSelection({ languageCode: event.target.value })}
          >
            <option value="">{tText("اختر لغة")}</option>
            {otherLanguages.map((language) => (
              <option value={language.code} key={language.code}>
                {language.name} · {language.code}
              </option>
            ))}
          </select>
        </label>
      </div>

      {listsLoading && <div className="skeleton" aria-label={tText("جارٍ التحميل")} />}
      {!listsLoading && listsError && (
        <div className="status error" role="alert">
          {tText("تعذر تحميل قوائم الترجمات.")}
        </div>
      )}
      {!listsLoading && !listsError && !records.length && (
        <div className="admin-empty">{tText("لا توجد سجلات من هذا النوع.")}</div>
      )}
      {!listsLoading && !listsError && recordId && !otherLanguages.length && (
        <div className="status info">{tText("أضف لغة مفعلة من صفحة اللغات أولًا.")}</div>
      )}

      {recordId && languageCode && query.isLoading && (
        <div className="skeleton admin-translation-status" aria-label={tText("جارٍ تحميل الترجمة")} />
      )}
      {recordId && languageCode && query.error && (
        <div className="status error admin-translation-status" role="alert">
          {tText("تعذر تحميل الترجمات.")}
          <button className="btn secondary" type="button" onClick={() => void query.refetch()}>
            <UiText source="إعادة المحاولة" />
          </button>
        </div>
      )}

      {recordId && languageCode && !query.isLoading && !query.error && (
        <>
          <div className={`status ${activeTranslation ? "success" : "info"} admin-translation-status`}>
            <Languages size={16} aria-hidden="true" />
            {activeTranslation
              ? `${tText("توجد ترجمة لهذه اللغة.")} ${languageCode}`
              : `${tText("لا توجد ترجمة بعد. يمكنك إضافتها الآن.")} ${languageCode}`}
          </div>
          <form className="form-grid admin-translation-form" onSubmit={(event) => void save(event)}>
            <label className="field-label">
              {tText("الاسم")}
              <input
                id="translation-name"
                className="field"
                required
                minLength={2}
                value={form.name}
                onChange={(event) => setForm({ ...form, name: event.target.value })}
              />
            </label>
            <label className="field-label">
              {tText("الوصف")}
              <textarea
                id="translation-description"
                className="field"
                value={form.description}
                onChange={(event) => setForm({ ...form, description: event.target.value })}
              />
            </label>
            {entity === "directorates" && (
              <label className="field-label">
                {tText("الموقع")}
                <input
                  className="field"
                  value={form.location}
                  onChange={(event) => setForm({ ...form, location: event.target.value })}
                />
              </label>
            )}
            <div className="row form-field full">
              <button className="btn" disabled={busy}>
                <Save size={16} aria-hidden="true" />
                {busy ? tText("جارٍ الحفظ…") : tText("حفظ الترجمة")}
              </button>
              {activeTranslation && (
                <button
                  className="btn danger"
                  type="button"
                  disabled={busy}
                  onClick={() => void removeTranslation()}
                >
                  <Trash2 size={16} aria-hidden="true" />
                  {tText("حذف الترجمة")}
                </button>
              )}
            </div>
          </form>
        </>
      )}
      <div className="admin-translation-status">
        <AdminAlert text={message} isError={isError} />
      </div>
    </section>
  );
}
