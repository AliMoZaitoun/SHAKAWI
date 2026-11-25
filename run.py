"""Run the web app and, when configured, the existing Telegram polling bot."""
import asyncio
import os
import signal
import sys
import aiohttp


def runtime_port():
    try:
        return int(os.environ.get("PORT", "5000"))
    except ValueError as exc:
        raise RuntimeError("PORT must be a valid integer") from exc


def configure_bot_api_url(port):
    # In a single Render Web Service, the bot can call the API over loopback.
    # Preserve an explicitly configured URL when the bot runs elsewhere.
    current = os.environ.get("API_BASE_URL", "").rstrip("/")
    local_default = "http://127.0.0.1:5000/api/v1"
    if not current or (port != 5000 and current == local_default):
        os.environ["API_BASE_URL"] = f"http://127.0.0.1:{port}/api/v1"


async def wait_for_api(web, port, timeout=120):
    deadline = asyncio.get_running_loop().time() + timeout
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=2)) as client:
        while web.returncode is None and asyncio.get_running_loop().time() < deadline:
            try:
                async with client.get(f"http://127.0.0.1:{port}/health") as response:
                    if response.status == 200:
                        return
            except (aiohttp.ClientError, TimeoutError):
                pass
            await asyncio.sleep(0.25)
    raise RuntimeError("API startup did not complete; Telegram polling was not started")


async def main():
    port = runtime_port()
    configure_bot_api_url(port)
    processes = []
    web = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", str(port)
    )
    processes.append(web)
    if os.environ.get("BOT_TOKEN"):
        # Backups and schema upgrades can exceed a fixed two-second sleep.
        try:
            await wait_for_api(web, port)
        except Exception:
            if web.returncode is None:
                web.terminate()
                await web.wait()
            raise
        processes.append(await asyncio.create_subprocess_exec(sys.executable, "-m", "bot.main"))
    else:
        print("Telegram polling is disabled: BOT_TOKEN is not configured.", flush=True)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    watchers = [asyncio.create_task(process.wait()) for process in processes]
    shutdown = asyncio.create_task(stop.wait())
    done, pending = await asyncio.wait(watchers + [shutdown], return_when=asyncio.FIRST_COMPLETED)
    failed = not stop.is_set()
    for process in processes:
        if process.returncode is None:
            process.terminate()
    for task in pending:
        task.cancel()
    await asyncio.gather(*(process.wait() for process in processes))
    if failed:
        raise SystemExit("A service exited. Check configuration and workflow logs.")


if __name__ == "__main__":
    asyncio.run(main())
