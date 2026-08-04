from content_ops import queueing


def test_wake_job_pushes_id_without_failing_request(monkeypatch):
    calls: list[tuple[str, str]] = []

    class FakeQueue:
        def rpush(self, key: str, value: str) -> None:
            calls.append((key, value))

        def close(self) -> None:
            calls.append(("close", ""))

    monkeypatch.setattr(queueing, "redis_client", lambda: FakeQueue())
    assert queueing.wake_job("job-1") is True
    assert calls == [(queueing.JOB_QUEUE, "job-1"), ("close", "")]