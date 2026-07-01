#!/usr/bin/env python3
"""Poll server responsiveness endpoints against an already-running server."""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import json
import math
import socket
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


WORK_ITEM_ID = "WORK-20260630-runtime-facade-server-responsiveness-evidence-harness"
DEFAULT_ENDPOINTS = (
    "/health",
    "/api/health",
    "/ready",
    "/api/ready",
    "/api/dm/combat",
    "/api/dm/combat?workspace=dmcontrol",
)


def positive_float(raw: str) -> float:
    try:
        value = float(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected a positive number, got {raw!r}") from exc
    if value <= 0:
        raise argparse.ArgumentTypeError(f"expected a positive number, got {raw!r}")
    return value


def port_number(raw: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected a port number, got {raw!r}") from exc
    if value < 1 or value > 65535:
        raise argparse.ArgumentTypeError(f"expected a port from 1 to 65535, got {raw!r}")
    return value


def default_output_path() -> Path:
    timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"{WORK_ITEM_ID}_{timestamp}.jsonl"
    return Path("logs") / "smoke" / filename


def build_base_url(host: str, port: int) -> str:
    host = host.strip().rstrip("/")
    if host.startswith("http://") or host.startswith("https://"):
        return host
    return f"http://{host}:{port}"


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds")


def classify_exception(exc: BaseException) -> str:
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return "timeout"
    if isinstance(exc, urllib.error.URLError):
        reason = getattr(exc, "reason", None)
        if isinstance(reason, (TimeoutError, socket.timeout)):
            return "timeout"
        if isinstance(reason, ConnectionRefusedError):
            return "connection_refused"
        if isinstance(reason, OSError):
            return reason.__class__.__name__
    return exc.__class__.__name__


def read_response_body(response: Any) -> Tuple[int, Optional[str], Optional[str]]:
    try:
        body = response.read()
    except Exception as exc:
        return 0, classify_exception(exc), str(exc)
    return len(body or b""), None, None


def poll_endpoint(
    *,
    base_url: str,
    endpoint: str,
    round_index: int,
    request_index: int,
    timeout_seconds: float,
    run_id: str,
) -> Dict[str, Any]:
    url = f"{base_url}{endpoint}"
    started_at_monotonic = time.perf_counter()
    record: Dict[str, Any] = {
        "record_type": "sample",
        "work_item_id": WORK_ITEM_ID,
        "run_id": run_id,
        "round": round_index,
        "request_index": request_index,
        "timestamp_utc": utc_now_iso(),
        "method": "GET",
        "endpoint": endpoint,
        "url": url,
        "timeout_seconds": timeout_seconds,
        "status": None,
        "latency_ms": None,
        "bytes_read": 0,
        "ok": False,
        "failure": True,
        "error_type": None,
        "error": None,
        "body_read_error_type": None,
        "body_read_error": None,
    }

    request = urllib.request.Request(
        url,
        headers={"User-Agent": f"{WORK_ITEM_ID}/1.0"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            status = int(getattr(response, "status", response.getcode()))
            record["status"] = status
            bytes_read, body_error_type, body_error = read_response_body(response)
            record["bytes_read"] = bytes_read
            record["body_read_error_type"] = body_error_type
            record["body_read_error"] = body_error
            record["ok"] = 200 <= status < 400
            record["failure"] = bool(body_error_type) or not record["ok"]
            if body_error_type:
                record["ok"] = False
                record["error_type"] = body_error_type
                record["error"] = body_error
    except urllib.error.HTTPError as exc:
        record["status"] = int(exc.code)
        bytes_read, body_error_type, body_error = read_response_body(exc)
        record["bytes_read"] = bytes_read
        record["body_read_error_type"] = body_error_type
        record["body_read_error"] = body_error
        record["ok"] = 200 <= int(exc.code) < 400
        record["failure"] = bool(body_error_type) or not record["ok"]
        record["error_type"] = "HTTPError"
        record["error"] = str(exc)
    except Exception as exc:  # Connection failures/timeouts are evidence, not crashes.
        record["error_type"] = classify_exception(exc)
        record["error"] = str(exc)
    finally:
        latency_ms = (time.perf_counter() - started_at_monotonic) * 1000.0
        record["latency_ms"] = round(latency_ms, 3)

    return record


def percentile(values: Iterable[float], percentile_value: float) -> Optional[float]:
    sorted_values = sorted(values)
    if not sorted_values:
        return None
    index = max(0, math.ceil((percentile_value / 100.0) * len(sorted_values)) - 1)
    return sorted_values[min(index, len(sorted_values) - 1)]


def format_latency(value: Optional[float]) -> str:
    if value is None:
        return "n/a"
    return f"{value:.3f} ms"


def status_summary(records: List[Dict[str, Any]]) -> str:
    counts: Dict[str, int] = {}
    for record in records:
        status = record.get("status")
        key = "error" if status is None else str(status)
        counts[key] = counts.get(key, 0) + 1
    return ", ".join(f"{key}:{counts[key]}" for key in sorted(counts))


def print_summary(records: List[Dict[str, Any]], output_path: Path) -> None:
    print(f"Evidence JSONL: {output_path}")
    print("endpoint count failures p50 p95 max statuses")
    for endpoint in DEFAULT_ENDPOINTS:
        endpoint_records = [record for record in records if record.get("endpoint") == endpoint]
        latencies = [
            float(record["latency_ms"])
            for record in endpoint_records
            if record.get("latency_ms") is not None
        ]
        failures = sum(1 for record in endpoint_records if record.get("failure"))
        p50 = percentile(latencies, 50)
        p95 = percentile(latencies, 95)
        max_latency = max(latencies) if latencies else None
        statuses = status_summary(endpoint_records) if endpoint_records else "none"
        print(
            f"{endpoint} "
            f"count={len(endpoint_records)} "
            f"failures={failures} "
            f"p50={format_latency(p50)} "
            f"p95={format_latency(p95)} "
            f"max={format_latency(max_latency)} "
            f"statuses={statuses}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Poll init-tracker health/readiness and DM combat routes concurrently "
            "against an already-running server and write bounded JSONL evidence."
        )
    )
    parser.add_argument("--host", default="127.0.0.1", help="server host, default: 127.0.0.1")
    parser.add_argument("--port", type=port_number, default=8787, help="server port, default: 8787")
    parser.add_argument(
        "--duration-seconds",
        type=positive_float,
        default=30.0,
        help="total polling duration, default: 30",
    )
    parser.add_argument(
        "--interval-seconds",
        type=positive_float,
        default=1.0,
        help="delay between concurrent polling rounds, default: 1",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=positive_float,
        default=2.0,
        help="per-request timeout, default: 2",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "JSONL output path, default: "
            "logs/smoke/WORK-20260630-runtime-facade-server-responsiveness-"
            "evidence-harness_<timestamp>.jsonl"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_path = args.output if args.output is not None else default_output_path()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    base_url = build_base_url(args.host, args.port)
    run_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    records: List[Dict[str, Any]] = []
    round_index = 0
    request_index = 0
    start_monotonic = time.monotonic()
    deadline = start_monotonic + args.duration_seconds
    next_round_at = start_monotonic

    run_start = {
        "record_type": "run_start",
        "work_item_id": WORK_ITEM_ID,
        "run_id": run_id,
        "timestamp_utc": utc_now_iso(),
        "base_url": base_url,
        "duration_seconds": args.duration_seconds,
        "interval_seconds": args.interval_seconds,
        "timeout_seconds": args.timeout_seconds,
        "endpoints": list(DEFAULT_ENDPOINTS),
    }

    with output_path.open("w", encoding="utf-8") as evidence_file:
        evidence_file.write(json.dumps(run_start, sort_keys=True) + "\n")
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(DEFAULT_ENDPOINTS)) as executor:
            while time.monotonic() < deadline:
                round_index += 1
                futures = []
                for endpoint in DEFAULT_ENDPOINTS:
                    request_index += 1
                    futures.append(
                        executor.submit(
                            poll_endpoint,
                            base_url=base_url,
                            endpoint=endpoint,
                            round_index=round_index,
                            request_index=request_index,
                            timeout_seconds=args.timeout_seconds,
                            run_id=run_id,
                        )
                    )
                for future in concurrent.futures.as_completed(futures):
                    record = future.result()
                    records.append(record)
                    evidence_file.write(json.dumps(record, sort_keys=True) + "\n")

                next_round_at += args.interval_seconds
                sleep_seconds = min(next_round_at, deadline) - time.monotonic()
                if sleep_seconds > 0:
                    time.sleep(sleep_seconds)

        run_end = {
            "record_type": "run_end",
            "work_item_id": WORK_ITEM_ID,
            "run_id": run_id,
            "timestamp_utc": utc_now_iso(),
            "rounds": round_index,
            "samples": len(records),
        }
        evidence_file.write(json.dumps(run_end, sort_keys=True) + "\n")

    print_summary(records, output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
