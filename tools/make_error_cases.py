"""Write ``cases/errors.json``: one case per error code the API description names.

    python tools/make_error_cases.py            # rewrite it
    python tools/make_error_cases.py --check    # fail if it is out of date (CI)

The codes and their HTTP statuses come from ``spec/openapi.yaml`` (``ErrorBody.code``'s
``x-known-values``), so a code the API adds becomes a case on the next refresh. Which typed error
a code becomes is the rule below: a code with its own error kind maps to it; any other maps by its
HTTP status. A code no SDK knows yet still arrives typed, by status.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "spec" / "openapi.yaml"
OUT = ROOT / "cases" / "errors.json"
TERMINAL = "0191f0c2-aaaa-7bbb-8ccc-000000000001"

#: Codes with an error kind of their own. Every other code maps by status.
BY_CODE = {
    "validation_error": "ValidationError",
    "auth_error": "AuthError",
    "forbidden": "ForbiddenError",
    "tenant_disabled": "TenantDisabledError",
    "tenant_suspended": "TenantSuspendedError",
    "maintenance": "MaintenanceError",
    "not_found": "NotFoundError",
    "conflict": "ConflictError",
    "state_error": "StateError",
    "placement_error": "PlacementError",
    "broker_not_supported": "UnsupportedBrokerError",
    "rate_limited": "RateLimitError",
    "upstream_error": "UpstreamError",
    "dependency_unavailable": "DependencyUnavailableError",
    "internal_error": "InternalError",
}
#: The kind for a code without its own, by HTTP status.
BY_STATUS = {
    400: "ValidationError",
    401: "AuthError",
    403: "ForbiddenError",
    404: "NotFoundError",
    409: "ConflictError",
    413: "ValidationError",
    422: "ValidationError",
    429: "RateLimitError",
    500: "InternalError",
    503: "UpstreamError",
}


def known_codes(spec: dict[str, Any]) -> dict[str, int]:
    """Each known code and the first HTTP status its description names."""
    values = spec["components"]["schemas"]["ErrorBody"]["properties"]["code"]["x-known-values"]
    out: dict[str, int] = {}
    for code, text in values.items():
        status = re.match(r"\s*(\d{3})", text)
        if status:
            out[code] = int(status.group(1))
    return out


def case(code: str, status: int) -> dict[str, Any]:
    """The case for one code: a read answered with it raises its kind and keeps the code."""
    kind = BY_CODE.get(code) or BY_STATUS.get(status, "ApiError")
    headers = {"Retry-After": "1"} if status in (429, 503) else {}
    return {
        "id": f"errors.{code}",
        "rule": f"An answer with code {code} ({status}) is a {kind} that keeps the code",
        "source": "Errors",
        "call": {"op": "terminals.get", "args": {"terminal_id": TERMINAL}},
        "server": [
            {
                "expect": {"method": "GET", "path": f"/v1/terminals/{TERMINAL}"},
                "answer": {
                    "status": status,
                    "headers": headers,
                    "body": {"error": {"code": code, "message": f"refused: {code}"}},
                },
                "times": "any",
            }
        ],
        "observe": {"raises": kind, "fields": {"code": code, "status": status}},
    }


def build(spec_path: Path = SPEC) -> list[dict[str, Any]]:
    """Every error case, in the order the API description lists the codes."""
    spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    return [case(code, status) for code, status in known_codes(spec).items()]


def render(cases: list[dict[str, Any]]) -> str:
    """The file's text: stable, so the check can compare it byte for byte."""
    return json.dumps(cases, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Rewrite the file, or with ``--check`` exit 1 when it differs from what the spec gives."""
    args = sys.argv[1:] if argv is None else argv
    text = render(build())
    if args[:1] == ["--check"]:
        current = OUT.read_text(encoding="utf-8") if OUT.is_file() else ""
        if current != text:
            sys.stderr.write(
                "cases/errors.json is out of date: run python tools/make_error_cases.py\n"
            )
            return 1
        return 0
    OUT.write_text(text, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
