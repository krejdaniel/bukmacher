import pandas as pd

from sqlalchemy import text
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import accuracy_score, classification_report
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import brier_score_loss

import joblib


from app.database.database import SessionLocal


db = SessionLocal()


query = """
SELECT
    date,
    home_team,
    away_team,

    home_points,
    home_avg_goals,
    home_avg_conceded,

    home_avg_xg,
    home_avg_xga,

    home_goal_difference,
    home_points_per_match,
    home_clean_sheet_rate,
    home_failed_to_score_rate,

    away_points,
    away_avg_goals,
    away_avg_conceded,
    
    away_avg_xg,
    away_avg_xga,

    home_attack_rating,
    home_defense_rating,

    away_attack_rating,
    away_defense_rating,

    away_goal_difference,
    away_points_per_match,
    away_clean_sheet_rate,
    away_failed_to_score_rate,

    home_odds,
    draw_odds,
    away_odds,

    home_implied_prob,
    draw_implied_prob,
    away_implied_prob,

    home_all_points,
    home_all_avg_goals,
    home_all_avg_conceded,

    away_all_points,
    away_all_avg_goals,
    away_all_avg_conceded,

    home_last3_points,
    away_last3_points,

    home_last3_avg_goals,
    away_last3_avg_goals,

    home_elo,
    away_elo,
    elo_diff,

    result

FROM training_matches
"""


df = pd.read_sql(
    text(query),
    db.bind
)


db.close()


df["date"] = pd.to_datetime(df["date"])

# różnice pomiędzy drużynami

df["points_diff"] = (
    df["home_points"] -
    df["away_points"]
)

df["avg_goals_diff"] = (
    df["home_avg_goals"] -
    df["away_avg_goals"]
)

df["avg_conceded_diff"] = (
    df["home_avg_conceded"] -
    df["away_avg_conceded"]
)

df["xg_diff"] = (
    df["home_avg_xg"] -
    df["away_avg_xg"]
)

df["xga_diff"] = (
    df["home_avg_xga"] -
    df["away_avg_xga"]
)

df["goal_difference_diff"] = (
    df["home_goal_difference"] -
    df["away_goal_difference"]
)

df["points_per_match_diff"] = (
    df["home_points_per_match"] -
    df["away_points_per_match"]
)

df["clean_sheet_diff"] = (
    df["home_clean_sheet_rate"] -
    df["away_clean_sheet_rate"]
)

df["failed_to_score_diff"] = (
    df["home_failed_to_score_rate"] -
    df["away_failed_to_score_rate"]
)

df["all_points_diff"] = (
    df["home_all_points"] -
    df["away_all_points"]
)


df["all_avg_goals_diff"] = (
    df["home_all_avg_goals"] -
    df["away_all_avg_goals"]
)


df["all_avg_conceded_diff"] = (
    df["home_all_avg_conceded"] -
    df["away_all_avg_conceded"]
)


df["last3_points_diff"] = (
    df["home_last3_points"] -
    df["away_last3_points"]
)


df["last3_goals_diff"] = (
    df["home_last3_avg_goals"] -
    df["away_last3_avg_goals"]
)

df["attack_rating_diff"] = (
    df["home_attack_rating"] -
    df["away_attack_rating"]
)

df["defense_rating_diff"] = (
    df["home_defense_rating"] -
    df["away_defense_rating"]
)

train_df = df[
    df["date"] < "2023-08-01"
]


test_df = df[
    df["date"] >= "2023-08-01"
]


print(
    "TRAIN:",
    len(train_df)
)


print(
    "TEST:",
    len(test_df)
)


print(
    "Liczba rekordów:",
    len(df)
)



features = [

    "points_diff",

    "avg_goals_diff",

    "avg_conceded_diff",
    
    "xg_diff",

    "xga_diff",

    "goal_difference_diff",

    "points_per_match_diff",

    "clean_sheet_diff",

    "failed_to_score_diff",

    "all_points_diff",

    "all_avg_goals_diff",

    "all_avg_conceded_diff",

    "last3_points_diff",

    "last3_goals_diff",

    "home_elo",

    "away_elo",

    "elo_diff",

    "attack_rating_diff",

    "defense_rating_diff",

    "home_implied_prob",

    "draw_implied_prob",

    "away_implied_prob"

]



X_train = train_df[features]

y_train = train_df["result"]



X_test = test_df[features]

y_test = test_df["result"]


base_model = HistGradientBoostingClassifier(
    learning_rate=0.05,
    max_iter=400,
    max_depth=5,
    min_samples_leaf=30,
    l2_regularization=1,
    random_state=42
)


model = CalibratedClassifierCV(
    base_model,
    method="isotonic",
    cv=3
)


model.fit(
    X_train,
    y_train
)


predictions = model.predict(
    X_test
)



print(
    "Accuracy:",
    accuracy_score(
        y_test,
        predictions
    )
)


print(
    classification_report(
        y_test,
        predictions
    )
)

print()

print("Brier scores")

probs = model.predict_proba(X_test)

for i, cls in enumerate(model.classes_):

    score = brier_score_loss(
        (y_test == cls).astype(int),
        probs[:, i]
    )

    print(cls, round(score, 4))

joblib.dump(
    model,
    "football_model_time_odds.pkl"
)


print(
    "Model zapisany"
)

from sklearn.inspection import permutation_importance


print("\nFeature importance")


result = permutation_importance(
    model,
    X_test,
    y_test,
    n_repeats=20,
    random_state=42,
    scoring="neg_log_loss"
)


importance_df = pd.DataFrame({

    "feature": features,

    "importance": result.importances_mean

})


importance_df = importance_df.sort_values(
    "importance",
    ascending=False
)


print(
    importance_df
)