import asyncio
import statistics
import time
import uuid
import httpx

API_URL = "http://127.0.0.1:8000/api/v1/scan"
ITERATIONS = 20

async def send_scan_request(
    client: httpx.AsyncClient,
    text: str,
) -> tuple[int, float]:
    """Send a scan request and return its status code and latency."""

    start_time = time.perf_counter()

    response = await client.post(
        API_URL,
        json={"text": text},
    )

    latency_ms = (time.perf_counter() - start_time) * 1000

    return response.status_code, latency_ms

def calculate_p95(latencies: list[float]) -> float:
    """Calculate the 95th percentile latency."""

    return statistics.quantiles(
        latencies,
        n=100,
        method="inclusive",
    )[94]


async def run_benchmark() -> None:
    """Measure cold and cached scan request latency."""

    cold_latencies = []
    cached_latencies = []

    benchmark_id = uuid.uuid4().hex

    async with httpx.AsyncClient(timeout=60.0) as client:
        for iteration in range(1, ITERATIONS + 1):

            # Unique text guarantees a cache miss for this benchmark run.
            test_text = (
                f"Benchmark {benchmark_id} iteration {iteration}: "
                "My email is guest@email.com"
            )

            # First request: expected cache miss.
            cold_status, cold_latency = await send_scan_request(
                client,
                test_text,
            )

            # Second request: expected cache hit.
            cached_status, cached_latency = await send_scan_request(
                client,
                test_text,
            )

            if cold_status != 200:
                raise RuntimeError(
                    f"Cold request failed with HTTP {cold_status}"
                )

            if cached_status != 200:
                raise RuntimeError(
                    f"Cached request failed with HTTP {cached_status}"
                )

            cold_latencies.append(cold_latency)
            cached_latencies.append(cached_latency)

            print(
                f"Iteration {iteration}: "
                f"cold={cold_latency:.2f} ms, "
                f"cached={cached_latency:.2f} ms"
            )

    # Cold statistics
    average_cold = statistics.mean(cold_latencies)
    median_cold = statistics.median(cold_latencies)
    p95_cold = calculate_p95(cold_latencies)
    minimum_cold = min(cold_latencies)
    maximum_cold = max(cold_latencies)

    # Cached statistics
    average_cached = statistics.mean(cached_latencies)
    median_cached = statistics.median(cached_latencies)
    p95_cached = calculate_p95(cached_latencies)
    minimum_cached = min(cached_latencies)
    maximum_cached = max(cached_latencies)

    improvement = average_cold / average_cached

    print("\n" + "=" * 60)
    print("PII Scan Performance Benchmark")
    print("=" * 60)

    print(f"Iterations: {ITERATIONS}")
    print(f"Total requests: {ITERATIONS * 2}")

    print("\nCold requests")
    print("-" * 30)
    print(f"Average:  {average_cold:.2f} ms")
    print(f"Median:   {median_cold:.2f} ms")
    print(f"P95:      {p95_cold:.2f} ms")
    print(f"Minimum:  {minimum_cold:.2f} ms")
    print(f"Maximum:  {maximum_cold:.2f} ms")

    print("\nCached requests")
    print("-" * 30)
    print(f"Average:  {average_cached:.2f} ms")
    print(f"Median:   {median_cached:.2f} ms")
    print(f"P95:      {p95_cached:.2f} ms")
    print(f"Minimum:  {minimum_cached:.2f} ms")
    print(f"Maximum:  {maximum_cached:.2f} ms")

    print("\nPerformance improvement")
    print("-" * 30)
    print(
        f"Cached requests are approximately "
        f"{improvement:.2f}x faster on average."
    )

    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_benchmark())
