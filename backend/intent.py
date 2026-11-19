"""Intent classifier for the chatbot: TF-IDF + logistic regression, trained on templated utterances.
Run `python intent.py` to retrain. It also trains itself on first start if models/intent.joblib is missing."""
import random
from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline

PATH = Path(__file__).resolve().parent.parent / "models" / "intent.joblib"
DESTS = ["Rome", "Paris", "Lisbon", "Prague", "Santorini", "Zermatt", "Nice", "Berlin", "Vienna", "Reykjavik"]
T = {
 "greet": ["hi", "hello", "hey there", "good morning", "hi can you help me", "hello who are you", "hey", "good evening", "what can you do"],
 "trip": ["i want a beach holiday in june", "looking for something cheap", "we are a family of 4", "find me a romantic place for our honeymoon",
          "somewhere with mountains and snow", "i have a budget of 1500 euros", "what do you recommend for summer", "suggest a city break",
          "can you suggest some destinations", "i prefer quiet places", "make it more luxurious", "change it to july", "actually make it {days} days",
          "i want to travel in december", "we want a relaxed trip", "show me other options", "i would like a cultural trip", "recommend somewhere for friends"],
 "info": ["what is the weather like in {d}", "tell me about {d}", "what food should i try in {d}", "what language do they speak in {d}",
          "which currency is used in {d}", "how do i get around in {d}", "any tips for {d}", "is {d} crowded", "do i need a schengen visa for {d}",
          "what is the nearest airport to {d}", "how expensive is {d}", "what is special about {d}"],
 "plan": ["plan my itinerary", "give me a day by day plan", "show me the itinerary for {d}", "what should i do each day", "create a plan for {d}",
          "can you plan the trip", "show it on the map", "build an itinerary", "plan {d} for me"],
 "memory": ["what do you remember about me", "what did i tell you", "what are my preferences", "remind me what i asked for",
            "do you remember my budget", "what have i said so far", "what do you know about my trip"],
 "forget": ["forget everything", "start over", "reset", "clear my preferences", "new trip", "let us start again", "forget what i said"],
 "thanks": ["thanks", "thank you so much", "great thanks", "bye", "goodbye", "that is all thanks", "cheers", "perfect thank you"],
}
PRE = ["", "", "please ", "hey, ", "can you ", "i would like to know ", "quick question: "]
POST = ["", "", " please", " thanks", "?"]


def build(split):
    """Every 5th template is held out for testing, so the test sentences are unseen wordings."""
    rnd, X, y = random.Random(0), [], []
    for label, temps in T.items():
        for i, t in enumerate(temps):
            if (i % 5 == 4) != (split == "test"):
                continue
            for _ in range(8):
                X.append(rnd.choice(PRE) + t.format(d=rnd.choice(DESTS), days=rnd.randint(2, 9)) + rnd.choice(POST))
                y.append(label)
    return X, y


def fit(X, y):
    return make_pipeline(TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True), LogisticRegression(max_iter=1000, C=10)).fit(X, y)


def train():
    (Xa, ya), (Xb, yb) = build("train"), build("test")
    acc = fit(Xa, ya).score(Xb, yb)
    print(f"Intent classifier: {acc:.0%} accuracy on unseen sentence templates ({len(Xa)} train / {len(Xb)} test)")
    PATH.parent.mkdir(exist_ok=True)
    joblib.dump({"model": fit(Xa + Xb, ya + yb), "accuracy": acc}, PATH)


_bundle = None


def predict(text):
    """Returns (intent, confidence). Low confidence returns 'fallback'."""
    global _bundle
    if _bundle is None:
        if not PATH.exists():
            train()
        _bundle = joblib.load(PATH)
    p = _bundle["model"].predict_proba([text.lower()])[0]
    i = int(p.argmax())
    return (_bundle["model"].classes_[i], float(p[i])) if p[i] >= 0.3 else ("fallback", float(p[i]))


if __name__ == "__main__":
    train()
