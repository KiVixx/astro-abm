from __future__ import annotations

import json
import os
from typing import Any


class RequestBodyLimitMiddleware:
    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http" or scope.get("method") in {"GET", "HEAD", "OPTIONS"}:
            await self.app(scope, receive, send)
            return

        maximum = _max_request_body_bytes()
        content_length = _content_length(scope)
        if content_length is not None and content_length > maximum:
            await _send_too_large(send, maximum)
            return

        body = bytearray()
        while True:
            message = await receive()
            if message.get("type") == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > maximum:
                await _send_too_large(send, maximum)
                return
            if not message.get("more_body", False):
                break

        delivered = False

        async def replay() -> dict[str, Any]:
            nonlocal delivered
            if delivered:
                return {"type": "http.disconnect"}
            delivered = True
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        await self.app(scope, replay, send)


def _max_request_body_bytes() -> int:
    try:
        value = int(os.getenv("ASTRO_ABM_MAX_REQUEST_BODY_BYTES", str(4 * 1024 * 1024)))
    except ValueError:
        value = 4 * 1024 * 1024
    return max(1024, min(64 * 1024 * 1024, value))


def _content_length(scope: dict[str, Any]) -> int | None:
    for name, value in scope.get("headers", []):
        if name.lower() != b"content-length":
            continue
        try:
            return max(0, int(value.decode("ascii")))
        except (UnicodeDecodeError, ValueError):
            return None
    return None


async def _send_too_large(send: Any, maximum: int) -> None:
    body = json.dumps(
        {"detail": "request body too large", "max_bytes": maximum},
        separators=(",", ":"),
    ).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
                (b"cache-control", b"no-store"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
