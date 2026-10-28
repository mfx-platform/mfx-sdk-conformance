"""The suite itself is well formed: every case loads, names an operation and an outcome the
vocabulary knows, cites the API section it proves, and the error cases match the API description."""

from __future__ import annotations

import json
import sys
from pathlib import Path

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
