from chat_agents.message_queue import enqueue_message


def test_enqueue_message_basic():
    job = {"platform": "telegram", "to": 12345, "text": "hello"}
    status = enqueue_message(job)
    assert isinstance(status, dict)
    assert "job_id" in status
    assert "eta_seconds" in status
