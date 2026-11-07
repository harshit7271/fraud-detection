"""
Automated benchmark runner for FACEGUARD AI Locust Load Tests.
Executes headless tests and outputs RPS, p50, p95, p99 latencies and failure rates.
"""
import subprocess
import sys


def run_benchmark(users: int = 10, spawn_rate: int = 2, run_time: str = "15s", host: str = "http://localhost:8000") -> int:
    print(f"Starting Locust Benchmark: Users={users}, SpawnRate={spawn_rate}, RunTime={run_time}, Host={host}")
    cmd = [
        sys.executable,
        "-m",
        "locust",
        "-f",
        "tests/performance/locustfile.py",
        "--headless",
        "-u",
        str(users),
        "-r",
        str(spawn_rate),
        "--run-time",
        run_time,
        "--host",
        host,
    ]
    return subprocess.run(cmd).returncode


if __name__ == "__main__":
    users = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    spawn_rate = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    run_time = sys.argv[3] if len(sys.argv) > 3 else "15s"
    host = sys.argv[4] if len(sys.argv) > 4 else "http://localhost:8000"
    code = run_benchmark(users, spawn_rate, run_time, host)
    sys.exit(code)
