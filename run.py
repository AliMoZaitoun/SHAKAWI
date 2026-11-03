"""Run the web app and, when configured, the existing Telegram polling bot."""
import asyncio
import os
import signal
import sys


async def main():
    processes = []
    web = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5000"
    )
    processes.append(web)
    if os.environ.get("BOT_TOKEN"):
        # Give the API a chance to finish startup before Telegram updates arrive.
        await asyncio.sleep(2)
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
