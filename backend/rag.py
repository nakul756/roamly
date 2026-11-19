"""Retrieval for the chat assistant (the R in RAG). Every destination and every place becomes a short text passage;
a TF-IDF index (scikit-learn, no extra install, works offline) finds the passages closest to the user's question, and
chat.py hands them to the language model as the only facts it may use. Open questions such as "quiet village with good
hiking" or "where can I see the northern lights" then get answers grounded in the dataset instead of the model's memory."""
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer


class Retriever:
    def __init__(self, df, places_df):
        self.docs, self.meta = [], []
        for d, g in df.groupby("destination", sort=True):
            r = g.iloc[0]
            text = (f"{d}, {r['country']}. {r['description']} Highlights: {str(r['highlights']).replace(';', ', ')}. "
                    f"Best months: {str(r['best_months']).replace(';', ', ')}. Food: {str(r['must_try_food']).replace(';', ', ')}. "
                    f"Crowds: {r['crowd_level']}. Trip type: {r['trip_type']}. Getting around: {r['getting_around']}. Tip: {r['travel_tip']}.")
            self.docs.append(text); self.meta.append({"destination": d, "kind": "destination"})
        for r in places_df.itertuples():
            self.docs.append(f"{r.name} in {r.destination}, a {r.kind}."); self.meta.append({"destination": r.destination, "kind": "place"})
        self.vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
        self.matrix = self.vec.fit_transform(self.docs)

    def search(self, query, k=4, destination=None, min_score=0.08):
        """Top-k passages for the query, best first, as dicts with destination, kind, text and score. A destination
        restricts the search to that city. Returns [] when nothing is close enough."""
        scores = (self.matrix @ self.vec.transform([query]).T).toarray().ravel()
        if destination:
            scores = scores * np.array([m["destination"] == destination for m in self.meta])
        out = []
        for i in np.argsort(-scores)[:k]:
            if scores[i] >= min_score:
                out.append({**self.meta[i], "text": self.docs[i], "score": round(float(scores[i]), 3)})
        return out
