"""
runner.py
=========
MirrorRunner — manages all active mirror bots concurrently.
Each mirror runs as an independent PTB Application in its own asyncio task.
The system bot can add new mirrors at runtime via start_mirror().
"""
import asyncio
import logging
from telegram.ext import Application
from mirror.main import build_mirror_app

logger = logging.getLogger(__name__)


class MirrorRunner:
    def __init__(self):
        self._tasks: dict[int, asyncio.Task] = {}          # mirror_id → task
        self._apps:  dict[int, Application]  = {}          # mirror_id → app

    async def start_all(self, mirrors: list[dict]):
        """Called at startup to launch all active mirrors from DB."""
        for m in mirrors:
            await self.start_mirror(m["id"], m["bot_token"])

    async def start_mirror(self, mirror_id: int, token: str):
        """Start a single mirror bot. Safe to call for already-running mirrors."""
        if mirror_id in self._tasks and not self._tasks[mirror_id].done():
            logger.info("Mirror %d already running — skipping", mirror_id)
            return

        app = build_mirror_app(token, mirror_id)
        self._apps[mirror_id] = app

        task = asyncio.create_task(
            self._run_app(mirror_id, app),
            name=f"mirror-{mirror_id}",
        )
        self._tasks[mirror_id] = task
        logger.info("Started mirror bot %d", mirror_id)

    async def stop_mirror(self, mirror_id: int):
        app = self._apps.get(mirror_id)
        if app:
            try:
                await app.stop()
                await app.shutdown()
            except Exception as e:
                logger.warning("Error stopping mirror %d: %s", mirror_id, e)
        task = self._tasks.get(mirror_id)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks.pop(mirror_id, None)
        self._apps.pop(mirror_id, None)
        logger.info("Stopped mirror bot %d", mirror_id)

    async def stop_all(self):
        for mid in list(self._tasks.keys()):
            await self.stop_mirror(mid)

    async def _run_app(self, mirror_id: int, app: Application):
        try:
            await app.initialize()
            await app.start()
            await app.updater.start_polling(
                allowed_updates=["message", "callback_query", "chat_member"],
            )
            # Keep running until cancelled
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            logger.info("Mirror %d task cancelled", mirror_id)
        except Exception as e:
            logger.error("Mirror %d crashed: %s", mirror_id, e)
        finally:
            try:
                await app.updater.stop()
                await app.stop()
                await app.shutdown()
            except Exception:
                pass
