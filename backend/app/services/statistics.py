from sqlalchemy.orm import Session

from app.models.match import Match


def get_team_matches(
    db: Session,
    team: str,
    before_date,
    limit: int = 5,
    location="all",
    current_match_id=None
):
    # Podstawowy filtr: mecze przed datą before_date
    query = db.query(Match).filter(Match.date < before_date)

    # Dodatkowy warunek dla meczów z tą samą datą, ale tylko jeśli current_match_id nie jest None
    if current_match_id is not None:
        query = query.filter(
            (Match.date < before_date) |
            ((Match.date == before_date) & (Match.id < current_match_id))
        )
    # Jeśli current_match_id jest None, pomijamy ten warunek

    # Filtrowanie po lokalizacji
    if location == "home":
        query = query.filter(Match.home_team == team)
    elif location == "away":
        query = query.filter(Match.away_team == team)
    else:
        query = query.filter(
            (Match.home_team == team) | (Match.away_team == team)
        )

    return (
        query
        .order_by(Match.date.desc())
        .limit(limit)
        .all()
    )
    
def calculate_form(matches, team):

    points = 0

    wins = 0
    draws = 0
    losses = 0

    goals_for = 0
    goals_against = 0

    clean_sheets = 0
    failed_to_score = 0

    home_points = 0
    away_points = 0

    xg_for = 0

    xg_against = 0

    form = []


    for match in reversed(matches):

        if match.home_team == team:

            gf = match.home_goals
            ga = match.away_goals

            result = match.result


            goals_for += gf
            goals_against += ga
            
            xg_for += match.home_xg or 0

            xg_against += match.away_xg or 0
            
            if ga == 0:
                clean_sheets += 1

            if gf == 0:
                failed_to_score += 1

            if result == "H":
                points += 3
                home_points += 3
                wins += 1
                form.append("W")

            elif result == "D":
                points += 1
                home_points += 1
                draws += 1
                form.append("D")

            else:
                losses += 1
                form.append("L")


        else:

            gf = match.away_goals
            ga = match.home_goals

            goals_for += gf
            goals_against += ga

            xg_for += match.away_xg or 0

            xg_against += match.home_xg or 0

            if ga == 0:
                clean_sheets += 1

            if gf == 0:
                failed_to_score += 1

            if match.result == "A":
                points += 3
                away_points += 3
                wins += 1
                form.append("W")

            elif match.result == "D":
                points += 1
                away_points += 1
                draws += 1
                form.append("D")

            else:
                losses += 1
                form.append("L")


    count = len(matches)


    return {

        "matches": count,

        "points": points,

        "wins": wins,

        "draws": draws,

        "losses": losses,


        "goals_for": goals_for,

        "goals_against": goals_against,


        "avg_goals_for":
            goals_for / count
            if count else 0,


        "avg_goals_against":
            goals_against / count
            if count else 0,

        "clean_sheets": clean_sheets,
        "failed_to_score": failed_to_score,

        "goal_difference": goals_for - goals_against,

        "avg_goal_difference":
            (goals_for - goals_against) / count
            if count else 0,

        "clean_sheet_rate":
            clean_sheets / count
            if count else 0,

        "failed_to_score_rate":
            failed_to_score / count
            if count else 0,

        "points_per_match":
            points / count
            if count else 0,

        "xg_for": xg_for,

        "xg_against": xg_against,

        "avg_xg_for":
            xg_for / count
            if count else 0,

        "avg_xg_against":
            xg_against / count
            if count else 0,

        "xg_difference":
            xg_for - xg_against,

        "avg_xg_difference":
            (xg_for - xg_against) / count
            if count else 0,

        "form":
            "".join(form)

    }