import time
import statistics
import platform
import concurrent.futures
import requests

BASE_URL = "http://127.0.0.1:8000"
TOTAL_REQUESTS = 200
CONCURRENCY = 10

def benchmark_endpoint(endpoint_url: str, name: str):
    latencies = []
    errors = 0

    def single_req():
        start = time.perf_counter()
        try:
            r = requests.get(endpoint_url, timeout=5)
            elapsed = (time.perf_counter() - start) * 1000.0
            if r.status_code == 200:
                return elapsed, True
            else:
                return elapsed, False
        except Exception:
            return 0.0, False

    start_total = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        futures = [executor.submit(single_req) for _ in range(TOTAL_REQUESTS)]
        for f in concurrent.futures.as_completed(futures):
            elapsed, success = f.result()
            if success:
                latencies.append(elapsed)
            else:
                errors += 1

    total_time = time.perf_counter() - start_total
    latencies.sort()

    p50 = statistics.median(latencies) if latencies else 0
    p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0
    p99 = latencies[int(len(latencies) * 0.99)] if latencies else 0
    avg = statistics.mean(latencies) if latencies else 0
    rps = len(latencies) / total_time if total_time > 0 else 0

    return {
        "name": name,
        "total_requests": TOTAL_REQUESTS,
        "successful_requests": len(latencies),
        "errors": errors,
        "total_time_seconds": round(total_time, 3),
        "rps": round(rps, 1),
        "avg_ms": round(avg, 2),
        "min_ms": round(min(latencies), 2) if latencies else 0,
        "p50_ms": round(p50, 2),
        "p95_ms": round(p95, 2),
        "p99_ms": round(p99, 2),
        "max_ms": round(max(latencies), 2) if latencies else 0
    }

def run_benchmarks():
    print("=== ENVIRONMENT SPECS ===")
    print(f"OS: {platform.system()} {platform.release()} ({platform.version()})")
    print(f"Machine: {platform.machine()}")
    print(f"Processor: {platform.processor()}")
    print(f"Python: {platform.python_version()}")
    print(f"Database: PostgreSQL 16.2 (localhost:5432)")

    print("\nRunning benchmark on GET /api/v1/health ...")
    h_res = benchmark_endpoint(f"{BASE_URL}/api/v1/health", "GET /api/v1/health")
    print(f"Health RPS: {h_res['rps']} req/s | Avg: {h_res['avg_ms']}ms | p50: {h_res['p50_ms']}ms | p95: {h_res['p95_ms']}ms | p99: {h_res['p99_ms']}ms")

    print("\nRunning benchmark on GET /api/v1/products ...")
    p_res = benchmark_endpoint(f"{BASE_URL}/api/v1/products", "GET /api/v1/products (DB Query)")
    print(f"Products RPS: {p_res['rps']} req/s | Avg: {p_res['avg_ms']}ms | p50: {p_res['p50_ms']}ms | p95: {p_res['p95_ms']}ms | p99: {p_res['p99_ms']}ms")

    return h_res, p_res

if __name__ == "__main__":
    run_benchmarks()
