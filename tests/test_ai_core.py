import pytest
from ai_core import Answerer
from pathlib import Path


def test_answerer_matches_kb(tmp_path):
    kb = tmp_path / 'kb.txt'
    kb.write_text('How do I set up Twilio?\nFollow the Twilio docs to configure a WhatsApp sandbox.')

    a = Answerer(kb_path=str(kb), threshold=0.0)
    res = a.answer('How do I set up Twilio?')
    assert 'Twilio' in res['answer']


def test_answerer_fallback(tmp_path):
    kb = tmp_path / 'kb.txt'
    kb.write_text('Only one line here.')
    a = Answerer(kb_path=str(kb), threshold=0.9)
    res = a.answer('Unrelated query that should not match')
    assert 'couldn' in res['answer'] or res['index'] is None
