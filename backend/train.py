"""Trains the destination ranker.  Run:  python train.py

Why simulated data? The CSV has only 43 rows and no record of what travellers liked, so it cannot be
used to train a model directly. Instead we simulate many travellers (random trip type, budget, month,
length, plus hidden tastes such as crowd aversion), score every destination/hotel for each of them,
and label the pair 1 ("good match") or 0. A gradient-boosted model then learns to predict that label
from the pair's features.  The hidden tastes and random noise mean the model cannot just memorise a rule.

Real data: every thumbs-up/down in the app is stored with the trip it was about (type, budget, month, days).
`python train.py` blends those rows into the training set (weighted FEEDBACK_WEIGHT times a simulated row) once at
least MIN_FEEDBACK of them exist. `python train.py --no-feedback` trains on simulation only."""
import json
import sqlite3
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupShuffleSplit

import ranker
from config import DB_DIR

SEED = 42
N_USERS = 3000
LABEL_THRESHOLD = 2.5   # utility above this = good match (about 10% of pairs)
FEEDBACK_WEIGHT = 25    # one real thumbs-up/down counts as this many simulated rows
MIN_FEEDBACK = 20       # below this, feedback is ignored (too little to learn from)


def real_feedback(df: pd.DataFrame) -> pd.DataFrame:
    """Feature rows built from stored thumbs-up/down that include their trip context (empty if none)."""
    path = DB_DIR / "chat.db"
    if not path.exists():
        return pd.DataFrame()
    con = sqlite3.connect(path)
    try:
        rows = con.execute("SELECT destination, hotel, liked, trip_type, budget, month, days FROM feedback "
                           "WHERE trip_type IS NOT NULL AND month IS NOT NULL AND budget IS NOT NULL AND days IS NOT NULL").fetchall()
    except sqlite3.OperationalError:
        return pd.DataFrame()
    finally:
        con.close()
    parts = []
    for dest, hotel, liked, t, b, m, d in rows:
        match = df[(df["destination"] == dest) & (df["hotel_name"] == hotel)]
        if match.empty:
            continue
        f = ranker.build_features(t, int(b), int(m), int(d), match)
        f["y"] = int(liked)
        parts.append(f)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def simulate(df: pd.DataFrame, n_users: int, rng: np.random.Generator) -> pd.DataFrame:
    types = sorted(df["trip_type"].unique())
    parts = []
    for uid in range(n_users):
        t = str(rng.choice(types))
        budget, month, days = int(rng.integers(1, 4)), int(rng.integers(1, 13)), int(rng.integers(1, 22))
        # hidden tastes (not given to the model)
        crowd_aversion = rng.uniform(0, 1)
        activity_pref = int(rng.integers(1, 4))
        f = ranker.build_features(t, budget, month, days, df)
        over = f["budget_diff"].to_numpy()
        utility = (
            5.0 * f["type_match"] + 1.5 * f["in_season"] - 0.25 * f["month_dist"]
            - np.where(over > 0, 1.8, 0.6) * np.abs(over)          # too expensive hurts more than too cheap
            + 1.0 * (f["rating"] - 4.6)
            - 0.8 * crowd_aversion * f["crowd_high"]
            - 0.4 * np.abs(f["activity"] - activity_pref)
            - 0.15 * np.abs(f["days_diff"])
            + rng.normal(0, 0.6, len(df))                           # unexplained human randomness
        )
        f["y"] = (utility > LABEL_THRESHOLD).astype(int)
        f["uid"] = uid
        f["destination"] = df["destination"].to_numpy()
        f["row"] = np.arange(len(df))
        f["q_type"], f["q_budget"], f["q_month"] = t, budget, month
        parts.append(f)
    return pd.concat(parts, ignore_index=True)


def new_model() -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(max_depth=4, learning_rate=0.1, max_iter=200,
                                          l2_regularization=1.0, random_state=SEED)


def precision_at_k(data: pd.DataFrame, scores: np.ndarray, k: int = 3) -> float:
    """Share of the top-k results (per traveller) that are good matches, averaged over travellers."""
    d = data.assign(_s=scores).sort_values(["uid", "_s"], ascending=[True, False])
    return float(d.groupby("uid").head(k).groupby("uid")["y"].mean().mean())


def knn_baseline_scores(data: pd.DataFrame, df: pd.DataFrame) -> np.ndarray:
    """The old hand-weighted KNN, as a baseline to beat (higher = closer)."""
    types = sorted(df["trip_type"].unique())

    def enc(t, b, s):
        a = 2 * np.pi * s / 4
        return np.array([2.0 if t == x else 0.0 for x in types] + [(b - 1) / 2 * 1.5, np.sin(a), np.cos(a)])

    X = np.array([enc(r.trip_type, r.budget_level, r.best_season) for r in df.itertuples()])
    out = np.zeros(len(data))
    for uid, idx in data.groupby("uid").indices.items():
        r = data.iloc[idx[0]]
        q = enc(r["q_type"], r["q_budget"], ranker.season_of(int(r["q_month"])))
        out[idx] = -np.linalg.norm(X[data["row"].to_numpy()[idx]] - q, axis=1)
    return out


def evaluate(train_df, test_df, df, label):
    m = new_model().fit(train_df[ranker.FEATURES], train_df["y"])
    s = m.predict_proba(test_df[ranker.FEATURES])[:, 1]
    res = {"auc": round(float(roc_auc_score(test_df["y"], s)), 3),
           "precision_at_3": round(precision_at_k(test_df, s), 3),
           "knn_baseline_precision_at_3": round(precision_at_k(test_df, knn_baseline_scores(test_df, df)), 3)}
    print(f"{label:<34} AUC {res['auc']:.3f} | P@3 model {res['precision_at_3']:.3f} "
          f"vs old KNN {res['knn_baseline_precision_at_3']:.3f}")
    return res


def main(use_feedback: bool = True):
    import seed
    df = seed.load_destinations()   # CSV plus the extra hotels added in v6, same rows the server uses
    rng = np.random.default_rng(SEED)
    data = simulate(df, N_USERS, rng)
    print(f"{len(data):,} training pairs from {N_USERS} simulated travellers; "
          f"{data['y'].mean():.1%} labelled good match")

    metrics = {}
    # 1) new travellers, destinations already seen
    tr, te = next(GroupShuffleSplit(1, test_size=0.2, random_state=SEED).split(data, groups=data["uid"]))
    metrics["held_out_travellers"] = evaluate(data.iloc[tr], data.iloc[te], df, "Held-out travellers")
    # 2) destinations the model has never seen (harder: tests that it learned patterns, not names)
    tr, te = next(GroupShuffleSplit(1, test_size=0.2, random_state=SEED).split(data, groups=data["destination"]))
    metrics["held_out_destinations"] = evaluate(data.iloc[tr], data.iloc[te], df, "Held-out destinations")

    # final model: train on everything (plus real feedback when there is enough of it)
    fb = real_feedback(df) if use_feedback else pd.DataFrame()
    n_fb = len(fb) if len(fb) >= MIN_FEEDBACK else 0
    X, y, w = data[ranker.FEATURES], data["y"], np.ones(len(data))
    if n_fb:
        X = pd.concat([X, fb[ranker.FEATURES]], ignore_index=True)
        y = pd.concat([y, fb["y"]], ignore_index=True)
        w = np.concatenate([w, np.full(n_fb, float(FEEDBACK_WEIGHT))])
        print(f"Blended in {n_fb} real feedback rows (weight {FEEDBACK_WEIGHT}x)")
    elif use_feedback:
        print(f"Only {len(fb)} usable feedback rows (need {MIN_FEEDBACK}); trained on simulation only")
    metrics["trained_on_feedback_rows"] = n_fb
    model = new_model().fit(X, y, sample_weight=w)
    ranker.MODEL_PATH.parent.mkdir(exist_ok=True)
    joblib.dump({"model": model, "features": ranker.FEATURES, "metrics": metrics,
                 "n_pairs": len(data), "n_users": N_USERS}, ranker.MODEL_PATH)
    (ranker.MODEL_PATH.parent / "metrics.json").write_text(json.dumps(metrics, indent=2))
    print(f"Saved {ranker.MODEL_PATH}")


if __name__ == "__main__":
    main(use_feedback="--no-feedback" not in sys.argv)
