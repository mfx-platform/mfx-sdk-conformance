# Changelog

Every release of the suite, newest first. An SDK pins a release; a new case in a release can make
an SDK that passed the previous one fail, which is the point.

## Unreleased

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
