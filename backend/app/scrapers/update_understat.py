from datetime import datetime

from app.database.database import SessionLocal

from app.models.match import Match

from app.services.understat_service import get_understat_matches

from app.services.team_mapping import TEAM_MAP


SEASONS = [

    2015,

    2016,

    2017,

    2018,

    2019,

    2020,

    2021,

    2022,

    2023,

    2024,

    2025

]


db = SessionLocal()

updated = 0


for season in SEASONS:

    print("Sezon", season)

    matches = get_understat_matches(season)

    for m in matches:

        date = datetime.strptime(
            m["datetime"][:10],
            "%Y-%m-%d"
        ).date()

        home = TEAM_MAP.get(

            m["h"]["title"],

            m["h"]["title"]

        )

        away = TEAM_MAP.get(

            m["a"]["title"],

            m["a"]["title"]

        )

        row = (

            db.query(Match)

            .filter(

                Match.date == date,

                Match.home_team == home,

                Match.away_team == away

            )

            .first()

        )

        if row is None:

            continue

        row.home_xg = float(m["xG"]["h"])

        row.away_xg = float(m["xG"]["a"])

        updated += 1


db.commit()

db.close()

print()

print("Uzupełniono", updated)