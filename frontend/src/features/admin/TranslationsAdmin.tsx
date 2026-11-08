import { TranslationManager } from "./TranslationManager";
import { AdminPage } from "./AdminPage";

export function TranslationsAdmin() {
  return (
    <AdminPage
      title="إدارة الترجمات"
      subtitle="ترجمات ثابتة للأسماء والوصف. لا تترجم نصوص المواطنين تلقائيًا."
    >
      <TranslationManager />
    </AdminPage>
  );
}
