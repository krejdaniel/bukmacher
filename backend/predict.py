import pandas as pd
import numpy as np
import joblib
from datetime import date, datetime
from sqlalchemy import func
from app.database.database import SessionLocal
from app.services.statistics import get_team_matches, calculate_form
from app.services.team_mapping import TEAM_MAP
from app.services.sinceawin import get_premier_league_elo
from app.superbet import scrape_superbet_premier_league
from app.sts import scrape_sts_premier_league
from app.betclic import scrape_betclic_premier_league
from app.models.match import Match
import os
import re

MIN_EV = 0.05
MIN_EDGE = 0.02
MIN_CONFIDENCE = 0.45
MIN_ODDS = 1.20
MAX_ODDS = 5.0
STAKE_PERCENT = 0.02 

bet_names = {
    "H": "Gospodarz",
    "D": "Remis",
    "A": "Gość"
}

TEAM_ALIASES = {
    # Arsenal
    "Arsenal": "Arsenal",

    # Coventry
    "Coventry": "Coventry City",
    "Coventry City": "Coventry City",

    # Hull
    "Hull": "Hull City",
    "Hull City": "Hull City",

    # Manchester United
    "Manchester Utd": "Manchester United",
    "Manchester United": "Manchester United",

    # Nottingham
    "Nottingham": "Nottingham Forest",
    "Nottingham Forest": "Nottingham Forest",

    # Leeds
    "Leeds": "Leeds United",
    "Leeds United": "Leeds United",

    # Ipswich
    "Ipswich": "Ipswich Town",
    "Ipswich Town": "Ipswich Town",

    # pozostałe
    "Sunderland": "Sunderland",
    "Everton": "Everton",
    "Crystal Palace": "Crystal Palace",
    "Brentford": "Brentford",
    "Tottenham": "Tottenham",
    "Brighton": "Brighton",
    "Aston Villa": "Aston Villa",
    "Manchester City": "Manchester City",
    "Bournemouth": "Bournemouth",
    "Newcastle": "Newcastle",
    "Liverpool": "Liverpool",
    "Fulham": "Fulham",
    "Chelsea": "Chelsea",
}


def normalize_team_name(name):
    if not name:
        return ""

    name = name.strip()

    # najpierw nasze aliasy
    if name in TEAM_ALIASES:
        return TEAM_ALIASES[name]

    # potem istniejący TEAM_MAP
    return TEAM_MAP.get(name, name)


def extract_teams(match_str):
    if not match_str:
        return None, None

    parts = match_str.split(" - ")

    if len(parts) != 2:
        return None, None

    home, away = parts

    home = normalize_team_name(home)
    away = normalize_team_name(away)

    return home, away

def format_bookmaker_odds(bookmakers):
    parts = []

    for bookmaker, odds in bookmakers.items():

        parts.append(
            f"{bookmaker}: "
            f"1:{odds.get('H', 0):.2f} "
            f"X:{odds.get('D', 0):.2f} "
            f"2:{odds.get('A', 0):.2f}"
        )

    return " | ".join(parts)

def format_odds(value):
    return f"{value:.2f}" if value is not None else "BRAK"

def normalize_match_datetime(date_str, time_str=""):
    """
    Normalizuje datę/godzinę z różnych bukmacherów.

    Przykłady:

    Superbet:
        Pt 21. Sie, 21:00-2026

    STS:
        21.08.2026
        21:00

    Betclic:
        Pt. 21/08
        21:00
    """

    # ---------------------------------------------------------
    # Superbet: "Pt 21. Sie, 21:00-2026"
    # ---------------------------------------------------------

    if date_str:

        match = re.search(
            r'(\d{1,2})\.\s*([A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]+),\s*(\d{1,2}):(\d{2})-(\d{4})',
            str(date_str)
        )

        if match:

            day = int(match.group(1))
            month_name = match.group(2).lower()
            hour = match.group(3)
            minute = match.group(4)
            year = int(match.group(5))

            months = {
                "sty": 1,
                "lut": 2,
                "mar": 3,
                "kwi": 4,
                "maj": 5,
                "cze": 6,
                "lip": 7,
                "sie": 8,
                "wrz": 9,
                "paź": 10,
                "lis": 11,
                "gru": 12,
            }

            month = months.get(month_name)

            if month:
                normalized_date = f"{year:04d}-{month:02d}-{day:02d}"
                normalized_time = f"{hour}:{minute}"

                return normalized_date, normalized_time

    # ---------------------------------------------------------
    # STS: "21.08.2026"
    # ---------------------------------------------------------

    if date_str:

        try:
            dt = datetime.strptime(
                str(date_str).strip(),
                "%d.%m.%Y"
            )

            normalized_date = dt.strftime("%Y-%m-%d")

            normalized_time = (
                str(time_str).strip()
                if time_str
                else ""
            )

            return normalized_date, normalized_time

        except ValueError:
            pass

    # ---------------------------------------------------------
    # Betclic: "Pt. 21/08"
    # ---------------------------------------------------------

    if date_str:

        match = re.search(
            r'(\d{1,2})/(\d{1,2})',
            str(date_str)
        )

        if match:

            day = int(match.group(1))
            month = int(match.group(2))

            # tutaj zakładamy aktualny sezon 2026
            year = datetime.now().year

            normalized_date = (
                f"{year:04d}-{month:02d}-{day:02d}"
            )

            normalized_time = (
                str(time_str).strip()
                if time_str
                else ""
            )

            return normalized_date, normalized_time

    # Nie przekazujemy dalej nierozpoznanej daty.
    # Dzięki temu błędny tekst nie zatrzyma całego skryptu.
    return "", str(time_str).strip() if time_str else ""


def match_key(match):
    """
    Klucz do połączenia tego samego meczu
    z różnych bukmacherów.

    NIE używamy daty ani godziny, ponieważ
    każdy bukmacher może zwracać je w innym formacie.

    Klucz:
        gospodarz + gość
    """

    home, away = extract_teams(
        match.get("Mecz", "")
    )

    if not home or not away:
        return None

    home = normalize_team_name(home)
    away = normalize_team_name(away)

    return (
        home.lower().strip(),
        away.lower().strip()
    )


def parse_odds(match):
    """
    Pobiera kursy 1/X/2 z rekordu bukmachera.
    """

    try:
        h = float(str(match.get("1", "0")).replace(",", "."))
        d = float(str(match.get("X", "0")).replace(",", "."))
        a = float(str(match.get("2", "0")).replace(",", "."))

        if h <= 1 or d <= 1 or a <= 1:
            return None

        return {
            "H": h,
            "D": d,
            "A": a
        }

    except (ValueError, TypeError):
        return None
    
TAX_RATE = 0.12


def get_effective_odds(bookmaker, odds):
    """
    Kurs efektywny po uwzględnieniu 12% podatku.

    Superbet i STS:
        kurs * 0.88

    Betclic:
        bez podatku
    """

    if odds is None:
        return None

    if bookmaker in ("Superbet", "STS"):
        return odds * (1 - TAX_RATE)

    return odds

def get_best_bookmaker_odds(bookmakers, outcome):

    best_bookmaker = None
    best_odds = None

    for bookmaker, odds in bookmakers.items():

        if not odds:
            continue

        current_odds = odds.get(outcome)

        if current_odds is None:
            continue

        # kurs efektywny po podatku
        effective_odds = get_effective_odds(
            bookmaker,
            current_odds
        )

        if effective_odds is None:
            continue

        if best_odds is None or effective_odds > best_odds:
            best_odds = effective_odds
            best_bookmaker = bookmaker

    return best_bookmaker, best_odds

def get_raw_bookmaker_odds(bookmakers, bookmaker, outcome):

    odds = bookmakers.get(bookmaker)

    if not odds:
        return None

    return odds.get(outcome)

def build_bookmaker_matches(
    superbet_matches,
    sts_matches,
    betclic_matches
):
    """
    Łączy ten sam mecz z trzech bukmacherów.
    """

    bookmakers = {
        "Superbet": superbet_matches,
        "STS": sts_matches,
        "Betclic": betclic_matches
    }

    combined = {}

    for bookmaker_name, matches in bookmakers.items():

        for match in matches:

            key = match_key(match)

            if not key:
                continue

            odds = parse_odds(match)

            if not odds:
                continue

            if key not in combined:

                home, away = extract_teams(
                    match.get("Mecz", "")
                )

                normalized_date, normalized_time = (
                    normalize_match_datetime(
                        match.get("Data", ""),
                        match.get("Godzina", "")
                    )
                )

                combined[key] = {
                    "home": home,
                    "away": away,
                    "date": normalized_date,
                    "time": normalized_time,
                    "bookmakers": {}
                }

            else:

                normalized_date, normalized_time = (
                    normalize_match_datetime(
                        match.get("Data", ""),
                        match.get("Godzina", "")
                    )
                )

                if not combined[key]["date"] and normalized_date:
                    combined[key]["date"] = normalized_date

                if not combined[key]["time"] and normalized_time:
                    combined[key]["time"] = normalized_time

            combined[key]["bookmakers"][bookmaker_name] = odds

    return combined

def get_league_avg_goals(db):
    avg = db.query(func.avg((Match.home_goals + Match.away_goals) / 2)).scalar()
    return float(avg) if avg else 1.5

def run_results_scraper():
    import subprocess
    import sys

    print("\n=== URUCHAMIAM RESULT SCRAPER ===", flush=True)

    try:
        result = subprocess.run(
            [sys.executable, "results_scraper.py"],
            check=True
        )

        print(
            "\n=== RESULT SCRAPER ZAKOŃCZONY ===",
            flush=True
        )

    except subprocess.CalledProcessError as e:
        print(
            f"\nBŁĄD result_scraper.py: {e}",
            flush=True
        )

def main():
    print("=== PREDICT_STARTED ===", flush=True)
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    print("Pobieranie aktualnych kursów...", flush=True)

    print("-> Superbet", flush=True)
    superbet_matches = scrape_superbet_premier_league()

    print("-> STS", flush=True)
    sts_matches = scrape_sts_premier_league()

    print("-> Betclic", flush=True)
    betclic_matches = scrape_betclic_premier_league()

    print(
        f"Superbet: {len(superbet_matches)}",
        flush=True
    )

    print(
        f"STS:      {len(sts_matches)}",
        flush=True
    )

    print(
        f"Betclic:   {len(betclic_matches)}",
        flush=True
    )

    if not superbet_matches:
        print(
            "Brak meczów z Superbet - "
            "Superbet pozostaje źródłem kursów modelowych.",
            flush=True
        )
        return

    combined_matches = build_bookmaker_matches(
        superbet_matches,
        sts_matches,
        betclic_matches
    )

    print(
        f"Po połączeniu znaleziono "
        f"{len(combined_matches)} unikalnych meczów.",
        flush=True
    )
    model = joblib.load("football_model_time_odds.pkl")

    print("\n=== FEATUREY ZAPISANE W MODELU ===", flush=True)

    if hasattr(model, "feature_names_in_"):
        print(
            list(model.feature_names_in_),
            flush=True
        )
    else:
        print(
            "Model nie posiada feature_names_in_",
            flush=True
        )


    classes = model.classes_
    
    print("Klasy modelu:", classes, flush=True)

    if hasattr(model, "feature_names_in_"):
        print(
            "Cechy modelu:",
            list(model.feature_names_in_),
            flush=True
        )
    
    db = SessionLocal()



    league_avg_goals = get_league_avg_goals(db)
    print(f"Średnia bramek w lidze: {league_avg_goals:.2f}",flush=True)

    elo_list = get_premier_league_elo()
    elo_dict = {item['team']: item['elo'] for item in elo_list}
    DEFAULT_ELO = 1500

    predictions = []
    for match_data in combined_matches.values():
        date_str = match_data["date"]
        time_str = match_data["time"]

        home_team = match_data["home"]
        away_team = match_data["away"]

        # ---------------------------------------------------------
        # SUPERBET = KURSY REFERENCYJNE DLA MODELU
        # ---------------------------------------------------------

        superbet_odds = match_data["bookmakers"].get("Superbet")

        if not superbet_odds:
            print(
                f"Pomijam {home_team} - {away_team} "
                f"- brak kursów Superbet.",
                flush=True
            )
            continue

        home_odds = superbet_odds["H"]
        draw_odds = superbet_odds["D"]
        away_odds = superbet_odds["A"]
        if not home_team or not away_team:
            continue

        try:
            ref_date = datetime.strptime(
                str(date_str).strip(),
                "%Y-%m-%d"
            ).date()
        except (ValueError, TypeError):
            print(
                f"[BŁĘDNA DATA] Pomijam mecz "
                f"{home_team} - {away_team}. "
                f"Otrzymana data: {date_str!r}",
                flush=True
            )
            continue

        home_matches = get_team_matches(db, home_team, ref_date, 5, location="home")
        away_matches = get_team_matches(db, away_team, ref_date, 5, location="away")
        home_all_matches = get_team_matches(db, home_team, ref_date, 5, location="all")
        away_all_matches = get_team_matches(db, away_team, ref_date, 5, location="all")
        home_last3 = get_team_matches(db, home_team, ref_date, 3, location="all")
        away_last3 = get_team_matches(db, away_team, ref_date, 3, location="all")

        home_form = calculate_form(home_matches, home_team)
        away_form = calculate_form(away_matches, away_team)
        home_all_form = calculate_form(home_all_matches, home_team)
        away_all_form = calculate_form(away_all_matches, away_team)
        home_last3_form = calculate_form(home_last3, home_team)
        away_last3_form = calculate_form(away_last3, away_team)

        home_attack_rating = home_form["avg_goals_for"] / league_avg_goals if league_avg_goals else 0
        home_defense_rating = league_avg_goals / max(home_form["avg_goals_against"], 0.1)
        away_attack_rating = away_form["avg_goals_for"] / league_avg_goals if league_avg_goals else 0
        away_defense_rating = league_avg_goals / max(away_form["avg_goals_against"], 0.1)

        ph = 1 / home_odds if home_odds else 0
        prob_draw = 1 / draw_odds if draw_odds else 0
        pa = 1 / away_odds if away_odds else 0
        total = ph + prob_draw + pa
        if total == 0:
            continue
        home_implied = ph / total
        draw_implied = prob_draw / total
        away_implied = pa / total

        home_elo = elo_dict.get(home_team, DEFAULT_ELO)
        away_elo = elo_dict.get(away_team, DEFAULT_ELO)
        elo_diff = home_elo - away_elo

        points_diff = home_form["points"] - away_form["points"]
        avg_goals_diff = home_form["avg_goals_for"] - away_form["avg_goals_for"]
        avg_conceded_diff = home_form["avg_goals_against"] - away_form["avg_goals_against"]
        xg_diff = home_form.get("avg_xg_for", 0) - away_form.get("avg_xg_for", 0)
        xga_diff = home_form.get("avg_xg_against", 0) - away_form.get("avg_xg_against", 0)
        goal_difference_diff = home_form["goal_difference"] - away_form["goal_difference"]
        points_per_match_diff = home_form["points_per_match"] - away_form["points_per_match"]
        clean_sheet_diff = home_form["clean_sheet_rate"] - away_form["clean_sheet_rate"]
        failed_to_score_diff = home_form["failed_to_score_rate"] - away_form["failed_to_score_rate"]
        all_points_diff = home_all_form["points"] - away_all_form["points"]
        all_avg_goals_diff = home_all_form["avg_goals_for"] - away_all_form["avg_goals_for"]
        all_avg_conceded_diff = home_all_form["avg_goals_against"] - away_all_form["avg_goals_against"]
        last3_points_diff = home_last3_form["points"] - away_last3_form["points"]
        last3_goals_diff = home_last3_form["avg_goals_for"] - away_last3_form["avg_goals_for"]
        attack_rating_diff = home_attack_rating - away_attack_rating
        defense_rating_diff = home_defense_rating - away_defense_rating

        feature_dict = {
            "points_diff": points_diff,
            "avg_goals_diff": avg_goals_diff,
            "avg_conceded_diff": avg_conceded_diff,
            "xg_diff": xg_diff,
            "xga_diff": xga_diff,
            "goal_difference_diff": goal_difference_diff,
            "points_per_match_diff": points_per_match_diff,
            "clean_sheet_diff": clean_sheet_diff,
            "failed_to_score_diff": failed_to_score_diff,
            "all_points_diff": all_points_diff,
            "all_avg_goals_diff": all_avg_goals_diff,
            "all_avg_conceded_diff": all_avg_conceded_diff,
            "last3_points_diff": last3_points_diff,
            "last3_goals_diff": last3_goals_diff,
            "home_elo": home_elo,
            "away_elo": away_elo,
            "elo_diff": elo_diff,
            "attack_rating_diff": attack_rating_diff,
            "defense_rating_diff": defense_rating_diff,
            "home_implied_prob": home_implied,
            "draw_implied_prob": draw_implied,
            "away_implied_prob": away_implied,
        }

        predictions.append({
            "home": home_team,
            "away": away_team,
            "date": date_str,
            "time": time_str,

            # kursy referencyjne modelu
            "home_odds": home_odds,
            "draw_odds": draw_odds,
            "away_odds": away_odds,

            # WSZYSTKIE kursy
            "bookmakers": match_data["bookmakers"],

            "features": feature_dict
        })

    if not predictions:
        print("Brak meczów do predykcji.",flush=True)
        db.close()
        return

    feature_names = [
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

    X = pd.DataFrame([p["features"] for p in predictions], columns=feature_names)

    probs = model.predict_proba(X)

    results = []

    print("\n" + "="*60)
    print("PROGNOZY NA NADCHODZĄCE MECZE",flush=True)
    print("="*60)

    for i, pred in enumerate(predictions):
        prob_dict = dict(zip(classes, probs[i]))
        edge_h = prob_dict['H'] - X.loc[i, "home_implied_prob"]
        edge_d = prob_dict['D'] - X.loc[i, "draw_implied_prob"]
        edge_a = prob_dict['A'] - X.loc[i, "away_implied_prob"]

        # =========================================================
        # NAJLEPSZY KURS DLA KAŻDEGO TYPU
        # =========================================================

        best_h_bookmaker, best_h_odds = get_best_bookmaker_odds(
            pred["bookmakers"],
            "H"
        )

        best_d_bookmaker, best_d_odds = get_best_bookmaker_odds(
            pred["bookmakers"],
            "D"
        )

        best_a_bookmaker, best_a_odds = get_best_bookmaker_odds(
            pred["bookmakers"],
            "A"
        )

        # =========================================================
        # EV NA NAJLEPSZYCH KURSACH
        # =========================================================

        ev_h_best = (
            prob_dict["H"] * best_h_odds - 1
            if best_h_odds is not None
            else -999
        )

        ev_d_best = (
            prob_dict["D"] * best_d_odds - 1
            if best_d_odds is not None
            else -999
        )

        ev_a_best = (
            prob_dict["A"] * best_a_odds - 1
            if best_a_odds is not None
            else -999
        )

        evs = {
            "H": ev_h_best,
            "D": ev_d_best,
            "A": ev_a_best
        }

        edges = {
            "H": edge_h,
            "D": edge_d,
            "A": edge_a
        }

        best = max(evs, key=evs.get)

        confidence = prob_dict[best]
        edge = edges[best]
        ev = evs[best]

        # =========================================================
        # NAJLEPSZY BUKMACHER DLA WYBRANEGO TYPU
        # =========================================================

        best_bookmaker, best_odds = get_best_bookmaker_odds(
            pred["bookmakers"],
            best
        )

        raw_odds = get_raw_bookmaker_odds(
            pred["bookmakers"],
            best_bookmaker,
            best
        )

        if best_bookmaker is None or best_odds is None:
            continue

        effective_odds = best_odds

        # =========================================================
        # EV LICZONE NA NAJLEPSZYM KURSIE
        # =========================================================

        ev = confidence * effective_odds - 1

        recommend = True

        if edge < MIN_EDGE:
            recommend = False

        if ev < MIN_EV:
            recommend = False

        if confidence < MIN_CONFIDENCE:
            recommend = False

        if raw_odds < MIN_ODDS:
            recommend = False

        if raw_odds > MAX_ODDS:
            recommend = False

        if best == "D" and prob_dict["D"] < 0.35:
            recommend = False

        results.append({
            "Generated": generated,
            "Data": pred['date'],
            "Godzina": pred['time'],
            "Gospodarz": pred['home'],
            "Gość": pred['away'],
            "Kurs_1_Superbet": pred["bookmakers"].get("Superbet", {}).get("H"),
            "Kurs_X_Superbet": pred["bookmakers"].get("Superbet", {}).get("D"),
            "Kurs_2_Superbet": pred["bookmakers"].get("Superbet", {}).get("A"),

            "Kurs_1_STS": pred["bookmakers"].get("STS", {}).get("H"),
            "Kurs_X_STS": pred["bookmakers"].get("STS", {}).get("D"),
            "Kurs_2_STS": pred["bookmakers"].get("STS", {}).get("A"),

            "Kurs_1_Betclic": pred["bookmakers"].get("Betclic", {}).get("H"),
            "Kurs_X_Betclic": pred["bookmakers"].get("Betclic", {}).get("D"),
            "Kurs_2_Betclic": pred["bookmakers"].get("Betclic", {}).get("A"),
            "Najlepszy_Bukmacher_H": best_h_bookmaker,
            "Najlepszy_Kurs_H": best_h_odds,
            "Najlepszy_Kurs_H_Raw": get_raw_bookmaker_odds(
                pred["bookmakers"],
                best_h_bookmaker,
                "H"
            ),

            "Najlepszy_Bukmacher_D": best_d_bookmaker,
            "Najlepszy_Kurs_D": best_d_odds,
            "Najlepszy_Kurs_D_Raw": get_raw_bookmaker_odds(
                pred["bookmakers"],
                best_d_bookmaker,
                "D"
            ),

            "Najlepszy_Bukmacher_A": best_a_bookmaker,
            "Najlepszy_Kurs_A": best_a_odds,
            "Najlepszy_Kurs_A_Raw": get_raw_bookmaker_odds(
                pred["bookmakers"],
                best_a_bookmaker,
                "A"
            ),
            "Najlepszy_Bukmacher": best_bookmaker,
            "Najlepszy_Kurs": raw_odds,
            "Najlepszy_Kurs_Efektywny": effective_odds,
            "Najlepszy_Kurs_Raw": raw_odds,
            "P_H": prob_dict['H'],
            "P_D": prob_dict['D'],
            "P_A": prob_dict['A'],
            "EV_H": ev_h_best,
            "EV_D": ev_d_best,
            "EV_A": ev_a_best,
            "Edge_H": edge_h,
            "Edge_D": edge_d,
            "Edge_A": edge_a,
            "Best_Edge": best,
            "Best_Edge_Value": edge,

            "Confidence": confidence,
            "EV": ev,
            "Odds": raw_odds,
            "Effective_Odds": effective_odds,
            "Suggested_Stake_%": STAKE_PERCENT * 100,
            "Rekomendacja": bet_names[best] if recommend else "Brak",
            "Bukmacher": best_bookmaker if recommend else ""
        })

        print(f"\n{pred['home']} vs {pred['away']}  ({pred['date']} {pred['time']})",flush=True)
        print(
            f"Kursy:\n"
            f"  Superbet: 1:{pred['bookmakers'].get('Superbet', {}).get('H', 0):.2f} "
            f"X:{pred['bookmakers'].get('Superbet', {}).get('D', 0):.2f} "
            f"2:{pred['bookmakers'].get('Superbet', {}).get('A', 0):.2f}\n"
            f"  STS:      1:{pred['bookmakers'].get('STS', {}).get('H', 0):.2f} "
            f"X:{pred['bookmakers'].get('STS', {}).get('D', 0):.2f} "
            f"2:{pred['bookmakers'].get('STS', {}).get('A', 0):.2f}\n"
            f"  Betclic:   1:{pred['bookmakers'].get('Betclic', {}).get('H', 0):.2f} "
            f"X:{pred['bookmakers'].get('Betclic', {}).get('D', 0):.2f} "
            f"2:{pred['bookmakers'].get('Betclic', {}).get('A', 0):.2f}",
            flush=True
        )
        print(f"Model:    H:{prob_dict['H']:.3f}  D:{prob_dict['D']:.3f}  A:{prob_dict['A']:.3f}",flush=True)
        print(
            f"Najlepsze kursy:\n"
            f"  H: {format_odds(best_h_odds)} ({best_h_bookmaker or 'BRAK'}) | EV={ev_h_best:+.3f}\n"
            f"  D: {format_odds(best_d_odds)} ({best_d_bookmaker or 'BRAK'}) | EV={ev_d_best:+.3f}\n"
            f"  A: {format_odds(best_a_odds)} ({best_a_bookmaker or 'BRAK'}) | EV={ev_a_best:+.3f}",
            flush=True
        )
        print(f"Edge:     H:{edge_h:+.3f}  D:{edge_d:+.3f}  A:{edge_a:+.3f}",flush=True)
        if recommend:
            print(
                f"REKOMENDACJA: {bet_names[best]} @ {raw_odds:.2f} "
                f"({best_bookmaker}) | "
                f"Sugerowana stawka: {STAKE_PERCENT*100:.0f}% bankrolla | "
                f"EV={ev:.3f} | "
                f"Edge={edge:.3f} | "
                f"Confidence={confidence:.3f} | "
                f"Kurs efektywny={effective_odds:.2f}",
                flush=True
            )
        else:
            print("Brak zakładu",flush=True)

    # Zapis do CSV
    df_results = pd.DataFrame(results)

    if df_results.empty:
        print("Brak wyników do zapisania.", flush=True)
        db.close()
        return

    df_bets = df_results[
        df_results["Rekomendacja"] != "Brak"
    ].copy()

    csv_file = "predykcje.csv"

    history_dir = "history"
    os.makedirs(history_dir, exist_ok=True)

    history_file = os.path.join(
        history_dir,
        f"predykcje_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.csv"
    )

    if os.path.exists(csv_file):
        existing = pd.read_csv(
            csv_file,
            sep=";",
            decimal=",",
            encoding="utf-8-sig"
        )

        df_bets = pd.concat([existing, df_bets], ignore_index=True)

        # usuwamy duplikaty tego samego meczu

        df_bets["MatchID"] = (
            df_bets["Gospodarz"].fillna("").str.strip() + "|" +
            df_bets["Gość"].fillna("").str.strip() + "|" +
            df_bets["Data"].fillna("").str.strip()
        )

        df_bets.drop_duplicates(
            subset=["MatchID"],
            keep="last",
            inplace=True
        )

        df_bets.drop(columns=["MatchID"], inplace=True)

    df_bets.sort_values(
        by=["Data", "Gospodarz", "Gość"],
        inplace=True
    )

    df_bets.to_csv(
        csv_file,
        index=False,
        sep=";",
        decimal=",",
        encoding="utf-8-sig"
    )

    df_bets.to_csv(
        history_file,
        index=False,
        sep=";",
        decimal=",",
        encoding="utf-8-sig"
    )

    # =====================================
    # Aktualizacja portfolio.csv
    # =====================================

    portfolio_file = "portfolio.csv"

    portfolio_columns = [
        "Generated",
        "Data",
        "Godzina",
        "Gospodarz",
        "Gość",
        "Rekomendacja",
        "Najlepszy_Bukmacher",
        "Najlepszy_Kurs",
        "Najlepszy_Kurs_Efektywny",
        "EV",
        "Best_Edge_Value"
    ]

    portfolio = df_bets[portfolio_columns].copy()

    portfolio.rename(
        columns={
            "Rekomendacja": "Typ",
            "Najlepszy_Bukmacher": "Bukmacher",
            "Najlepszy_Kurs": "Kurs",
            "Best_Edge_Value": "Edge"
        },
        inplace=True
    )

    portfolio["Stake_%"] = STAKE_PERCENT
    portfolio["Profit"] = np.nan
    portfolio["Status"] = "WAITING"

    # Dane wyniku meczu
    portfolio["Wynik"] = ""
    portfolio["Gole_Gospodarz"] = np.nan
    portfolio["Gole_Gość"] = np.nan
    portfolio["Wynik_Rzeczywisty"] = ""

    if os.path.exists(portfolio_file):

        existing = pd.read_csv(
            portfolio_file,
            sep=";",
            decimal=",",
            encoding="utf-8-sig"
        )

        required_columns = {
            "Profit": np.nan,
            "Status": "WAITING",
            "Wynik": "",
            "Gole_Gospodarz": np.nan,
            "Gole_Gość": np.nan,
            "Wynik_Rzeczywisty": ""
        }

        for column, default_value in required_columns.items():

            if column not in existing.columns:
                existing[column] = default_value

        portfolio = pd.concat(
            [existing, portfolio],
            ignore_index=True
        )

    portfolio["MatchID"] = (
        portfolio["Gospodarz"].fillna("").str.strip()
        + "|"
        + portfolio["Gość"].fillna("").str.strip()
        + "|"
        + portfolio["Data"].fillna("").str.strip()
    )

    portfolio.drop_duplicates(
        subset=["MatchID"],
        keep="first",
        inplace=True
    )

    #portfolio.drop(columns=["MatchID"], inplace=True)

    portfolio.sort_values(
        by=["Data", "Godzina"],
        inplace=True
    )

    portfolio.to_csv(
        portfolio_file,
        index=False,
        sep=";",
        decimal=",",
        encoding="utf-8-sig"
    )

    print(f"\nW pliku znajduje się {len(df_bets)} rekomendowanych zakładów.", flush=True)

    print(f"Portfolio zawiera {len(portfolio)} zakładów.", flush=True)

    db.close()

    print("\n=== PREDICT_FINISHED ===", flush=True)

if __name__ == "__main__":
    try:
        main()
    finally:
        run_results_scraper()