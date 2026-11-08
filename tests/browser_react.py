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
                    page.get_by_label("صورة الهوية (مطلوبة)", exact=True).set_input_files(image)
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
                    page.get_by_label("عنوان الشكوى", exact=True).fill("طلب صيانة إنارة الحديقة")
                    page.get_by_role("combobox").select_option(index=1)
                    page.get_by_label("نوع الشكوى", exact=True).fill("إنارة")
                    page.get_by_label("التفاصيل", exact=True).fill("طلب تجريبي لإصلاح الإنارة في الطريق الرئيسي.")
                    page.get_by_label("مرفقات اختيارية", exact=True).set_input_files(image)
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
                    staff.screenshot(path=str(output / "staff-complaint.png"), full_page=True)
                    staff.goto(base + "/employee/statistics")
                    expect(staff.get_by_text("إجمالي الشكاوى", exact=True)).to_be_visible()
                    for route in ("directorates", "employees", "roles", "languages", "audit"):
                        staff.goto(base + f"/employee/admin/{route}")
                        expect(staff.locator("main h1")).to_be_visible()
                        assert "لا تملك صلاحية" not in staff.locator("main").inner_text()
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
