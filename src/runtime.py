"""Streamlit session bridge to one long-lived asyncio loop and pooled gateway.

Only the Streamlit session thread polls a thread-safe queue. The provider's
asyncio loop never performs blocking queue.get(), time.sleep() or SDK I/O.
Connections are reused across requests on the SAME loop and closed on expiry.
"""
import asyncio
from contextlib import aclosing
from concurrent.futures import CancelledError as FutureCancelled
import queue
import threading
import time
from src.gateway import UnifiedLLMGateway
from src.errors import GatewayProviderError


class SessionRuntime:
    def __init__(self, idle_seconds=900):
        self._loop = asyncio.new_event_loop()
        self._gateway = None
        self._settings = None
        self._demo = None
        self._active = False
        self._last_used = time.monotonic()
        self._idle = idle_seconds
        self._thread = threading.Thread(target=self._run, daemon=True, name="gateway-session-loop")
        self._thread.start()

    @property
    def alive(self):
        return self._thread.is_alive() and not self._loop.is_closed()

    def _run(self):
        asyncio.set_event_loop(self._loop)
        self._loop.create_task(self._watchdog())
        try:
            self._loop.run_forever()
        finally:
            pending = asyncio.all_tasks(self._loop)
            for task in pending:
                task.cancel()
            self._loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            if self._gateway:
                self._loop.run_until_complete(self._gateway.aclose())
            self._loop.run_until_complete(self._loop.shutdown_asyncgens())
            self._loop.run_until_complete(self._loop.shutdown_default_executor())
            self._loop.close()

    async def _watchdog(self):
        while True:
            await asyncio.sleep(5)
            if not self._active and time.monotonic() - self._last_used > self._idle:
                self._loop.stop()
                return

    async def _work(self, output, settings, demo, prompt, model, temperature, max_tokens, simulate):
        async def emit(kind, value):
            while True:
                try:
                    output.put_nowait((kind, value))
                    return
                except queue.Full:
                    await asyncio.sleep(.01)
        if self._active:
            await emit("error", {"code":"busy", "message":"A request is already running in this session."})
            await emit("end", None)
            return
        self._active = True
        try:
            if self._gateway is None or self._settings != settings or self._demo != demo:
                if self._gateway:
                    await self._gateway.aclose()
                self._gateway = UnifiedLLMGateway(settings, demo=demo)
                self._settings, self._demo = settings, demo
            if simulate:
                from src.errors import AuthenticationError
                raise AuthenticationError("simulated")
            async with aclosing(self._gateway.stream(prompt, model, temperature, max_tokens)) as stream:
                async for chunk in stream:
                    await emit("chunk", chunk)
        except GatewayProviderError as exc:
            await emit("error", {"code":exc.code, "message":str(exc)})
        except asyncio.CancelledError:
            raise
        except Exception:
            await emit("error", {"code":"internal", "message":"Request failed safely. Check configuration; no provider details were exposed."})
        finally:
            self._active = False
            self._last_used = time.monotonic()
            try:
                output.put_nowait(("end", None))
            except queue.Full:
                pass

    def iter_events(self, settings, demo, prompt, model, temperature, max_tokens, simulate=False):
        output = queue.Queue(maxsize=512)
        future = asyncio.run_coroutine_threadsafe(self._work(output,settings,demo,prompt,model,temperature,max_tokens,simulate),self._loop)
        try:
            while True:
                try:
                    kind, value = output.get(timeout=.1)
                except queue.Empty:
                    if future.done():
                        try:
                            future.result()
                        except FutureCancelled:
                            pass
                        break
                    continue
                if kind == "end":
                    break
                yield kind, value
        finally:
            if not future.done():
                future.cancel()

    def close(self):
        if self.alive:
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join(timeout=5)
