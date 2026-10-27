# MFX Hub SDK conformance suite

The shared test suite every MFX Hub SDK must pass before it releases. The rules of the
[MFX Hub API](https://docs.mfxhub.com) are written here once, as language-neutral cases, and a
fake MFX Hub plays each case back on localhost. Each SDK has a small runner that turns a case into
a call in its own language and checks what came back, so the Python, TypeScript, .NET and Java
SDKs keep exactly the same promises.

## What is in it

| Path | What it is |
|---|---|
| [`cases/`](cases/) | One JSON file per area: signing, errors, decimals, idempotency, paging, execution, stream. Each case is one rule. |
| [`fixtures.json`](fixtures.json) | API objects cases refer to by name with `$fixture`, so a case does not repeat a whole terminal. |
| [`vocabulary.json`](vocabulary.json) | The neutral names cases use: operations, error kinds, markers and outcomes. A runner maps each to its language. |
| [`src/mfx_fake_hub/`](src/mfx_fake_hub/) | The fake MFX Hub: checks every request against the case, verifies its signature with the test key, and answers as the case says. |
| [`spec/openapi.yaml`](spec/openapi.yaml) | The API description the cases are written from. `cases/errors.json` is generated from its error codes. |

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
gets (none here: it must refuse first), and `observe` is what the caller must see. A stream case has
`stream` instead: one list of steps per WebSocket connection, each a frame the SDK must send
(`recv`), a frame the hub sends (`send`), or a close with its code (`close`).

## Running it from an SDK

An SDK pins a release tag, so a new case reaches it only when it moves the pin.

```bash
git clone --depth 1 --branch v0.2.0 https://github.com/mfx-platform/mfx-sdk-conformance
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
