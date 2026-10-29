from datetime import date

from app.database.database import SessionLocal
from app.services.statistics import (
    get_team_matches,
    calculate_form
)


db = SessionLocal()


matches = get_team_matches(
    db,
    "Liverpool",
    date(2025,1,1),
    5,
    "home"
)


print("Liczba meczów:", len(matches))


form = calculate_form(
    matches,
    "Liverpool"
)


print(form)


db.close()