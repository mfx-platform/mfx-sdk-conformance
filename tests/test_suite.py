"""The suite itself is well formed: every case loads, names an operation and an outcome the
vocabulary knows, cites the API section it proves, and the error cases match the API description."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import pytest

from mfx_fake_hub import load_cases

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import make_error_cases  # noqa: E402

VOCABULARY = json.loads((ROOT / "vocabulary.json").read_text(encoding="utf-8"))


def test_every_case_is_well_formed_and_the_error_cases_follow_the_api(tmp_path: Path) -> None:
    """Given the suite's cases, fixtures and vocabulary, and the vendored API description
    When the suite is loaded
    Then ids are unique and namespaced by their file, every operation and error kind is in the
    vocabulary, every case cites its source and expects only /v1 paths, no fixture marker is left
    unexpanded, each observes exactly one outcome, and the error cases are exactly what the API
    description's codes give - so a new code is a new case; and a duplicate id is refused."""
    cases = load_cases(ROOT / "cases")
    assert len(cases) >= 30
    ops, kinds = set(VOCABULARY["ops"]), set(VOCABULARY["errors"])
    for case in cases.values():
        area = case.id.split(".")[0]
        assert (ROOT / "cases" / f"{area}.json").is_file(), case.id
        assert case.call["op"] in ops, case.id
        assert case.source and case.rule, case.id
        outcome = set(case.observe) - {"fields"}
        assert len(outcome) == 1 and outcome <= set(VOCABULARY["observe"]), case.id
        if "raises" in case.observe:
            assert case.observe["raises"] in kinds, case.id
        if "returns" in case.observe:  # a runner maps only the fields the vocabulary names
            named = set(VOCABULARY["ops"][case.call["op"]]["returns"])
            assert set(case.observe["returns"]) <= named, case.id
        for step in case.server:
            assert step.expect["path"].startswith("/v1/"), case.id
        assert "$fixture" not in json.dumps(case.raw), case.id

    assert make_error_cases.main(["--check"]) == 0
    codes = make_error_cases.known_codes(
        __import__("yaml").safe_load((ROOT / "spec" / "openapi.yaml").read_text(encoding="utf-8"))
    )
    assert {f"errors.{code}" for code in codes} <= set(cases)
    assert cases["errors.rate_limited"].observe["raises"] == "RateLimitError"
    assert cases["errors.no_room"].observe["raises"] == "ConflictError"  # by status

    (tmp_path / "cases").mkdir()
    one = {"id": "x.one", "rule": "r", "call": {"op": "x"}, "observe": {}}
    (tmp_path / "cases" / "a.json").write_text(json.dumps([one]))
    (tmp_path / "cases" / "b.json").write_text(json.dumps(one))
    with pytest.raises(ValueError, match="x.one is in both"):
        load_cases(tmp_path / "cases")


COPY = [case for case in load_cases(ROOT / "cases").values() if case.id.startswith("copy.")]
#: The contract's closed list of reasons a copy did not fill (CopyReason), in its order.
REFUSAL_REASONS = [
    "mapping",
    "min_volume",
    "no_stop",
    "risk_rule",
    "plan_limit",
    "stopped_out",
    "signal_expired",
    "skip_pending",
    "close_only",
    "paused",
    "account_not_connected",
    "market_closed",
    "no_conversion",
    "not_on_this_venue",
    "venue_unavailable",
    "broker",
]


def test_every_copy_operation_has_a_case_and_every_copy_write_carries_its_key() -> None:
    """Given the copy cases and the vocabulary's copy operations
    When the suite is loaded
    Then every copy operation is called by at least one case, every request a copy case expects is
    under /v1/copy, every write (a POST, PATCH or DELETE other than the preview) expects the
    Idempotency-Key the call was given, and the preview, which is a read, and a rollover's dry
    run, which changes nothing, expect none."""
    ops = {op for op in VOCABULARY["ops"] if op.startswith("copy.")}
    assert ops == {case.call["op"] for case in COPY}
    for case in COPY:
        for step in case.server:
            expect = step.expect
            assert expect["path"].startswith("/v1/copy/"), case.id
            dry_run = expect["path"].endswith("/rollover") and case.call["args"]["dry_run"]
            if expect["path"] == "/v1/copy/followers/preview" or dry_run:
                assert expect["headers"] == {"Idempotency-Key": None}, case.id
            elif expect["method"] != "GET":
                key = case.call["args"]["idempotency_key"]
                assert expect["headers"] == {"Idempotency-Key": key}, case.id


def test_the_copy_cases_read_every_refusal_reason_and_refuse_a_word_outside_the_list() -> None:
    """Given the contract's closed list of refusal reasons
    When the copy cases are read
    Then one case serves every reason, in the list's order, and observes each read back as sent,
    with the venue's own code beside broker only; and one case asks for a reason outside the list
    and observes it refused before anything is sent."""
    by_id = {case.id: case for case in COPY}
    every = by_id["copy.log_reads_every_refusal_reason"]
    rows = every.server[0].answer["body"]["items"]
    assert [row["reason"] for row in rows] == REFUSAL_REASONS
    assert every.observe["returns"]["reasons"] == REFUSAL_REASONS
    assert [row["reason"] for row in rows if row["venue_code"]] == ["broker"]
    outside = by_id["copy.log_reason_outside_the_closed_list_refused"]
    assert outside.server == ()
    assert outside.observe == {"refuses": "invalid_argument"}
    assert not set(outside.call["args"]["reason"]) & set(REFUSAL_REASONS)
    for case in COPY:
        for reason in case.observe.get("returns", {}).get("reasons", []):
            assert reason is None or reason in REFUSAL_REASONS or reason == "in_another_group"


#: Each copy event's fields as the contract types them: ``str`` a text (a decimal is text, never a
#: JSON number), ``float`` a JSON number, ``dict`` an object, ``list`` an array, and ``None``
#: beside another kind where the contract allows null. Every field listed is required.
_COMMON: dict[str, tuple[Any, ...]] = {
    "schema_version": (str,),
    "follower_id": (str,),
    "leader_id": (str,),
    "account_id": (str,),
    "venue": (str,),
    "at": (str,),
}
COPY_EVENT_SHAPES: dict[str, dict[str, tuple[Any, ...]]] = {
    "copy.copied": {
        **_COMMON,
        "signal_id": (str,),
        "command_id": (str,),
        "deal": (dict,),
        "as": (dict,),
        "latency_ms": (float, None),
        "slippage": (str, None),
        "stages": (dict,),
    },
    "copy.refused": {
        **_COMMON,
        "signal_id": (str,),
        "deal": (dict,),
        "outcome": (str,),
        "reason": (str,),
        "venue_code": (str, None),
        "why": (str, None),
        "risk": (dict, None),
    },
    "copy.stopout": {
        **_COMMON,
        "stopout_id": (str,),
        "limit": (str,),
        "used": (str,),
        "closed": (list,),
    },
    "copy.drift": {**_COMMON, "drift_pct": (str,)},
    "copy.state_changed": {**_COMMON, "from": (str,), "to": (str,), "why": (str,)},
    "copy.closed": {
        **_COMMON,
        "close_id": (str,),
        "cause": (str,),
        "state": (str,),
        "closed": (list,),
        "not_closed": (list,),
    },
}
#: The nested objects, by the field that holds them (``closed`` holds a list of them).
_PARTS: dict[str, dict[str, tuple[Any, ...]]] = {
    "deal": {
        "action": (str,),
        "side": (str,),
        "units": (str,),
        "price": (str, None),
        "instrument_key": (str, None),
    },
    "as": {"symbol": (str,), "side": (str,), "volume": (str,), "price": (str, None)},
    "closed": {"symbol": (str,), "volume": (str,), "command_id": (str, None)},
    "not_closed": {"symbol": (str,), "volume": (str, None), "why": (str, None)},
    "risk": {
        "reason": (str,),
        "rule": (str, None),
        "policy_id": (str, None),
        "version": (float, None),
        "used": (str, None),
        "limit": (str, None),
        "would_be": (str, None),
        "challenge_id": (str, None),
        "challenge_version": (float, None),
    },
}
#: The contract's CopyDecimal, and the fields that are one.
_DECIMAL = re.compile(r"^-?[0-9]+(\.[0-9]+)?$")
_DECIMALS = {"units", "price", "volume", "slippage", "used", "drift_pct"}


def _fits(value: Any, kinds: tuple[Any, ...]) -> bool:  # noqa: ANN401 - any JSON value
    if value is None:
        return None in kinds
    if isinstance(value, bool):
        return False
    if float in kinds and isinstance(value, int | float):
        return True
    return any(kind is not None and type(value) is kind for kind in kinds)


def _shape_problems(where: str, data: Any, shape: dict[str, tuple[Any, ...]]) -> list[str]:  # noqa: ANN401
    """How ``data`` differs from the contract's shape; empty when it is exactly that shape."""
    if not isinstance(data, dict):
        return [f"{where} is not an object"]
    out = [f"{where}.{name} is not the contract's" for name in data if name not in shape]
    for name, kinds in shape.items():
        if name not in data:
            out.append(f"{where}.{name} is missing")
            continue
        value = data[name]
        if not _fits(value, kinds):
            out.append(f"{where}.{name} is {value!r}, not {'/'.join(map(_kind, kinds))}")
        elif name in _DECIMALS and isinstance(value, str) and not _DECIMAL.match(value):
            out.append(f"{where}.{name} is {value!r}, not a decimal")
        elif name in _PARTS and isinstance(value, dict):
            out += _shape_problems(f"{where}.{name}", value, _PARTS[name])
        elif name in _PARTS and isinstance(value, list):
            for index, item in enumerate(value):
                out += _shape_problems(f"{where}.{name}[{index}]", item, _PARTS[name])
        elif name == "stages":
            for stage, ms in value.items():
                if not stage.endswith("_ms") or not _fits(ms, (float,)):
                    out.append(f"{where}.stages.{stage} is {ms!r}, not milliseconds as a number")
    return out


def _kind(kind: Any) -> str:  # noqa: ANN401 - a type or None
    return {str: "text", float: "number", dict: "object", list: "array", None: "null"}[kind]


def test_each_copy_event_has_its_case_in_the_contracts_shape_naming_accounts_and_venues() -> None:
    """Given the copy events cases
    When their stream scripts are read
    Then there is one case for each of copy.copied, copy.refused, copy.stopout, copy.drift,
    copy.state_changed and copy.closed, each sending its one event on the events channel; every
    payload is exactly the contract's shape - nested objects as objects, numbers as numbers,
    decimals as decimal text, nulls as null, every required field and no other (a refusal's Risk
    detail is null or an object) - and names the follower account and its
    venue, never a terminal, a ticket, a magic number or an MT5 return code; a cTrader follower's
    volumes are in units; a refusal carries its reason and the venue's own code; and a payload
    with a number as text, an object as text, a decimal as a number or a field the contract does
    not have is named a problem."""
    events = [case for case in COPY if case.call["op"] == "copy.read_events"]
    kinds: list[str] = []
    payloads: dict[str, dict[str, Any]] = {}
    for case in events:
        (connection,) = case.stream
        sent = [step["send"] for step in connection if step.get("send", {}).get("op") == "msg"]
        assert len(sent) == 1 == case.call["args"]["count"], case.id
        (message,) = sent
        kind, data = message["type"], message["data"]
        kinds.append(kind)
        payloads[kind] = data
        assert message["ch"] == "events" and message["seq"] == 1, case.id
        assert _shape_problems(kind, data, COPY_EVENT_SHAPES[kind]) == [], case.id
        text = json.dumps(data)
        for word in ("terminal", "ticket", "magic", "mt5_retcode"):
            assert word not in text, (case.id, word)
        returns = case.observe["returns"]
        assert returns["types"] == [kind], case.id
        assert returns["accounts"] == [data["account_id"]], case.id
        assert returns["venues"] == [data["venue"]] == ["ctrader"], case.id
        assert returns["reasons"] == [data.get("reason")], case.id
        volumes = [data.get("as", {}).get("volume")] + [i["volume"] for i in data.get("closed", [])]
        assert all(v is None or "." not in v for v in volumes), (case.id, "cTrader is in units")
    assert kinds == list(COPY_EVENT_SHAPES)
    assert payloads["copy.refused"]["reason"] in REFUSAL_REASONS
    assert payloads["copy.refused"]["venue_code"]

    copied, shape = payloads["copy.copied"], COPY_EVENT_SHAPES["copy.copied"]
    deal = json.dumps(copied["deal"])
    assert _shape_problems("e", {**copied, "latency_ms": "12.5"}, shape) == [
        "e.latency_ms is '12.5', not number/null"
    ]
    assert _shape_problems("e", {**copied, "deal": deal}, shape) == [
        f"e.deal is {deal!r}, not object"
    ]
    assert _shape_problems("e", {**copied, "stages": {"detect_ms": "2"}}, shape) == [
        "e.stages.detect_ms is '2', not milliseconds as a number"
    ]
    assert _shape_problems("e", {**copied, "slippage": 0.5, "terminal_id": "t"}, shape) == [
        "e.terminal_id is not the contract's",
        "e.slippage is 0.5, not text/null",
    ]
    assert _shape_problems("e", {**copied, "slippage": "2e-5", "latency_ms": True}, shape) == [
        "e.latency_ms is True, not number/null",
        "e.slippage is '2e-5', not a decimal",
    ]
    assert _shape_problems("e", "{}", shape) == ["e is not an object"]
    closed = {**payloads["copy.stopout"], "closed": [{"symbol": "EURUSD", "volume": 50000}]}
    assert _shape_problems("e", closed, COPY_EVENT_SHAPES["copy.stopout"]) == [
        "e.closed[0].volume is 50000, not text",
        "e.closed[0].command_id is missing",
    ]


def _schemas() -> dict[str, Any]:
    spec = __import__("yaml").safe_load(
        (ROOT / "spec" / "openapi.yaml").read_text(encoding="utf-8")
    )
    return spec["components"]["schemas"]  # type: ignore[no-any-return]


def _missing(schema: dict[str, Any], body: dict[str, Any]) -> list[str]:
    """The fields the schema requires that ``body`` does not carry."""
    return [name for name in schema.get("required", []) if name not in body]


def test_the_copy_cases_answer_in_the_contracts_final_shapes_and_a_group_close_names_pause() -> (
    None
):
    """Given the vendored API description and the copy cases
    When each answer and each request body a copy case holds is read
    Then a group's close sends exactly its reason and pause, pause being required with no
    default, and answers every field of CopyGroupCloseResult; a rollover answers every field of
    CopyGroupRolloverResult and each member's result; every requested close listed carries every
    field of CopyClose and every page the stats of CopyClosePage; every copy log row carries the
    leader's deal, the follower's symbol and the Risk detail, and the log's stats the p95s; and
    every preview row names both contract sizes and the follower's volume unit."""
    schemas = _schemas()
    assert schemas["CopyGroupClose"]["required"] == ["reason", "pause"]
    assert schemas["CopyGroupClose"]["additionalProperties"] is False
    page_stats = schemas["CopyClosePage"]["properties"]["stats"]
    log_stats = schemas["CopyLogPage"]["properties"]["stats"]
    preview_row = schemas["CopyPreview"]["properties"]["rows"]["items"]
    seen: set[str] = set()
    for case in COPY:
        op = case.call["op"]
        for step in case.server:
            body = step.answer.get("body") or {}
            if op == "copy.close_group":
                sent = step.expect["json"]
                assert set(sent) == {"reason", "pause"} and isinstance(sent["pause"], bool), case.id
                assert _missing(schemas["CopyGroupCloseResult"], body) == [], case.id
            elif op == "copy.rollover_group":
                assert _missing(schemas["CopyGroupRolloverResult"], body) == [], case.id
                item = schemas["CopyGroupRolloverResult"]["properties"]["results"]["items"]
                assert all(_missing(item, r) == [] for r in body["results"]), case.id
            elif op == "copy.closes":
                assert _missing(page_stats, body["stats"]) == [], case.id
                assert all(_missing(schemas["CopyClose"], c) == [] for c in body["items"]), case.id
            elif op == "copy.log" and body:
                assert _missing(log_stats, body["stats"]) == [], case.id
                rows = body["items"]
                assert all(_missing(schemas["CopyLogEntry"], r) == [] for r in rows), case.id
            elif op == "copy.preview_follower":
                assert all(_missing(preview_row, r) == [] for r in body["rows"]), case.id
            else:
                continue
            seen.add(op)
    assert seen == {
        "copy.close_group",
        "copy.rollover_group",
        "copy.closes",
        "copy.log",
        "copy.preview_follower",
    }
    assert _missing(schemas["CopyClose"], {}) and _missing(log_stats, {"copies": 1})


#: The cases that answer an enum word the contract does not list, and the fields that carry it.
LATER_WORDS = {
    "copy.closes_a_cause_from_a_later_version_is_read_not_refused": ("CopyClose", {"cause"}),
    "copy.leaders_a_source_and_state_from_a_later_version_are_read_not_refused": (
        "CopyLeader",
        {"source", "state"},
    ),
}


def test_an_enum_word_from_a_later_version_is_answered_and_the_call_returns() -> None:
    """Given the vendored API description and the copy cases that answer a word it does not list
    When each such case's answer is read
    Then every named field is a contract enum the item carries with a word outside that enum's
    list, the item is otherwise in the contract's shape, and the case observes the call returning
    (never raising) with the page's ids in the order served - so an SDK that fails on a word a
    later version adds fails the suite."""
    schemas = _schemas()
    cases = {case.id: case for case in COPY}
    for case_id, (schema_name, fields) in LATER_WORDS.items():
        case = cases[case_id]
        schema = schemas[schema_name]
        items = [i for step in case.server for i in step.answer["body"]["items"]]
        unknown = set()
        for item in items:
            assert _missing(schema, item) == [], case_id
            for field in fields:
                ref = schema["properties"][field]["$ref"].rsplit("/", 1)[-1]
                if item[field] not in schemas[ref]["enum"]:
                    unknown.add(field)
        assert unknown == fields, case_id
        assert set(case.observe) == {"returns"}, case_id
        assert case.observe["returns"]["ids"] == [i["id"] for i in items], case_id


AGREEMENT = {
    case.id: case
    for case in load_cases(ROOT / "cases").values()
    if case.id.startswith("agreement.")
}
#: The typed error each plan-agreement code is, and the fields each document in its details has.
AGREEMENT_ERRORS = {
    "service_agreement_not_accepted": (
        "ServiceAgreementNotAcceptedError",
        {"document", "number", "plan", "grace_ends_at"},
    ),
    "terms_not_accepted": ("TermsNotAcceptedError", {"document", "number", "grace_ends_at"}),
}


def _spec() -> dict[str, Any]:
    return __import__("yaml").safe_load(  # type: ignore[no-any-return]
        (ROOT / "spec" / "openapi.yaml").read_text(encoding="utf-8")
    )


def test_the_agreement_refusals_are_typed_and_carry_the_contracts_details() -> None:
    """Given the plan-agreement cases and the vendored API description
    When each refusal case is read
    Then service_agreement_not_accepted is raised as a ServiceAgreementNotAcceptedError and
    terms_not_accepted as a TermsNotAcceptedError, both 409 codes the API names, in the agreement
    cases and in the generated error cases alike; each refusal is one request, never sent again;
    the caller observes the details exactly as sent; a Service Agreement refusal's details are
    plan_change (every field of PlanChangeSummary, or null), documents (each document, number, plan
    and grace_ends_at) and accept_url, and a Terms refusal's details are documents (each document,
    number and grace_ends_at); and one case has the Terms held too, still a Service Agreement
    refusal listing the Terms among its documents."""
    codes = make_error_cases.known_codes(_spec())
    summary = _schemas()["PlanChangeSummary"]
    cases = load_cases(ROOT / "cases")
    seen: set[str] = set()
    terms_in_an_agreement_refusal = False
    for case in AGREEMENT.values():
        if case.call["op"] != "terminals.create":
            continue
        (step,) = case.server
        assert step.times == 1, case.id
        error = step.answer["body"]["error"]
        code, details = error["code"], error["details"]
        kind, document = AGREEMENT_ERRORS[code]
        assert codes[code] == 409 == step.answer["status"], case.id
        assert case.observe == {
            "raises": kind,
            "fields": {"code": code, "status": 409, "details": details},
        }, case.id
        assert cases[f"errors.{code}"].observe["raises"] == kind
        assert details["documents"], case.id
        assert all(set(doc) == document for doc in details["documents"]), case.id
        if code == "service_agreement_not_accepted":
            assert set(details) == {"plan_change", "documents", "accept_url"}, case.id
            assert details["accept_url"].startswith("https://"), case.id
            change = details["plan_change"]
            assert change is None or _missing(summary, change) == [], case.id
            terms_in_an_agreement_refusal |= any(
                doc["document"] == "terms" for doc in details["documents"]
            )
        else:
            assert set(details) == {"documents"}, case.id
        seen.add(code)
    assert seen == set(AGREEMENT_ERRORS)
    assert terms_in_an_agreement_refusal
    assert {"ServiceAgreementNotAcceptedError", "TermsNotAcceptedError"} <= set(
        VOCABULARY["errors"]
    )


def test_the_service_agreement_read_answers_the_contracts_shape_and_returns_it() -> None:
    """Given the vendored API description and the tenant.service_agreement cases
    When each answer is read
    Then the call is GET /v1/tenant/service-agreement, which the API describes; every answer
    carries every field of TenantServiceAgreement, each document every field of its item and a
    plan change every field of PlanChangeSummary; what the caller observes is the answer's due,
    held, plan, the plan change's state and to (null with none), each document's key and
    accept_url; one case has something due and one nothing; and MFX-Service-Agreement: due is
    sent exactly when something is due."""
    spec = _spec()
    operation = spec["paths"]["/tenant/service-agreement"]["get"]
    assert operation["operationId"] == "getTenantServiceAgreement"
    schema = spec["components"]["schemas"]["TenantServiceAgreement"]
    document = schema["properties"]["documents"]["items"]
    summary = spec["components"]["schemas"]["PlanChangeSummary"]
    reads = [c for c in AGREEMENT.values() if c.call["op"] == "tenant.service_agreement"]
    dues: list[bool] = []
    for case in reads:
        (step,) = case.server
        assert step.expect == {"method": "GET", "path": "/v1/tenant/service-agreement"}, case.id
        body = step.answer["body"]
        assert _missing(schema, body) == [], case.id
        assert all(_missing(document, d) == [] for d in body["documents"]), case.id
        change = body["plan_change"]
        assert change is None or _missing(summary, change) == [], case.id
        assert case.observe["returns"] == {
            "due": body["due"],
            "held": body["held"],
            "plan": body["plan"],
            "plan_change_state": change and change["state"],
            "plan_change_to": change and change["to"],
            "documents": [d["document"] for d in body["documents"]],
            "accept_url": body["accept_url"],
        }, case.id
        due = step.answer["headers"].get("MFX-Service-Agreement") == "due"
        assert due == body["due"], case.id
        dues.append(due)
    assert sorted(dues) == [False, True]


def test_the_due_header_cases_expect_one_warning_per_client_never_one_per_answer() -> None:
    """Given the vendored API description's MFX-Service-Agreement header and the warning cases
    When each case is read
    Then every answer of a due case carries the header with a value the API allows, and an answer
    of the other case carries none; the hub expects every call of every client; the warnings
    expected are one per client when the header is sent, whatever the number of answers carrying
    it, and none without it; and one case gives one client several answers, one gives several
    clients, and one sends no header."""
    allowed = _spec()["components"]["headers"]["ServiceAgreement"]["schema"]["enum"]
    warns = [c for c in AGREEMENT.values() if c.call["op"] == "agreement.due_warnings"]
    shapes: set[str] = set()
    for case in warns:
        args = case.call["args"]
        (step,) = case.server
        assert step.times == args["clients"] * args["calls"], case.id
        assert step.expect == {
            "method": "GET",
            "path": "/v1/terminals/" + args["terminal_id"],
        }, case.id
        header = step.answer["headers"].get("MFX-Service-Agreement")
        assert header is None or header in allowed, case.id
        expected = args["clients"] if header else 0
        assert case.observe == {"returns": {"warnings": expected}}, case.id
        if header is None:
            shapes.add("no header")
        elif args["clients"] == 1 and args["calls"] > 1:
            shapes.add("once for many answers")
        elif args["clients"] > 1 and args["calls"] > 1:
            shapes.add("once per client")
    assert shapes == {"once for many answers", "once per client", "no header"}
