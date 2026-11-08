import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { translateUiText } from "./dictionary";

type LanguageCode = "ar" | "en";
const words = {
  ar: {
    home: "الرئيسية",
    submit: "تقديم شكوى",
    track: "متابعة شكوى",
    public: "الشفافية العامة",
    staff: "بوابة الموظفين",
    login: "دخول الموظفين",
    overview: "خدمة تحفظ حقك وتوضح ما يحدث",
    language: "English",
    loading: "جارٍ التحميل",
    retry: "إعادة المحاولة",
    empty: "لا توجد نتائج ضمن هذه المعايير",
    error: "تعذر تحميل البيانات",
    back: "العودة",
    search: "بحث",
    refresh: "تحديث",
    logout: "تسجيل الخروج",
    status: "الحالة",
    title: "العنوان",
    details: "التفاصيل",
    category: "التصنيف",
    directorate: "الجهة",
    date: "التاريخ",
    save: "حفظ",
    cancel: "إلغاء",
    send: "إرسال",
    actions: "إجراءات",
    private: "خاصة",
    publicLabel: "منشورة للعامة",
    pending: "جديدة",
    inProgress: "قيد المعالجة",
    resolved: "تمت المعالجة",
    rejected: "مرفوضة",
  },
  en: {
    home: "Home",
    submit: "Submit a complaint",
    track: "Track a complaint",
    public: "Public transparency",
    staff: "Staff portal",
    login: "Staff sign in",
    overview: "A service that protects your voice and shows what happens next",
    language: "العربية",
    loading: "Loading",
    retry: "Try again",
    empty: "No results for these filters",
    error: "Could not load this information",
    back: "Back",
    search: "Search",
    refresh: "Refresh",
    logout: "Sign out",
    status: "Status",
    title: "Title",
    details: "Details",
    category: "Category",
    directorate: "Directorate",
    date: "Date",
    save: "Save",
    cancel: "Cancel",
    send: "Send",
    actions: "Actions",
    private: "Private",
    publicLabel: "Published",
    pending: "New",
    inProgress: "In progress",
    resolved: "Resolved",
    rejected: "Rejected",
  },
};
type Dict = typeof words.ar;
const Context = createContext<{
  lang: LanguageCode;
  t: (key: keyof Dict) => string;
  tText: (source: string) => string;
  setLang: (code: LanguageCode) => void;
}>({ lang: "ar", t: (key) => words.ar[key], tText: (source) => source, setLang: () => {} });
export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<LanguageCode>(() =>
    localStorage.getItem("shakwa-language") === "en" ? "en" : "ar",
  );
  const setLang = (code: LanguageCode) => {
    localStorage.setItem("shakwa-language", code);
    setLangState(code);
  };
  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
  }, [lang]);
  const value = useMemo(
    () => ({
      lang,
      t: (key: keyof Dict) => words[lang][key],
      tText: (source: string) => translateUiText(source, lang),
      setLang,
    }),
    [lang],
  );
  return <Context.Provider value={value}>{children}</Context.Provider>;
}
export const useI18n = () => useContext(Context);
