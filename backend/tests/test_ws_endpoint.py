"""WebSocket endpoint integration tests — requires running backend on port 3090.

These tests connect to the actual WebSocket endpoint, so the backend must be running:
    cd backend && .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 3090

Skip automatically if the backend is not reachable.
"""

import asyncio
import json
import pytest

try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False

WS_URL = "ws://localhost:3090/api/v1/ws/virtual-human"

pytestmark = [
    pytest.mark.skipif(not HAS_WEBSOCKETS, reason="websockets library not installed"),
]


async def _check_backend_running() -> bool:
    """Check if backend WS endpoint is reachable."""
    try:
        async with websockets.connect(WS_URL, open_timeout=2) as ws:
            await ws.close()
        return True
    except Exception:
        return False


@pytest.fixture(autouse=True)
async def skip_if_backend_down():
    """Skip tests if backend is not running."""
    if not await _check_backend_running():
        pytest.skip("Backend not running on localhost:3090")


class TestWSConnectAndInit:
    @pytest.mark.asyncio
    async def test_ws_connect_and_init(self):
        """First frame should be type=init with expected fields."""
        async with websockets.connect(WS_URL) as ws:
            raw = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(raw)
            assert data["type"] == "init"
            assert "vitals" in data
            assert "interactions" in data
            assert "categories" in data
            assert "ecg_sr" in data
            assert data["ecg_sr"] == 500
            assert data["pcg_sr"] == 4000


class TestWSSignalFrames:
    @pytest.mark.asyncio
    async def test_receives_signal_frames(self):
        """Should receive signal frames within 500ms."""
        async with websockets.connect(WS_URL) as ws:
            # Skip init frame
            await asyncio.wait_for(ws.recv(), timeout=5)

            signal_count = 0
            for _ in range(5):
                raw = await asyncio.wait_for(ws.recv(), timeout=2)
                data = json.loads(raw)
                if data["type"] == "signal":
                    signal_count += 1
                    assert "ecg" in data
                    assert "pcg" in data
                    assert "vitals" in data
                    assert "t" in data
                    assert len(data["ecg"]) == 50
                    assert len(data["pcg"]) == 400

            assert signal_count >= 2


class TestWSCommand:
    @pytest.mark.asyncio
    async def test_send_command(self):
        """Sending run command should increase heart rate over time."""
        async with websockets.connect(WS_URL) as ws:
            # Get init frame
            init_raw = await asyncio.wait_for(ws.recv(), timeout=5)
            init_data = json.loads(init_raw)
            initial_hr = init_data["vitals"]["heart_rate"]

            # Send run command
            await ws.send(json.dumps({
                "type": "command",
                "command": "run",
                "params": {},
            }))

            # Wait for HR to start changing (collect several frames)
            max_hr = initial_hr
            for _ in range(30):  # ~3 seconds of frames
                raw = await asyncio.wait_for(ws.recv(), timeout=2)
                data = json.loads(raw)
                if data["type"] == "signal":
                    hr = data["vitals"]["heart_rate"]
                    max_hr = max(max_hr, hr)

            assert max_hr > initial_hr + 5  # HR should have increased


class TestWSInvalidCommand:
    @pytest.mark.asyncio
    async def test_send_invalid_command(self):
        """Unknown command should produce an error frame."""
        async with websockets.connect(WS_URL) as ws:
            # Skip init
            await asyncio.wait_for(ws.recv(), timeout=5)

            await ws.send(json.dumps({
                "type": "command",
                "command": "totally_invalid_command_xyz",
                "params": {},
            }))

            # Look for error frame among the next few messages
            found_error = False
            for _ in range(10):
                raw = await asyncio.wait_for(ws.recv(), timeout=2)
                data = json.loads(raw)
                if data["type"] == "error":
                    found_error = True
                    assert "message" in data
                    break

            assert found_error, "Expected an error frame for invalid command"


class TestWSPingPong:
    @pytest.mark.asyncio
    async def test_ping_pong(self):
        """Sending ping should get pong response."""
        async with websockets.connect(WS_URL) as ws:
            # Skip init
            await asyncio.wait_for(ws.recv(), timeout=5)

            await ws.send(json.dumps({"type": "ping"}))

            # Look for pong among next messages
            found_pong = False
            for _ in range(10):
                raw = await asyncio.wait_for(ws.recv(), timeout=2)
                data = json.loads(raw)
                if data["type"] == "pong":
                    found_pong = True
                    break

            assert found_pong, "Expected a pong frame"
