import pandas as pd
import joblib
from collections import Counter
from sqlalchemy import text
import csv
from app.database.database import SessionLocal
from pathlib import Path
from datetime import datetime

# =========================
# Ustawienia
# =========================

START_BANKROLL = 1000

STAKE_PERCENT = 0.01

MIN_EV = 0.12

MIN_EV_VALUES = [
    0.05,
    0.08,
    0.10,
    0.12,
    0.15,
    0.18,
    0.20
]

EDGE_VALUES = [
    0.02,
    0.04,
    0.05,
    0.06,
    0.08
]

CONFIDENCE_VALUES = [
    0.40,
    0.45,
    0.50,
    0.55,
    0.60
]

MIN_ODDS_VALUES = [
    1.20,
    1.30,
    1.50
]

MAX_ODDS_VALUES = [
    3,
    4,
    5,
    6
]

STAKE_VALUES = [
    0.005,
    0.01,
    0.02
]

# =========================
# Pobranie danych testowych
# =========================

def main():
    print("=== BACKTEST_STARTED ===", flush=True)
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


    WHERE date >= '2023-08-01'


    ORDER BY date
    """


    df = pd.read_sql(
        text(query),
        db.bind
    )


    db.close()

    # =========================
    # Cechy różnicowe
    # =========================

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


    # =========================
    # Model
    # =========================

    model = joblib.load(
        "football_model_time_odds.pkl"
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


    X = df[features]


    probabilities = model.predict_proba(X)

    import numpy as np

    classes = model.classes_

    def run_backtest(
        df,
        probabilities,
        classes,
        min_ev,
        min_edge,
        min_confidence,
        min_odds,
        max_odds,
        stake_percent
    ):
        
        # =========================
        # Statystyki EV
        # =========================

        roi_ranges = {
            "1-2": {"bets":0,"wins":0},
            "2-3": {"bets":0,"wins":0},
            "3-5": {"bets":0,"wins":0},
            "5+": {"bets":0,"wins":0},
        }

        ev_ranges = {
            "5-10%": {"bets": 0, "wins": 0},
            "10-20%": {"bets": 0, "wins": 0},
            "20%+": {"bets": 0, "wins": 0}
        }



        ev_values = []
        odds_values = []
        predicted_values = []

        actual_values = []
        edges = []

        # =========================
        # Bankroll
        # =========================

        bankroll = START_BANKROLL

        bets = 0
        wins = 0
        losses = 0

        gross_profit = 0
        gross_loss = 0

        peak = START_BANKROLL
        max_drawdown = 0

        draw_bets = 0



        # =========================
        # Symulacja zakładów
        # =========================

        for index, row in df.iterrows():


            probs = dict(
                zip(
                    classes,
                    probabilities[index]
                )
            )


            odds = {

                "H": row.home_odds,
                "D": row.draw_odds,
                "A": row.away_odds

            }

            book = {
                "H": row.home_implied_prob,
                "D": row.draw_implied_prob,
                "A": row.away_implied_prob
            }

            # =====================
            # Obliczenie EV
            # =====================

            values = {}
            edge = {}

            for outcome in ["H","D","A"]:

                values[outcome] = (
                    probs[outcome]
                    * odds[outcome]
                ) - 1

                edge[outcome] = (
                    probs[outcome]
                    -
                    book[outcome]
                )


            
            best = max(edge, key=edge.get)        

            ev = values[best]

            if edge[best] < min_edge:
                continue

            if ev < min_ev:
                continue

            confidence = probs[best]

            # brak wartości
            if confidence < min_confidence:
                continue

            if odds[best] > max_odds:
                continue

            if odds[best] < min_odds:
                continue

            if best == "D" and probs["D"] < 0.35:
                continue

            if best == "D":
                draw_bets += 1

            bets += 1

            ev_values.append(ev)

            odds_values.append(
                odds[best]
            )

            predicted_values.append(
                probs[best]
            )

            actual_values.append(
                1 if best == row.result else 0
            )

            edges.append(
                edge[best]
            )

            stake = bankroll * stake_percent



            # =====================
            # Wynik zakładu
            # =====================

            won = False


            if best == row.result:

                won = True
                wins += 1

                profit = stake * (odds[best] - 1)

                gross_profit += profit

                bankroll += profit

            else:

                losses += 1

                gross_loss += stake

                bankroll -= stake

            peak = max(peak, bankroll)

            drawdown = (peak - bankroll) / peak

            max_drawdown = max(max_drawdown, drawdown)

            o = odds[best]

            if o < 2:
                key = "1-2"

            elif o < 3:
                key = "2-3"

            elif o < 5:
                key = "3-5"

            else:
                key = "5+"

            roi_ranges[key]["bets"] += 1

            if won:
                roi_ranges[key]["wins"] += 1



            # =====================
            # Statystyki EV
            # =====================

            if 0.05 <= ev < 0.10:

                ev_ranges["5-10%"]["bets"] += 1

                if won:
                    ev_ranges["5-10%"]["wins"] += 1



            elif 0.10 <= ev < 0.20:

                ev_ranges["10-20%"]["bets"] += 1

                if won:
                    ev_ranges["10-20%"]["wins"] += 1



            elif ev >= 0.20:

                ev_ranges["20%+"]["bets"] += 1

                if won:
                    ev_ranges["20%+"]["wins"] += 1



        roi = (
            (bankroll - START_BANKROLL)
            /
            START_BANKROLL
        ) * 100

        # =========================
        # CSV z historią zakładów
        # =========================

        return {
            "bets": bets,
            "wins": wins,
            "losses": losses,
            "bankroll": bankroll,
            "roi": roi,

            "hit_rate": wins / bets if bets else 0,

            "avg_ev": np.mean(ev_values) if ev_values else 0,

            "avg_edge": np.mean(edges) if edges else 0,

            "avg_confidence": np.mean(predicted_values) if predicted_values else 0,

            "avg_odds": np.mean(odds_values) if odds_values else 0,

            "draw_bets": draw_bets,

            "profit_factor": round(
                gross_profit / gross_loss,
                2
            ) if gross_loss else 999,

            "max_drawdown": round(
        max_drawdown * 100,
        2
    )
    }

    results = []

    total_tests = (
        len(MIN_EV_VALUES)
        * len(EDGE_VALUES)
        * len(CONFIDENCE_VALUES)
        * len(MIN_ODDS_VALUES)
        * len(MAX_ODDS_VALUES)
        * len(STAKE_VALUES)
    )

    current_test = 0

    for min_ev in MIN_EV_VALUES:
        for min_edge in EDGE_VALUES:
            for confidence in CONFIDENCE_VALUES:
                for min_odds in MIN_ODDS_VALUES:
                    for max_odds in MAX_ODDS_VALUES:
                        for stake in STAKE_VALUES:

                            if min_odds >= max_odds:
                                continue

                            current_test += 1

                            if current_test % 50 == 0 or current_test == 1:
                                print(
                                    f"=== BACKTEST {current_test}/{total_tests} ===",
                                    flush=True
                                )

                            result = run_backtest(
                                df=df,
                                probabilities=probabilities,
                                classes=classes,
                                min_ev=min_ev,
                                min_edge=min_edge,
                                min_confidence=confidence,
                                min_odds=min_odds,
                                max_odds=max_odds,
                                stake_percent=stake
                            )

                            result.update({
                                "min_ev": min_ev,
                                "min_edge": min_edge,
                                "confidence": confidence,
                                "min_odds": min_odds,
                                "max_odds": max_odds,
                                "stake": stake
                            })

                            results.append(result)

    results_df = pd.DataFrame(results)

    results_df = results_df[
        results_df["bets"] >= 150
    ]

    results_df = results_df[
        results_df["roi"] > 0
    ]

    results_df = results_df.sort_values(
        by=[
            "roi",
            "max_drawdown",
            "profit_factor",
            "bets"
        ],

        ascending=[
            False,
            True,   # mniejszy drawdown jest lepszy
            False,
            False
        ]
    )

    print(
        results_df[
            [
                "roi",
                "bankroll",
                "bets",
                "hit_rate",
                "profit_factor",
                "max_drawdown",
                "avg_ev",
                "avg_edge",
                "avg_confidence",
                "avg_odds",
                "draw_bets",
                "min_ev",
                "min_edge",
                "confidence",
                "min_odds",
                "max_odds",
                "stake"
            ]
        ].head(20)
    )

    history_dir = Path("history")
    history_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")

    latest_file = Path("parameter_search.csv")

    history_file = history_dir / f"parameter_search_{timestamp}.csv"

    results_df.to_csv(
        latest_file,
        index=False,
        sep=";",
        decimal=",",
        encoding="utf-8-sig"
    )

    results_df.to_csv(
        history_file,
        index=False,
        sep=";",
        decimal=",",
        encoding="utf-8-sig"
    )

    print("\n=== BACKTEST_FINISHED ===", flush=True)

if __name__ == "__main__":
    main()