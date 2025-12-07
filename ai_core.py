"""
ai_core.py

Simple local answer engine using TF-IDF similarity over `kb.txt` sentences.
This is intentionally lightweight and works offline. Replace the `Answerer` class
with calls to an external LLM if you prefer (OpenAI, or local LLM) for richer answers.
"""
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np
import re
import yaml


class Answerer:
    def __init__(self, kb_path: str = None, threshold: float = 0.2):
    # Expect YAML `faq.yml` by default with structure: faq: - q: ... - a: ...
    self.kb_path = kb_path or Path(__file__).parent / 'faq.yml'
        self.threshold = threshold
        self.questions = []
        self.answers = []
        self.vectorizer = None
        self.tfidf = None
        self._load_faq()

    def _load_faq(self):
        p = Path(self.kb_path)
        if not p.exists():
            return
        # If YAML, parse structured entries
        if p.suffix.lower() in ('.yml', '.yaml'):
            data = yaml.safe_load(p.read_text(encoding='utf-8'))
            items = data.get('faq') if isinstance(data, dict) else None
            if items:
                for item in items:
                    q = item.get('q')
                    a = item.get('a')
                    if q and a:
                        self.questions.append(str(q).strip())
                        self.answers.append(str(a).strip())
        else:
            # fallback: parse simple markdown blocks (older format)
            txt = p.read_text(encoding='utf-8')
            blocks = [b.strip() for b in re.split(r"\n\s*\n", txt) if b.strip()]
            for block in blocks:
                lines = [l.strip() for l in block.splitlines() if l.strip()]
                if not lines:
                    continue
                q = lines[0]
                q = re.sub(r'^#+\s*', '', q)
                q = re.sub(r'^Q:\s*', '', q)
                q = q.strip()
                a = '\n'.join(lines[1:]).strip() if len(lines) > 1 else ''
                if q and a:
                    self.questions.append(q)
                    self.answers.append(a)

        if self.questions:
            self.vectorizer = TfidfVectorizer().fit(self.questions)
            self.tfidf = self.vectorizer.transform(self.questions)

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

        if not self.questions:
            return {'answer': "I don't have any FAQ loaded yet. Please add entries to faq.md.", 'score': 0.0, 'index': None}

        q_vec = self.vectorizer.transform([q])
        sims = (self.tfidf @ q_vec.T).toarray().ravel()
        best_idx = int(np.argmax(sims))
        best_score = float(sims[best_idx])

        if best_score < self.threshold:
            return {'answer': "I couldn't find a confident answer. Can you rephrase or give more details?",
                    'score': best_score, 'index': None}

        return {'answer': self.answers[best_idx], 'score': best_score, 'index': best_idx}


if __name__ == '__main__':
    a = Answerer()
    for q in ["How do I set up Twilio?", "hello", "what is supported"]:
        print(q, '=>', a.answer(q))
