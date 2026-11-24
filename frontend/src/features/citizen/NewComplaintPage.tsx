import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Check, Clipboard, Upload } from "lucide-react";
import { api, upload } from "../../shared/api/client";
import { useDirectorates, useResource } from "../../shared/api/hooks";
import type { Citizen, Complaint, ComplaintInput, ComplaintType } from "../../shared/api/types";
import { useI18n } from "../../shared/i18n/I18n";
import { formatDuration } from "../../shared/formatDuration";
import { FormField as Field } from "../../shared/ui/FormField";
import { UiText } from "../../shared/i18n/UiText";
import { CitizenLoadError } from "./shared";

export function NewComplaintPage() {
  const { lang, tText } = useI18n();
  const directorates = useDirectorates(lang);
  const complaintTypes = useResource<ComplaintType[]>("/complaint-types", lang);
  const [step, setStep] = useState(1);
  const [form, setForm] = useState({
    first_name: "",
    last_name: "",
    phone: "",
    national_id: "",
    title: "",
    details: "",
    complaint_type_id: "",
    directorate_id: "",
    is_public: false,
  });
  const [idPhoto, setIdPhoto] = useState<File | null>(null);
  const [idPhotoUploaded, setIdPhotoUploaded] = useState(false);
  const [files, setFiles] = useState<File[]>([]);
  const [citizenId, setCitizenId] = useState<number | null>(null);
  const [complaint, setComplaint] = useState<Complaint | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [createdId, setCreatedId] = useState<number | null>(null);
  const set = (name: keyof typeof form, value: string | boolean) =>
    setForm((previous) => ({ ...previous, [name]: value }));

  async function send() {
    setBusy(true);
    setError("");
    try {
      let savedCitizen = citizenId;
      if (!savedCitizen) {
        const person = await api<Citizen>("/citizens/", {
          method: "POST",
          body: {
            first_name: form.first_name.trim(),
            last_name: form.last_name.trim(),
            phone: form.phone,
            national_id: form.national_id,
          },
        });
        savedCitizen = person.id;
        setCitizenId(person.id);
      }
      if (idPhoto && savedCitizen && !idPhotoUploaded) {
        await upload(`/citizens/${savedCitizen}/id-image/`, idPhoto);
        setIdPhotoUploaded(true);
      }
      let savedComplaint = createdId;
      if (!savedComplaint) {
        const result = await api<Complaint>("/complaints/", {
          method: "POST",
          body: {
            citizen_id: savedCitizen,
            directorate_id: Number(form.directorate_id),
            title: form.title.trim(),
            details: form.details.trim(),
            complaint_type_id: Number(form.complaint_type_id),
            is_public: form.is_public,
          } satisfies ComplaintInput,
        });
        savedComplaint = result.id;
        setCreatedId(result.id);
        setComplaint(result);
      }
      for (const file of [...files]) {
        await upload(`/complaints/${savedComplaint}/attachments/`, file);
        setFiles((pending) => pending.filter((item) => item !== file));
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : tText("تعذر إكمال الطلب."));
    } finally {
      setBusy(false);
    }
  }

  if (complaint && !error && !busy && files.length === 0) {
    return (
      <div className="panel" role="status">
        <span className="empty-icon">
          <Check />
        </span>
        <span className="eyebrow">RECEIPT / محفوظ</span>
        <h1 style={{ color: "var(--brand-dark)" }}>
          <UiText source="تم استلام شكواك" />
        </h1>
        <p className="muted">
          <UiText source="احتفظ برمز المتابعة الخاص. لا يمكن استعادته من هذه الصفحة." />
        </p>
        <div className="status info code" dir="ltr">
          {complaint.tracking_code}
        </div>
        <button
          className="btn secondary"
          onClick={() => void navigator.clipboard?.writeText(complaint.tracking_code)}
        >
          <Clipboard size={16} />
          <UiText source="نسخ الرمز" />
        </button>
        <Link className="btn" to="/track">
          <UiText source="فتح المتابعة" />
        </Link>
        <p className="muted">
          <UiText source="إصدار مفتاح الاستعادة اختياري ولا يحدث تلقائيًا. استخدم صفحة استعادة الوصول عند الحاجة." />
        </p>
      </div>
    );
  }

  return (
    <div className="panel" style={{ maxWidth: 820, margin: "auto" }}>
      <span className="eyebrow">CITIZEN SERVICE / شکوى جديدة</span>
      <h1 style={{ color: "var(--brand-dark)", fontSize: 30 }}>
        <UiText source="قدّم شكوى، دون حساب" />
      </h1>
      <p className="muted">
        <UiText source="يُستخدم رقم الهوية للتحقق من الملكية. لا يظهر في العرض العام." />
      </p>
      <div className="stepper">
        <div className={`step ${step === 1 ? "current" : ""}`}>
          ١ · <UiText source="بيانات المواطن" />
        </div>
        <div className={`step ${step === 2 ? "current" : ""}`}>
          ٢ · <UiText source="تفاصيل الشكوى" />
        </div>
      </div>
      {error && (
        <div className="status error" role="alert">
          {error}
        </div>
      )}
      {createdId && (
        <div className="status info">
          {tText("تم إنشاء الشكوى")} ({tText("المعرّف")} {createdId}).{" "}
          {tText(
            "المرفقات المتبقية محفوظة في هذه الصفحة؛ أعد المحاولة لإكمال الرفع دون إنشاء شكوى جديدة.",
          )}
        </div>
      )}
      {step === 1 ? (
        <form
          key="citizen-identity-step"
          className="form-grid"
          onSubmit={(event) => {
            event.preventDefault();
            if (!idPhoto && !idPhotoUploaded) {
              setError(tText("صورة الهوية مطلوبة."));
              return;
            }
            setError("");
            setStep(2);
          }}
        >
          <Field label="الاسم الأول">
            <input
              required
              minLength={2}
              maxLength={50}
              pattern="[^0-9٠-٩]{2,50}"
              className="field"
              value={form.first_name}
              onChange={(event) => set("first_name", event.target.value)}
            />
          </Field>
          <Field label="اسم العائلة">
            <input
              required
              minLength={2}
              maxLength={50}
              pattern="[^0-9٠-٩]{2,50}"
              className="field"
              value={form.last_name}
              onChange={(event) => set("last_name", event.target.value)}
            />
          </Field>
          <Field label="رقم الهاتف">
            <input
              required
              minLength={8}
              maxLength={20}
              pattern="[+]?[0-9]{8,20}"
              className="field"
              dir="ltr"
              value={form.phone}
              onChange={(event) => set("phone", event.target.value)}
            />
          </Field>
          <Field label="الرقم الوطني">
            <input
              required
              minLength={5}
              maxLength={20}
              pattern="[0-9]{5,20}"
              className="field"
              dir="ltr"
              value={form.national_id}
              onChange={(event) => set("national_id", event.target.value)}
            />
          </Field>
          <Field label="صورة الهوية (مطلوبة)" full>
            <input
              required={!idPhotoUploaded}
              type="file"
              accept="image/*"
              className="field"
              onChange={(event) => {
                setIdPhoto(event.target.files?.[0] ?? null);
                setIdPhotoUploaded(false);
              }}
            />
          </Field>
          <div className="form-field full row">
            <button className="btn" type="submit">
              <UiText source="متابعة التفاصيل" /> <ArrowLeft size={16} />
            </button>
          </div>
        </form>
      ) : (
        <form
          key="complaint-details-step"
          className="form-grid"
          onSubmit={(event) => {
            event.preventDefault();
            void send();
          }}
        >
          <Field label="عنوان الشكوى">
            <input
              required
              minLength={5}
              className="field"
              value={form.title}
              onChange={(event) => set("title", event.target.value)}
            />
          </Field>
          <Field label="الجهة">
            <select
              className="field"
              required
              value={form.directorate_id}
              onChange={(event) => set("directorate_id", event.target.value)}
            >
              <option value="">
                <UiText source="اختر جهة" />
              </option>
              {directorates.data?.map((directorate) => (
                <option key={directorate.id} value={directorate.id}>
                  {directorate.hierarchy_path ?? directorate.name}
                </option>
              ))}
            </select>
            {directorates.error && (
              <CitizenLoadError
                message={tText("تعذر تحميل الجهات.")}
                onRetry={() => void directorates.refetch()}
              />
            )}
          </Field>
          <Field label="نوع الشكوى" full>
            <select
              className="field"
              required
              value={form.complaint_type_id}
              disabled={complaintTypes.isLoading || !!complaintTypes.error}
              onChange={(event) => set("complaint_type_id", event.target.value)}
            >
              <option value="">{tText("اختر نوع الشكوى")}</option>
              {complaintTypes.data?.map((type) => (
                <option key={type.id} value={type.id}>
                  {type.name}
                </option>
              ))}
            </select>
            {complaintTypes.isLoading && <p className="muted">{tText("جارٍ تحميل الأنواع…")}</p>}
            {complaintTypes.error && (
              <CitizenLoadError
                message={tText("تعذر تحميل أنواع الشكاوى.")}
                onRetry={() => void complaintTypes.refetch()}
              />
            )}
            {(() => {
              const selected = complaintTypes.data?.find(
                (type) => String(type.id) === form.complaint_type_id,
              );
              if (!selected) return null;
              return (
                <div className="status info" style={{ marginTop: 10 }}>
                  {selected.description && <p>{selected.description}</p>}
                  <b>{tText("المدة التقديرية")}: </b>
                  {selected.code === "other"
                    ? tText("لا توجد مهلة تقديرية لهذا النوع.")
                    : selected.sla_duration_minutes
                      ? formatDuration(selected.sla_duration_minutes, lang)
                      : tText("لم تُحدد المدة لهذا النوع بعد.")}
                  {selected.code !== "other" && selected.sla_duration_minutes && (
                    <small className="muted" style={{ display: "block" }}>
                      {tText("مدة متواصلة من وقت تقديم الشكوى، وليست أيام دوام.")}
                    </small>
                  )}
                </div>
              );
            })()}
          </Field>
          <Field label="التفاصيل" full>
            <textarea
              required
              minLength={10}
              rows={5}
              className="field"
              value={form.details}
              onChange={(event) => set("details", event.target.value)}
            />
          </Field>
          <Field label="مرفقات اختيارية" full>
            <input
              type="file"
              multiple
              className="field"
              onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
            />
          </Field>
          <div className="form-field full">
            <p className="muted">
              <UiText source="مرفقات الشكوى منفصلة عن صورة الهوية." />
            </p>
            {files.length > 0 && (
              <ul className="file-selection-list" aria-label={tText("مرفقات الشكوى المحددة")}>
                {files.map((file, index) => (
                  <li key={`${file.name}-${file.lastModified}-${index}`}>
                    <span dir="auto">{file.name}</span>
                    <button
                      type="button"
                      className="btn secondary"
                      aria-label={`${tText("إزالة مرفق")} ${file.name}`}
                      onClick={() => setFiles((selected) => selected.filter((_, i) => i !== index))}
                    >
                      <UiText source="إزالة" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <label className="form-field full status info">
            <input
              type="checkbox"
              checked={form.is_public}
              onChange={(event) => set("is_public", event.target.checked)}
            />{" "}
            {tText("نشر نص الشكوى اختياريًا. لا تدرج بيانات تعريفية؛ الهوية والمرفقات لا تُنشر.")}
          </label>
          <div className="form-field full row">
            <button type="button" className="btn secondary" onClick={() => setStep(1)}>
              <UiText source="السابق" />
            </button>
            <button disabled={busy} className="btn" type="submit">
              {busy ? <UiText source="جارٍ الإرسال…" /> : <UiText source="إرسال الشكوى" />}{" "}
              <Upload size={16} />
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
