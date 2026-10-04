"""Light load test (P54): concurrent conversations against a running VERA, with the latency of every request.

Each virtual customer opens a demo session, starts a conversation, states a claim and answers until the case is
registered or the conversation ends, the way the end-to-end tests do. Run it against a local server with a raised
limit of messages per minute, never against the public demo:

    VERA_MESSAGES_PER_MINUTE=10000 make serve
    uv run python scripts/load_test.py http://127.0.0.1:8000 --conversations 60 --workers 12
"""

import argparse
import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import httpx2

CLAIM = "No reconozco un cargo de mi tarjeta"


def conversation(base: str, customer: str, latencies: list[float], errors: list[str], lock: threading.Lock) -> None:
    with httpx2.Client(base_url=base, timeout=30) as client:

        def call(method: str, path: str, **kwargs) -> dict:
            started = time.perf_counter()
            response = client.request(method, path, **kwargs)
            with lock:
                latencies.append((time.perf_counter() - started) * 1000)
                if response.status_code >= 400:
                    errors.append(f"{response.status_code} {path.split('/')[2]}")
            return response.json() if response.status_code < 400 else {}

        token = call("POST", "/v1/demo-session", json={"demo_customer": customer}).get("token")
        if not token:
            return
        headers = {"Authorization": f"Bearer {token}"}
        conversation_id = call("POST", "/v1/conversations", json={}, headers=headers).get("conversation_id")
        reply = call("POST", f"/v1/conversations/{conversation_id}/messages", json={"text": CLAIM}, headers=headers)
        for _ in range(8):
            options = reply.get("options") or []
            if not options:
                break
            pending = (reply.get("pending_confirmation") or {}).get("action")
            if pending == "register_dispute" or not options[0].get("answer"):
                answer = {"selected_option": "yes" if pending else options[0]["n"]}
            elif reply.get("multiple_choice"):
                answer = {"text": "todos"}
            else:
                answer = {"selected_option": "no"}
            reply = call("POST", f"/v1/conversations/{conversation_id}/messages", json=answer, headers=headers)
            if pending == "register_dispute":
                break


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("base", help="base URL of a running VERA")
    parser.add_argument("--conversations", type=int, default=60)
    parser.add_argument("--workers", type=int, default=12)
    arguments = parser.parse_args()
    with httpx2.Client(base_url=arguments.base, timeout=30) as client:
        customers = [c["customer_ref"] for c in client.get("/v1/demo-customers").json()]
    latencies: list[float] = []
    errors: list[str] = []
    lock = threading.Lock()
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=arguments.workers) as pool:
        for index in range(arguments.conversations):
            customer = customers[index % len(customers)]
            pool.submit(conversation, arguments.base, customer, latencies, errors, lock)
    seconds = time.perf_counter() - started
    cuts = statistics.quantiles(latencies, n=20)
    print(f"conversations {arguments.conversations}, workers {arguments.workers}, requests {len(latencies)}")
    print(f"latency ms: p50 {statistics.median(latencies):.1f}, p95 {cuts[18]:.1f}, max {max(latencies):.1f}")
    print(f"throughput: {len(latencies) / seconds:.1f} requests/s over {seconds:.1f} s")
    print(f"errors: {len(errors)} {sorted(set(errors))}")


if __name__ == "__main__":
    main()
