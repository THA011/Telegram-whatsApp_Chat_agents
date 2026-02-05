from chat_agents.ai_core import AnswerEngine


def test_answer_engine_returns_str_and_handles_memory():
    ae = AnswerEngine()
    # returns a string reply for a simple query
    reply = ae.answer("hello there", memory=[{"role": "user", "text": "hi"}])
    assert isinstance(reply, str)
