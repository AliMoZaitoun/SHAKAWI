"""End-to-end recovery UI against an isolated synthetic database.

Run: PYTHONPATH=. python tests/browser_recovery.py
Telegram's external transport is replaced by authenticated backend calls.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

from playwright.sync_api import sync_playwright, expect


def run():
    root = Path(__file__).resolve().parents[1]
    output = root / "generated-artifacts" / "recovery-check"
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="recovery-browser-") as temp:
        env = os.environ.copy()
        for key in ("REPLIT_DEV_DOMAIN", "REPLIT_DEPLOYMENT", "GOVERNOR_PASSWORD", "SERVICES_PASSWORD"):
            env.pop(key, None)
        env.update(SHAKWA_DATABASE_URL=f"sqlite:///{temp}/test.db",
                   BOT_TOKEN="browser-test-only-bot-token", ENABLE_DEMO_ACCOUNTS="0")
        with (output / "server.log").open("w") as log:
            server = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app",
                                       "--host", "127.0.0.1", "--port", "8008"],
                                      cwd=root, env=env, stdout=log, stderr=log)
            try:
                for _ in range(60):
                    try:
                        urllib.request.urlopen("http://127.0.0.1:8008/health")
                        break
                    except OSError:
                        time.sleep(0.2)
                with sync_playwright() as p:
                    browser = p.chromium.launch(executable_path=shutil.which("chromium"),
                                                headless=True, args=["--no-sandbox"])
                    context = browser.new_context(viewport={"width": 390, "height": 844})
                    page = context.new_page()
                    errors = []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.goto("http://127.0.0.1:8008/")
                    response = context.request.post("http://127.0.0.1:8008/api/v1/citizens/", data={
                        "first_name": "مالك", "last_name": "تجريبي", "phone": "0998765432",
                        "national_id": "98765432101"})
                    assert response.ok
                    citizen_id = response.json()["id"]
                    assert context.request.post("http://127.0.0.1:8008/api/v1/complaints/", data={
                        "citizen_id": citizen_id, "directorate_id": 2,
                        "title": "شكوى اختبار الاستعادة", "details": "تفاصيل شكوى مخصصة للاختبار",
                        "category": "طرق", "is_public": False}).ok
                    page.reload()
                    page.locator("#citizen-access summary").click()
                    expect(page.locator("#owner-access")).to_be_visible()
                    page.locator("#issue-recovery-key").click()
                    expect(page.locator("#new-recovery-key")).not_to_be_empty()
                    key = page.locator("#new-recovery-key").inner_text()
                    page.locator("#link-consent").check()
                    page.locator("#issue-telegram-link").click()
                    expect(page.locator("#link-command")).to_contain_text("/link ")
                    token = page.locator("#link-command").inner_text().split()[1]
                    assert context.request.post(
                        "http://127.0.0.1:8008/api/v1/citizens/recovery/telegram/confirm-link",
                        data={"token": token, "telegram_id": 98765},
                        headers={"X-Bot-Token": env["BOT_TOKEN"]}).ok
                    context.clear_cookies()
                    page.reload()
                    page.locator("#citizen-access summary").click()
                    expect(page.locator("#owner-access")).not_to_be_visible()
                    page.locator("#recovery-key").fill(key)
                    page.locator("#restore-key-form button").click()
                    expect(page.locator("#owner-access")).to_be_visible()
                    expect(page.locator("#citizen-complaints")).to_contain_text("شكوى اختبار الاستعادة")
                    page.locator("#citizen-complaints button").click()
                    expect(page.locator("#sec-view")).to_be_visible()
                    page.locator("#tab-submit").click()
                    context.clear_cookies()
                    page.reload()
                    page.locator("#citizen-access summary").click()
                    page.locator("#recovery-telegram").fill("98765")
                    page.locator("#recovery-consent").check()
                    page.locator("#restore-telegram-form button").click()
                    expect(page.locator("#recovery-command")).to_contain_text("/recover ")
                    token = page.locator("#recovery-command").inner_text().split()[1]
                    assert context.request.post(
                        "http://127.0.0.1:8008/api/v1/citizens/recovery/telegram/approve",
                        data={"token": token, "telegram_id": 98765},
                        headers={"X-Bot-Token": env["BOT_TOKEN"]}).ok
                    page.locator("#finish-recovery").click()
                    expect(page.locator("#owner-access")).to_be_visible()
                    expect(page.locator("#citizen-complaints")).to_contain_text("شكوى اختبار الاستعادة")
                    assert page.locator("body").evaluate("(el) => el.scrollWidth <= innerWidth")
                    page.screenshot(path=str(output / "recovered-mobile.png"), full_page=True)
                    assert not errors, errors
                    browser.close()
                print("Recovery browser checks passed: key recovery, Telegram consent and recovery, complaint access, mobile layout.")
            finally:
                server.terminate()
                server.wait(timeout=10)


if __name__ == "__main__":
    run()
