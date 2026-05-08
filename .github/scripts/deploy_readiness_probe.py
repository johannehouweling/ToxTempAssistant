#!/usr/bin/env python3
"""Helpers for deploy workflow readiness checks."""

from __future__ import annotations

import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


def parse_env_dump(text: str) -> dict[str, str]:
    env: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            env[key] = value
    return env


def normalize_host_candidate(value: str) -> str:
    candidate = value.strip()
    if not candidate or candidate == "*":
        return ""

    if "://" in candidate:
        try:
            candidate = urlparse(candidate).hostname or ""
        except ValueError:
            return ""
    elif candidate.startswith("["):
        inner, separator, _rest = candidate[1:].partition("]")
        if not separator:
            return ""
        candidate = f"[{inner}]"
    elif candidate.count(":") == 1:
        # Unbracketed IPv6 literals contain multiple colons, so only treat a
        # single colon as a host:port separator.
        candidate = candidate.split(":", 1)[0]

    candidate = candidate.strip().strip(".")
    if not candidate or candidate == "*":
        return ""
    if ":" in candidate and not candidate.startswith("["):
        return f"[{candidate}]"
    return candidate


def probe_host_from_env(text: str) -> str:
    env = parse_env_dump(text)
    site_url = env.get("SITE_URL", "").strip()
    if site_url:
        host = normalize_host_candidate(site_url)
        if host:
            return host

    for entry in env.get("ALLOWED_HOSTS", "").split(","):
        candidate = normalize_host_candidate(entry)
        if candidate:
            return candidate

    return "localhost"


def command_probe_host() -> int:
    print(probe_host_from_env(sys.stdin.read()))
    return 0


def command_http_status(url: str, timeout: float) -> int:
    probe_host = os.environ.get("PROBE_HOST")
    if not probe_host:
        print(
            "Environment variable PROBE_HOST is required for http-status probes.",
            file=sys.stderr,
        )
        return 1
    try:
        with urlopen(
            Request(url, headers={"Host": probe_host}),
            timeout=timeout,
        ) as response:
            print(response.status)
    except HTTPError as exc:
        print(f"HTTP {exc.code}: {exc.reason}", file=sys.stderr)
        return 1
    except (TimeoutError, URLError, OSError) as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    if os.environ.get("PROBE_MODE") == "http-status":
        url = os.environ.get("PROBE_URL")
        if not url:
            print("PROBE_URL is required when PROBE_MODE=http-status.", file=sys.stderr)
            return 1
        try:
            timeout = float(os.environ.get("PROBE_TIMEOUT_SECONDS", "5"))
        except ValueError:
            print(
                "PROBE_TIMEOUT_SECONDS must be a valid number.",
                file=sys.stderr,
            )
            return 1
        return command_http_status(url, timeout)

    if sys.argv[1:] == ["probe-host"]:
        return command_probe_host()

    print(
        "Usage: deploy_readiness_probe.py probe-host "
        "or PROBE_MODE=http-status PROBE_URL=<url> PROBE_HOST=<host> "
        "python3 - < deploy_readiness_probe.py",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
