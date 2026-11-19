"""Feature building and model loading for the trained destination ranker.
Used by train.py (to train) and main.py (to serve). No web dependencies, so it is easy to test."""
import joblib
import numpy as np
import pandas as pd

from config import CSV, MODELS

MODEL_PATH = MODELS / "ranker.joblib"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

FEATURES = [
    "type_match", "in_season", "month_dist", "season_dist",
    "user_budget", "row_budget", "budget_diff",
    "days", "rec_days", "days_diff", "trip_cost",
    "hotel_price", "cost_per_day", "avg_temp", "crowd_high", "activity", "rating",
]


def season_of(month: int) -> int:
    """1 = winter, 2 = spring, 3 = summer, 4 = autumn (same codes as the dataset)."""
    return {12: 1, 1: 1, 2: 1, 3: 2, 4: 2, 5: 2, 6: 3, 7: 3, 8: 3}.get(month, 4)


def _circ(a, b, period):
    d = np.abs(np.asarray(a) - np.asarray(b)) % period
    return np.minimum(d, period - d)


def build_features(trip_type: str, budget: int, month: int, days: int, rows: pd.DataFrame) -> pd.DataFrame:
    """One feature row per (trip query, destination/hotel row) pair."""
    best = [[MONTHS.index(m) + 1 for m in s.split(";") if m in MONTHS] for s in rows["best_months"]]
    in_season = np.array([month in b for b in best], dtype=int)
    month_dist = np.array([min(_circ(month, m, 12) for m in b) if b else 6 for b in best], dtype=float)
    rec = rows["recommended_days"].to_numpy(dtype=float)
    cost = rows["cost_per_day_total_eur"].to_numpy(dtype=float)
    row_budget = rows["budget_level"].to_numpy(dtype=float)
    return pd.DataFrame({
        "type_match": (rows["trip_type"].to_numpy() == trip_type).astype(int),
        "in_season": in_season,
        "month_dist": month_dist,
        "season_dist": _circ(season_of(month), rows["best_season"].to_numpy(), 4),
        "user_budget": float(budget),
        "row_budget": row_budget,
        "budget_diff": row_budget - budget,          # > 0 means the option is pricier than the user wants
        "days": float(days),
        "rec_days": rec,
        "days_diff": days - rec,
        "trip_cost": cost * days,
        "hotel_price": rows["hotel_price_eur"].to_numpy(dtype=float),
        "cost_per_day": cost,
        "avg_temp": rows["avg_temp_c"].to_numpy(dtype=float),
        "crowd_high": (rows["crowd_level"].to_numpy() == "high").astype(int),
        "activity": rows["activity_level"].to_numpy(dtype=float),
        "rating": rows["rating"].to_numpy(dtype=float),
    })[FEATURES]


def load(auto_train: bool = True) -> dict:
    """Load the trained model bundle; train it first if it does not exist yet."""
    if not MODEL_PATH.exists():
        if not auto_train:
            raise FileNotFoundError("No trained model found. Run: python train.py")
        import train          # lazy import avoids a circular import
        train.main()
    return joblib.load(MODEL_PATH)


def score(bundle: dict, trip_type: str, budget: int, month: int, days: int, rows: pd.DataFrame) -> np.ndarray:
    """Probability (0-1) that each row is a good match for the trip."""
    feats = build_features(trip_type, budget, month, days, rows)
    return bundle["model"].predict_proba(feats[bundle["features"]])[:, 1]
