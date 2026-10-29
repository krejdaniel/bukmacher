import requests


URL = "https://understat.com/league/EPL"


def get_matches():

    html = requests.get(URL).text

    start = html.find("datesData")

    if start == -1:
        raise Exception("Nie znaleziono danych Understat")

    start = html.find("('", start) + 2
    end = html.find("')", start)

    raw = html[start:end]

    raw = (
        raw
        .encode("utf8")
        .decode("unicode_escape")
    )

    import json

    return json.loads(raw)