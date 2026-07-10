"""Tests for BridgeMetrics and the /health, /metrics HTTP server."""

from __future__ import annotations

import asyncio
import contextlib

import httpx

from mcp2xiaozhi.metrics import BridgeMetrics, start_metrics_server


def test_render_prometheus_format():
    m = BridgeMetrics(
        name="calc", transport="stdio", connected=True, ws_to_mcp=3, mcp_to_ws=2, reconnects=1
    )
    text = m.render()
    assert "# HELP mcp2xiaozhi_connected" in text
    assert "# TYPE mcp2xiaozhi_connected gauge" in text
    assert 'mcp2xiaozhi_connected{server="calc"} 1' in text
    assert 'mcp2xiaozhi_messages_total{server="calc",direction="ws_to_mcp"} 3' in text
    assert 'mcp2xiaozhi_messages_total{server="calc",direction="mcp_to_ws"} 2' in text
    assert 'mcp2xiaozhi_reconnects_total{server="calc"} 1' in text


def test_render_disconnected_gauge_is_zero():
    m = BridgeMetrics(name="x", connected=False)
    assert 'mcp2xiaozhi_connected{server="x"} 0' in m.render()


def test_render_escapes_label_value():
    m = BridgeMetrics(name='se"r')
    text = m.render()
    # Prometheus escapes backslash and quote and newline in label values.
    assert 'server="se\\"r"' in text


def test_as_dict_shape():
    m = BridgeMetrics(name="calc", transport="sse", connected=True, ws_to_mcp=1, tool_calls_blocked=2)
    d = m.as_dict()
    assert d["name"] == "calc"
    assert d["transport"] == "sse"
    assert d["connected"] is True
    assert d["ws_to_mcp"] == 1
    assert d["tool_calls_blocked"] == 2


async def test_metrics_server_health_and_metrics_and_404():
    collectors = [
        BridgeMetrics(name="calc", transport="stdio", connected=True, ws_to_mcp=5, mcp_to_ws=4)
    ]
    server = await start_metrics_server("127.0.0.1", 0, collectors)
    port = server.sockets[0].getsockname()[1]
    task = asyncio.create_task(server.serve_forever())
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"http://127.0.0.1:{port}/health")
            assert r.status_code == 200
            data = r.json()
            assert data["status"] == "ok"
            assert data["servers"][0]["name"] == "calc"
            assert data["servers"][0]["connected"] is True
            assert data["servers"][0]["ws_to_mcp"] == 5

            r = await client.get(f"http://127.0.0.1:{port}/metrics")
            assert r.status_code == 200
            assert "mcp2xiaozhi_connected" in r.text
            assert 'server="calc"' in r.text
            assert "mcp2xiaozhi_messages_total" in r.text

            r = await client.get(f"http://127.0.0.1:{port}/nope")
            assert r.status_code == 404
    finally:
        server.close()
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
