import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, ApiError } from "../../shared/api/client";
import type { Citizen } from "../../shared/api/types";
import { useI18n } from "../../shared/i18n/I18n";
import { FormField as Field } from "../../shared/ui/FormField";
import { CitizenLoadError } from "./shared";

export function AccessPage() {
  const { tText } = useI18n();
  const [restore, setRestore] = useState("");
  const [telegram, setTelegram] = useState("");
  const [consent, setConsent] = useState(false);
  const [pending, setPending] = useState("");
  const [finishToken, setFinishToken] = useState("");
  const [key, setKey] = useState("");
  const [linkConsent, setLinkConsent] = useState(false);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const own = useQuery({
    queryKey: ["recovery-me"],
    queryFn: () => api<{ citizen: Citizen; has_recovery_key: boolean }>("/citizens/recovery/me"),
    retry: false,
  });

  async function act(action: () => Promise<void>) {
    setBusy(true);
    setMessage("");
    try {
      await action();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : tText("تعذر إتمام الإجراء"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid grid-two">
      <section className="panel">
        <span className="eyebrow">ACCOUNT OWNERSHIP</span>
        <h1>{tText("استعادة الوصول")}</h1>
        <p className="muted">
          {tText(
            "الاسم أو الرقم الوطني وحده لا يثبت ملكية السجل. لا تشارك مفاتيح الاستعادة أو رموز تيليغرام.",
          )}
        </p>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void act(async () => {
              await api("/citizens/recovery/key/restore", {
                method: "POST",
                body: { token: restore },
              });
              setRestore("");
              setMessage(tText("تمت الاستعادة. استُهلك المفتاح."));
            });
          }}
        >
          <Field label={tText("مفتاح الاستعادة (استخدام واحد)")}>
            <input
              className="field code"
              type="password"
              autoComplete="off"
              required
              value={restore}
              onChange={(event) => setRestore(event.target.value)}
            />
          </Field>
          <button className="btn" disabled={busy}>
            {tText("استعادة بالمفتاح")}
          </button>
        </form>
        <hr />
        <h3>{tText("طلب عبر تيليغرام")}</h3>
        <Field label={tText("معرّف تيليغرام الرقمي")}>
          <input
            className="field"
            dir="ltr"
            inputMode="numeric"
            pattern="[1-9][0-9]*"
            required
            value={telegram}
            onChange={(event) => setTelegram(event.target.value)}
          />
        </Field>
        <label className="muted">
          <input
            type="checkbox"
            checked={consent}
            onChange={(event) => setConsent(event.target.checked)}
          />{" "}
          {tText("أوافق على طلب إثبات الملكية عبر الحساب المرتبط أصلًا.")}
        </label>
        <button
          className="btn secondary"
          disabled={busy || !consent || !telegram}
          onClick={() =>
            void act(async () => {
              const telegramId = Number(telegram);
              if (!Number.isSafeInteger(telegramId) || telegramId <= 0) {
                throw new Error(tText("أدخل معرّف تيليغرام رقميًا صحيحًا."));
              }
              const result = await api<{ token: string; expires_in: number }>(
                "/citizens/recovery/telegram/start",
                { method: "POST", body: { telegram_id: telegramId, consent: true } },
              );
              setPending(`/recover ${result.token}`);
              setFinishToken(result.token);
            })
          }
        >
          {tText("بدء الاستعادة")}
        </button>
        {pending.startsWith("/recover") && (
          <div className="status info code">
            {pending}
            <p className="muted">
              {tText(
                "أرسل الأمر في محادثة خاصة مع البوت الرسمي ووافق هناك فقط إن كنت بدأت الطلب. ثم أكمل من هذا المتصفح.",
              )}
            </p>
            <button
              className="btn"
              onClick={() =>
                void act(async () => {
                  await api("/citizens/recovery/telegram/finish", {
                    method: "POST",
                    body: { token: finishToken },
                  });
                  setPending("");
                  setMessage(tText("تمت الاستعادة."));
                })
              }
            >
              {tText("أكملت الموافقة")}
            </button>
          </div>
        )}
      </section>
      <section className="panel">
        <span className="eyebrow">TRUSTED BROWSER</span>
        <h2>{tText("إدارة وسائل الوصول")}</h2>
        {own.isLoading ? (
          <div className="skeleton" />
        ) : own.error && own.error instanceof ApiError && own.error.status !== 403 ? (
          <CitizenLoadError message={own.error.message} onRetry={() => void own.refetch()} />
        ) : own.error ? (
          <p className="status info">
            {tText("لا توجد جلسة مواطن موثوقة في هذا المتصفح. استعد الوصول أولًا.")}
          </p>
        ) : (
          <>
            <p className="muted">
              {tText("جلسة موثوقة للمواطن")} {own.data?.citizen.first_name}.{" "}
              {own.data?.has_recovery_key
                ? tText("يوجد مفتاح حالي؛ الاستبدال يبطل السابق.")
                : tText("لا يوجد مفتاح حالي.")}
            </p>
            <button
              className="btn gold"
              disabled={busy}
              onClick={() =>
                void act(async () => {
                  if (
                    own.data?.has_recovery_key &&
                    !window.confirm(tText("إصدار مفتاح جديد سيبطل السابق. متابعة؟"))
                  )
                    return;
                  const result = await api<{ key: string }>("/citizens/recovery/key", {
                    method: "POST",
                    body: {},
                  });
                  setKey(result.key);
                })
              }
            >
              {tText("إصدار مفتاح استعادة")}
            </button>
            {key && (
              <div className="status info">
                <p className="code">{key}</p>
                <p>{tText("احفظه الآن خارج المتصفح. لن يُعرض مرة أخرى.")}</p>
                <button
                  className="btn secondary"
                  onClick={() => void navigator.clipboard?.writeText(key)}
                >
                  {tText("نسخ")}
                </button>
                <button
                  className="btn secondary"
                  onClick={() => {
                    const anchor = document.createElement("a");
                    anchor.href = URL.createObjectURL(new Blob([key], { type: "text/plain" }));
                    anchor.download = "shakwa-recovery-key.txt";
                    anchor.click();
                    URL.revokeObjectURL(anchor.href);
                  }}
                >
                  {tText("تنزيل")}
                </button>
              </div>
            )}
            <label className="muted">
              <input
                type="checkbox"
                checked={linkConsent}
                onChange={(event) => setLinkConsent(event.target.checked)}
              />{" "}
              {tText("أوافق على ربط تيليغرام بهذه الجلسة الموثوقة.")}
            </label>
            <button
              className="btn secondary"
              disabled={busy || !linkConsent}
              onClick={() =>
                void act(async () => {
                  const result = await api<{ token: string }>("/citizens/recovery/telegram/link", {
                    method: "POST",
                    body: {},
                  });
                  setPending(`/link ${result.token}`);
                })
              }
            >
              {tText("إنشاء إذن الربط")}
            </button>
            {pending.startsWith("/link") && (
              <div className="status info code">
                {pending}
                <p className="muted">
                  {tText("أرسل إلى البوت من الحساب المطلوب ووافق هناك. لا تُرسل الإذن لأحد.")}
                </p>
              </div>
            )}
          </>
        )}
        {message && (
          <div className="status info" role="status">
            {message}
          </div>
        )}
      </section>
    </div>
  );
}
