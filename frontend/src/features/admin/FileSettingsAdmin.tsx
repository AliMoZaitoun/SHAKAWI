import { useEffect, useMemo, useState, type FormEvent } from "react";
import { AlertTriangle, Database, FileClock, Save, ShieldCheck } from "lucide-react";
import { api } from "../../shared/api/client";
import { useResource } from "../../shared/api/hooks";
import { useI18n } from "../../shared/i18n/I18n";
import { UiText } from "../../shared/i18n/UiText";
import { AdminAlert, AdminPage, useAdminSave } from "./AdminPage";
import "./admin-ui.css";

type FileTypeLimit = {
  mime_type: string;
  label_ar: string;
  label_en: string;
  max_bytes: number;
};
type RetentionState = {
  enabled: boolean;
  days: number;
  scope: string[];
  policy_version: number;
  reviewed_at: string | null;
};
type RetentionRun = {
  id: number;
  status: string;
  files_scanned: number;
  files_purged: number;
  bytes_purged: number;
  failures: number;
  started_at: string;
  finished_at: string | null;
};
type FileSettings = {
  hard_max_bytes: number;
  mime_types: FileTypeLimit[];
  retention: RetentionState;
  recent_runs: RetentionRun[];
};
type RetentionPreview = {
  preview_token: string;
  expires_at: string;
  cutoff_at: string;
  days: number;
  scope: string[];
  file_count: number;
  bytes_total: number;
  complaints: { tracking_code: string; resolved_at: string; file_count: number; bytes_total: number }[];
  includes_identity_files: boolean;
  preserves_complaint_and_audit_history: boolean;
};

const MiB = 1024 * 1024;

function sizeLabel(bytes: number, lang: string) {
  return `${(bytes / MiB).toLocaleString(lang, { maximumFractionDigits: 2 })} MiB`;
}

export function FileSettingsAdmin() {
  const { lang, tText } = useI18n();
  const query = useResource<FileSettings>("/admin/settings/files", lang);
  const save = useAdminSave();
  const [limitInputs, setLimitInputs] = useState<Record<string, string>>({});
  const [days, setDays] = useState("30");
  const [scope, setScope] = useState<string[]>(["complaint_files", "evidence_reply_files"]);
  const [preview, setPreview] = useState<RetentionPreview | null>(null);
  const [previewBusy, setPreviewBusy] = useState(false);

  useEffect(() => {
    if (!query.data) return;
    setLimitInputs(Object.fromEntries(
      query.data.mime_types.map((item) => [item.mime_type, String(item.max_bytes / MiB)]),
    ));
    setDays(String(query.data.retention.days));
    setScope(query.data.retention.scope);
  }, [query.data]);

  const displayTypes = useMemo(
    () => query.data?.mime_types ?? [],
    [query.data?.mime_types],
  );

  async function saveLimits(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const mime_limits: Record<string, number> = {};
    for (const type of displayTypes) {
      const mib = Number(limitInputs[type.mime_type]);
      if (!Number.isFinite(mib) || mib <= 0 || mib > 10) {
        save.setMessage(tText("أدخل حدًا بين 0.01 و10 ميغابايت لكل نوع."));
        return;
      }
      mime_limits[type.mime_type] = Math.round(mib * MiB);
    }
    await save.run(() => api("/admin/settings/files/limits", {
      method: "PUT",
      body: { mime_limits },
    }));
  }

  async function saveRetention(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parsedDays = Number(days);
    if (!Number.isInteger(parsedDays) || parsedDays < 1 || parsedDays > 3650 || !scope.length) {
      save.setMessage(tText("حدد مدة بين يوم و10 سنوات ونطاق ملف واحد على الأقل."));
      return;
    }
    setPreview(null);
    await save.run(() => api("/admin/settings/files/retention", {
      method: "PUT",
      body: { retention_days: parsedDays, retention_scope: scope },
    }));
  }

  async function createPreview() {
    setPreviewBusy(true);
    setPreview(null);
    save.setMessage("");
    try {
      const result = await api<RetentionPreview>("/admin/settings/files/retention/preview", {
        method: "POST",
      });
      setPreview(result);
    } catch (error) {
      save.setMessage(error instanceof Error ? error.message : tText("تعذر إنشاء المعاينة."));
    } finally {
      setPreviewBusy(false);
    }
  }

  async function enableRetention() {
    if (!preview) return;
    const ok = await save.run(() => api("/admin/settings/files/retention/enable", {
      method: "POST",
      body: { preview_token: preview.preview_token },
    }));
    if (ok) setPreview(null);
  }

  async function disableRetention() {
    const ok = await save.run(() => api("/admin/settings/files/retention/disable", {
      method: "POST",
    }));
    if (ok) setPreview(null);
  }

  function toggleScope(value: string) {
    setScope((current) => current.includes(value)
      ? current.filter((item) => item !== value)
      : [...current, value]);
    setPreview(null);
  }

  return (
    <AdminPage
      title="حدود الملفات والاحتفاظ"
      subtitle="اضبط أحجام الرفع وسياسة حذف محتوى المرفقات دون المساس بسجلات الشكاوى."
      required="files.manage"
    >
      {query.isLoading ? (
        <div className="skeleton" />
      ) : query.error || !query.data ? (
        <div className="status error" role="alert">
          {tText("تعذر تحميل إعدادات الملفات.")}
          <button className="btn secondary" type="button" onClick={() => void query.refetch()}>
            <UiText source="إعادة المحاولة" />
          </button>
        </div>
      ) : (
        <>
          <section className="admin-settings-section">
            <div className="admin-settings-heading">
              <div className="admin-settings-icon"><Database size={20} /></div>
              <div>
                <h2><UiText source="حدود حجم الرفع" /></h2>
                <p className="muted">
                  <UiText source="تُطبق الحدود نفسها على الموقع وتيليغرام ومرفقات طلبات الأدلة." />
                </p>
              </div>
            </div>
            <div className="status info">
              <UiText source="أنواع الملفات ثابتة ومتحقق من محتواها؛ تعديل الحجم لا يضيف نوعًا جديدًا." />
            </div>
            <form onSubmit={(event) => void saveLimits(event)}>
              <div className="file-limit-grid">
                {displayTypes.map((type) => (
                  <label className="field-label file-limit-field" key={type.mime_type}>
                    <span>{lang === "ar" ? type.label_ar : type.label_en}</span>
                    <div className="file-limit-input">
                      <input
                        className="field"
                        type="number"
                        min="0.01"
                        max="10"
                        step="0.01"
                        required
                        value={limitInputs[type.mime_type] ?? ""}
                        onChange={(event) => setLimitInputs({
                          ...limitInputs,
                          [type.mime_type]: event.target.value,
                        })}
                      />
                      <span>MiB</span>
                    </div>
                    <small className="muted">{type.mime_type}</small>
                  </label>
                ))}
              </div>
              <p className="muted">
                <UiText source="الحد الأعلى المدعوم" />: {sizeLabel(query.data.hard_max_bytes, lang)}
              </p>
              <button className="btn" disabled={save.busy}>
                <Save size={16} />
                <UiText source="حفظ حدود الملفات" />
              </button>
            </form>
          </section>

          <section className="admin-settings-section">
            <div className="admin-settings-heading">
              <div className="admin-settings-icon"><FileClock size={20} /></div>
              <div>
                <h2><UiText source="الاحتفاظ بالمرفقات المحلولة" /></h2>
                <p className="muted">
                  <UiText source="يبدأ احتساب المدة من تاريخ حل الشكوى، وتحصل الملفات المضافة لاحقًا على مدة كاملة أيضًا." />
                </p>
              </div>
            </div>
            <div className="status warning">
              <AlertTriangle size={17} />
              <span>
                <UiText source="الحذف مغلق افتراضيًا. لن تُحذف وثائق الهوية أو سجل الشكوى أو سجل التدقيق." />
              </span>
            </div>
            <form className="retention-policy-form" onSubmit={(event) => void saveRetention(event)}>
              <label className="field-label">
                <UiText source="مدة الاحتفاظ بالأيام" />
                <input
                  className="field"
                  type="number"
                  min="1"
                  max="3650"
                  step="1"
                  required
                  value={days}
                  onChange={(event) => {
                    setDays(event.target.value);
                    setPreview(null);
                  }}
                />
              </label>
              <fieldset className="retention-scope">
                <legend><UiText source="نطاق الملفات المشمولة" /></legend>
                <label className="row">
                  <input
                    type="checkbox"
                    checked={scope.includes("complaint_files")}
                    onChange={() => toggleScope("complaint_files")}
                  />
                  <UiText source="مرفقات الشكوى المباشرة" />
                </label>
                <label className="row">
                  <input
                    type="checkbox"
                    checked={scope.includes("evidence_reply_files")}
                    onChange={() => toggleScope("evidence_reply_files")}
                  />
                  <UiText source="مرفقات ردود الأدلة" />
                </label>
              </fieldset>
              <AdminAlert text={save.message} isError={save.isError} />
              <div className="row">
                <button className="btn" disabled={save.busy}>
                  <Save size={16} />
                  <UiText source="حفظ سياسة الاحتفاظ" />
                </button>
                {query.data.retention.enabled ? (
                  <button
                    className="btn danger"
                    type="button"
                    disabled={save.busy}
                    onClick={() => void disableRetention()}
                  >
                    <UiText source="إيقاف الحذف الدوري" />
                  </button>
                ) : (
                  <button
                    className="btn secondary"
                    type="button"
                    disabled={save.busy || previewBusy || !scope.length}
                    onClick={() => void createPreview()}
                  >
                    <ShieldCheck size={16} />
                    {previewBusy
                      ? <UiText source="جارٍ إعداد المعاينة…" />
                      : <UiText source="معاينة الملفات قبل التفعيل" />}
                  </button>
                )}
              </div>
            </form>
            <p className="muted retention-caution">
              <UiText source="السجلات القديمة التي لا تملك تاريخ حل موثوقًا تبقى خارج الحذف التلقائي." />
            </p>

            {preview && (
              <div className="retention-preview" role="region" aria-live="polite">
                <h3><UiText source="معاينة أثر سياسة الاحتفاظ" /></h3>
                <p>
                  <UiText source="سيُحذف محتوى هذه الملفات فقط، مع بقاء بيانات الشكوى والتدقيق." />
                </p>
                <div className="admin-role-meta">
                  <span><b>{preview.file_count}</b> <UiText source="ملفًا" /></span>
                  <span><b>{sizeLabel(preview.bytes_total, lang)}</b> <UiText source="إجمالي المحتوى" /></span>
                  <span>
                    <UiText source="قبل" />{" "}
                    {new Date(preview.cutoff_at).toLocaleString(lang)}
                  </span>
                </div>
                {preview.includes_identity_files && (
                  <div className="status error" role="alert">
                    <UiText source="المعاينة تتضمن وثائق هوية؛ لن يُسمح بالتفعيل." />
                  </div>
                )}
                {preview.complaints.length ? (
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th><UiText source="رمز الشكوى" /></th>
                          <th><UiText source="تاريخ الحل" /></th>
                          <th><UiText source="الملفات" /></th>
                          <th><UiText source="الحجم" /></th>
                        </tr>
                      </thead>
                      <tbody>
                        {preview.complaints.map((item) => (
                          <tr key={item.tracking_code}>
                            <td>{item.tracking_code}</td>
                            <td>{new Date(item.resolved_at).toLocaleString(lang)}</td>
                            <td>{item.file_count}</td>
                            <td>{sizeLabel(item.bytes_total, lang)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="empty"><UiText source="لا توجد ملفات مستحقة للحذف حاليًا." /></div>
                )}
                <div className="status warning">
                  <AlertTriangle size={17} />
                  <span>
                    <UiText source="التفعيل يسمح للحذف المجدول اليومي مستقبلًا وفق هذه السياسة." />
                    {" "}
                    <UiText source="الحذف يزيل الملف من التخزين النشط فقط؛ النسخ الاحتياطية التي أُنشئت سابقًا لا تتغير." />
                  </span>
                </div>
                <div className="row">
                  <button
                    className="btn danger"
                    type="button"
                    disabled={save.busy || preview.includes_identity_files}
                    onClick={() => void enableRetention()}
                  >
                    <ShieldCheck size={16} />
                    <UiText source="أوافق على التفعيل بعد مراجعة المعاينة" />
                  </button>
                  <button
                    className="btn secondary"
                    type="button"
                    disabled={save.busy}
                    onClick={() => setPreview(null)}
                  >
                    <UiText source="إلغاء المعاينة" />
                  </button>
                </div>
              </div>
            )}
          </section>

          <section className="admin-settings-section">
            <h2><UiText source="آخر عمليات الاحتفاظ" /></h2>
            {query.data.recent_runs.length ? (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      {["النتيجة", "تم فحصها", "حُذف محتواها", "الحجم", "إخفاقات", "التاريخ"].map((label) => (
                        <th key={label}><UiText source={label} /></th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {query.data.recent_runs.map((run) => (
                      <tr key={run.id}>
                        <td><UiText source={run.status === "completed" ? "اكتملت" : "بحاجة لمراجعة"} /></td>
                        <td>{run.files_scanned}</td>
                        <td>{run.files_purged}</td>
                        <td>{sizeLabel(run.bytes_purged, lang)}</td>
                        <td>{run.failures}</td>
                        <td>{new Date(run.started_at).toLocaleString(lang)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="empty"><UiText source="لم تُنفذ عمليات حذف بعد." /></p>
            )}
          </section>
        </>
      )}
      {!query.data && <AdminAlert text={save.message} isError={save.isError} />}
    </AdminPage>
  );
}
