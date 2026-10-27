"""The fake hub plays a stream script back faithfully: each connection's frames in order, its
closes with their codes, a signed upgrade, and every way an SDK's stream can differ named."""

from __future__ import annotations

import asyncio
import base64
import time
from typing import Any

import pytest
from aiohttp import WSMsgType
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from mfx_fake_hub import TEST_KEY_ID, Case, Hub, make_app
from mfx_fake_hub import stream as stream_module
from mfx_fake_hub.server import signing_message

SIGNER = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
_NONCES = iter(f"{n:016d}" for n in range(10_000))


def upgrade_headers() -> dict[str, str]:
    timestamp, nonce = str(int(time.time() * 1000)), next(_NONCES)
    signature = SIGNER.sign(signing_message(timestamp, nonce, "GET", "/v1/stream", b""))
    return {
        "X-MFX-Key": TEST_KEY_ID,
        "X-MFX-Timestamp": timestamp,
        "X-MFX-Nonce": nonce,
        "X-MFX-Signature": base64.b64encode(signature).decode(),
    }


def case(stream: list[list[dict[str, Any]]]) -> Case:
    return Case.from_dict(
        {"id": "s", "rule": "r", "call": {"op": "stream.read"}, "observe": {}, "stream": stream}
    )


async def client_for(aiohttp_client: Any, *scripts: Case) -> Any:  # noqa: ANN401
    client = await aiohttp_client(make_app(Hub({c.id: c for c in scripts})))
    await client.post("/_hub/case", json={"id": "s"})
    return client


async def verdict(client: Any) -> dict[str, Any]:  # noqa: ANN401
    return await (await client.get("/_hub/verdict")).json()


async def test_the_hub_plays_a_stream_script_and_names_every_difference(
    aiohttp_client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Given a stream script of two connections, the first ending in a close with a code
    When an SDK opens both with signed upgrades and sends the frames the script expects
    Then it receives the script's frames and closes in order and the verdict is ok; and an
    unsigned upgrade, a wrong or missing frame, a frame that is not JSON, the connection ending
    early, a frame after the script, a connection the script does not have and one it expects
    but never sees are each named in the verdict."""
    script = case(
        [
            [
                {"recv": {"op": "subscribe", "ch": "events"}},
                {"send": {"op": "msg", "ch": "events", "seq": 1}},
                {"close": 4009, "reason": "lifetime"},
            ],
            [
                {"recv": {"op": "resume", "ch": "events", "after_seq": 1}},
                {"send": {"op": "msg", "ch": "events", "seq": 2}},
            ],
        ]
    )
    client = await client_for(aiohttp_client, script)
    first = await client.ws_connect("/v1/stream", headers=upgrade_headers())
    await first.send_str('{"op":"subscribe","ch":"events"}')
    assert (await first.receive_json())["seq"] == 1
    closed = await first.receive()
    assert closed.type == WSMsgType.CLOSE and closed.data == 4009
    second = await client.ws_connect("/v1/stream", headers=upgrade_headers())
    await second.send_str('{"op":"resume","ch":"events","after_seq":1}')
    assert (await second.receive_json())["seq"] == 2
    await second.close()
    await asyncio.sleep(0.05)
    assert await verdict(client) == {"ok": True, "problems": [], "requests": 0}

    monkeypatch.setattr(stream_module, "RECV_TIMEOUT_S", 0.2)
    client = await client_for(aiohttp_client, script)
    wrong = await client.ws_connect("/v1/stream")  # unsigned
    await wrong.send_str('{"op":"subscribe","ch":"md:x"}')
    await wrong.receive()  # the scripted message
    await wrong.receive()  # the scripted close
    extra = await client.ws_connect("/v1/stream", headers=upgrade_headers())
    await extra.send_str("not json")
    await asyncio.sleep(0.05)
    await extra.send_str('{"op":"ping"}')
    await extra.close()
    surplus = await client.ws_connect("/v1/stream", headers=upgrade_headers())
    assert (await surplus.receive()).data == 1011
    await asyncio.sleep(0.05)
    problems = "\n".join((await verdict(client))["problems"])
    for reason in (
        "stream connection 1: not signed",
        "frame field ch is 'md:x'",
        "a frame that is not a JSON object",
        "unexpected frame after the script",
        "stream connection 3 was opened, and the case expects no more",
    ):
        assert reason in problems, reason

    client = await client_for(aiohttp_client, script)
    silent = await client.ws_connect("/v1/stream", headers=upgrade_headers())
    await asyncio.sleep(0.4)
    await silent.close()
    problems = "\n".join((await verdict(client))["problems"])
    assert "no frame came" in problems
    assert "stream connection 1 stopped before step 1" in problems
    assert "stream connection 2 was never opened" in problems

    client = await client_for(aiohttp_client, script)
    gone = await client.ws_connect("/v1/stream", headers=upgrade_headers())
    await gone.close()
    await asyncio.sleep(0.05)
    assert "the connection ended" in "\n".join((await verdict(client))["problems"])
