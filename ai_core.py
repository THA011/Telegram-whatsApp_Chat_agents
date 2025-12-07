"""
ai_core.py

Simple local answer engine using TF-IDF similarity over `kb.txt` sentences.
This is intentionally lightweight and works offline. Replace the `Answerer` class
with calls to an external LLM if you prefer (OpenAI, or local LLM) for richer answers.
"""
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np


class Answerer:
    def __init__(self, kb_path: str = None, threshold: float = 0.2):
        self.kb_path = kb_path or Path(__file__).parent / 'kb.txt'
        self.threshold = threshold
        self.sentences = []
        self.vectorizer = None
        self.tfidf = None
        self._load_kb()

    def _load_kb(self):
        p = Path(self.kb_path)
        if not p.exists():
            self.sentences = []
            return
        txt = p.read_text(encoding='utf-8')
        # simple split on newlines and filter empty
        self.sentences = [s.strip() for s in txt.splitlines() if s.strip()]
        if self.sentences:
            self.vectorizer = TfidfVectorizer().fit(self.sentences)
            self.tfidf = self.vectorizer.transform(self.sentences)

    def answer(self, query: str) -> dict:
        """Return a dict: {answer:str, score:float, source_index:int or None}

        If no confident match is found, return a polite fallback asking for clarification.
        """
        q = (query or '').strip()
        if not q:
            return {'answer': "I didn't get a message — please type your question.", 'score': 0.0, 'index': None}

        # quick heuristic for greetings
        if q.lower() in ('hi', 'hello', 'hey', 'good morning', 'good evening'):
            return {'answer': 'Hello — tell me what you need help with or ask a question.', 'score': 1.0, 'index': None}

        if not self.sentences:
            return {'answer': "I don't have knowledge loaded yet. Please add sentences to kb.txt.", 'score': 0.0, 'index': None}

        q_vec = self.vectorizer.transform([q])
        sims = (self.tfidf @ q_vec.T).toarray().ravel()
        best_idx = int(np.argmax(sims))
        best_score = float(sims[best_idx])

        if best_score < self.threshold:
            return {'answer': "I couldn't find a confident answer. Can you rephrase or give more details?",
                    'score': best_score, 'index': None}

        return {'answer': self.sentences[best_idx], 'score': best_score, 'index': best_idx}


if __name__ == '__main__':
    a = Answerer()
    for q in ["How do I set up Twilio?", "hello", "what is supported"]:
        print(q, '=>', a.answer(q))
