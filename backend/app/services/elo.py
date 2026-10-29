from math import pow

START_ELO = 1500

K = 20

HOME_ADVANTAGE = 50


def expected_score(team_elo, opponent_elo):

    return 1 / (
        1 + pow(
            10,
            (opponent_elo - team_elo) / 400
        )
    )


def update_elo(
    home_elo,
    away_elo,
    result,
    home_goals,
    away_goals
):

    expected_home = expected_score(
        home_elo + HOME_ADVANTAGE,
        away_elo
    )

    expected_away = expected_score(
        away_elo,
        home_elo + HOME_ADVANTAGE
    )

    if result == "H":

        score_home = 1
        score_away = 0

    elif result == "D":

        score_home = 0.5
        score_away = 0.5

    else:

        score_home = 0
        score_away = 1

    goal_diff = abs(home_goals - away_goals)

    if goal_diff == 0:
        multiplier = 1.0

    elif goal_diff == 1:
        multiplier = 1.0

    elif goal_diff == 2:
        multiplier = 1.5

    elif goal_diff == 3:
        multiplier = 1.75

    else:
        multiplier = 2.0

    home_elo += (
        K
        * multiplier
        * (score_home - expected_home)
    )

    away_elo += (
        K
        * multiplier
        * (score_away - expected_away)
    )

    return (
        home_elo, away_elo
    )