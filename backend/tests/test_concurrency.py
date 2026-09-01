"""Regression test for a real crash found during manual browser testing:
a cached sqlite3 connection (check_same_thread=False) was shared across
FastAPI's sync-route threadpool. Two requests hitting the same session
concurrently (React Query fires several queries in parallel on page load)
could get dispatched to different worker threads and use that one shared
connection object at the same time, which segfaulted the process --
check_same_thread=False only disables sqlite3's safety check, it does not
make a connection safe for concurrent use.

Fixed by never caching connections across requests: app.deps.get_session_db
now opens a fresh connection per request and closes it when the request
ends (see storage/session_db.py). Each request's connection is only ever
touched by the one thread handling that request, so there is nothing left
to serialize.

(An earlier attempted fix wrapped a threading.Lock around a yield-based
FastAPI dependency, but FastAPI does not guarantee the "before yield" and
"after yield" halves of a sync generator dependency run on the same
worker thread, so releasing a lock acquired on a different thread raised
RuntimeError: cannot release un-acquired lock. Per-request connections
sidestep that class of bug entirely.)
"""
from concurrent.futures import ThreadPoolExecutor


def test_concurrent_requests_do_not_crash(isolated_data_dir, ready_session_id: str):
    from fastapi.testclient import TestClient

    from app.main import app

    endpoints = [
        "/api/v1/sessions/%s/vips" % ready_session_id,
        "/api/v1/sessions/%s/pools" % ready_session_id,
        "/api/v1/sessions/%s/nodes" % ready_session_id,
        "/api/v1/sessions/%s/vlans" % ready_session_id,
        "/api/v1/sessions/%s" % ready_session_id,
    ]

    def hit(url: str) -> int:
        # A single TestClient instance isn't meant to be driven concurrently
        # from multiple threads (it owns one blocking portal), so each
        # worker gets its own client -- all of them still hit the same
        # in-process app and open their own connection per request, which
        # is exactly the real-world (separate browser requests) scenario
        # that crashed before the fix.
        with TestClient(app) as c:
            return c.get(url).status_code

    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(hit, endpoints * 8))

    assert all(status == 200 for status in results), results
