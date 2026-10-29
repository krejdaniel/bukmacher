import pandas as pd
import requests
import os
from datetime import datetime

PORTFOLIO_FILE = "portfolio.csv"

# ESPN API dla Premier League
ESPN_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/"
    "soccer/eng.1/scoreboard"
)

TEAM_ALIASES_RESULTS = {
    "Manchester United": "Manchester United",
    "Manchester Utd": "Manchester United",

    "Manchester City": "Manchester City",

    "Newcastle United": "Newcastle United",
    "Newcastle": "Newcastle United",

    "Tottenham Hotspur": "Tottenham Hotspur",
    "Tottenham": "Tottenham Hotspur",

    "Brighton and Hove Albion": "Brighton",
    "Brighton & Hove Albion": "Brighton",
    "Brighton": "Brighton",

    "Wolverhampton Wanderers": "Wolverhampton Wanderers",
    "Wolves": "Wolverhampton Wanderers",

    "Nottingham Forest": "Nottingham Forest",
    "Nottingham": "Nottingham Forest",

    "West Ham United": "West Ham United",
    "West Ham": "West Ham United",

    "Ipswich Town": "Ipswich Town",
    "Sunderland": "Sunderland",

    "Leeds United": "Leeds United",
    "Leeds": "Leeds United",

    "Coventry City": "Coventry City",
    "Coventry": "Coventry City",

    "Hull City": "Hull City",
    "Hull": "Hull City",
}


def normalize_team_name(name):
    if not name:
        return ""

    name = str(name).strip()

    return TEAM_ALIASES_RESULTS.get(name, name)


def normalize_date(value):
    """
    Zamienia:
        2026-08-22
        22.08.2026
        itp.
    na:
        YYYY-MM-DD
    """

    if pd.isna(value):
        return ""

    value = str(value).strip()

    formats = [
        "%Y-%m-%d",
        "%d.%m.%Y",
        "%d/%m/%Y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass

    return value


def get_portfolio():
    if not os.path.exists(PORTFOLIO_FILE):
        print(f"Brak pliku {PORTFOLIO_FILE}")
        return None

    return pd.read_csv(
        PORTFOLIO_FILE,
        sep=";",
        decimal=",",
        encoding="utf-8-sig"
    )


def get_results_for_date(match_date):
    """
    Pobiera mecze Premier League dla konkretnego dnia.
    ESPN wymaga formatu YYYYMMDD.
    """

    try:
        espn_date = datetime.strptime(
            str(match_date),
            "%Y-%m-%d"
        ).strftime("%Y%m%d")

        response = requests.get(
            ESPN_URL,
            params={
                "dates": espn_date
            },
            timeout=20
        )

        response.raise_for_status()

        data = response.json()

        return data.get("events", [])

    except Exception as e:
        print(
            f"Błąd pobierania wyników dla {match_date}: {e}",
            flush=True
        )

        return []


def parse_result(event):
    """
    Wyciąga z ESPN:

        home
        away
        home_goals
        away_goals
        date
        status
    """

    try:
        competition = event["competitions"][0]

        competitors = competition["competitors"]

        home = None
        away = None

        home_score = None
        away_score = None

        for team in competitors:

            team_name = team["team"]["displayName"]

            if team["homeAway"] == "home":
                home = normalize_team_name(team_name)
                home_score = int(team["score"])

            elif team["homeAway"] == "away":
                away = normalize_team_name(team_name)
                away_score = int(team["score"])

        event_date = event["date"][:10]

        status = (
            event
            .get("status", {})
            .get("type", {})
            .get("name", "")
        )

        return {
            "home": home,
            "away": away,
            "date": event_date,
            "home_goals": home_score,
            "away_goals": away_score,
            "status": status,
        }

    except Exception as e:

        print(
            f"Błąd parsowania meczu ESPN: {e}"
        )

        return None


def build_result_key(home, away, match_date):

    return (
        normalize_team_name(home).lower().strip(),
        normalize_team_name(away).lower().strip(),
        normalize_date(match_date)
    )


def load_results(dates):
    """
    Pobiera wyniki dla wszystkich potrzebnych dat.
    Zwraca zarówno mecze zakończone,
    jak i przełożone/anulowane.
    """

    results = {}

    for match_date in dates:

        print(
            f"Pobieranie wyników: {match_date}",
            flush=True
        )

        events = get_results_for_date(match_date)

        print(
            f"  znaleziono wydarzeń: {len(events)}",
            flush=True
        )

        for event in events:
            print("\n--- DEBUG EVENT ESPN ---", flush=True)
            print("Nazwa wydarzenia:", event.get("name"), flush=True)
            print("Data:", event.get("date"), flush=True)
            print(
                "Status:",
                event.get("status", {}).get("type", {}),
                flush=True
            )

            competition = (event.get("competitions") or [{}])[0]
            for team in competition.get("competitors", []):
                print(
                    "Drużyna:",
                    team.get("team", {}).get("displayName"),
                    "| homeAway:",
                    team.get("homeAway"),
                    "| score:",
                    team.get("score"),
                    flush=True
                )

            result = parse_result(event)

            if not result:
                print("ODRZUCONO: parse_result zwrócił None", flush=True)
                continue

            print("Wynik po parsowaniu:", result, flush=True)

                
            
            if result["status"] not in (
                "STATUS_FINAL",
                "STATUS_FULL_TIME",
                "STATUS_FINAL_AET",
                "STATUS_FINAL_PEN",
                "STATUS_POSTPONED",
                "STATUS_CANCELED",
                "STATUS_CANCELLED",
            ):
                print(
                    f"Pominięto mecz: {result['home']} - {result['away']} "
                    f"| status: {result['status']}",
                    flush=True
                )
                continue

            if (
                result["home"] is None
                or result["away"] is None
            ):
                continue

            key = build_result_key(
                result["home"],
                result["away"],
                result["date"]
            )

            results[key] = result

    return results


def get_prediction_outcome(typ):
    """
    Zamienia polską nazwę typu zakładu
    na H / D / A.
    """

    mapping = {
        "Gospodarz": "H",
        "Remis": "D",
        "Gość": "A",
    }

    return mapping.get(str(typ).strip())


def get_actual_outcome(home_goals, away_goals):

    if home_goals > away_goals:
        return "H"

    if home_goals < away_goals:
        return "A"

    return "D"


def calculate_profit(row, won):

    stake_percent = float(row["Stake_%"])
    odds = float(row["Kurs"])

    if won:
        return stake_percent * (odds - 1)

    return -stake_percent


def update_portfolio():

    portfolio = get_portfolio()

    if portfolio is None:
        return

    if portfolio.empty:
        print("Portfolio jest puste.")
        return

    # ---------------------------------------------------------
    # Tylko oczekujące zakłady
    # ---------------------------------------------------------

    waiting = portfolio[
        portfolio["Status"].astype(str).str.upper() == "WAITING"
    ].copy()
    
    # ---------------------------------------------------------
    # Kolumny wynikowe jako tekst
    # ---------------------------------------------------------

    portfolio["Wynik"] = (
        portfolio["Wynik"]
        .fillna("")
        .astype(str)
    )

    portfolio["Wynik_Rzeczywisty"] = (
        portfolio["Wynik_Rzeczywisty"]
        .fillna("")
        .astype(str)
    )

    if waiting.empty:
        print("Brak oczekujących zakładów.")
        return

    print(
        f"Oczekujących zakładów: {len(waiting)}",
        flush=True
    )

    # ---------------------------------------------------------
    # Daty, dla których potrzebujemy wyników
    # ---------------------------------------------------------

    waiting["Data_Normalized"] = waiting["Data"].apply(
        normalize_date
    )

    today = datetime.now().date()

    dates = []

    for value in waiting["Data_Normalized"].dropna().unique():

        try:
            match_date = datetime.strptime(
                value,
                "%Y-%m-%d"
            ).date()

            # Nie pobieramy przyszłych meczów
            if match_date <= today:
                dates.append(value)

        except ValueError:
            continue

    if not dates:
        print(
            "Nie ma jeszcze żadnych zakończonych "
            "lub potencjalnie zakończonych meczów."
        )
        return

    print(
        f"Dat do sprawdzenia: {len(dates)}",
        flush=True
    )

    # ---------------------------------------------------------
    # Pobieramy wszystkie wyniki
    # ---------------------------------------------------------

    results = load_results(dates)
    
    print("\n=== DEBUG: WYNIKI Z ESPN ===")

    for key, result in results.items():
        print(
            f"Klucz: {key} | "
            f"Mecz: {result['home']} - {result['away']} | "
            f"Data: {result['date']} | "
            f"Wynik: {result['home_goals']}:{result['away_goals']} | "
            f"Status: {result['status']}"
        )

    print("=== KONIEC DEBUG ===\n")

    print(
        f"Pobrano zakończonych meczów: {len(results)}",
        flush=True
    )

    updated = 0

    # ---------------------------------------------------------
    # Rozliczamy portfolio
    # ---------------------------------------------------------

    for index, row in portfolio.iterrows():

        status = str(row["Status"]).upper()
        
        match_date = normalize_date(row["Data"])

        try:
            if datetime.strptime(match_date, "%Y-%m-%d").date() > today:
                continue
        except ValueError:
            print(f"Nieprawidłowa data meczu: {row['Data']}", flush=True)
            continue

        if status != "WAITING":
            continue

        key = build_result_key(
            row["Gospodarz"],
            row["Gość"],
            match_date
        )

        result = results.get(key)

        if not result:
            print(
                f"Brak wyniku: "
                f"{row['Gospodarz']} - {row['Gość']} "
                f"({match_date})",
                flush=True
            )

            continue

        # ---------------------------------------------------------
        # MECZ PRZEŁOŻONY / ANULOWANY
        # ---------------------------------------------------------

        if result["status"] in (
            "STATUS_POSTPONED",
            "STATUS_CANCELED",
            "STATUS_CANCELLED"
        ):

            portfolio.at[index, "Status"] = "VOID"
            portfolio.at[index, "Profit"] = 0

            print(
                f"{row['Gospodarz']} - {row['Gość']}",
                flush=True
            )

            print(
                "  >>> MECZ PRZEŁOŻONY/ANULOWANY | VOID",
                flush=True
            )

            updated += 1

            continue

        if (
            result["home_goals"] is None
            or result["away_goals"] is None
        ):
            print(
                f"Brak końcowego wyniku: "
                f"{row['Gospodarz']} - {row['Gość']}",
                flush=True
            )
            continue

        home_goals = result["home_goals"]
        away_goals = result["away_goals"]

        actual = get_actual_outcome(
            home_goals,
            away_goals
        )

        portfolio.at[index, "Gole_Gospodarz"] = home_goals
        portfolio.at[index, "Gole_Gość"] = away_goals
        portfolio.at[index, "Wynik"] = f"{home_goals}:{away_goals}"
        portfolio.at[index, "Wynik_Rzeczywisty"] = actual

        predicted = get_prediction_outcome(
            row["Typ"]
        )

        print(
            f"\n{row['Gospodarz']} - {row['Gość']}",
            flush=True
        )

        print(
            f"  Wynik: {home_goals}:{away_goals}",
            flush=True
        )

        print(
            f"  Predykcja: {row['Typ']}",
            flush=True
        )

        print(
            f"  Rzeczywisty wynik: {actual}",
            flush=True
        )

        if predicted == actual:

            profit = calculate_profit(
                row,
                won=True
            )

            portfolio.at[index, "Status"] = "WON"
            portfolio.at[index, "Profit"] = profit

            print(
                f"  >>> TRAFIONY | Profit: {profit:.2f}",
                flush=True
            )

        else:

            profit = calculate_profit(
                row,
                won=False
            )

            portfolio.at[index, "Status"] = "LOST"
            portfolio.at[index, "Profit"] = profit

            print(
                f"  >>> NIETRAFIONY | Profit: {profit:.2f}",
                flush=True
            )

        updated += 1

    # ---------------------------------------------------------
    # Zapis
    # ---------------------------------------------------------

    portfolio.to_csv(
        PORTFOLIO_FILE,
        index=False,
        sep=";",
        decimal=",",
        encoding="utf-8-sig"
    )

    print(
        f"\nZaktualizowano {updated} zakładów.",
        flush=True
    )

    print(
        f"Portfolio zapisane: {PORTFOLIO_FILE}",
        flush=True
    )


if __name__ == "__main__":
    print("\n=== RESULT CHECK STARTED ===\n")

    update_portfolio()

    print("\n=== RESULT CHECK FINISHED ===")