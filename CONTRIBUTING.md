# Contributing to the MFX Hub SDK conformance suite

Thank you for helping. A case that pins down a rule the API description states, a clearer rule, or
a fix to the fake hub are all welcome.

## Before you start

- **A security problem?** Do not open an issue. Follow [SECURITY.md](SECURITY.md).
- **A case you believe is wrong?** Open an issue naming the case id, the section of the
  [API description](https://docs.mfxhub.com/api) it cites, and what the description says instead.
- **A new case?** Every case states one rule the API description already states, and cites the
  section by its heading in `source`. A rule the description does not state is a question for
  support@mfxhub.com first, not a case.

## Setting up

You need [uv](https://docs.astral.sh/uv/) and Python 3.12 or later.

```bash
uv sync
uv run pytest                               # the fake hub's tests, 100% line coverage
uv run ruff format --check . && uv run ruff check .
uv run mypy src
uv run python tools/make_error_cases.py --check
```

## What a change needs

- **One rule a case**, with an id `<area>.<what>` in the file for its area, a `rule` written as
  a sentence anyone can check, and exactly one outcome in `observe`.
- **Only names from `vocabulary.json`.** A new operation or error kind is added there first,
  with what it means, so every language's runner can map it.
- **No hand edits to `cases/errors.json`.** It is generated from the API description's error
  codes by `tools/make_error_cases.py`, and CI fails when it is out of date.
- **No real credentials, ever.** Requests are signed with the published test key only.

## Signing off your commits

Every commit must carry a Developer Certificate of Origin sign-off: a statement that you wrote the
change, or otherwise have the right to submit it under this project's licence. The full text is at
[developercertificate.org](https://developercertificate.org). Add it with `git commit -s`.

## How a pull request lands

The suite is developed in a private repository alongside the platform and the SDKs, and each
release is published here as a single commit. So a pull request here is not merged directly: we
review it here, apply it to the next release keeping you as the author and your sign-off, and close
the pull request with a link to the release.

## Licence and conduct

By contributing, you agree that your contribution is licensed under the
[Apache License 2.0](LICENSE). Everyone taking part follows the [code of conduct](CODE_OF_CONDUCT.md).
