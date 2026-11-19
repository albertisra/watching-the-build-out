"""Local CONNECT proxy that counts the bytes GDAL receives over the network.

Machine-wide byte counters are useless on a shared laptop (other jobs download at the same
time) and GDAL hides its HTTP traffic from Python, so GDAL is pointed at this proxy through
``GDAL_HTTP_PROXY``. The proxy only tunnels (TLS stays end to end) and counts the bytes of both
directions per tunnel. ``bytes_down`` is what the remote servers sent us (TLS records, so a few
percent above the payload); ``tunnels`` counts CONNECT requests, a lower bound on HTTP requests
because curl reuses connections.
"""

from __future__ import annotations

import asyncio
import contextlib
import threading

from .quota import GLOBAL


class CountingProxy:
    def __init__(self):
        self.bytes_down = 0
        self.bytes_up = 0
        self.tunnels = 0
        self.port: int | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._ready = threading.Event()

    async def _pipe(self, r, w, down: bool):
        try:
            while True:
                data = await r.read(65536)
                if not data:
                    break
                if down:
                    self.bytes_down += len(data)
                    GLOBAL.add(net_bytes_proxy=len(data))
                else:
                    self.bytes_up += len(data)
                w.write(data)
                await w.drain()
        except (ConnectionError, asyncio.CancelledError):
            pass
        finally:
            with contextlib.suppress(OSError, RuntimeError):
                w.close()

    async def _handle(self, reader, writer):
        try:
            head = await reader.readuntil(b"\r\n\r\n")
            line = head.split(b"\r\n")[0].decode()
            method, target, _ = line.split(" ")
            if method != "CONNECT":
                writer.write(b"HTTP/1.1 405 Method Not Allowed\r\n\r\n")
                writer.close()
                return
            host, port = target.rsplit(":", 1)
            ur, uw = await asyncio.open_connection(host, int(port))
            self.tunnels += 1
            GLOBAL.add(net_tunnels=1)
            writer.write(b"HTTP/1.1 200 Connection established\r\n\r\n")
            await writer.drain()
            await asyncio.gather(self._pipe(reader, uw, False), self._pipe(ur, writer, True))
        except (OSError, ValueError, asyncio.IncompleteReadError, asyncio.LimitOverrunError):
            with contextlib.suppress(OSError, RuntimeError):
                writer.close()

    def start(self) -> int:
        def run():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            server = self._loop.run_until_complete(
                asyncio.start_server(self._handle, "127.0.0.1", 0))
            self.port = server.sockets[0].getsockname()[1]
            self._ready.set()
            self._loop.run_forever()

        threading.Thread(target=run, daemon=True).start()
        self._ready.wait(10)
        return int(self.port)


_PROXY: CountingProxy | None = None


def ensure_proxy() -> CountingProxy:
    """Start the proxy once and route GDAL's HTTP traffic through it."""
    global _PROXY
    if _PROXY is None:
        from . import io as bio

        _PROXY = CountingProxy()
        port = _PROXY.start()
        bio.GDAL_ENV["GDAL_HTTP_PROXY"] = f"http://127.0.0.1:{port}"
        bio.GDAL_ENV["GDAL_PROXY_AUTH"] = "BASIC"
    return _PROXY
