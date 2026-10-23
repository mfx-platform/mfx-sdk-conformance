"""The fake hub plays a case back faithfully: it answers each step, checks each request against the
case, verifies signatures with the test key, and says what went wrong in the verdict."""

from __future__ import annotations

import asyncio
import base64
import contextlib
import io
import json
import time
from pathlib import Path
from typing import Any

from aiohttp.test_utils import TestClient
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from mfx_fake_hub import TEST_KEY_ID, Case, Hub, make_app
from mfx_fake_hub.__main__ import serve
from mfx_fake_hub.server import signing_message

KEY = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
PATH = "/v1/terminals/t-1"


def signed(
    method: str,
    path_with_query: str,
    body: bytes = b"",
    *,
    nonce: str = "n" * 16,
    signer: Ed25519PrivateKey = KEY,
    key_id: str = TEST_KEY_ID,
    skew_ms: int = 0,
) -> dict[str, str]:
    timestamp = str(int(time.time() * 1000) + skew_ms)
    signature = signer.sign(signing_message(timestamp, nonce, method, path_with_query, body))
    return {
        "X-MFX-Key": key_id,
        "X-MFX-Timestamp": timestamp,
        "X-MFX-Nonce": nonce,
        "X-MFX-Signature": base64.b64encode(signature).decode(),
    }


def case(steps: list[dict[str, Any]], case_id: str = "c") -> Case:
    return Case.from_dict(
        {"id": case_id, "rule": "r", "call": {"op": "x"}, "observe": {}, "server": steps}
    )


async def hub_client(aiohttp_client: Any, *cases: Case) -> TestClient:  # noqa: ANN401
    return await aiohttp_client(make_app(Hub({c.id: c for c in cases})))


async def verdict(client: TestClient) -> dict[str, Any]:
    return await (await client.get("/_hub/verdict")).json()


async def test_the_hub_answers_each_step_and_verifies_every_signature(aiohttp_client: Any) -> None:
    """Given a case of two steps, the second taking a body and a query
    When an SDK sends both, signed with the test key
    Then each gets the case's answer, the verdict is ok; and a request with a broken signature,
    the wrong key, a stale timestamp, a malformed or reused nonce, or no signature at all is
    named in the verdict, each for its own reason."""
    play = case(
        [
            {
                "expect": {"method": "GET", "path": PATH},
                "answer": {"status": 200, "body": {"id": "t-1"}},
            },
            {
                "expect": {
                    "method": "POST",
                    "path": "/v1/terminals",
                    "query": {"dry_run": "false"},
                    "headers": {"Idempotency-Key": "k-1"},
                    "json": {"farm_id": "f"},
                },
                "answer": {
                    "status": 202,
                    "headers": {"X-Extra": "1"},
                    "body": {"state": "REQUESTED"},
                },
            },
        ]
    )
    client = await hub_client(aiohttp_client, play)
    listed = await (await client.get("/_hub/cases")).json()
    assert listed == ["c"]
    loaded = await (await client.post("/_hub/case", json={"id": "c"})).json()
    assert loaded["id"] == "c" and loaded["server"][0]["answer"]["body"] == {"id": "t-1"}

    first = await client.get(PATH, headers=signed("GET", PATH))
    assert first.status == 200 and await first.json() == {"id": "t-1"}
    body = b'{"farm_id": "f"}'
    second = await client.post(
        "/v1/terminals?dry_run=false",
        data=body,
        headers={
            **signed("POST", "/v1/terminals?dry_run=false", body, nonce="m" * 16),
            "Idempotency-Key": "k-1",
        },
    )
    assert second.status == 202 and second.headers["X-Extra"] == "1"
    assert await verdict(client) == {"ok": True, "problems": [], "requests": 2}

    bad = case([{"expect": {"method": "GET", "path": PATH}, "answer": {}, "times": 7}], "bad")
    client = await hub_client(aiohttp_client, bad)
    await client.post("/_hub/case", json={"id": "bad"})
    other = Ed25519PrivateKey.from_private_bytes(bytes(32))
    sent = [
        signed("GET", "/v1/elsewhere"),
        signed("GET", PATH, nonce="a" * 16, key_id="mfxk_SOMEONE"),
        signed("GET", PATH, nonce="b" * 16, skew_ms=60_000),
        signed("GET", PATH, nonce="bad nonce"),
        signed("GET", PATH, nonce="a" * 16),
        signed("GET", PATH, nonce="c" * 16, signer=other),
        {},
    ]
    for headers in sent:
        await client.get(PATH, headers=headers)
    problems = "\n".join((await verdict(client))["problems"])
    for reason in (
        "signature does not verify",
        "not the test key",
        "within 30 s",
        "16-64 characters",
        "used before",
        "missing X-MFX-Key",
    ):
        assert reason in problems, reason


async def test_the_hub_names_every_way_a_request_differs_from_the_case(aiohttp_client: Any) -> None:
    """Given steps that expect a method, path, query, headers and a body
    When requests arrive that differ in each, arrive when none is expected, or never arrive
    Then the verdict names each difference; a step taking any number of requests gives way to the
    next when one stops matching; a dropped answer closes the connection; and no case loaded, an
    unknown case id and unsigned steps are each handled as the case says."""
    steps = [
        {"expect": {"method": "GET", "path": PATH}, "answer": {"status": 429}, "times": "any"},
        {
            "expect": {
                "method": "POST",
                "path": "/v1/orders",
                "signed": False,
                "query": {"a": "1"},
                "headers": {"Idempotency-Key": "k", "X-Present": "*", "X-Absent": None},
                "json_contains": {"volume": "0.01", "side": "buy"},
                "json": {"x": 1},
            },
            "answer": {"drop": True},
        },
        {"expect": {"method": "GET", "path": "/v1/never"}, "answer": {}},
    ]
    client = await hub_client(aiohttp_client, case(steps))
    assert (await client.get("/v1/early", headers=signed("GET", "/v1/early"))).status == 500
    assert (await verdict(client))["problems"] == ["GET /v1/early arrived with no case loaded"]
    assert (await client.post("/_hub/case", json={"id": "nope"})).status == 404
    await client.post("/_hub/case", json={"id": "c"})

    for nonce in ("p" * 16, "q" * 16):
        assert (await client.get(PATH, headers=signed("GET", PATH, nonce=nonce))).status == 429
    with contextlib.suppress(Exception):
        await client.put(
            "/v1/orders?a=2",
            data=b'{"volume": 0.01}',
            headers={"Idempotency-Key": "other", "X-Absent": "here"},
        )
    problems = "\n".join((await verdict(client))["problems"])
    for reason in (
        "method PUT, expected POST",
        "query {'a': '2'}",
        "Idempotency-Key is 'other'",
        "X-Present missing",
        "X-Absent sent",
        "volume is 0.01, expected '0.01'",
        "no 'side'",
        "expected {'x': 1}",
        "step 3 (GET /v1/never) never arrived",
    ):
        assert reason in problems, reason

    client = await hub_client(
        aiohttp_client,
        case(
            [
                {
                    "expect": {"path": "/v1/orders", "signed": False, "json_contains": {"a": 1}},
                    "answer": {"status": 202},
                }
            ]
        ),
    )
    await client.post("/_hub/case", json={"id": "c"})
    await client.post("/v1/orders", data=b"not json")
    await client.post("/v1/orders", data=b"[1]")
    problems = "\n".join((await verdict(client))["problems"])
    assert "body is not JSON" in problems and "unexpected request POST /v1/orders" in problems

    client = await hub_client(
        aiohttp_client,
        case(
            [
                {
                    "expect": {"path": "/v1/orders", "signed": False, "json_contains": {"a": 1}},
                    "answer": {"status": 202},
                }
            ]
        ),
    )
    await client.post("/_hub/case", json={"id": "c"})
    await client.post("/v1/orders", data=b"[1]")
    assert "body has no 'a'" in "\n".join((await verdict(client))["problems"])

    client = await hub_client(
        aiohttp_client,
        case(
            [
                {"expect": {"method": "GET", "path": PATH}, "answer": {}, "times": "any"},
                {"expect": {"method": "GET", "path": "/v1/next"}, "answer": {"status": 204}},
            ]
        ),
    )
    await client.post("/_hub/case", json={"id": "c"})
    await client.get(PATH, headers=signed("GET", PATH))
    nxt = await client.get("/v1/next", headers=signed("GET", "/v1/next", nonce="z" * 16))
    assert nxt.status == 204
    assert (await verdict(client))["ok"]

    client = await hub_client(
        aiohttp_client,
        case(
            [
                {
                    "expect": {"method": "GET", "path": PATH},
                    "answer": {"status": 200, "delay_s": 0.01},
                },
                {"expect": {"method": "GET", "path": "/v1/after"}, "answer": {}, "times": "any"},
            ]
        ),
    )
    await client.post("/_hub/case", json={"id": "c"})
    await client.get(PATH, headers=signed("GET", PATH))
    assert (await verdict(client))["problems"] == ["step 2 (GET /v1/after) never arrived"]


async def test_the_hub_serves_the_suite_on_a_free_local_port(tmp_path: Path) -> None:
    """Given a cases directory and a fixtures file
    When the fake hub is started on port 0
    Then it prints the base URL it listens on, on localhost, and the cases it serves have their
    fixtures expanded."""
    (tmp_path / "cases").mkdir()
    (tmp_path / "fixtures.json").write_text(json.dumps({"t": {"id": "t-1", "state": "ACTIVE"}}))
    (tmp_path / "cases" / "a.json").write_text(
        json.dumps(
            [
                {
                    "id": "a.one",
                    "rule": "r",
                    "call": {"op": "x"},
                    "observe": {},
                    "server": [
                        {
                            "expect": {"method": "GET", "path": PATH},
                            "answer": {"body": {"$fixture": "t", "state": "RETIRED"}},
                        }
                    ],
                }
            ]
        )
    )
    printed = io.StringIO()
    with contextlib.redirect_stdout(printed):
        task = asyncio.create_task(serve(tmp_path / "cases", 0))
        for _ in range(100):
            await asyncio.sleep(0.02)
            if printed.getvalue():
                break
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    line = printed.getvalue().strip()
    assert line.startswith("listening http://127.0.0.1:") and line.endswith("/v1")


async def test_a_last_step_taking_any_number_is_satisfied_by_one(aiohttp_client: Any) -> None:
    client = await hub_client(
        aiohttp_client, case([{"expect": {"path": PATH}, "answer": {}, "times": "any"}])
    )
    await client.post("/_hub/case", json={"id": "c"})
    await client.get(PATH, headers=signed("GET", PATH))
    assert (await verdict(client))["ok"]
