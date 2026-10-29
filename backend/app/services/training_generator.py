from app.models.match import Match
from app.models.training_match import TrainingMatch
from app.services.elo import (
    START_ELO,
    update_elo
)
from app.services.statistics import (
    get_team_matches,
    calculate_form
)
from sqlalchemy import func

def generate_training_data(db):

    matches = (
    db.query(Match)
    .filter(
        Match.result.isnot(None)
    )
    .order_by(
        Match.date.asc()
    )
    .all()
)


    created = 0
    elo = {}
    skipped_no_history = 0

    league_avg = db.query(
        func.avg(Match.home_goals)
    ).scalar()

    league_avg = float(league_avg or 1.0)

    for match in matches:

        home_elo = elo.get(
            match.home_team,
            START_ELO
        )

        away_elo = elo.get(
            match.away_team,
            START_ELO
        )

        # sprawdzamy czy już istnieje

        exists = (
            db.query(TrainingMatch)
            .filter(
                TrainingMatch.match_id == match.id
            )
            .first()
        )


        if exists:
            continue



        home_matches = get_team_matches(
            db,
            match.home_team,
            match.date,
            5,
            location="home",
            current_match_id=match.id
        )


        away_matches = get_team_matches(
            db,
            match.away_team,
            match.date,
            5,
            location="away",
            current_match_id=match.id
        )


        home_all_matches = get_team_matches(
            db,
            match.home_team,
            match.date,
            5,
            location="all",
            current_match_id=match.id
        )

        away_all_matches = get_team_matches(
            db,
            match.away_team,
            match.date,
            5,
            location="all",
            current_match_id=match.id
        )


        # pomijamy mecze, gdzie nie mamy historii
        
        if len(home_matches) < 5:
            skipped_no_history += 1
            continue

        if len(away_matches) < 5:
            skipped_no_history += 1
            continue



        home_form = calculate_form(
            home_matches,
            match.home_team
        )


        away_form = calculate_form(
            away_matches,
            match.away_team
        )
    

        home_attack_rating = (
            home_form["avg_goals_for"] /
            league_avg
        )

        home_defense_rating = (
            league_avg /
            max(home_form["avg_goals_against"], 0.1)
        )

        away_attack_rating = (
            away_form["avg_goals_for"] /
            league_avg
        )

        away_defense_rating = (
            league_avg /
            max(away_form["avg_goals_against"], 0.1)
        )

        home_all_form = calculate_form(
            home_all_matches,
            match.home_team
        )

        away_all_form = calculate_form(
            away_all_matches,
            match.away_team
        )
        
        if not (
            match.home_odds
            and match.draw_odds
            and match.away_odds
        ):
            continue

        ph = 1 / match.home_odds
        pd = 1 / match.draw_odds
        pa = 1 / match.away_odds

        total = ph + pd + pa

        home_implied_prob = ph / total
        draw_implied_prob = pd / total
        away_implied_prob = pa / total

        home_last3 = get_team_matches(
            db,
            match.home_team,
            match.date,
            3,
            location="all",
            current_match_id=match.id
        )

        away_last3 = get_team_matches(
            db,
            match.away_team,
            match.date,
            3,
            location="all",
            current_match_id=match.id
        )

        home_last3_form = calculate_form(
            home_last3,
            match.home_team
        )

        away_last3_form = calculate_form(
            away_last3,
            match.away_team
        )

        training = TrainingMatch(

            match_id=match.id,

            date=match.date,

            home_team=match.home_team,

            away_team=match.away_team,


            home_points=home_form["points"],

            home_avg_goals=
                home_form["avg_goals_for"],

            home_avg_conceded=
                home_form["avg_goals_against"],
                
            home_avg_xg=
                home_form["avg_xg_for"],

            home_avg_xga=
                home_form["avg_xg_against"],

            away_points=away_form["points"],

            away_avg_goals=
                away_form["avg_goals_for"],

            away_avg_conceded=
                away_form["avg_goals_against"],
                
            away_avg_xg=
                away_form["avg_xg_for"],

            away_avg_xga=
                away_form["avg_xg_against"],
                
            home_attack_rating=home_attack_rating,
            home_defense_rating=home_defense_rating,

            away_attack_rating=away_attack_rating,
            away_defense_rating=away_defense_rating,

            home_goal_difference =
                home_form["goal_difference"],


            home_points_per_match =
                home_form["points_per_match"],


            home_clean_sheet_rate =
                home_form["clean_sheet_rate"],


            home_failed_to_score_rate =
                home_form["failed_to_score_rate"],

            home_all_points=
                home_all_form["points"],

            home_all_avg_goals=
                home_all_form["avg_goals_for"],

            home_all_avg_conceded=
                home_all_form["avg_goals_against"],

            away_all_points=
                away_all_form["points"],

            away_all_avg_goals=
                away_all_form["avg_goals_for"],

            away_all_avg_conceded=
                away_all_form["avg_goals_against"],

            away_goal_difference =
                away_form["goal_difference"],


            away_points_per_match =
                away_form["points_per_match"],


            away_clean_sheet_rate =
                away_form["clean_sheet_rate"],


            away_failed_to_score_rate =
                away_form["failed_to_score_rate"],

            home_odds=match.home_odds,

            draw_odds=match.draw_odds,

            away_odds=match.away_odds,

            home_implied_prob=home_implied_prob,

            draw_implied_prob=draw_implied_prob,

            away_implied_prob=away_implied_prob,

            home_last3_points=
                home_last3_form["points"],

            away_last3_points=
                away_last3_form["points"],

            home_last3_avg_goals=
                home_last3_form["avg_goals_for"],

            away_last3_avg_goals=
                away_last3_form["avg_goals_for"],
                
            home_elo=home_elo,

            away_elo=away_elo,

            elo_diff=home_elo-away_elo,

            result=match.result

        )


        db.add(training)

        new_home_elo, new_away_elo = update_elo(
            home_elo,
            away_elo,
            match.result,
            match.home_goals,
            match.away_goals
        )

        elo[match.home_team] = new_home_elo
        elo[match.away_team] = new_away_elo

        created += 1

        if created % 100 == 0:

            db.commit()

            print(
                f"Dodano {created}"
            )


    db.commit()

    print(
        f"Brak historii: {skipped_no_history}"
    )

    print(
        f"Gotowe. Utworzono {created} rekordów"
    )
    
    print()

    print("Najwyższe ELO")

    top = sorted(
        elo.items(),
        key=lambda x: x[1],
        reverse=True
    )

    for team, rating in top[:20]:
        print(team, round(rating, 1))
    
    print()

    print("Najniższe ELO")

    for team, rating in top[-20:]:
        print(team, round(rating, 1))