import os


def test_compose_has_worker_and_db():
    path = os.path.join(os.path.dirname(__file__), "..", "docker-compose.yml")
    path = os.path.normpath(path)
    assert os.path.exists(path)
    with open(path, "r", encoding="utf-8") as fh:
        txt = fh.read()
    assert "worker" in txt
    assert "./zac.db" in txt
