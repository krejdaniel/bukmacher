import requests
from bs4 import BeautifulSoup
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

URL = "https://sinceawin.com/elo-ratings/premier-league"


def get_premier_league_elo():

    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/138.0.0.0 Safari/537.36"
        )
    }

    response = requests.get(
        URL,
        headers=headers,
        timeout=30,
        verify=False
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    table = soup.find("table")

    if table is None:
        print("Nie znaleziono tabeli ELO.")
        return []

    teams = []

    rows = table.find("tbody").find_all("tr")

    for row in rows:

        cells = row.find_all("td")

        if len(cells) < 4:
            continue

        try:

            team = cells[1].get_text(strip=True)

            elo = float(
                cells[2]
                .get_text(strip=True)
                .replace(",", ".")
            )

            teams.append({
                "team": team,
                "elo": elo
            })

        except Exception:
            continue

    return teams


if __name__ == "__main__":

    elo = get_premier_league_elo()

    for team in elo:
        print(team)