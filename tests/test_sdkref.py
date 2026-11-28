"""The SDK reference format: the schema, the page list and the checker every SDK runs in CI on its
generated ``docs/sdkref.json``. A clean file passes, and each rule has a file that breaks it."""

from __future__ import annotations

import copy
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sdkref"))

import check_sdkref  # noqa: E402

SCHEMA = json.loads((ROOT / "sdkref" / "sdkref.schema.json").read_text(encoding="utf-8"))
PAGES = json.loads((ROOT / "sdkref" / "pages.json").read_text(encoding="utf-8"))

#: Built from pieces so this file publishes none of the words it proves are refused.
WORK_ITEM = "AB" + "#1234"
DECISION = "DEC" + "-12"
REPO = "mfx-sdk-python" + "-intern" + "al"

Doc = dict[str, Any]


def good() -> Doc:
    """A small, clean reference: three pages, cross-references, code spans and every key."""
    return {
        "format": "mfx-sdkref/1",
        "language": "python",
        "package": "mfx-sdk",
        "version": "0.19.0",
        "install": "pip install mfx-sdk",
        "links": {
            "package": "https://pypi.org/project/mfx-sdk/",
            "source": "https://github.com/mfx-platform/mfx-sdk-python",
        },
        "pages": [
            {
                "id": "client",
                "intro": "Every call goes through a [Client](#client.Client).",
                "types": [
                    {
                        "anchor": "client.Client",
                        "kind": "class",
                        "name": "Client",
                        "signature": "class Client",
                        "doc": "Signs each request. Lists come back as `Page<Terminal>`.",
                        "members": [
                            {
                                "anchor": "client.Client.__init__",
                                "kind": "constructor",
                                "name": "__init__",
                                "signature": "Client(key_id: str, *args: str, **kwargs: str)",
                                "doc": "See [the guide](https://docs.mfxhub.com) first.",
                                "params": [
                                    {
                                        "name": "key_id",
                                        "type": "str",
                                        "default": '""',
                                        "doc": "Which key signs.",
                                    }
                                ],
                            }
                        ],
                    }
                ],
            },
            {
                "id": "execution",
                "intro": "Orders and positions on the terminal.\n\n```python\nx = a < b\n```\n",
                "types": [
                    {
                        "anchor": "execution.Execution",
                        "kind": "class",
                        "name": "Execution",
                        "signature": "class Execution",
                        "doc": "",
                        "extends": ["object"],
                        "members": [
                            {
                                "anchor": "execution.Execution.close_position",
                                "kind": "method",
                                "name": "close_position",
                                "signature": (
                                    "async def close_position(self, position_id: str, *, "
                                    "comment: str | None = None) -> ExecutionResult"
                                ),
                                "doc": "Closes it once. Venue `mt5` or `ctrader`.",
                                "params": [
                                    {
                                        "name": "comment",
                                        "type": "str | None",
                                        "default": "None",
                                        "doc": "At most 31 characters.",
                                    }
                                ],
                                "returns": {"type": "ExecutionResult", "doc": "What happened."},
                                "raises": [
                                    {
                                        "type": "ServiceAgreementNotAcceptedError",
                                        "doc": "[Why](#errors.ServiceAgreementNotAcceptedError).",
                                    }
                                ],
                                "operation": "closePosition",
                                "deprecated": "Use [Client](#client.Client) instead.",
                            }
                        ],
                    }
                ],
            },
            {
                "id": "errors",
                "intro": "Every error is an `ApiError`.",
                "types": [
                    {
                        "anchor": "errors.ServiceAgreementNotAcceptedError",
                        "kind": "error",
                        "name": "ServiceAgreementNotAcceptedError",
                        "signature": "class ServiceAgreementNotAcceptedError(ConflictError)",
                        "doc": "The service agreement is due.",
                        "extends": ["ConflictError"],
                        "code": "service_agreement_not_accepted",
                    },
                    {
                        "anchor": "errors.ConflictError",
                        "kind": "error",
                        "name": "ConflictError",
                        "signature": "class ConflictError(ApiError)",
                        "doc": "A 409.",
                    },
                ],
            },
        ],
    }


def encode(doc: Doc) -> bytes:
    return (json.dumps(doc, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def problems(doc: Doc) -> list[str]:
    return check_sdkref.check_bytes(encode(doc))


def _set(path: str, value: Any) -> Callable[[Doc], None]:
    """A change that sets ``path`` (dots and list indexes, ``pages.1.types.0``) to ``value``."""

    def change(doc: Doc) -> None:
        *parents, last = path.split(".")
        node: Any = doc
        for part in parents:
            node = node[int(part)] if isinstance(node, list) else node[part]
        node[int(last) if isinstance(node, list) else last] = value

    return change


def _drop(path: str) -> Callable[[Doc], None]:
    def change(doc: Doc) -> None:
        *parents, last = path.split(".")
        node: Any = doc
        for part in parents:
            node = node[int(part)] if isinstance(node, list) else node[part]
        del node[last]

    return change


def _then(*changes: Callable[[Doc], None]) -> Callable[[Doc], None]:
    def change(doc: Doc) -> None:
        for one in changes:
            one(doc)

    return change


CLOSE = "pages.1.types.0.members.0"


def test_the_page_list_and_schema_are_the_format_and_a_clean_reference_passes() -> None:
    """Given the suite's sdkref folder: the schema, the page list and the checker
    When the page list is read and a clean reference in each of the four languages is checked
    Then the page list is the twelve pages in their fixed order with the docs site's titles and a
    one-line plain-text summary each, the schema is draft 2020-12 and allows exactly those page
    ids, each language's package is the one its registry knows, and a clean file has no problem;
    a keyword the checker's validator does not implement is an error in the schema, not a pass."""
    assert SCHEMA["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert [(p["id"], p["title"]) for p in PAGES] == [
        ("client", "Client and signing"),
        ("terminals", "Terminals"),
        ("execution", "Execution"),
        ("trading-accounts", "Trading accounts"),
        ("accounts", "Accounts and catalogue"),
        ("market-data", "Market data"),
        ("stream", "Stream and live account"),
        ("risk", "Risk"),
        ("copy", "Copy trading"),
        ("billing", "Billing"),
        ("tenant", "Tenant"),
        ("errors", "Errors"),
    ]
    for page in PAGES:
        assert set(page) == {"id", "title", "summary"}, page
        summary = page["summary"]
        assert summary.endswith(".") and "\n" not in summary, page
        assert not set(summary) & set("`[]<>*_#"), page  # plain text, not Markdown
    assert check_sdkref.word_problems(PAGES) == []
    assert SCHEMA["$defs"]["page"]["properties"]["id"]["enum"] == [p["id"] for p in PAGES]

    assert problems(good()) == []
    for language, package in (
        ("typescript", "@mfxhub/sdk"),
        ("csharp", "MfxHub.Sdk"),
        ("java", "com.mfxhub:mfx-sdk"),
    ):
        doc = good()
        doc.update(language=language, package=package)
        assert problems(doc) == [], language

    function = good()  # a free function carries its call like a method does
    _set("pages.0.types.0.kind", "function")(function)
    _set("pages.0.types.0.params", [{"name": "body", "type": "bytes", "doc": ""}])(function)
    _set("pages.0.types.0.returns", {"type": "bool", "doc": "True when it verifies."})(function)
    _set("pages.0.types.0.raises", [{"type": "ValueError", "doc": ""}])(function)
    _set("pages.0.types.0.operation", "getTenantServiceAgreement")(function)
    assert problems(function) == []

    with pytest.raises(check_sdkref.SchemaError, match="unsupported keyword"):
        check_sdkref.validate({}, {"uniqueItems": True})
    with pytest.raises(check_sdkref.SchemaError, match="local references"):
        check_sdkref.validate({}, {"$ref": "https://example.com/x.json"})
    with pytest.raises(check_sdkref.SchemaError, match="as false only"):
        check_sdkref.validate({}, {"additionalProperties": True})


@pytest.mark.parametrize(
    ("change", "says"),
    [
        (_set("format", "mfx-sdkref/2"), '$.format: must be "mfx-sdkref/1"'),
        (_set("language", "go"), "$.language: "),
        (_set("package", "mfx_sdk"), '$.package: must be "mfx-sdk"'),
        (_then(_set("language", "java"), _set("package", "mfx-sdk")), "$.package: "),
        (_set("version", "v0.19"), "$.version: "),
        (_drop("install"), "$: install is required"),
        (_set("install", "pip install\nmfx-sdk"), "$.install: "),
        (_set("links", {}), "$.links: must not be empty"),
        (_set("links", None), "$.links: must be a JSON object"),
        (_set("links.source", "http://example.com"), "$.links.source: "),
        (_set("title", "MFX"), "$: title is not allowed"),
        (_set("pages", []), "$.pages: must not be empty"),
        (_set("pages.0.id", "clients"), "$.pages[0].id: "),
        (_set("pages.0.title", "Client"), "$.pages[0]: title is not allowed"),
        (_set("pages.0.types", []), "$.pages[0].types: must not be empty"),
        (_set("pages.0.types.0.anchor", "client"), "$.pages[0].types[0].anchor: "),
        (_set("pages.0.types.0.anchor", "client.Client.x"), "$.pages[0].types[0].anchor: "),
        (_set("pages.0.types.0.kind", "struct"), "$.pages[0].types[0].kind: "),
        (_set("pages.0.types.0.members", []), "$.pages[0].types[0].members: must not be"),
        (_set("pages.0.types.0.code", "conflict"), "$.pages[0].types[0]: must not match"),
        (_set("pages.0.types.0.extends", None), "$.pages[0].types[0].extends: must be"),
        (_set("pages.0.types.0.signature", ""), "$.pages[0].types[0].signature: must not be"),
        (_drop("pages.0.types.0.doc"), "$.pages[0].types[0]: doc is required"),
        (_set("pages.2.types.0.code", "Conflict"), "$.pages[2].types[0].code: "),
        (_set(f"{CLOSE}.anchor", "execution.Execution"), "$.pages[1].types[0].members[0].anchor"),
        (_set(f"{CLOSE}.kind", "event"), "$.pages[1].types[0].members[0].kind: "),
        (_set(f"{CLOSE}.params", []), "$.pages[1].types[0].members[0].params: must not be"),
        (_set(f"{CLOSE}.params.0.default", ""), ".params[0].default: must not be empty"),
        (_set(f"{CLOSE}.params.0.default", None), ".params[0].default: must be a JSON string"),
        (_drop(f"{CLOSE}.params.0.type"), ".params[0]: type is required"),
        (_set(f"{CLOSE}.returns", {"type": "X"}), ".returns: doc is required"),
        (_set(f"{CLOSE}.raises", []), ".raises: must not be empty"),
        (_set(f"{CLOSE}.raises.0.code", "x"), ".raises[0]: code is not allowed"),
        (_set(f"{CLOSE}.operation", "close_position"), ".operation: "),
        (_set(f"{CLOSE}.deprecated", ""), ".deprecated: must not be empty"),
        (_set(f"{CLOSE}.signature", "def close_position(\n) -> None"), ".signature: "),
        (
            _set("pages.0.types.0.returns", {"type": "None", "doc": ""}),
            "$.pages[0].types[0]: must not match",
        ),
        (
            _then(_set("pages.0.types.0.kind", "function"), _set("pages.0.types.0.params", [])),
            "$.pages[0].types[0].params: must not be empty",
        ),
    ],
)
def test_the_schema_refuses_a_file_that_is_not_the_format(
    change: Callable[[Doc], None], says: str
) -> None:
    """Given a clean reference
    When one key is changed so the file no longer fits the schema: a wrong format, language,
    package or version, a required key missing, a key the format does not have, an optional key
    that is null or empty, a malformed anchor, kind, error code or operation, an error code on
    something that is not an error, or a signature over two lines
    Then the checker names the path that broke and what is wrong with it."""
    doc = good()
    change(doc)
    found = problems(doc)
    assert any(says in problem for problem in found), found


@pytest.mark.parametrize(
    ("change", "says"),
    [
        (
            lambda doc: doc["pages"].reverse(),
            "$.pages[1].id: page execution comes before errors in the page list",
        ),
        (
            lambda doc: doc["pages"].append(copy.deepcopy(doc["pages"][2])),
            "$.pages[3].id: page errors appears twice",
        ),
        (
            _set("pages.0.types.0.anchor", "execution.Client"),
            "$.pages[0].types[0].anchor: execution.Client does not start with its page, client",
        ),
        (
            _set("pages.2.types.1.anchor", "errors.ServiceAgreementNotAcceptedError"),
            "is also the anchor of $.pages[2].types[0]",
        ),
        (
            _set(f"{CLOSE}.anchor", "execution.Other.close_position"),
            "does not start with execution.Execution.",
        ),
        (
            _set("pages.0.intro", "Use [Terminal](#terminals.Terminal)."),
            "$.pages[0].intro: [Terminal](#terminals.Terminal) names no anchor in this file",
        ),
        (_set("pages.0.intro", "Use [](#client.Client)."), "has no name"),
        (_set("pages.0.intro", "Use [it](client.Client)."), "link to 'client.Client'"),
        (_set("pages.0.intro", "Use [it](http://x.io)."), "link to 'http://x.io'"),
        (_set(f"{CLOSE}.signature", "def close_position(...)"), "never elided"),
        (_set(f"{CLOSE}.signature", "def close_position(a, ...) -> None"), "never elided"),
        (_set(f"{CLOSE}.signature", "def close_position(a, …)"), "never elided"),
        (_set(f"{CLOSE}.signature", "X: Final[tuple[str, ...]] = ..."), "never elided"),
    ],
)
def test_pages_anchors_cross_references_and_signatures_hold_together(
    change: Callable[[Doc], None], says: str
) -> None:
    """Given a clean reference
    When its pages are out of the page list's order or repeated, an anchor does not start with
    its page id or a member's with its type's anchor, two entries share an anchor, a
    cross-reference names no anchor in the file or has no name, a link is neither
    [Name](#anchor) nor an https address, or a signature is elided with an ellipsis
    Then the checker refuses the file and says where; rest parameters, varargs and Python's
    typing ellipsis (tuple[X, ...], Callable[..., R]) are part of the type, not an elision."""
    doc = good()
    change(doc)
    found = problems(doc)
    assert any(says in problem for problem in found), found

    for signature in (
        "function f(...args: string[]): void",
        "void f(String... names)",
        "records: tuple[EaRecord, ...]",
        "deals: tuple[VenueDeal, ...] = ()",
        "def on(handler: Callable[..., None]) -> None",
    ):
        clean = good()
        _set(f"{CLOSE}.signature", signature)(clean)
        assert problems(clean) == [], signature


@pytest.mark.parametrize(
    ("text", "says"),
    [
        ("Returns a Page<Terminal>.", "angle bracket outside a code span"),
        ('See <see cref="Client"/>.', "angle bracket outside a code span"),
        ("Line one<br>line two.", "angle bracket outside a code span"),
        ("See {@link Client}.", "doc-tool markup"),
        ("See [Client][client].", "reference-style link"),
        (f"Fixed in {WORK_ITEM}.", "a work item id"),
        (f"As {DECISION} decided.", "a decision id"),
        ("Sent to the MT5 terminal.", "MT5 (write: the terminal)"),
        ("Runs in a cell.", "contains cell"),
        ("Runs in the Cells.", "contains cell"),
        (f"Mirrored from {REPO}.", "an internal repository name"),
    ],
)
def test_doc_text_is_markdown_without_html_or_internal_words(text: str, says: str) -> None:
    """Given a clean reference
    When a doc text holds raw HTML or a generic outside a code span, markup the language's doc
    tool left behind, or an internal word: a work item or decision id, MT5, cell or cells, or an
    internal repository's name
    Then the checker refuses it; the same words in a signature are refused too, while angle
    brackets in a code span or a fenced block, and the contract's lower-case venue value, pass."""
    doc = good()
    _set("pages.0.types.0.doc", text)(doc)
    found = problems(doc)
    assert any(says in problem for problem in found), found
    assert all(problem.startswith("$.pages[0].types[0].doc: ") for problem in found), found

    if says not in ("angle bracket outside a code span", "doc-tool markup", "reference-style link"):
        doc = good()
        _set("pages.0.types.0.signature", f"class Client  # {text}")(doc)
        assert any(says in problem for problem in problems(doc))

    assert check_sdkref.without_code("a `x<y>` b\n```\n<p>\n```\n") == "a code b\n\n"


def test_the_bytes_are_canonical_and_the_command_says_what_it_found(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Given a clean reference written as two-space JSON, non-ASCII as itself, LF and a final LF
    When the same data is written any other way: CRLF, four spaces, no final newline, escaped
    non-ASCII, a byte order mark, bytes that are not UTF-8 or not JSON, or a key given twice; and
    when the command is run on a clean file, a broken one, a missing one and nothing
    Then only the canonical bytes pass, each other form is refused with where it first differs or
    why it cannot be read, and the command exits 0 for clean, 1 with one line per problem, and 2
    when there is nothing it can read."""
    doc = good()
    doc["pages"][0]["intro"] = "Prices in € — exactly."
    canonical = encode(doc)
    assert check_sdkref.check_bytes(canonical) == []
    variants = {
        "crlf": canonical.replace(b"\n", b"\r\n"),
        "four spaces": (json.dumps(doc, indent=4, ensure_ascii=False) + "\n").encode(),
        "no final newline": canonical[:-1],
        "escaped": (json.dumps(doc, indent=2) + "\n").encode(),
    }
    for name, raw in variants.items():
        found = check_sdkref.check_bytes(raw)
        assert len(found) == 1 and "not the canonical form" in found[0], (name, found)
    assert check_sdkref.check_bytes(canonical[:-1])[0].startswith("line ")
    assert check_sdkref.check_bytes(b"\xef\xbb\xbf" + canonical) == [
        "the file starts with a byte order mark; write UTF-8 without one"
    ]
    assert check_sdkref.check_bytes(b'{"a": "\xff"}\n')[0].startswith("not UTF-8")
    assert check_sdkref.check_bytes(b"{")[0].startswith("not JSON")
    assert check_sdkref.check_bytes(b'{"a": 1, "a": 2}\n') == ["not JSON: duplicate key a"]

    clean, broken = tmp_path / "clean.json", tmp_path / "broken.json"
    clean.write_bytes(canonical)
    broken.write_bytes(canonical.replace(b"\n", b"\r\n"))
    assert check_sdkref.main([str(clean)]) == 0
    assert capsys.readouterr().out == f"{clean}: a clean mfx-sdkref/1 file\n"
    assert check_sdkref.main([str(clean), str(broken)]) == 1
    out = capsys.readouterr().out.splitlines()
    assert out[0].endswith("a clean mfx-sdkref/1 file")
    assert out[1].startswith(f"{broken}: line 1: not the canonical form")
    assert check_sdkref.main([str(tmp_path / "absent.json")]) == 2
    assert "no such file" in capsys.readouterr().err
    assert check_sdkref.main([]) == 2
    assert "usage" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("change", "says"),
    [
        (_set("pages.1.types.0.schema", "position_row"), "$.pages[1].types[0].schema: "),
        (_set("pages.1.types.0.schema", "Position.Id"), "$.pages[1].types[0].schema: "),
        (_set("pages.1.types.0.schema", "1Position"), "$.pages[1].types[0].schema: "),
        (_set("pages.1.types.0.schema", ""), "$.pages[1].types[0].schema: "),
        (_set("pages.1.types.0.schema", None), "$.pages[1].types[0].schema: must be a JSON"),
        (
            _then(
                _set("pages.0.types.0.kind", "function"), _set("pages.0.types.0.schema", "Position")
            ),
            "$.pages[0].types[0]: must not match",
        ),
        (_set(f"{CLOSE}.schema", "Position"), ".members[0]: schema is not allowed"),
    ],
)
def test_a_type_names_the_contract_schema_it_represents_exactly_as_the_contract_writes_it(
    change: Callable[[Doc], None], says: str
) -> None:
    """Given a clean reference
    When a type carries the optional key schema: the name of the contract schema it represents,
    exactly as a key of components.schemas in the API description, case kept
    Then a name of letters and digits starting with a letter passes on a type of every kind but
    function; a name with any other character, an empty or null one, one on a function, and one
    on a member are refused, each saying where; the docs site links the type to that schema's
    entry on its objects page."""
    for kind in ("class", "interface", "record", "enum", "error", "constant", "alias"):
        doc = good()
        _set("pages.1.types.0.kind", kind)(doc)
        _set("pages.1.types.0.schema", "Position")(doc)
        assert problems(doc) == [], kind
    schema_key = SCHEMA["$defs"]["type"]["properties"]["schema"]
    assert schema_key["pattern"] == "^[A-Za-z][A-Za-z0-9]*$"
    assert "/docs/objects#" in schema_key["description"]

    doc = good()
    change(doc)
    found = problems(doc)
    assert any(says in problem for problem in found), found


def test_the_checker_refuses_a_schema_name_the_vendored_contract_does_not_have(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Given a reference whose types name contract schemas, and the suite's API description in
    spec/openapi.yaml beside the sdkref folder
    When a name is one the description's components.schemas has, one it lacks, or one that
    differs only in case; when the command is given another description with --spec, a --spec
    that names no file or nothing at all; and when there is no description beside the checker
    and none is given
    Then a name the description has passes and any other is refused, naming the type; the names
    read are exactly the description's schema names; --spec checks against that description
    instead, a missing one is exit 2; and with no description at all the file is checked without
    the names, saying so, never failed for it."""
    contract = yaml.safe_load((ROOT / "spec" / "openapi.yaml").read_text(encoding="utf-8"))
    names = check_sdkref.load_contract(check_sdkref.SPEC_FILE)
    assert names is not None and set(names) == set(contract["components"]["schemas"])
    assert check_sdkref.contract_schemas(
        "openapi: 3.1.0\n"
        "paths:\n  /x:\n    Fake:\n      get: {}\n"
        "components:\n"
        "  parameters:\n    NotASchema:\n      in: query\n"
        "  schemas:\n"
        "    # a comment\n"
        "    Position:\n      type: object\n\n"
        "    'Quoted':\n      type: string\n"
        '    "Double": {type: string}\n'
        "  responses:\n    Gone:\n      description: x\n"
        "x-tail:\n    Late: 1\n"
    ) == {"Position", "Quoted", "Double"}

    named = good()
    _set("pages.1.types.0.schema", "Position")(named)
    assert problems(named) == []
    for wrong in ("Positions", "position"):
        doc = good()
        _set("pages.1.types.0.schema", wrong)(doc)
        assert problems(doc) == [
            f"$.pages[1].types[0].schema: {wrong} is not a schema in the contract "
            "(a key of components.schemas, case kept)"
        ], wrong

    other = tmp_path / "openapi.yaml"
    other.write_text("components:\n  schemas:\n    Order:\n      type: object\n", encoding="utf-8")
    file = tmp_path / "sdkref.json"
    file.write_bytes(encode(named))
    assert check_sdkref.main([str(file)]) == 0
    capsys.readouterr()
    assert check_sdkref.main(["--spec", str(other), str(file)]) == 1
    assert "Position is not a schema in the contract" in capsys.readouterr().out
    assert check_sdkref.main(["--spec", str(tmp_path / "absent.yaml"), str(file)]) == 2
    assert "absent.yaml: no such file" in capsys.readouterr().err
    for incomplete in (["--spec"], ["--spec", str(other)]):
        assert check_sdkref.main(incomplete) == 2
        assert "usage" in capsys.readouterr().err

    monkeypatch.setattr(check_sdkref, "SPEC_FILE", tmp_path / "spec" / "openapi.yaml")
    assert check_sdkref.main([str(file)]) == 0
    captured = capsys.readouterr()
    assert captured.out == f"{file}: a clean mfx-sdkref/1 file\n"
    assert "schema names are not checked" in captured.err


@pytest.mark.parametrize("default", ["...", "…", "{...}", "Config(...)", "Limits(a=1, …)"])
def test_a_parameter_default_is_the_value_itself_never_elided(default: str) -> None:
    """Given a clean reference
    When a parameter's default, on a member or on a function, is cut short with an ellipsis,
    three dots or the one character, as a signature may not be
    Then the checker refuses it and names the default; a default that only holds dots inside a
    string, an empty tuple and Python's typing ellipsis pass."""
    doc = good()
    _set(f"{CLOSE}.params.0.default", default)(doc)
    assert problems(doc) == [
        "$.pages[1].types[0].members[0].params[0].default: a default is the value itself, "
        "never elided with ..."
    ]

    function = good()
    _set("pages.0.types.0.kind", "function")(function)
    _set("pages.0.types.0.params", [{"name": "x", "type": "Any", "default": default, "doc": ""}])(
        function
    )
    assert problems(function) == [
        "$.pages[0].types[0].params[0].default: a default is the value itself, "
        "never elided with ..."
    ]

    for value in ('"..."', "()", "None", "tuple[int, ...]"):
        clean = good()
        _set(f"{CLOSE}.params.0.default", value)(clean)
        assert problems(clean) == [], value
