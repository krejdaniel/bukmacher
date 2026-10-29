import pandas as pd
import requests
from io import StringIO
from datetime import datetime

from app.database.database import SessionLocal
from app.models.match import Match


SEASONS = [
    "1516",
    "1617",
    "1718",
    "1819",
    "1920",
    "2021",
    "2122",
    "2223",
    "2324",
    "2425",
    "2526"
]

def parse_date(value):

    value = str(value)

    for fmt in (
        "%d/%m/%Y",
        "%d/%m/%y"
    ):

        try:
            return datetime.strptime(
                value,
                fmt
            )

        except ValueError:
            pass


    raise ValueError(
        f"Nieznany format daty: {value}"
    )

def import_season(season):

    url = (
        f"https://www.football-data.co.uk/mmz4281/"
        f"{season}/E0.csv"
    )


    print(f"Pobieram sezon {season}")


    response = requests.get(url)

    df = pd.read_csv(
        StringIO(response.text)
    )


    db = SessionLocal()


    for _, row in df.iterrows():

        if pd.isna(row["HomeTeam"]):
            continue


        existing = (
            db.query(Match)
            .filter(
                Match.date == parse_date(
                    row["Date"]
                ),
                Match.home_team == row["HomeTeam"],
                Match.away_team == row["AwayTeam"]
            )
            .first()
        )


        if existing:
            continue

        match = Match(

            date=parse_date(
                row["Date"]
            ),

            season=season,

            home_team=row["HomeTeam"],

            away_team=row["AwayTeam"],

            home_goals=row["FTHG"],

            away_goals=row["FTAG"],

            home_odds=row.get("B365H"),

            draw_odds=row.get("B365D"),

            away_odds=row.get("B365A")
        )


        db.add(match)


    db.commit()

    db.close()


def main():

    for season in SEASONS:
        import_season(season)


if __name__ == "__main__":
    main()