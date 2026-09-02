import asyncio
import time
import httpx

API_URL = "http://127.0.0.1:8000/api/v1/scan"
ITERATIONS = 10

async def send_scan_request(client: httpx.AsyncClient,text: str) -> tuple[int, float]:
    """Send a scan request and return its status code and latency."""

    start_time = time.perf_counter()
    response = await client.post(
        API_URL,
        json={"text": text},
    )

    latency_ms = (time.perf_counter() - start_time) * 1000

    return response.status_code, latency_ms


async def run_benchmark() -> None:
    """Measure cold and cached scan request latency."""

    cold_latencies = []
    cached_latencies = []

    async with httpx.AsyncClient(timeout=60.0) as client:

        for iteration in range(1, ITERATIONS + 1):

            test_text = (
                f"Benchmark request {iteration}: "
                "My email is guest@email.com"
            )

            cold_status, cold_latency = await send_scan_request(
                client,
                test_text,
            )

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

    average_cold = sum(cold_latencies) / len(cold_latencies)
    average_cached = sum(cached_latencies) / len(cached_latencies)

    minimum_cold = min(cold_latencies)
    maximum_cold = max(cold_latencies)

    minimum_cached = min(cached_latencies)
    maximum_cached = max(cached_latencies)

    improvement = average_cold / average_cached

    print("\n" + "=" * 55)
    print("PII Performance Benchmark")
    print("=" * 55)

    print(f"Iterations: {ITERATIONS}")

    print("\nCold requests")
    print(f"Average: {average_cold:.2f} ms")
    print(f"Minimum: {minimum_cold:.2f} ms")
    print(f"Maximum: {maximum_cold:.2f} ms")

    print("\nCached requests")
    print(f"Average: {average_cached:.2f} ms")
    print(f"Minimum: {minimum_cached:.2f} ms")
    print(f"Maximum: {maximum_cached:.2f} ms")

    print("\nPerformance improvement")
    print(f"Cached requests are approximately {improvement:.2f}x faster.")

    print("=" * 55)


if __name__ == "__main__":
    asyncio.run(run_benchmark())
