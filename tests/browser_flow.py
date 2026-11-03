"""Manual browser regression: isolated synthetic database, no live citizen data."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

from playwright.sync_api import sync_playwright, expect
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.complaint import Complaint
from app.models.user import Citizen


def run():
    root = Path(__file__).resolve().parents[1]
    output = root / "generated-artifacts" / "browser-check"
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="shakwa-browser-") as temp:
        database = Path(temp) / "test.db"
        engine = create_engine(f"sqlite:///{database}")
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            citizen = Citizen(first_name="مواطن", last_name="تجريبي", phone="0900000000",
                              national_id="00000000000")
            db.add(citizen)
            db.flush()
            db.add_all([
                Complaint(citizen_id=citizen.id, tracking_code="CMP-BROWSER-PUBLIC",
                          directorate_id=2, category="طرق", title="إصلاح الطريق الرئيسي",
                          details="طلب صيانة الطريق وتعبيده لتحسين مرور المركبات",
                          is_public=True, status="RESOLVED", progress=100,
                          resolution_report="تمت صيانة الطريق وإعادة فتحه أمام المركبات"),
                Complaint(citizen_id=citizen.id, tracking_code="CMP-BROWSER-PRIVATE",
                          directorate_id=1, category="أخرى", title="شكوى خاصة للمحافظة",
                          details="تفاصيل شكوى خاصة لا تظهر في الدليل", is_public=False),
            ])
            db.commit()
        engine.dispose()
        with (output / "server.log").open("w") as log:
            server = subprocess.Popen([
                "env", "-u", "REPLIT_DEV_DOMAIN", "-u", "REPLIT_DEPLOYMENT",
                "-u", "GOVERNOR_PASSWORD", "-u", "SERVICES_PASSWORD",
                f"SHAKWA_DATABASE_URL=sqlite:///{database}", "ENABLE_DEMO_ACCOUNTS=1",
                "APP_ENV=test", "BOT_TOKEN=", sys.executable, "-m", "uvicorn",
                "app.main:app", "--host", "127.0.0.1", "--port", "8008",
            ], cwd=root, stdout=log, stderr=log)
            try:
                for _ in range(60):
                    try:
                        urllib.request.urlopen("http://127.0.0.1:8008/health", timeout=1)
                        break
                    except OSError:
                        time.sleep(0.2)
                else:
                    raise RuntimeError("Isolated browser test server did not start")
                with sync_playwright() as p:
                    browser = p.chromium.launch(executable_path=shutil.which("chromium"),
                                                headless=True, args=["--no-sandbox"])
                    page = browser.new_page(viewport={"width": 1280, "height": 900})
                    errors = []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.goto("http://127.0.0.1:8008/#public")
                    expect(page.locator("#sec-public")).to_be_visible()
                    expect(page.get_by_text("إصلاح الطريق الرئيسي", exact=True)).to_be_visible()
                    expect(page.get_by_text("شكوى خاصة للمحافظة", exact=True)).not_to_be_visible()
                    page.goto("http://127.0.0.1:8008/#public-1")
                    expect(page.get_by_text("تمت صيانة الطريق وإعادة فتحه أمام المركبات", exact=True)).to_be_visible()
                    page.locator("#public-report-reason-1").fill("معلومات طرف ثالث تحتاج مراجعة")
                    page.get_by_role("button", name="إرسال للمراجعة", exact=True).click()
                    expect(page.locator("#public-detail")).to_contain_text("تم استلام البلاغ للمراجعة")
                    page.screenshot(path=str(output / "public-desktop.png"), full_page=True)
                    page.set_viewport_size({"width": 390, "height": 844})
                    page.screenshot(path=str(output / "public-mobile.png"), full_page=True)
                    page.set_viewport_size({"width": 1280, "height": 900})
                    page.get_by_role("button", name="دخول الموظفين", exact=True).click()
                    page.locator("#login-username").fill("services")
                    page.locator("#login-password").fill("123456")
                    page.locator("#login-form button[type=submit]").click()
                    expect(page.locator("#sec-list")).to_be_visible()
                    expect(page.locator("#complaints-table-body")).to_contain_text("إصلاح الطريق الرئيسي")
                    expect(page.locator("#complaints-table-body")).not_to_contain_text("شكوى خاصة للمحافظة")
                    expect(page.locator("#complaints-table-body")).to_contain_text("بلاغات: 1")
                    page.get_by_role("button", name="معالجة الشكوى", exact=True).click()
                    expect(page.locator("#p-public-review")).to_contain_text("معلومات طرف ثالث تحتاج مراجعة")
                    page.locator("#review-decision-reason").fill("إخفاء مؤقت لحماية خصوصية الطرف الآخر")
                    page.get_by_role("button", name="حفظ قرار المراجعة", exact=True).click()
                    expect(page.locator("#p-public-review")).to_contain_text("نصوص شكواك العامة مخفية")
                    page.goto("http://127.0.0.1:8008/#public-1")
                    expect(page.locator("#public-detail")).to_contain_text("مخفية مؤقتًا")
                    expect(page.locator("#public-detail")).not_to_contain_text("إصلاح الطريق الرئيسي")
                    expect(page.locator("#public-detail")).not_to_contain_text("تمت صيانة الطريق")
                    expect(page.locator("#public-detail")).not_to_contain_text("الطرف الآخر")
                    page.screenshot(path=str(output / "hidden-public-text.png"), full_page=True)
                    page.locator("#tab-view").click()
                    page.locator("#search-code-input").fill("CMP-BROWSER-PUBLIC")
                    page.locator("#track-button").click()
                    expect(page.locator("#v-public-review")).to_contain_text("إخفاء مؤقت لحماية خصوصية الطرف الآخر")
                    page.locator("#owner-report-reason-1").fill("اعتراض على إخفاء النص وطلب إعادة مراجعته")
                    page.locator("#v-public-review").get_by_role("button", name="إرسال للمراجعة").click()
                    expect(page.locator("#v-public-review")).to_contain_text("تم استلام البلاغ")
                    page.locator("#tab-list").click()
                    page.get_by_role("button", name="معالجة الشكوى", exact=True).click()
                    expect(page.locator("#p-public-review")).to_contain_text("اعتراض على إخفاء النص")
                    page.locator("#review-decision-reason").fill("راجعت النصوص وأؤكد سلامتها لإعادة إظهارها")
                    page.once("dialog", lambda dialog: dialog.accept())
                    page.get_by_role("button", name="حفظ قرار المراجعة", exact=True).click()
                    expect(page.locator("#p-public-review")).to_contain_text("أُعيد إظهار النصوص العامة")
                    page.goto("http://127.0.0.1:8008/#public-1")
                    expect(page.locator("#public-detail")).to_contain_text("إصلاح الطريق الرئيسي")
                    expect(page.locator("#public-detail")).to_contain_text("تمت صيانة الطريق")
                    page.locator("#tab-statistics").click()
                    expect(page.locator("#stats-results")).to_be_visible()
                    expect(page.locator("#stats-summary")).to_contain_text("1")
                    page.screenshot(path=str(output / "services-statistics.png"), full_page=True)
                    page.get_by_role("button", name="تغيير كلمة المرور", exact=True).click()
                    page.locator("#current-password").fill("123456")
                    page.locator("#new-password").fill("browser-test-new-password")
                    page.locator("#password-form button[type=submit]").click()
                    expect(page.locator("#password-dialog")).not_to_be_visible()
                    # A failed request must not claim that the server session ended.
                    page.route("**/api/v1/auth/logout", lambda route: route.abort("failed"))
                    page.get_by_role("button", name="تسجيل الخروج", exact=True).click()
                    expect(page.locator("#notice")).to_contain_text("تعذر تسجيل الخروج")
                    expect(page.get_by_role("button", name="تسجيل الخروج", exact=True)).to_be_visible()
                    expect(page.locator("#tab-statistics")).to_be_visible()
                    page.unroute("**/api/v1/auth/logout")
                    page.reload()
                    expect(page.get_by_role("button", name="تسجيل الخروج", exact=True)).to_be_visible()
                    page.get_by_role("button", name="تسجيل الخروج", exact=True).click()
                    expect(page.locator("#tab-statistics")).not_to_be_visible()
                    page.get_by_role("button", name="دخول الموظفين", exact=True).click()
                    page.locator("#login-username").fill("governor")
                    page.locator("#login-password").fill("123456")
                    page.locator("#login-form button[type=submit]").click()
                    expect(page.locator("#complaints-table-body")).to_contain_text("شكوى خاصة للمحافظة")
                    page.locator("#tab-statistics").click()
                    expect(page.locator("#stats-results")).to_be_visible()
                    expect(page.locator("#stats-summary")).to_contain_text("2")
                    page.screenshot(path=str(output / "governor-statistics.png"), full_page=True)
                    assert not errors, errors
                    browser.close()
                print("Browser checks passed: public desktop/mobile, report/hide/owner notice/objection/restore, both roles, statistics, password change, logout.")
            finally:
                server.terminate()
                server.wait(timeout=15)


if __name__ == "__main__":
    run()
