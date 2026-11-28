# Changelog

Every release of the suite, newest first. An SDK pins a release; a new case in a release can make
an SDK that passed the previous one fail, which is the point.

## 0.13.0

- **cases**: `copy.closes_a_cause_from_a_later_version_is_read_not_refused` answers a close whose
  `cause` is a word the contract does not list, and
  `copy.leaders_a_source_and_state_from_a_later_version_are_read_not_refused` a leader whose
  `source` and `state` are such words. The call must return the page, never fail: an SDK reads a
  word it does not know as its Unknown value. An SDK that refuses the word fails this
  release.

## 0.12.0

- **cases**: `agreement.terms_not_accepted_names_the_documents`: its documents carry `grace_ends_at`, when the grace
  period ends or ended, as the API description now names it for `terms_not_accepted` and as
  `service_agreement_not_accepted` already did. The platform no longer sends `grace_ended_at`, so
  an SDK that reads only that name fails this release.
- **spec**: `spec/openapi.yaml` is re-vendored from the public contract; no error code changed, so
  `cases/errors.json` is as it was.

## 0.11.0

- **sdkref**: a type may name the contract object it represents in the new optional key `schema`,
  exactly as the key of `components.schemas` in the API description, case kept
  (`"schema": "Position"`), pattern `^[A-Za-z][A-Za-z0-9]*$`. Every kind of type but `function`
  may carry it, and no member. The docs site links the type to `/docs/objects#<schema>`.
- **sdkref**: `check_sdkref.py` refuses a `schema` the API description lacks. It reads
  `spec/openapi.yaml` beside the `sdkref` folder, or the description given with
  `--spec <openapi.yaml>` before the files; with neither it checks everything else and says on
  stderr that the names were not checked.
- **sdkref**: a parameter's `default` cut short with `...` or `…` is refused, as an elided signature
  is; Python's typing ellipsis is still not an elision. No case changes: an SDK that passed 0.10.1
  passes this release unless its reference elides a default.

## 0.10.1

- **sdkref**: Python's typing ellipsis is part of a type, not an elision: `tuple[X, ...]` and
  `Callable[..., R]` now pass the signature check. A value cut to `= ...` is still refused.
- **sdkref**: a type of kind `function` may carry `params`, `returns`, `raises` and
  `operation`, as a method does; no other kind of type may.

## 0.10.0

- **sdkref**: the format of each SDK's generated API reference, `docs/sdkref.json`
  (`mfx-sdkref/1`), in a new `sdkref/` folder an SDK vendors with the cases:
  `sdkref.schema.json`, a JSON Schema (draft 2020-12) of the file; `pages.json`, the twelve pages
  in their fixed order (client, terminals, execution, trading-accounts, accounts, market-data,
  stream, risk, copy, billing, tenant, errors) with each one's title and one-line summary; and
  `check_sdkref.py`, a checker with no dependencies an SDK runs in CI as
  `python <vendored suite>/sdkref/check_sdkref.py docs/sdkref.json`. Beyond the schema it checks
  the page order, unique anchors that start with their page id, cross-references that resolve, no
  raw HTML outside code, no elided signatures, no internal words, and the canonical bytes. No case
  changes: an SDK that passed 0.9.0 passes this release.

## 0.9.0

- **agreement**: eight cases for the plan agreements, in `cases/agreement.json`. A terminal
  refused 409 `service_agreement_not_accepted` is a `ServiceAgreementNotAcceptedError` that keeps
  the code and gives `details.plan_change`, `details.documents` and `details.accept_url` exactly as
  sent, and is not sent again; where the Terms are held too it is still that error, listing every
  document due. A terminal refused 409 `terms_not_accepted` is a `TermsNotAcceptedError` with
  `details.documents`. `tenant.service_agreement()` reads `GET /v1/tenant/service-agreement` and
  returns what is due, whether additions are held, the plan, the plan change and accept_url, and
  says so when nothing is due. A client that sees `MFX-Service-Agreement: due` logs one warning the
  first time, not one per answer, and each client warns once; answers without it log nothing.
- The vocabulary gains the error kinds `ServiceAgreementNotAcceptedError` and
  `TermsNotAcceptedError` (both 409, each a `ConflictError` of its own kind, as
  `TenantSuspendedError` is a `ForbiddenError`), the operation `tenant.service_agreement`, and
  `agreement.due_warnings`, which counts the warnings an SDK logs over several calls and clients:
  a rule about logging is observed as a number, with no change to the case format.
  `fixtures.json` gains a `plan_change`.
- **errors**: `errors.service_agreement_not_accepted` and `errors.terms_not_accepted` now expect
  those two kinds instead of a plain `ConflictError`. An SDK without them fails these.

## 0.8.0

- **copy**: nineteen cases for Copy Trading, in `cases/copy.json`: making a leader sends its
  account and the idempotency key, and one over the plan is a `quota_exceeded` conflict sent once;
  leaders are filtered by state as one comma-separated value and followed to the last page with the
  stats row kept; an external leader's open sends the volume as a decimal string, a repeat is the
  original signal marked duplicate, and a float volume is refused; a follow sends its mandate, and
  one from an account its venue cannot copy to (an MT5 netting account) is a validation error
  naming `not_on_this_venue`; a preview is a read with no idempotency key, naming each row's volume
  in the follower venue's unit, or its reason; unfollowing sends `close_copied` as chosen;
  resetting with no active stop-out is a state error; the copy log sends its filters
  comma-separated and its window as instants, reads every refusal reason of the closed list, and
  refuses one outside it; adding followers to a group answers each apart; and each of the five
  `copy.*` events has its own case, arriving on the events channel in exactly the contract's shape
  (objects as objects, numbers as numbers, nulls as null) and naming the account and its venue.
  The vocabulary gains ten `copy.*` operations and `fixtures.json` a leader, a follower on cTrader
  and a copy log row. An SDK with no copy client yet fails these.
- **copy**, the contract's final shapes: four more cases, twenty-three in all. A group's close
  sends its reason and `pause` (required, no default) with the idempotency key and answers the
  batch; a rollover's dry run sends its fields and page size with no key and answers each member's
  outcome; the requested closes are filtered by batch and state, comma-separated, and followed to
  the last page with the stats row kept; and `copy.closed` names what a requested close closed and
  what it did not. `copy.refused` carries `risk` (null here), a copy log row the leader's `deal`,
  the follower's `symbol` and `risk`, the log's stats the p95s, and a preview row both contract
  sizes and the follower's volume unit. The vocabulary gains `copy.close_group`,
  `copy.rollover_group` and `copy.closes`, and `fixtures.json` a requested close.
- The fake hub compares the query parameters a step names in `query_instants` as instants, so one
  time spelt two ways matches; every other parameter is still compared exactly. A repeated filter
  is still the list of its values.
- **errors**: the API description is vendored again (the public cut with Copy Trading's final
  contract), and the error cases follow its codes: 83 cases, one new - `gone` (410), an `ApiError`
  that keeps the code.

## 0.7.1

- **errors**: the API description is vendored again, and the
  error cases follow its codes: 82 cases, 19 new. Among them are the sign-in and account codes
  (`credentials_invalid`, `factor_required`, `step_up_required`, `session_required`,
  `password_breached`, `password_too_short`, `password_too_long`, `email_in_use`, `code_invalid`,
  `terms_outdated`, `organisation_required`, `origin_refused`, `caller_refused`,
  `permission_denied`, `telegram_code_expired`, `recipients_required`) and the support codes
  (`support_invalid`, `support_state`, `support_case_claimed`). Each is the error class its HTTP
  status maps to, keeping the code. `preview_moved`, `preview_expired`, `bars_unreadable` and
  `ticks_unreadable` were already covered in 0.7.0.

## 0.7.0

- **risk**: six cases for Risk Management, in `cases/risk.json`.
  - An order checked against the account's rules sends its volume as exact decimal text; a float
    volume is refused before anything is sent.
  - An entry a rule refuses is a `ValidationError` with code `risk_refused`, whose `details` name
    the rule, the version and the figures as text.
  - Creating a policy sends its rules as given with the `Idempotency-Key`, and a failed create is
    never sent again.
  - A challenge's accounts, filtered by several states and sorted by a figure, follow
    `next_cursor` with the same filters and sort on every page.
  The vocabulary gains `risk.check`, `risk.create_plan`, `risk.create_policy` and
  `risk.challenge_accounts`. An SDK with no `client.risk` fails these.
- The fake hub matches a filter given several values (repeated parameters) as the list of them,
  in order. A case writes such a query value as a list.
- **errors**: the API description is vendored again, and the error cases follow its codes,
  `risk_refused`, `risk_override_required` and `venue_suspended` among them: 63 cases.

## 0.6.0

- **md**: four cases for market data by a cTrader account, in `cases/md.json`:
  subscribing sends the account's own symbol name with the idempotency key and returns the
  subscription, pending; subscribing on an MT5 account is a `state_error` (`not_on_this_venue`);
  listing follows `next_cursor` to the end; candles are read by account, oldest first, with exact
  decimal prices. The vocabulary gains `md.subscribe_account`, `md.account_subscriptions` and
  `md.account_candles`. An SDK that has no `client.md` for cTrader accounts yet fails these.

## 0.5.0

- **live**: a new set of nine cases, in `live/cases.json`, that run against a real MFX Hub rather
  than the fake one: signing accepted and the test key refused, an unknown terminal not found, a
  list that follows its cursor, an exact decimal price, a float volume refused, an order repeated
  with one idempotency key that stays one order, and ticks in `seq` order. The fake hub never
  loads them.
- The vocabulary gains a `live` section: the run values a live case names, `client`, `needs`, and
  the observations `includes`, `exact`, `ascending` and `repeat`. `terminals.list` takes an
  optional `limit` and `catalog.quote` an optional `server_id`; a runner that ignores them still
  passes every fake-hub case.

## 0.4.0

- **stream**: four more cases, 12 in all. Closing the stream ends a read that is waiting, with
  nothing and no reconnect (a stream that reconnected instead kept a script from ever ending). A
  message of a type the SDK has never heard of is delivered as it came. After a reconnect each
  channel resumes from its own last seq. Every lifetime close is followed by a reconnect, however
  many there are, and each is counted.
- The vocabulary gains `stream.close_waiting`. An SDK that does not run it yet lists it in its
  `not-yet.json`; it is not skipped silently.

## 0.3.0

- **idempotency**: a write sent again with the same key and already final is answered with its
  state only, so the SDK reads the command once and returns the original result in full: price,
  tickets and the broker's comment, with `ok` true for a success. When that read fails, the call
  still returns what the platform said, and never raises. A duplicate still in flight is reported
  as it is, with no extra read. Two new cases; `idempotency.duplicate_is_the_original` now answers
  a command still executing.
- The vocabulary's `execution.place_order` returns `exec_price`, `position` and `comment_raw` too,
  and every field a case observes must be one the vocabulary names.

## 0.2.0

- **stream**: the fake hub serves the WebSocket stream from a script per connection. Eight cases:
  a signed upgrade and messages in order; a seq gap counted; a lifetime close (4009) and a
  slow-consumer close (4008) each reconnect and resume from the last seq; re-authenticate (4001)
  stops with an authentication error and no reconnect; prices subscribed again, not resumed, after
  a reconnect; a resync reported and not counted as a gap; a refused channel costing only itself.
- The vocabulary gains `stream.read`.

## 0.1.0

The first release: the fake MFX Hub and 64 cases.

- **signing**: the API description's test vector byte for byte; every request signed with a fresh
  nonce; the query string signed as sent; a retried read signed again.
- **errors**: every error code the API description names maps to its typed error and keeps the
  code; generated from the description.
- **decimals**: volumes sent as decimal strings, an exponent written plainly, a float refused
  before the wire, prices read with every digit.
- **idempotency**: the key sent as the `Idempotency-Key` header, a write never retried, a
  duplicate read as the original.
- **paging**: a list follows the cursor to the end; a page is one request with no total.
- **execution**: a refusal, a rate limit and a dropped connection are results, never errors; an
  accepted order carries its command.
