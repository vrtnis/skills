#!/usr/bin/env python3
"""Custom patent search API helper CLI.

Usage examples:
  python patsearch_search.py --q '{"_contains":{"patent_title":"battery"}}'
  python patsearch_search.py --endpoint patent/us_patent_citation --body-file query.json
  python patsearch_search.py --q '{}' --o '{"size":10}' --out results.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import requests


DEFAULT_BASE_URL = "https://your-custom-endpoint.example/api/v1"
ALLOWED_PAYLOAD_KEYS = ("q", "f", "s", "o")


class CliError(Exception):
    """User-facing validation and runtime errors."""


def parse_args() -> argparse.Namespace:
    epilog = (
        "Examples:\n"
        "  python patsearch_search.py --q '{\"_contains\":{\"patent_title\":\"battery\"}}'\n"
        "  python patsearch_search.py --body-file query.json --endpoint patent\n"
        "  python patsearch_search.py --q '{}' --f '[\"patent_number\"]' --o '{\"size\":25}'"
    )

    parser = argparse.ArgumentParser(
        description="Run a single-page patent search API query and save the JSON response.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=epilog,
    )
    parser.add_argument(
        "--base-url",
        help=(
            "Base API URL (for example, https://your-endpoint.example/api/v1). "
            "Overrides PATSEARCH_BASE_URL."
        ),
    )
    parser.add_argument(
        "--endpoint",
        default="patent",
        help="Endpoint path under the base URL (for example, patent or patent/us_patent_citation).",
    )
    parser.add_argument("--q", help="Query object as JSON string.")
    parser.add_argument("--f", help="Fields selector as JSON string.")
    parser.add_argument("--s", help="Sort selector as JSON string.")
    parser.add_argument("--o", help="Options object as JSON string (supports size/after).")
    parser.add_argument(
        "--body-file",
        type=Path,
        help="Path to a JSON object containing one or more of: q, f, s, o.",
    )
    parser.add_argument(
        "--api-key",
        help="API key. Defaults to PATSEARCH_API_KEY env var.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        help="Output path for JSON response. If it exists, an auto-versioned name is used.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="HTTP timeout in seconds (default: 30).",
    )
    return parser.parse_args()


def parse_json_arg(arg_name: str, raw_value: str) -> Any:
    try:
        return json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise CliError(f"Invalid JSON for {arg_name}: {exc.msg} (pos {exc.pos})") from exc


def load_body_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise CliError(f"Body file not found: {path}")

    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            payload = json.load(handle)
    except json.JSONDecodeError as exc:
        raise CliError(f"Invalid JSON in --body-file {path}: {exc.msg} (pos {exc.pos})") from exc
    except OSError as exc:
        raise CliError(f"Unable to read --body-file {path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise CliError("--body-file must contain a top-level JSON object.")

    return payload


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    payload: dict[str, Any] = {}

    if args.body_file:
        body_payload = load_body_file(args.body_file)
        for key in ALLOWED_PAYLOAD_KEYS:
            if key in body_payload:
                payload[key] = body_payload[key]

    cli_json_values = {
        "q": args.q,
        "f": args.f,
        "s": args.s,
        "o": args.o,
    }
    for key, raw_value in cli_json_values.items():
        if raw_value is not None:
            payload[key] = parse_json_arg(f"--{key}", raw_value)

    if "q" not in payload:
        raise CliError("Missing required query: provide --q or include q in --body-file.")

    options = payload.get("o")
    if options is not None:
        if not isinstance(options, dict):
            raise CliError("The o value must be a JSON object when provided.")
        if "size" in options:
            size_value = options["size"]
            if not isinstance(size_value, int):
                raise CliError("o.size must be an integer.")
            if size_value > 1000:
                raise CliError("o.size cannot be greater than 1000.")

    return payload


def normalize_endpoint(endpoint: str) -> str:
    normalized = endpoint.strip().strip("/")
    if not normalized:
        raise CliError("--endpoint cannot be empty.")
    return normalized


def resolve_base_url(cli_value: str | None) -> str:
    base_url = cli_value or os.getenv("PATSEARCH_BASE_URL") or DEFAULT_BASE_URL
    normalized = base_url.strip().rstrip("/")
    if not normalized:
        raise CliError("Missing base URL. Provide --base-url or set PATSEARCH_BASE_URL.")
    return normalized


def resolve_api_key(cli_value: str | None) -> str:
    api_key = cli_value or os.getenv("PATSEARCH_API_KEY")
    if not api_key:
        raise CliError("Missing API key. Pass --api-key or set PATSEARCH_API_KEY.")
    return api_key


def default_output_path(endpoint: str) -> Path:
    safe_endpoint = re.sub(r"[^A-Za-z0-9_-]", "_", endpoint.replace("/", "_"))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path(f"patsearch_{safe_endpoint}_{timestamp}.json")


def auto_version_path(path: Path) -> Path:
    if not path.exists():
        return path

    parent = path.parent
    stem = path.stem
    suffix = path.suffix

    counter = 2
    while True:
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def build_url(base_url: str, endpoint: str) -> str:
    return f"{base_url}/{endpoint}/"


def run_request(url: str, api_key: str, payload: dict[str, Any], timeout_seconds: float) -> dict[str, Any]:
    headers = {
        "X-Api-Key": api_key,
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=timeout_seconds)
    except requests.exceptions.Timeout as exc:
        raise CliError(
            f"Request timed out after {timeout_seconds:.1f}s. Try increasing --timeout or retrying."
        ) from exc
    except requests.exceptions.ConnectionError as exc:
        raise CliError("Network connection error while calling the API. Verify network access and retry.") from exc
    except requests.exceptions.RequestException as exc:
        raise CliError(f"Unexpected request error: {exc}") from exc

    if not response.ok:
        snippet = response.text.strip().replace("\n", " ")[:500]
        raise CliError(f"API request failed with HTTP {response.status_code}: {snippet}")

    try:
        response_json = response.json()
    except json.JSONDecodeError as exc:
        raise CliError("API response was not valid JSON.") from exc

    if not isinstance(response_json, dict):
        raise CliError("API response JSON was not an object.")

    return response_json


def write_output(path: Path, payload: dict[str, Any]) -> Path:
    output_path = auto_version_path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
    except OSError as exc:
        raise CliError(f"Unable to write output file {output_path}: {exc}") from exc

    return output_path


def print_summary(output_path: Path, response_json: dict[str, Any]) -> None:
    print(f"Wrote response to: {output_path.resolve()}")

    if "count" in response_json:
        print(f"count: {response_json['count']}")
    if "total_hits" in response_json:
        print(f"total_hits: {response_json['total_hits']}")


def main() -> int:
    args = parse_args()

    try:
        base_url = resolve_base_url(args.base_url)
        endpoint = normalize_endpoint(args.endpoint)
        payload = build_payload(args)
        api_key = resolve_api_key(args.api_key)

        url = build_url(base_url, endpoint)
        response_json = run_request(url, api_key, payload, timeout_seconds=args.timeout)

        output_path = args.out if args.out else default_output_path(endpoint)
        written_path = write_output(output_path, response_json)
        print_summary(written_path, response_json)
        return 0
    except CliError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
