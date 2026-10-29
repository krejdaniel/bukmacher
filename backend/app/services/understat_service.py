from understatapi import UnderstatClient


LEAGUE = "EPL"


def get_understat_matches(season):

    with UnderstatClient() as understat:

        league = understat.league(LEAGUE)

        matches = league.get_match_data(str(season))

    return matches