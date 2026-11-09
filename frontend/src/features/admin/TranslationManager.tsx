import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../shared/api/client";
import { useResource } from "../../shared/api/hooks";
import { useI18n } from "../../shared/i18n/I18n";
import type { Directorate, Language, Permission, Role, Translation } from "../../shared/api/types";
import { UiText } from "../../shared/i18n/UiText";

type Entity = "roles" | "permissions" | "directorates";

export function TranslationManager() {
  const { lang, tText } = useI18n();
  const roles = useResource<Role[]>("/admin/roles", lang);
  const permissions = useResource<Permission[]>("/admin/permissions", lang);
  const directorates = useResource<Directorate[]>("/admin/directorates", lang);
  const languages = useResource<Language[]>("/admin/languages", lang);
  const [entity, setEntity] = useState<Entity>("roles");
  const [recordId, setRecordId] = useState("");
  const [languageCode, setLanguageCode] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [location, setLocation] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const queryClient = useQueryClient();
  const records: { id: string; label: string }[] =
    entity === "roles"
      ? (roles.data ?? []).map((role) => ({ id: String(role.id), label: role.name }))
      : entity === "permissions"
        ? (permissions.data ?? []).map((item) => ({ id: item.code, label: item.name }))
        : (directorates.data ?? []).map((item) => ({
            id: String(item.id),
            label: item.hierarchy_path ?? item.name,
          }));
  const query = useQuery({
    queryKey: ["translations", entity, recordId],
    queryFn: () =>
      api<Translation[]>(`/admin/translations/${entity}/${encodeURIComponent(recordId)}`),
    enabled: Boolean(recordId),
    retry: false,
  });
  const activeTranslation = query.data?.find((item) => item.language_code === languageCode);
  const otherLanguages = (languages.data ?? []).filter(
    (language) => language.code !== "ar" && language.is_active !== false,
  );

  useEffect(() => {
    const translation = query.data?.find((item) => item.language_code === languageCode);
    setName(translation?.name ?? "");
    setDescription(translation?.description ?? "");
    setLocation(translation?.location ?? "");
  }, [entity, recordId, languageCode, query.data]);

  function chooseLanguage(code: string) {
    setLanguageCode(code);
    const translation = query.data?.find((item) => item.language_code === code);
    setName(translation?.name ?? "");
    setDescription(translation?.description ?? "");
    setLocation(translation?.location ?? "");
  }

  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    try {
      await api(`/admin/translations/${entity}/${encodeURIComponent(recordId)}/${languageCode}`, {
        method: "PUT",
        body: entity === "directorates" ? { name, description, location } : { name, description },
      });
      await queryClient.invalidateQueries({ queryKey: ["translations", entity, recordId] });
      setMessage("حُفظت الترجمة.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "تعذر حفظ الترجمة.");
    } finally {
      setBusy(false);
    }
  }

  async function removeTranslation() {
    if (!activeTranslation || !window.confirm("حذف هذه الترجمة؟")) return;
    setBusy(true);
    setMessage("");
    try {
      await api(`/admin/translations/${entity}/${encodeURIComponent(recordId)}/${languageCode}`, {
        method: "DELETE",
      });
      await queryClient.invalidateQueries({ queryKey: ["translations", entity, recordId] });
      setName("");
      setDescription("");
      setLocation("");
      setMessage("حُذفت الترجمة.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "تعذر حذف الترجمة.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel" aria-labelledby="translation-heading">
      <div className="eyebrow">LOCALIZED RECORDS</div>
      <h2 id="translation-heading">{tText("إدارة الترجمات")}</h2>
      <p className="muted">
        العربية أساسية ولا يمكن حذف ترجمتها. اختر سجلًا ولغة لعرض القيمة الحالية أو حفظ ترجمة جديدة.
      </p>
      <div className="form-grid">
        <label className="field-label">
          {tText("نوع السجل")}
          <select
            className="field"
            value={entity}
            onChange={(event) => {
              setEntity(event.target.value as Entity);
              setRecordId("");
              setLanguageCode("");
            }}
          >
            <option value="roles">الأدوار</option>
            <option value="permissions">الصلاحيات</option>
            <option value="directorates">المديريات</option>
          </select>
        </label>
        <label className="field-label">
          {tText("السجل")}
          <select
            className="field"
            value={recordId}
            onChange={(event) => setRecordId(event.target.value)}
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
            onChange={(event) => chooseLanguage(event.target.value)}
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
      {query.isLoading && <div className="skeleton" aria-label="تحميل الترجمات" />}
      {query.error && (
        <div className="status error" role="alert">
          {tText("تعذر تحميل الترجمات.")}
          <button className="btn secondary" type="button" onClick={() => void query.refetch()}>
            <UiText source="إعادة المحاولة" />
          </button>
        </div>
      )}
      {recordId && languageCode && !query.isLoading && !query.error && (
        <form className="form-grid" onSubmit={(event) => void save(event)}>
          <p className="muted form-field full">
            {activeTranslation
              ? `${tText("تعديل ترجمة")} ${languageCode}`
              : `${tText("إضافة ترجمة")} ${languageCode}`}
          </p>
          <label className="field-label">
            {tText("الاسم")}
            <input
              className="field"
              required
              minLength={2}
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </label>
          <label className="field-label">
            {tText("الوصف")}
            <textarea
              className="field"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
            />
          </label>
          {entity === "directorates" && (
            <label className="field-label">
              {tText("الموقع")}
              <input
                className="field"
                value={location}
                onChange={(event) => setLocation(event.target.value)}
              />
            </label>
          )}
          <div className="row form-field full">
            <button className="btn" disabled={busy}>
              {busy ? tText("جارٍ الحفظ…") : tText("حفظ الترجمة")}
            </button>
            {activeTranslation && (
              <button
                className="btn danger"
                type="button"
                disabled={busy}
                onClick={() => void removeTranslation()}
              >
                {tText("حذف الترجمة")}
              </button>
            )}
          </div>
        </form>
      )}
      {message && (
        <div className="status info" role="status">
          {message}
        </div>
      )}
    </section>
  );
}
