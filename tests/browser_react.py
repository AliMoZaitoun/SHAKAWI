"""React end-to-end smoke checks, isolated synthetic SQLite data only."""
import io
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

from PIL import Image
from playwright.sync_api import sync_playwright, expect


def run():
    root = Path(__file__).resolve().parents[1]
    if not (root / "frontend/dist/index.html").exists():
        raise RuntimeError("Build the React frontend first: pnpm build")
    output = root / "generated-artifacts/react-browser-check"
    output.mkdir(parents=True, exist_ok=True)
    png = io.BytesIO()
    Image.new("RGB", (40, 40), color="green").save(png, format="PNG")
    image = {"name": "synthetic-identity.png", "mimeType": "image/png", "buffer": png.getvalue()}
    with tempfile.TemporaryDirectory(prefix="shakwa-react-") as temp:
        env = os.environ.copy()
        for name in ("REPLIT_DEV_DOMAIN", "REPLIT_DEPLOYMENT", "GOVERNOR_PASSWORD", "SERVICES_PASSWORD"):
            env.pop(name, None)
        env.update(
            SHAKWA_DATABASE_URL=f"sqlite:///{temp}/test.db",
            ENABLE_DEMO_ACCOUNTS="1",
            APP_ENV="test",
            BOT_TOKEN="",
            SHAKWA_UI="react",
            SYSTEM_ADMIN_PASSWORD="test-only-not-a-live-password",
        )
        with (output / "server.log").open("w") as log:
            server = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8009"],
                cwd=root, env=env, stdout=log, stderr=log,
            )
            try:
                for _ in range(100):
                    try:
                        urllib.request.urlopen("http://127.0.0.1:8009/health", timeout=1)
                        break
                    except OSError:
                        time.sleep(0.2)
                else:
                    raise RuntimeError("React test server did not start")
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True, executable_path=shutil.which("chromium"))
                    citizen_context = browser.new_context(viewport={"width": 1366, "height": 900})
                    page = citizen_context.new_page()
                    errors = []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    base = "http://127.0.0.1:8009"
                    page.goto(base)
                    expect(page.get_by_role("heading", level=1)).to_be_visible()
                    page.get_by_role("button", name="English", exact=True).click()
                    expect(page.locator("html")).to_have_attribute("dir", "ltr")
                    page.get_by_role("button", name="العربية", exact=True).click()
                    page.goto(base + "/complaints/new")
                    page.get_by_label("الاسم الأول", exact=True).fill("مواطن")
                    page.get_by_label("اسم العائلة", exact=True).fill("تجريبي")
                    page.get_by_label("رقم الهاتف", exact=True).fill("0900000042")
                    page.get_by_label("الرقم الوطني", exact=True).fill("00000000042")
                    identity_image = {
                        **image,
                        "name": "citizen-identity.png",
                    }
                    complaint_image = {
                        **image,
                        "name": "complaint-evidence.png",
                    }
                    page.get_by_label("صورة الهوية (مطلوبة)", exact=True).set_input_files(identity_image)
                    page.get_by_role("button", name=re.compile("متابعة التفاصيل")).click()
                    try:
                        page.get_by_label("عنوان الشكوى", exact=True).wait_for(timeout=3000)
                    except Exception:
                        print("Submission DOM:", page.locator("main").inner_text())
                        print("Invalid inputs:", page.locator(":invalid").evaluate_all(
                            "nodes => nodes.map(n => [n.tagName, n.type, n.validationMessage])"
                        ))
                        page.screenshot(path=str(output / "submission-failure.png"), full_page=True)
                        raise
                    attachment_input = page.get_by_label("مرفقات اختيارية", exact=True)
                    assert attachment_input.evaluate("input => input.files.length") == 0, (
                        "The identity image must not appear as a complaint attachment"
                    )
                    page.get_by_label("عنوان الشكوى", exact=True).fill("طلب صيانة إنارة الحديقة")
                    page.get_by_role("combobox").select_option(index=1)
                    page.get_by_label("نوع الشكوى", exact=True).fill("إنارة")
                    page.get_by_label("التفاصيل", exact=True).fill("طلب تجريبي لإصلاح الإنارة في الطريق الرئيسي.")
                    attachment_input.set_input_files(complaint_image)
                    selected_attachments = page.get_by_role("list", name="مرفقات الشكوى المحددة")
                    expect(selected_attachments.get_by_text("complaint-evidence.png")).to_be_visible()
                    assert "citizen-identity.png" not in selected_attachments.inner_text()
                    page.screenshot(path=str(output / "submission-step-two.png"), full_page=True)
                    page.locator('input[type="checkbox"]').check()
                    page.get_by_role("button", name=re.compile("إرسال الشكوى")).click()
                    expect(page.get_by_role("heading", name="تم استلام شكواك")).to_be_visible(timeout=15000)
                    tracking = re.search(r"CMP-[A-Za-z0-9_-]+", page.locator("main").inner_text()).group()
                    owned = citizen_context.request.get(base + "/api/v1/citizens/recovery/me").json()
                    assert not owned["has_recovery_key"], "Keys must never issue automatically"
                    complaints = citizen_context.request.get(
                        base + f"/api/v1/complaints/citizen/{owned['citizen']['id']}"
                    ).json()
                    assert len(complaints) == 1
                    complaint_id = complaints[0]["id"]
                    page.goto(base + "/track")
                    page.get_by_label("رمز المتابعة", exact=True).fill(tracking)
                    page.get_by_role("button", name="استعلام", exact=True).click()
                    expect(page.get_by_role("heading", name="طلب صيانة إنارة الحديقة")).to_be_visible()
                    page.goto(base + "/public")
                    page.locator(f'a[href="/public/{complaint_id}"]').click()
                    expect(page.get_by_role("heading", name="طلب صيانة إنارة الحديقة")).to_be_visible()
                    public_text = page.locator("main").inner_text()
                    for secret in (tracking, "0900000042", "00000000042"):
                        assert secret not in public_text
                    page.goto(base + "/access")
                    expect(page.get_by_role("heading", name="استعادة الوصول")).to_be_visible()
                    assert not citizen_context.request.get(
                        base + "/api/v1/citizens/recovery/me"
                    ).json()["has_recovery_key"]
                    staff_context = browser.new_context(viewport={"width": 1440, "height": 1000})
                    staff = staff_context.new_page()
                    staff.on("pageerror", lambda error: errors.append(str(error)))
                    staff.goto(base + "/employee/login")
                    staff.get_by_label("اسم المستخدم", exact=True).fill("governor")
                    staff.get_by_label("كلمة المرور", exact=True).fill("123456")
                    staff.get_by_role("button", name="دخول آمن", exact=True).click()
                    expect(staff).to_have_url(re.compile(r"/employee/complaints$"))
                    staff.goto(base + f"/employee/complaints/{complaint_id}")
                    expect(staff.get_by_role("heading", name="طلب صيانة إنارة الحديقة")).to_be_visible()
                    staff_complaint = staff_context.request.get(
                        base + f"/api/v1/complaints/{complaint_id}"
                    ).json()
                    assert len(staff_complaint["attachments"]) == 1
                    assert staff_complaint["attachments"][0]["name"] == "complaint-evidence.png"
                    staff.screenshot(path=str(output / "staff-complaint.png"), full_page=True)
                    staff.goto(base + "/employee/statistics")
                    expect(staff.get_by_text("إجمالي الشكاوى", exact=True)).to_be_visible()
                    expect(staff.get_by_role("img", name="مخطط أعمدة لحجم الشكاوى")).to_be_visible()
                    expect(staff.get_by_role("img", name="مخطط دائري يوضح توزيع الشكاوى حسب الحالة")).to_be_visible()
                    assert staff.locator(".statistics-chart .chart-bar").count() > 0
                    assert staff.locator(".statistics-summary").evaluate(
                        "element => getComputedStyle(element).gridTemplateColumns.split(' ').length"
                    ) == 3
                    staff.screenshot(path=str(output / "statistics-dashboard.png"), full_page=True)
                    staff.get_by_role("button", name="Switch language to English", exact=True).click()
                    expect(staff.get_by_role("heading", name="Complaint statistics")).to_be_visible()
                    expect(staff.get_by_role("img", name="Complaint volume bar chart")).to_be_visible()
                    staff.get_by_role("button", name="تغيير اللغة إلى العربية", exact=True).click()
                    expect(staff.get_by_role("heading", name="إحصائيات الشكاوى")).to_be_visible()
                    staff.get_by_role("button", name="تاريخ مخصص", exact=True).click()
                    expect(staff.get_by_label("من تاريخ", exact=True)).to_be_visible()
                    staff.get_by_role("button", name="إخفاء التواريخ", exact=True).click()
                    staff.get_by_role("button", name="٩٠ يومًا", exact=True).click()
                    expect(staff.get_by_role("button", name="٩٠ يومًا", exact=True)).to_have_attribute(
                        "aria-pressed", "true"
                    )
                    staff.set_viewport_size({"width": 390, "height": 844})
                    page_overflow = staff.evaluate("""() => {
                      const width = document.documentElement.clientWidth;
                      return [...document.querySelectorAll("body *")]
                        .map((element) => ({ element, rect: element.getBoundingClientRect() }))
                        .filter(({ rect }) => rect.right > width + 1 || rect.left < -1)
                        .map(({ element, rect }) => ({
                          tag: element.tagName,
                          className: typeof element.className === "string" ? element.className : "",
                          right: Math.round(rect.right),
                          left: Math.round(rect.left),
                          width: Math.round(rect.width),
                        }))
                        .slice(0, 12);
                    }""")
                    if staff.evaluate("document.documentElement.scrollWidth > innerWidth + 1"):
                        print("Statistics mobile overflow:", page_overflow)
                        staff.screenshot(path=str(output / "statistics-mobile-overflow.png"), full_page=True)
                    else:
                        staff.screenshot(path=str(output / "statistics-mobile.png"), full_page=True)
                    assert staff.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
                    assert staff.locator(".statistics-summary").evaluate(
                        "element => getComputedStyle(element).gridTemplateColumns.split(' ').length"
                    ) == 2
                    staff.set_viewport_size({"width": 1440, "height": 1000})
                    staff.get_by_role("button", name="تسجيل الخروج", exact=True).click()
                    staff.wait_for_url(base + "/", timeout=5000)
                    staff.goto(base + "/employee/login")
                    staff.get_by_label("اسم المستخدم", exact=True).fill("system_admin")
                    staff.get_by_label("كلمة المرور", exact=True).fill("test-only-not-a-live-password")
                    staff.get_by_role("button", name="دخول آمن", exact=True).click()
                    expect(staff).to_have_url(re.compile(r"/employee/complaints$"))
                    for route in ("directorates", "employees", "roles", "languages", "audit"):
                        staff.goto(base + f"/employee/admin/{route}")
                        expect(staff.locator("main h1")).to_be_visible()
                        page_text = staff.locator("main").inner_text()
                        assert "لا تملك صلاحية" not in page_text, f"{route}: {page_text}"

                    staff.goto(base + "/employee/admin/directorates")
                    staff.get_by_role("button", name="إضافة مديرية", exact=True).click()
                    expect(staff.get_by_role("dialog")).to_be_visible()
                    staff.get_by_label("الاسم", exact=True).fill("مديرية اختبار الحوار")
                    staff.get_by_role("button", name="حفظ", exact=True).click()
                    expect(staff.get_by_text("مديرية اختبار الحوار", exact=False)).to_be_visible()
                    staff.get_by_role(
                        "button", name="تعديل مديرية اختبار الحوار", exact=True
                    ).click()
                    staff.get_by_label("الوصف", exact=True).fill("تم تحديثها من نافذة التعديل")
                    staff.get_by_role("button", name="حفظ", exact=True).click()
                    expect(staff.get_by_text("تم تحديثها من نافذة التعديل")).to_be_visible()
                    staff.screenshot(path=str(output / "admin-directorates.png"), full_page=True)

                    staff.goto(base + "/employee/admin/roles")
                    staff.get_by_role("button", name="Switch language to English", exact=True).click()
                    expect(staff.get_by_role("heading", name="Roles & permission matrix")).to_be_visible()
                    expect(staff.get_by_role("button", name="Create role", exact=True)).to_be_visible()
                    staff.get_by_role("button", name="تغيير اللغة إلى العربية", exact=True).click()
                    expect(staff.get_by_role("heading", name="الأدوار ومصفوفة الصلاحيات")).to_be_visible()
                    staff.get_by_role("button", name="إنشاء دور", exact=True).click()
                    expect(staff.get_by_role("dialog")).to_be_visible()
                    staff.get_by_label("الرمز", exact=True).fill("qa_role")
                    staff.get_by_label("الاسم", exact=True).fill("دور اختبار الواجهة")
                    staff.get_by_label("الوصف", exact=True).fill("دور مخصص لاختبار الواجهة")
                    staff.get_by_role("checkbox").first.check()
                    staff.get_by_role("button", name="حفظ الدور", exact=True).click()
                    expect(staff.get_by_role("dialog")).to_have_count(0)
                    staff.locator("#role-search").fill("qa_role")
                    role_card = staff.locator(".admin-role-card").filter(has_text="qa_role")
                    expect(role_card).to_be_visible()
                    role_card.get_by_role("button", name="تعديل", exact=True).click()
                    staff.get_by_label("الاسم", exact=True).fill("دور اختبار محدث")
                    staff.get_by_role("button", name="حفظ الدور", exact=True).click()
                    expect(staff.get_by_text("دور اختبار محدث")).to_be_visible()
                    staff.screenshot(path=str(output / "admin-roles.png"), full_page=True)

                    staff.get_by_role("tab", name=re.compile("الصلاحيات")).click()
                    staff.get_by_role("button", name="Switch language to English", exact=True).click()
                    expect(staff.get_by_role("heading", name="Roles & permission matrix")).to_be_visible()
                    staff.get_by_role("tab", name=re.compile("Permissions")).click()
                    staff.locator("#permission-search").fill("complaints.view")
                    permission_row = staff.locator(".admin-permission-row").filter(
                        has_text="complaints.view"
                    )
                    expect(permission_row).to_be_visible()
                    permission_row.get_by_role("button", name="Edit", exact=True).click()
                    permission_name = staff.get_by_label("Arabic permission name", exact=True)
                    expect(permission_name).to_have_value("عرض الشكاوى")
                    permission_name.fill("صلاحية اختبار الترجمة")
                    staff.get_by_role("button", name="Update label", exact=True).click()
                    staff.get_by_role("button", name="تغيير اللغة إلى العربية", exact=True).click()
                    expect(staff.get_by_role("heading", name="الأدوار ومصفوفة الصلاحيات")).to_be_visible()
                    expect(staff.get_by_text("صلاحية اختبار الترجمة")).to_be_visible()
                    staff.screenshot(path=str(output / "admin-permissions.png"), full_page=True)

                    staff.goto(base + "/employee/admin/translations")
                    record_select = staff.locator(".admin-translation-controls select").nth(1)
                    record_select.select_option(index=1)
                    language_select = staff.locator(".admin-translation-controls select").nth(2)
                    language_select.select_option("en")
                    translation_name = staff.locator("#translation-name")
                    translation_name.fill("Temporary English role")
                    staff.get_by_label("الوصف", exact=True).fill("Translation persistence check")
                    staff.get_by_role("button", name="حفظ الترجمة", exact=True).click()
                    expect(staff.get_by_text(re.compile("حُفظت الترجمة|Translation saved"))).to_be_visible()
                    staff.screenshot(path=str(output / "admin-translations.png"), full_page=True)
                    staff.once("dialog", lambda dialog: dialog.accept())
                    staff.get_by_role("button", name="حذف الترجمة", exact=True).click()
                    expect(staff.get_by_text(re.compile("حُذفت الترجمة|Translation deleted"))).to_be_visible()

                    staff.set_viewport_size({"width": 390, "height": 844})
                    for route in ("directorates", "roles", "translations"):
                        staff.goto(base + f"/employee/admin/{route}")
                        expect(staff.locator("main h1")).to_be_visible()
                        assert staff.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), route
                        if route == "directorates":
                            staff.get_by_role("button", name="إضافة مديرية", exact=True).click()
                            dialog = staff.get_by_role("dialog")
                            expect(dialog).to_be_visible()
                            assert dialog.evaluate("element => element.getBoundingClientRect().width <= innerWidth")
                            staff.keyboard.press("Escape")
                            expect(dialog).to_have_count(0)
                        elif route == "roles":
                            staff.get_by_role("button", name="إنشاء دور", exact=True).click()
                            dialog = staff.get_by_role("dialog")
                            expect(dialog).to_be_visible()
                            assert dialog.evaluate("element => element.getBoundingClientRect().width <= innerWidth")
                            dialog.get_by_role("button", name="إلغاء", exact=True).click()
                            expect(dialog).to_have_count(0)
                    staff.set_viewport_size({"width": 1440, "height": 1000})
                    mobile = browser.new_context(viewport={"width": 390, "height": 844})
                    phone = mobile.new_page()
                    phone.on("pageerror", lambda error: errors.append(str(error)))
                    for route in ("/", "/complaints/new", "/public", "/track", "/access"):
                        phone.goto(base + route)
                        expect(phone.locator("main h1")).to_be_visible()
                        assert phone.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), route
                    assert not errors, errors
                    assert page.evaluate("Object.keys(localStorage)") == ["shakwa-language"]
                    assert page.evaluate("Object.keys(sessionStorage)") == []
                    browser.close()
                print("React checks passed: Arabic/English, guest submission+real uploads, tracking, privacy, no auto-key, login, staff/admin routes, mobile.")
            finally:
                server.terminate()
                server.wait(timeout=15)


if __name__ == "__main__":
    run()
