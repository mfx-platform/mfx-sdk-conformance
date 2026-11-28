# MFX Hub SDK conformance suite

The shared test suite every MFX Hub SDK must pass before it releases. The rules of the
[MFX Hub API](https://docs.mfxhub.com) are written here once, as language-neutral cases, and a
fake MFX Hub plays each case back on localhost. Each SDK has a small runner that turns a case into
a call in its own language and checks what came back, so the Python, TypeScript, .NET and Java
SDKs keep exactly the same promises.

## What is in it

| Path | What it is |
|---|---|
| [`cases/`](cases/) | One JSON file per area: signing, errors, decimals, idempotency, paging, execution, stream, market data, risk, copy, plan agreements. Each case is one rule. |
| [`fixtures.json`](fixtures.json) | API objects cases refer to by name with `$fixture`, so a case does not repeat a whole terminal. |
| [`vocabulary.json`](vocabulary.json) | The neutral names cases use: operations, error kinds, markers and outcomes. A runner maps each to its language. |
| [`src/mfx_fake_hub/`](src/mfx_fake_hub/) | The fake MFX Hub: checks every request against the case, verifies its signature with the test key, and answers as the case says. |
| [`live/cases.json`](live/cases.json) | Rules a real MFX Hub shows on its own, run against it rather than the fake one. See [Running the live cases](#running-the-live-cases). |
| [`spec/openapi.yaml`](spec/openapi.yaml) | The API description the cases are written from. `cases/errors.json` is generated from its error codes. |
| [`sdkref/`](sdkref/) | The format of each SDK's generated API reference, the docs site's page list, and the checker an SDK runs on its reference in CI. See [The SDK reference](#the-sdk-reference). |

## A case

```json
{
  "id": "decimals.float_refused",
  "rule": "A binary floating-point volume is refused before anything is sent",
  "source": "Decimals",
  "call": {"op": "execution.place_order", "args": {"volume": {"$float": 0.21000000000000002}, "...": "..."}},
  "server": [],
  "observe": {"refuses": "invalid_argument"}
}
```

`call` is what the caller does, `server` is every request the SDK must send and the answer each
gets (none here: it must refuse first), and `observe` is what the caller must see. A request's
`query` is matched exactly, except the parameters named in `query_instants`, which are times and
are compared as instants: `2026-11-12T00:00:00Z` and `2026-11-12T00:00:00.000Z` are one time. A rule about what an SDK logs is observed through an
operation that counts it: `agreement.due_warnings` makes reads through one or more clients and
returns how many warnings they logged that a Service Agreement is due, so "once per client" is a
number like any other. A stream case has
`stream` instead: one list of steps per WebSocket connection, each a frame the SDK must send
(`recv`), a frame the hub sends (`send`), or a close with its code (`close`).

## Running it from an SDK

An SDK pins a release tag, so a new case reaches it only when it moves the pin.

```bash
git clone --depth 1 --branch v0.13.0 https://github.com/mfx-platform/mfx-sdk-conformance
pip install ./mfx-sdk-conformance
python -m mfx_fake_hub --cases mfx-sdk-conformance/cases   # prints: listening http://127.0.0.1:<port>/v1
```

Then, for each case:

1. `POST /_hub/case` with `{"id": "<case id>"}`: loads the case and answers it, fixtures expanded.
2. Make the case's `call` through the SDK, with the test key from `vocabulary.json` and the base URL
   the hub printed. Configure the client so a retry does not actually sleep.
3. Compare what the call returned, raised or refused with `observe`.
4. `GET /_hub/verdict`: `{"ok": true}` when every request arrived in order, signed and shaped as
   the case says, and nothing else did; otherwise `problems` says what differed.

A case passes when both 3 and 4 hold. An SDK that fails a case does not release.

## Running the live cases

The cases in `live/` run against a real MFX Hub, with your own key, on a terminal that is logged
in to a demo account. A real hub cannot be told how to answer, so each holds a rule it shows on its
own: your signature is accepted and the published test key is refused, an unknown terminal is
`not_found`, a list follows its cursor, a price is an exact decimal, an order sent twice with one
idempotency key is one order, and ticks arrive in `seq` order. Values such as the terminal and a
fresh idempotency key come from the run (`{"$run": "terminal_id"}`); the vocabulary's `live`
section lists them and the extra observations live cases use. They send at most one market order,
of the symbol's smallest volume, and the runner closes it. A case that `needs` a market is skipped,
not failed, when the market is closed.

## The SDK reference

Each SDK generates `docs/sdkref.json` from its own source: its public surface, one entry per type
and member, which the docs site renders one page per page id with every language behind one
toggle. The format is `mfx-sdkref/1`:

| File | What it is |
|---|---|
| [`sdkref/sdkref.schema.json`](sdkref/sdkref.schema.json) | The JSON Schema (draft 2020-12) a reference must fit. An optional key is left out when it has nothing in it, never null or an empty list. |
| [`sdkref/pages.json`](sdkref/pages.json) | The pages in their fixed order, with the title and one-line summary the site shows. An SDK file names a page by its id only; a page a language lacks is left out. |
| [`sdkref/check_sdkref.py`](sdkref/check_sdkref.py) | The checker. Standard library only, so it runs with the Python an SDK already has for the fake hub. |

A type that represents a contract object names it in `schema`, exactly as the key of
`components.schemas` in the API description (`"schema": "Position"`), and the docs site links the
type to that object's entry on `/docs/objects#<schema>`. Every kind of type but `function` may
carry it.

An SDK vendors the whole `sdkref` folder with the cases and runs, in CI:

```bash
python <vendored suite>/sdkref/check_sdkref.py docs/sdkref.json
```

It exits 0 when the file is clean, and 1 with one line per problem when it is not. Beyond the
schema it checks that:

- the pages follow the page list's order, each at most once;
- every anchor is `<page id>.<Type>` or `<page id>.<Type>.<member>`, unique in the file, starts
  with its own page id, and a member's starts with its type's;
- a cross-reference in doc text is exactly `[Name](#anchor)` and names an anchor in the file; any
  other link is an `https://` address, and no `{@link}` or reference-style link is left over;
- doc text has no raw HTML: anything with `<` or `>` is in a code span or a fenced block;
- no signature and no parameter `default` is elided with `...` or `…` (a rest parameter, varargs
  or Python's typing ellipsis is not an elision);
- every `schema` is a key of `components.schemas` in the API description, case kept. The checker
  reads `spec/openapi.yaml` beside the `sdkref` folder, so vendor the suite's `spec` folder too,
  or name the description with `--spec <openapi.yaml>` before the file. With neither it checks
  everything else and says on stderr that the names were not checked;
- no internal word appears anywhere: a work item or decision id, `MT5` in prose (write "the
  terminal"; the API's own lower-case names such as the venue `mt5` stay), `cell` or `cells`, or
  an internal repository's name;
- the bytes are the canonical form: UTF-8 without a byte order mark, two-space indent, non-ASCII
  written as itself, LF line ends and one LF at the end, which is what
  `json.dumps(data, indent=2, ensure_ascii=False) + "\n"` and
  `JSON.stringify(data, null, 2) + "\n"` write. A generator that runs twice writes the same bytes.

## The test key

Every request is signed with the test key from the API description's signing test vector: its
private key is the 32 bytes `00` to `1f`. It is public on purpose, and a real MFX Hub accepts
nothing it signs.

## Support and security

- Questions and corrections: open an issue, or write to support@mfxhub.com.
- Security reports: see [SECURITY.md](SECURITY.md). Please do not open a public issue for one.
- Contributing: see [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

Licensed under the [Apache License 2.0](LICENSE).
