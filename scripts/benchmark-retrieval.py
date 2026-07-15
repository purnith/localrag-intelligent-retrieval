import argparse
import asyncio
import json
import statistics
import time
from pathlib import Path
from typing import Any

import httpx


DEFAULT_QUERIES = [
    "What does the policy say about vacation days?",
    "Summarize the uploaded documents.",
    "What security practices are described?",
    "What benefits are available to employees?",
]


def percentile(values: list[float], rank: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((rank / 100) * (len(ordered) - 1))))
    return ordered[index]


async def login(client: httpx.AsyncClient, api_url: str, email: str, password: str) -> None:
    response = await client.post(
        f"{api_url}/api/auth/login",
        json={"email": email, "password": password},
    )
    response.raise_for_status()


async def run_query(
    client: httpx.AsyncClient,
    api_url: str,
    query: str,
    endpoint: str,
    limit: int,
) -> dict[str, Any]:
    start = time.perf_counter()
    response = await client.post(
        f"{api_url}{endpoint}",
        json={"query": query, "limit": limit},
    )
    elapsed_ms = (time.perf_counter() - start) * 1000
    ok = response.is_success
    source_count = 0
    if ok:
        payload = response.json()
        if isinstance(payload, list):
            source_count = len(payload)
        elif isinstance(payload, dict):
            source_count = len(payload.get("sources", []))
    return {
        "query": query,
        "status_code": response.status_code,
        "ok": ok,
        "latency_ms": round(elapsed_ms, 2),
        "source_count": source_count,
    }


async def benchmark(args: argparse.Namespace) -> dict[str, Any]:
    queries = args.query or DEFAULT_QUERIES
    async with httpx.AsyncClient(timeout=args.timeout_seconds) as client:
        if args.email and args.password:
            await login(client, args.api_url, args.email, args.password)

        tasks = [
            run_query(client, args.api_url, query, args.endpoint, args.limit)
            for _ in range(args.repeat)
            for query in queries
        ]
        started_at = time.perf_counter()
        results = await asyncio.gather(*tasks)
        total_seconds = time.perf_counter() - started_at

    latencies = [result["latency_ms"] for result in results if result["ok"]]
    success_count = sum(1 for result in results if result["ok"])
    total_count = len(results)
    summary = {
        "endpoint": args.endpoint,
        "requests": total_count,
        "successes": success_count,
        "failures": total_count - success_count,
        "success_rate": round(success_count / total_count, 4) if total_count else 0,
        "total_seconds": round(total_seconds, 2),
        "requests_per_second": round(total_count / total_seconds, 2) if total_seconds else 0,
        "latency_ms": {
            "min": round(min(latencies), 2) if latencies else 0,
            "mean": round(statistics.mean(latencies), 2) if latencies else 0,
            "median": round(statistics.median(latencies), 2) if latencies else 0,
            "p95": round(percentile(latencies, 95), 2) if latencies else 0,
            "max": round(max(latencies), 2) if latencies else 0,
        },
    }
    return {"summary": summary, "results": results}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark LocalRAG retrieval endpoints.")
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--endpoint", default="/api/search", choices=["/api/search", "/api/ask", "/api/agent/ask"])
    parser.add_argument("--email", help="Existing LocalRAG user email.")
    parser.add_argument("--password", help="Existing LocalRAG user password.")
    parser.add_argument("--query", action="append", help="Query to benchmark. Repeat for multiple queries.")
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--timeout-seconds", type=float, default=180)
    parser.add_argument("--output", default="benchmark-results.json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = asyncio.run(benchmark(args))
    output_path = Path(args.output)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    print(f"wrote detailed results to {output_path}")


if __name__ == "__main__":
    main()

