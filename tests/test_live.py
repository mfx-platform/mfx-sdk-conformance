"""The live cases are well formed, and kept apart from the fake hub's.

A live case runs against a real MFX Hub, so it can script nothing: each holds a rule a real hub
shows on its own, with values that come from the run (the terminal, its broker, a fresh key).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mfx_fake_hub import load_cases

ROOT = Path(__file__).resolve().parents[1]
VOCABULARY = json.loads((ROOT / "vocabulary.json").read_text(encoding="utf-8"))
LIVE = json.loads((ROOT / "live" / "cases.json").read_text(encoding="utf-8"))
#: Observations that stand alone: a call that raises or refuses returns nothing to check.
ALONE = {"raises", "refuses"}


def _run_names(value: Any) -> set[str]:  # noqa: ANN401 - a case's JSON value
    """Every run value a case names, wherever it is."""
    if isinstance(value, dict):
        named = {value["$run"]} if "$run" in value else set()
        return named.union(*(_run_names(v) for v in value.values()))
    if isinstance(value, list):
        return set().union(*(_run_names(v) for v in value))
    return set()


def test_live_cases_name_only_what_the_vocabulary_knows_and_stay_off_the_fake_hub() -> None:
    """Given the live cases and the vocabulary's live section
    When the cases are read
    Then ids are unique and start live., each cites its rule and source, calls an operation the
    vocabulary knows with arguments it names, observes only what the live section names (raises
    and refuses alone, with a known error kind), names only run values the live section lists, and
    uses only the client and needs it lists; and loading the fake hub's cases finds none of them."""
    live = VOCABULARY["live"]
    ids = [case["id"] for case in LIVE]
    assert len(ids) == len(set(ids)) >= 9
    for case in LIVE:
        assert case["id"].startswith("live."), case["id"]
        assert case["rule"] and case["source"], case["id"]
        op = VOCABULARY["ops"][case["call"]["op"]]
        allowed = {name.removesuffix("?") for name in op["args"]}
        assert set(case["call"]["args"]) <= allowed, case["id"]
        observed = set(case["observe"]) - {"fields"}  # the fields of what raises
        assert observed and observed <= set(live["observe"]), case["id"]
        if observed & ALONE:
            assert len(observed) == 1, case["id"]
        if "raises" in observed:
            assert case["observe"]["raises"] in VOCABULARY["errors"], case["id"]
        returns = case["observe"].get("returns") or case["observe"].get("repeat", {}).get("returns")
        if returns:
            assert set(returns) <= set(op["returns"]), case["id"]
        same = case["observe"].get("repeat", {}).get("same", [])
        for name in case["observe"].get("exact", []) + same:
            assert name in op["returns"], case["id"]
        assert _run_names(case) <= set(live["run"]), case["id"]
        assert case.get("client", "test_key") == "test_key", case["id"]
        assert set(case.get("needs", [])) <= {"market"}, case["id"]

    assert not any(i.startswith("live.") for i in load_cases(ROOT / "cases"))
    orders = [
        c for c in LIVE
        if c["call"]["op"] == "execution.place_order" and "refuses" not in c["observe"]
    ]  # fmt: skip
    assert [c["call"]["args"]["volume"] for c in orders] == [{"$run": "min_volume"}], (
        "a live case sends at most one order, of the smallest volume"
    )
