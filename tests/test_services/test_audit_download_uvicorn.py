"""AuditedDownload against a real uvicorn server over raw local sockets.

uvicorn's ``send`` silently drops writes once the client is gone and may not
suspend at all, and its ``receive`` reports ``http.disconnect`` after every
completed response. These tests prove the recorded outcome against both of
its HTTP protocol implementations. Synchronisation is by in-process events,
not sleeps, so they are deterministic; they skip if no local port can be bound.
"""

from __future__ import annotations

import asyncio
import contextlib
import socket
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field

import pytest
import uvicorn

from cti.services import audit
from cti.services.audit import AuditOutcome

TIMEOUT = 5.0
HTTP_IMPLS = ["h11", "httptools"]


@dataclass
class Recorder:
    """Duck-typed ``Disclosure`` that captures the outcome in memory."""

    outcomes: list[tuple[str, int]] = field(default_factory=list)
    recorded: asyncio.Event = field(default_factory=asyncio.Event)

    async def record_outcome(self, outcome, summary) -> None:
        self.outcomes.append((AuditOutcome(outcome).value, summary["bytes_sent"]))
        self.recorded.set()


App = Callable[..., Awaitable[None]]


@contextlib.asynccontextmanager
async def serve(app: App, http: str) -> AsyncIterator[int]:
    if http == "httptools":
        pytest.importorskip("httptools")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # Inherited by accepted sockets: keeps kernel buffering small so that
        # the server's transport, not the kernel, holds unsent bytes.
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4096)
        sock.bind(("127.0.0.1", 0))
        sock.listen()
    except OSError as exc:  # sandboxed: no local sockets
        pytest.skip(f"cannot bind a local port: {exc}")
    sock.setblocking(False)
    config = uvicorn.Config(
        app,
        http=http,
        lifespan="off",
        log_level="critical",
        access_log=False,
        timeout_graceful_shutdown=1,
    )
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve(sockets=[sock]))
    try:
        async with asyncio.timeout(TIMEOUT):
            while not server.started:
                if task.done():
                    task.result()
                await asyncio.sleep(0.005)
        yield sock.getsockname()[1]
    finally:
        server.should_exit = True
        await asyncio.wait_for(task, TIMEOUT)
        sock.close()


async def connect(port: int, *, rcvbuf: int | None = None):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if rcvbuf is not None:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, rcvbuf)
    sock.setblocking(False)
    await asyncio.get_running_loop().sock_connect(sock, ("127.0.0.1", port))
    return await asyncio.open_connection(sock=sock)


REQUEST = b"GET /download HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n"


@pytest.mark.parametrize("http", HTTP_IMPLS)
async def test_client_gone_before_response_records_interrupted(http: str) -> None:
    recorder = Recorder()

    async def app(scope, receive, send) -> None:
        assert (await receive())["type"] == "http.request"
        # The handler is still busy (say, querying) when the client aborts.
        assert (await receive())["type"] == "http.disconnect"
        await audit.AuditedDownload(b"abcdefgh", disclosure=recorder)(scope, receive, send)

    async with serve(app, http) as port:
        _, writer = await connect(port)
        writer.write(REQUEST)
        await writer.drain()
        writer.transport.abort()
        await asyncio.wait_for(recorder.recorded.wait(), TIMEOUT)

    assert recorder.outcomes == [("interrupted", 0)]


@pytest.mark.parametrize("http", HTTP_IMPLS)
async def test_disconnect_while_final_send_is_flow_controlled(http: str) -> None:
    recorder = Recorder()
    chunk = 2 * 1024 * 1024
    body = b"x" * (2 * chunk)
    final_send_entered = asyncio.Event()

    async def app(scope, receive, send) -> None:
        async def watched_send(message: dict) -> None:
            if message.get("more_body") is False:
                final_send_entered.set()
            await send(message)

        response = audit.AuditedDownload(body, disclosure=recorder, chunk_size=chunk)
        await response(scope, receive, watched_send)

    async with serve(app, http) as port:
        _, writer = await connect(port, rcvbuf=4096)
        writer.write(REQUEST)
        await writer.drain()
        # The client never reads: the first 2 MB chunk overfills the server's
        # write buffer, so the final send is parked waiting for it to drain.
        await asyncio.wait_for(final_send_entered.wait(), TIMEOUT)
        await asyncio.sleep(0)
        writer.transport.abort()
        await asyncio.wait_for(recorder.recorded.wait(), TIMEOUT)

    [(outcome, bytes_sent)] = recorder.outcomes
    assert outcome == "interrupted"
    assert bytes_sent == chunk < len(body)


@pytest.mark.parametrize("http", HTTP_IMPLS)
async def test_normal_download_records_completed(http: str) -> None:
    recorder = Recorder()
    body = bytes(range(256)) * 1200  # 307,200 bytes in five chunks

    async def app(scope, receive, send) -> None:
        response = audit.AuditedDownload(body, disclosure=recorder, chunk_size=64 * 1024)
        await response(scope, receive, send)

    async with serve(app, http) as port:
        reader, writer = await connect(port)
        writer.write(REQUEST)
        await writer.drain()
        raw = await asyncio.wait_for(reader.read(), TIMEOUT)  # until the server closes
        writer.close()
        await asyncio.wait_for(recorder.recorded.wait(), TIMEOUT)

    head, _, received = raw.partition(b"\r\n\r\n")
    assert head.startswith(b"HTTP/1.1 200")
    assert received == body
    assert recorder.outcomes == [("completed", len(body))]
