import os
from chat_agents.ai_core import Answerer, AnswerEngine


def test_answerer_basic():
    a = Answerer()
    # should always return a dict with keys
    res = a.answer("hello")
    assert isinstance(res, dict)
    assert "answer" in res


def test_engine_returns_string():
    ae = AnswerEngine()
    reply = ae.answer("hello there", memory=[])
    assert isinstance(reply, str)


def test_env_example_contains_telegram_token():
    p = os.path.join(os.path.dirname(__file__), "..", ".env.example")
    p = os.path.abspath(p)
    with open(p, "r", encoding="utf-8") as f:
        txt = f.read()
    assert "TELEGRAM_TOKEN" in txt
