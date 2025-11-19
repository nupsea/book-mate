import math
import re
import pickle
import logging
from pathlib import Path
from collections import Counter

logger = logging.getLogger(__name__)

STOPWORDS = {"the", "a", "an", "and", "of", "in", "to"}


def simple_tokenize(text):
    return [w for w in re.findall(r"\w+", text.lower()) if w not in STOPWORDS]


class BM25Retriever:
    def __init__(self, k1=1.5, b=0.75):
        self.k1 = k1
        self.b = b
        self.docs = []
        self.doc_lens = []
        self.avgdl = 0
        self.df = {}
        self.idf = {}
        self.N = 0
        self.ids = []
        self.raw_docs = []

    def build_index(self, chunks):
        self.docs = []
        self.ids = []
        self.df = {}
        self.raw_docs = []

        for chunk in chunks:
            tokens = simple_tokenize(chunk["text"])
            self.docs.append(tokens)
            self.ids.append(chunk["id"])
            self.raw_docs.append(chunk["text"])

        self.N = len(self.docs)
        self.doc_lens = [len(doc) for doc in self.docs]
        self.avgdl = sum(self.doc_lens) / self.N if self.N > 0 else 0

        for doc in self.docs:
            for word in set(doc):
                self.df[word] = self.df.get(word, 0) + 1

        self.idf = {
            word: math.log((self.N - freq + 0.5) / (freq + 0.5) + 1)
            for word, freq in self.df.items()
        }

    def score(self, query_tokens, idx):
        doc = self.docs[idx]
        doc_len = self.doc_lens[idx]
        freqs = Counter(doc)
        score = 0.0
        for term in query_tokens:
            if term not in freqs:
                continue
            df = freqs[term]
            idf = self.idf.get(term, 0)
            numer = df * (self.k1 + 1)
            denom = df + self.k1 * (1 - self.b + self.b * doc_len / self.avgdl)
            score += idf * (numer / denom)
        return score

    def search(self, query, topk=7, book_slug=None):
        query_tokens = simple_tokenize(query)

        # Filter by book_slug if provided
        if book_slug:
            # Only score documents from the specified book
            valid_indices = [i for i in range(self.N) if self.ids[i].startswith(f"{book_slug}_")]
            scores = [(i, self.score(query_tokens, i)) for i in valid_indices]
        else:
            # Score all documents
            scores = [(i, self.score(query_tokens, i)) for i in range(self.N)]

        ranked = sorted(scores, key=lambda x: -x[1])[:topk]
        return [
            {"id": self.ids[i], "text": self.raw_docs[i], "score": s} for i, s in ranked
        ]

    def id_search(self, query: str, topk=7):
        search_results = self.search(query, topk)
        return [c["id"] for c in search_results]

    def save_index(self, filepath: str = "bm25_index.pkl"):
        """Save BM25 index to disk."""
        index_data = {
            "docs": self.docs,
            "doc_lens": self.doc_lens,
            "avgdl": self.avgdl,
            "df": self.df,
            "idf": self.idf,
            "N": self.N,
            "ids": self.ids,
            "raw_docs": self.raw_docs,
            "k1": self.k1,
            "b": self.b,
        }
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "wb") as f:
            pickle.dump(index_data, f)
        logger.info(f"BM25 index saved to {filepath}")

    def load_index(self, filepath: str = "bm25_index.pkl"):
        """Load BM25 index from disk."""
        if not Path(filepath).exists():
            raise FileNotFoundError(f"BM25 index not found at {filepath}")

        with open(filepath, "rb") as f:
            index_data = pickle.load(f)

        self.docs = index_data["docs"]
        self.doc_lens = index_data["doc_lens"]
        self.avgdl = index_data["avgdl"]
        self.df = index_data["df"]
        self.idf = index_data["idf"]
        self.N = index_data["N"]
        self.ids = index_data["ids"]
        self.raw_docs = index_data["raw_docs"]
        self.k1 = index_data.get("k1", 1.5)
        self.b = index_data.get("b", 0.75)
        logger.info(f"BM25 index loaded from {filepath} ({self.N} documents)")

    def cleanup(self):
        self.docs = []
        self.ids = []
        self.df = {}
        self.idf = {}
        self.doc_lens = []
        self.avgdl = 0
        self.N = 0
        self.raw_docs = []
        logger.info("BM25 index cleared.")
