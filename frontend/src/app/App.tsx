import { Link, Route, Routes } from "react-router-dom";
import { I18nProvider, useI18n } from "../shared/i18n/I18n";
import { Shell } from "../layouts/Shell";
import { AccessPage } from "../features/citizen/AccessPage";
import { HomePage } from "../features/citizen/HomePage";
import { NewComplaintPage } from "../features/citizen/NewComplaintPage";
import { PublicDetailPage } from "../features/citizen/PublicDetailPage";
import { PublicPage } from "../features/citizen/PublicPage";
import { TrackPage } from "../features/citizen/TrackPage";
import { EmployeeAccount } from "../features/employee/EmployeeAccount";
import { EmployeeLogin } from "../features/employee/EmployeeLogin";
import { EmployeeHome } from "../features/employee/EmployeeHome";
import { EmployeeComplaintDetail } from "../features/employee/EmployeeComplaintDetail";
import { Statistics } from "../features/employee/Statistics";
import { AuditAdmin } from "../features/admin/AuditAdmin";
import { DirectoratesAdmin } from "../features/admin/DirectoratesAdmin";
import { EmployeesAdmin } from "../features/admin/EmployeesAdmin";
import { LanguagesAdmin } from "../features/admin/LanguagesAdmin";
import { RolesAdmin } from "../features/admin/RolesAdmin";
import { TranslationsAdmin } from "../features/admin/TranslationsAdmin";
import { ComplaintToolsPage } from "../features/employee/EvidenceDesk";

function NotFound() {
  const { tText } = useI18n();
  return (
    <section className="panel" style={{ textAlign: "center", padding: 56 }}>
      <div className="eyebrow">404 · NOT FOUND</div>
      <h1>{tText("هذه الصفحة غير موجودة")}</h1>
      <p className="muted">{tText("تحقق من الرابط أو عد إلى الصفحة الرئيسية.")}</p>
      <Link className="btn" to="/">
        {tText("العودة للرئيسية")}
      </Link>
    </section>
  );
}
export default function App() {
  return (
    <I18nProvider>
      <Routes>
        <Route element={<Shell />}>
          <Route index element={<HomePage />} />
          <Route path="/complaints/new" element={<NewComplaintPage />} />
          <Route path="/track" element={<TrackPage />} />
          <Route path="/public" element={<PublicPage />} />
          <Route path="/public/:id" element={<PublicDetailPage />} />
          <Route path="/access" element={<AccessPage />} />
          <Route path="/employee/complaints" element={<EmployeeHome />} />
          <Route path="/employee/complaints/:id" element={<EmployeeComplaintDetail />} />
          <Route path="/employee/complaints/:id/tools" element={<ComplaintToolsPage />} />
          <Route path="/employee/statistics" element={<Statistics />} />
          <Route path="/employee/account" element={<EmployeeAccount />} />
          <Route path="/employee/admin/directorates" element={<DirectoratesAdmin />} />
          <Route path="/employee/admin/employees" element={<EmployeesAdmin />} />
          <Route path="/employee/admin/roles" element={<RolesAdmin />} />
          <Route path="/employee/admin/languages" element={<LanguagesAdmin />} />
          <Route path="/employee/admin/translations" element={<TranslationsAdmin />} />
          <Route path="/employee/admin/audit" element={<AuditAdmin />} />
          <Route path="*" element={<NotFound />} />
        </Route>
        <Route path="/employee/login" element={<EmployeeLogin />} />
      </Routes>
    </I18nProvider>
  );
}
