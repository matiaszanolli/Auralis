"""Artwork bodies are read in full or refused, never silently truncated (#6190, #6191).

``StreamReader.read(n)`` returns only what is buffered, so the old
``read(limit + 1)`` returned ~128 KB of a 1 MiB cover and the over-limit check
could not fire. These tests use a real aiohttp server, since mocking
``content.read`` is exactly what hid it.
"""

import sys
from pathlib import Path

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from services.artwork_providers.bounded_read import read_bounded, read_bounded_json

MIB = 1024 * 1024


async def _serve(handler):
    app = web.Application()
    app.router.add_get("/body", handler)
    server = TestServer(app)
    await server.start_server()
    return server


async def _fetch(server, limit, reader=read_bounded):
    async with aiohttp.ClientSession() as session:
        async with session.get(server.make_url("/body")) as resp:
            return await reader(resp, limit)


@pytest.mark.asyncio
async def test_a_body_larger_than_the_first_buffer_is_returned_whole():
    payload = bytes(range(256)) * (MIB // 256)  # 1 MiB, with Content-Length

    async def handler(request):
        return web.Response(body=payload)

    server = await _serve(handler)
    try:
        assert await _fetch(server, 5 * MIB) == payload
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_a_chunked_body_over_the_limit_is_refused_not_truncated():
    async def handler(request):  # no Content-Length: the pre-check cannot catch it
        resp = web.StreamResponse()
        await resp.prepare(request)
        for _ in range(6):
            await resp.write(b"x" * MIB)
        return resp

    server = await _serve(handler)
    try:
        assert await _fetch(server, 5 * MIB) is None
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_json_over_the_limit_is_refused_and_small_json_decodes():
    async def handler(request):
        return web.json_response({"pad": "y" * (2 * MIB)})

    server = await _serve(handler)
    try:
        assert await _fetch(server, MIB, read_bounded_json) is None
        decoded = await _fetch(server, 5 * MIB, read_bounded_json)
        assert len(decoded["pad"]) == 2 * MIB
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_a_declared_length_over_the_limit_is_refused_before_reading():
    async def handler(request):
        return web.Response(body=b"x" * (2 * MIB))

    server = await _serve(handler)
    try:
        assert await _fetch(server, MIB) is None
    finally:
        await server.close()
