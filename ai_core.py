"""
ai_core.py

Lightweight answer engine using TF-IDF similarity over `faq.yml`.
Provides a small wrapper `AnswerEngine` used by the webhook server. Keeps the
original `Answerer` for unit tests and simple offline use.
"""
from pathlib import Path
import os
import re
import json
from typing import List, Optional

import yaml
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

try:
    import openai
except Exception:
    openai = None


class Answerer:
    """TF-IDF based FAQ answerer.

    Keeps a vector store of questions and returns the most similar answer.
    """

    def __init__(self, kb_path: Optional[str] = None, threshold: float = 0.2):
        # Expect YAML `faq.yml` by default with structure: faq: - q: ... - a: ...
        self.kb_path = Path(kb_path) if kb_path else Path(__file__).parent / "faq.yml"
        self.threshold = float(threshold)
        self.questions: List[str] = []
        self.answers: List[str] = []
        self.vectorizer: Optional[TfidfVectorizer] = None
        self.tfidf = None
        self._load_faq()

    def _load_faq(self):
        p = Path(self.kb_path)
        if not p.exists():
            return

        if p.suffix.lower() in (".yml", ".yaml"):
            data = yaml.safe_load(p.read_text(encoding="utf-8"))
            items = data.get("faq") if isinstance(data, dict) else None
            if items:
                for item in items:
                    q = item.get("q")
                    a = item.get("a")
                    if q and a:
                        self.questions.append(str(q).strip())
                        self.answers.append(str(a).strip())
        else:
            txt = p.read_text(encoding="utf-8")
            blocks = [b.strip() for b in re.split(r"\n\s*\n", txt) if b.strip()]
            for block in blocks:
                lines = [l.strip() for l in block.splitlines() if l.strip()]
                if not lines:
                    continue
                q = lines[0]
                q = re.sub(r"^#+\s*", "", q)
                q = re.sub(r"^Q:\s*", "", q)
                q = q.strip()
                a = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""
                if q and a:
                    self.questions.append(q)
                    self.answers.append(a)

        if self.questions:
            self.vectorizer = TfidfVectorizer().fit(self.questions)
            self.tfidf = self.vectorizer.transform(self.questions)

    def answer(self, query: str) -> dict:
        """Return dict: {answer:str, score:float, index:int|None}.

        Keeps the original contract for tests and callers that want the score.
        """
        q = (query or "").strip()
        if not q:
            return {"answer": "I didn't get a message — please type your question.", "score": 0.0, "index": None}

        if q.lower() in ("hi", "hello", "hey", "good morning", "good evening"):
            return {"answer": "Hello — tell me what you need help with or ask a question.", "score": 1.0, "index": None}

        if not self.questions:
            return {"answer": "I don't have any FAQ loaded yet. Please add entries to faq.yml.", "score": 0.0, "index": None}

        q_vec = self.vectorizer.transform([q])
        sims = (self.tfidf @ q_vec.T).toarray().ravel()
        best_idx = int(np.argmax(sims))
        best_score = float(sims[best_idx])

        if best_score < self.threshold:
            return {"answer": "I couldn't find a confident answer. Can you rephrase or give more details?", "score": best_score, "index": None}

        return {"answer": self.answers[best_idx], "score": best_score, "index": best_idx}


class AnswerEngine:
    """Higher-level engine used by the webhook server.

    Provides a simple `answer(user_text, memory)` method which returns a text
    reply. If OpenAI is available and configured it may be used as a fallback
    for low-confidence TF-IDF replies.
    """

    def __init__(self, redis_client=None, kb_path: Optional[str] = None, use_llm: bool = False):
        self.redis = redis_client
        self.answerer = Answerer(kb_path=kb_path)
        self.use_llm = use_llm and (openai is not None)

        # configure openai if api key present
        if self.use_llm:
            api_key = os.environ.get("OPENAI_API_KEY")
            if api_key:
                openai.api_key = api_key
            else:
                self.use_llm = False

    def _call_llm(self, prompt: str) -> str:
        if openai is None:
            return ""
        try:
            resp = openai.ChatCompletion.create(
                model=os.environ.get("OPENAI_MODEL", "gpt-3.5-turbo"),
                messages=[{"role": "user", "content": prompt}],
                max_tokens=256,
                temperature=0.2,
            )
            return resp.choices[0].message.content.strip()
        except Exception:
            return ""

    def answer(self, user_text: str, memory: Optional[List[dict]] = None) -> str:
        # memory: list of {role, text, ts}
        mem_text = "\n".join([f"{m.get('role')}: {m.get('text')}" if isinstance(m, dict) else str(m) for m in (memory or [])])
        qa = self.answerer.answer(user_text)
        if qa.get("score", 0.0) >= self.answerer.threshold:
            return qa.get("answer")

        # low confidence — use LLM if enabled
        if self.use_llm:
            prompt = f"User: {user_text}\nContext:\n{mem_text}\nProvide a helpful, concise answer."
            llm_reply = self._call_llm(prompt)
            if llm_reply:
                return llm_reply

        # final fallback
        return qa.get("answer")


if __name__ == "__main__":
    ae = Answerer()
    for q in ["How do I set up Twilio?", "hello", "what is supported"]:
        print(q, "=>", ae.answer(q))
