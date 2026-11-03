"""End-to-end recovery UI against an isolated synthetic database.

Run: PYTHONPATH=. python tests/browser_recovery.py
Telegram's external transport is replaced by authenticated backend calls.
"""
import base64
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
                    key_requests = []
                    page.on("request", lambda request: key_requests.append(True)
                            if request.method == "POST" and request.url.endswith("/recovery/key") else None)
                    page.locator("#c-first-name").fill("مالك")
                    page.locator("#c-last-name").fill("تجريبي")
                    page.locator("#c-phone").fill("0998765432")
                    page.locator("#c-national-id").fill("98765432101")
                    page.locator("#c-id-card").set_input_files({
                        "name": "synthetic-identity.png", "mimeType": "image/png",
                        "buffer": base64.b64decode(
                            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0l"
                            "EQVR42mP8/x8AAwMCAO+aXioAAAAASUVORK5CYII="),
                    })
                    page.locator('[onclick="goToStep2()"]').click()
                    page.locator("#comp-title").fill("شكوى اختبار الاستعادة")
                    page.locator("#comp-details").fill("تفاصيل شكوى مخصصة للاختبار")
                    page.locator("#comp-entity").select_option("2")
                    page.locator("#comp-type").select_option("طرق")
                    with page.expect_response("**/id-image/") as identity_response:
                        page.locator("#submit-complaint").click()
                    identity_path = root / identity_response.value.json()["file_path"]
                    expect(page.locator("#sec-view")).to_be_visible()
                    owner_response = context.request.get(
                        "http://127.0.0.1:8008/api/v1/citizens/recovery/me")
                    assert owner_response.ok
                    citizen_id = owner_response.json()["citizen"]["id"]
                    assert owner_response.json()["has_recovery_key"] is False
                    assert not key_requests, "Submission must not silently issue or rotate an account key"
                    expect(page.locator("#post-submit-recovery")).to_be_visible()
                    expect(page.locator("#post-submit-recovery")).to_contain_text("رمز متابعة الشكوى")
                    page.locator("#post-submit-issue-recovery-key").click()
                    expect(page.locator("#post-submit-recovery-key")).not_to_be_empty()
                    key = page.locator("#post-submit-recovery-key").inner_text()
                    assert len(key_requests) == 1
                    with page.expect_download() as download:
                        page.locator("#download-post-submit-recovery-key").click()
                    assert Path(download.value.path()).read_text().strip() == key
                    page.once("dialog", lambda dialog: dialog.dismiss())
                    page.locator("#post-submit-issue-recovery-key").click()
                    assert len(key_requests) == 1, "Cancelling replacement must preserve the existing key"
                    expect(page.locator("#post-submit-recovery-key")).to_have_text(key)
                    assert page.locator("body").evaluate("(el) => el.scrollWidth <= innerWidth")
                    page.screenshot(path=str(output / "post-submit-mobile.png"), full_page=True,
                                    mask=[page.locator("#post-submit-recovery-key")])
                    page.locator("#open-citizen-access").click()
                    expect(page.locator("#owner-access")).to_be_visible()
                    page.once("dialog", lambda dialog: dialog.accept())
                    page.locator("#issue-recovery-key").click()
                    expect(page.locator("#new-recovery-key")).not_to_be_empty()
                    assert len(key_requests) == 2
                    expect(page.locator("#post-submit-recovery-key")).to_be_empty()
                    assert page.locator("#new-recovery-key").inner_text() != key
                    key = page.locator("#new-recovery-key").inner_text()
                    assert page.evaluate("([key]) => !location.href.includes(key) && !JSON.stringify(localStorage).includes(key) && !JSON.stringify(sessionStorage).includes(key)", [key])
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
                    expect(page.locator("#new-recovery-key")).to_be_empty()
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
                print("Recovery browser checks passed: real submission, visible key save/download, replacement consent, no auto-issuance or web storage, key recovery, Telegram consent and recovery, mobile layout.")
            finally:
                server.terminate()
                server.wait(timeout=10)
                # Delete only the synthetic upload made by this isolated test.
                if "identity_path" in locals() and identity_path.parent.resolve() == (root / "uploads").resolve():
                    identity_path.unlink(missing_ok=True)


if __name__ == "__main__":
    run()
