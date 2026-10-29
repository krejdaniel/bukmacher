from playwright.sync_api import sync_playwright
import pandas as pd
from pathlib import Path
import re
import time


URL = "https://www.betclic.pl/football-sfootball/premier-league-c3"

OUTPUT_FILE = Path("betclic_premier_league.csv")


# ============================================================
# POMOCNICZE
# ============================================================

def clean_text(text):
    if not text:
        return ""

    return " ".join(text.split()).strip()


def get_teams(card):
    """
    Pobiera nazwy gospodarza i gościa.
    """

    selectors = [
        ".scoreboard_contestantLabel",
        '[data-qa="contestant-1-label"]',
        '[data-qa="contestant-2-label"]'
    ]

    # Najpierw standardowy selektor
    labels = card.locator(".scoreboard_contestantLabel")

    try:
        count = labels.count()

        teams = []

        for i in range(count):
            text = clean_text(labels.nth(i).inner_text())

            if text:
                teams.append(text)

        if len(teams) >= 2:
            return teams[0], teams[1]

    except Exception:
        pass

    # Fallback po data-qa
    try:
        home = clean_text(
            card.locator('[data-qa="contestant-1-label"]').inner_text()
        )

        away = clean_text(
            card.locator('[data-qa="contestant-2-label"]').inner_text()
        )

        if home and away:
            return home, away

    except Exception:
        pass

    return "", ""


def get_time(card):
    """
    Pobiera godzinę meczu.
    """

    try:
        locator = card.locator(".scoreboard_hour")

        if locator.count() > 0:
            return clean_text(locator.first.inner_text())

    except Exception:
        pass

    return ""


def get_date(card):
    """
    Pobiera datę z grupy groupEvents.
    """

    try:
        parent_group = card.locator(
            "xpath=ancestor::div[contains(@class,'groupEvents')]"
        )

        date_locator = parent_group.locator(
            ".groupEvents_headTitle"
        )

        if date_locator.count() > 0:
            return clean_text(
                date_locator.first.inner_text()
            )

    except Exception:
        pass

    return ""


def get_kolejka(card, retries=5):
    """
    Pobiera kolejkę.

    Betclic czasami renderuje breadcrumb z opóźnieniem,
    dlatego robimy kilka prób.
    """

    for attempt in range(retries):

        try:

            breadcrumb_items = card.locator(
                "bcdk-breadcrumb-item"
            )

            count = breadcrumb_items.count()

            for i in range(count):

                text = clean_text(
                    breadcrumb_items.nth(i).inner_text()
                )

                if "Kolejka" in text:

                    # np.
                    # Premier League • Kolejka 1

                    match = re.search(
                        r"(Premier League\s*•\s*Kolejka\s+\d+)",
                        text,
                        re.IGNORECASE
                    )

                    if match:
                        return match.group(1)

                    return text

        except Exception:
            pass

        # Czasami breadcrumb pojawia się chwilę później
        time.sleep(0.5)

    return ""


def get_odds(card, retries=5):
    """
    Pobiera kursy 1/X/2.

    Betclic używa:
    bcdk-bet-button-odds-animated

    W przypadku opóźnionego renderowania wykonujemy
    kilka prób.
    """

    for attempt in range(retries):

        odds = []

        try:

            odds_locator = card.locator(
                "bcdk-bet-button-odds-animated"
            )

            count = odds_locator.count()

            for i in range(count):

                text = clean_text(
                    odds_locator.nth(i).inner_text()
                )

                text = text.replace(",", ".")

                try:
                    value = float(text)

                    # Kursy bukmacherskie powinny być > 1
                    if value > 1:
                        odds.append(value)

                except ValueError:
                    continue

            if len(odds) >= 3:

                return [
                    str(odds[0]),
                    str(odds[1]),
                    str(odds[2])
                ]

        except Exception:
            pass

        time.sleep(0.5)

    return []


# ============================================================
# GŁÓWNY SCRAPER
# ============================================================

def scrape_betclic_premier_league():

    data = []

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=False
        )

        context = browser.new_context(

            viewport={
                "width": 1920,
                "height": 1080
            },

            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),

            locale="pl-PL"
        )

        page = context.new_page()

        # ====================================================
        # OTWARCIE
        # ====================================================

        print("Otwieranie Betclic...")

        page.goto(
            URL,
            wait_until="domcontentloaded",
            timeout=90000
        )

        print("Strona załadowana.")

        # ====================================================
        # COOKIES
        # ====================================================

        try:

            cookie_buttons = page.get_by_role(
                "button",
                name="Zaakceptuj wszystko"
            )

            if cookie_buttons.count() > 0:

                cookie_buttons.first.click()

                print("Cookies zaakceptowane.")

                page.wait_for_timeout(2000)

        except Exception as e:

            print(
                "Cookies: brak przycisku lub błąd:",
                e
            )

        # ====================================================
        # CZEKAJ NA PIERWSZE MECZE
        # ====================================================

        try:

            first_card = page.locator(
                "a.cardEvent[sports-events-event-card]"
            ).first

            first_card.wait_for(
                state="visible",
                timeout=30000
            )

            print(
                "Pierwsze mecze zostały znalezione."
            )

        except Exception as e:

            print(
                "Nie znaleziono kart meczów:",
                e
            )

            page.screenshot(
                path="betclic_debug.png",
                full_page=True
            )

            browser.close()

            return data

        # ====================================================
        # ZNAJDŹ WEWNĘTRZNY SCROLLER
        # ====================================================

        scroller = page.locator(
            ".verticalScroller_wrapper"
        ).first

        try:

            scroller.wait_for(
                state="visible",
                timeout=10000
            )

            print(
                "Znaleziono wewnętrzny scroller Betclic."
            )

        except Exception:

            print(
                "Nie znaleziono .verticalScroller_wrapper."
            )

            browser.close()

            return data

        # ====================================================
        # PRZEWIJANIE
        # ====================================================

        print()
        print(
            "Pobieranie wszystkich dostępnych kart..."
        )

        previous_count = 0
        stable_count = 0

        MAX_SCROLLS = 40

        for scroll_number in range(1, MAX_SCROLLS + 1):

            # --------------------------------------------
            # Aktualna liczba kart
            # --------------------------------------------

            cards_locator = page.locator(
                "a.cardEvent[sports-events-event-card]"
            )

            current_count = cards_locator.count()

            # --------------------------------------------
            # Parametry scrollera
            # --------------------------------------------

            try:

                scroll_data = scroller.evaluate(
                    """
                    el => ({
                        scrollTop: el.scrollTop,
                        scrollHeight: el.scrollHeight,
                        clientHeight: el.clientHeight
                    })
                    """
                )

                scroll_top = scroll_data["scrollTop"]
                scroll_height = scroll_data["scrollHeight"]
                client_height = scroll_data["clientHeight"]

            except Exception:

                scroll_top = 0
                scroll_height = 0
                client_height = 0

            print(
                f"Scroll {scroll_number}/{MAX_SCROLLS} | "
                f"Mecze: {current_count} | "
                f"scrollTop: {scroll_top} | "
                f"scrollHeight: {scroll_height}"
            )

            # --------------------------------------------
            # Przewijamy PRAWDZIWY wewnętrzny scroller
            # --------------------------------------------

            try:

                scroller.evaluate(
                    """
                    el => {
                        el.scrollTop =
                            Math.min(
                                el.scrollTop + 900,
                                el.scrollHeight
                            );
                    }
                    """
                )

            except Exception:
                pass

            # Dodatkowo scroll myszką nad scrollerem
            try:

                box = scroller.bounding_box()

                if box:

                    page.mouse.move(
                        box["x"] + box["width"] / 2,
                        box["y"] + box["height"] / 2
                    )

                    page.mouse.wheel(
                        0,
                        1000
                    )

            except Exception:
                pass

            # --------------------------------------------
            # Czekamy na lazy loading
            # --------------------------------------------

            page.wait_for_timeout(1200)

            # --------------------------------------------
            # Sprawdzamy ponownie liczbę kart
            # --------------------------------------------

            new_count = page.locator(
                "a.cardEvent[sports-events-event-card]"
            ).count()

            if new_count > current_count:

                print(
                    f"-> znaleziono nowe mecze: "
                    f"{current_count} -> {new_count}"
                )

                stable_count = 0

            else:

                stable_count += 1

                print(
                    f"-> brak nowych meczów "
                    f"({stable_count}/6)"
                )

            # --------------------------------------------
            # Sprawdź czy jesteśmy na dole
            # --------------------------------------------

            try:

                position = scroller.evaluate(
                    """
                    el => ({
                        top: el.scrollTop,
                        height: el.scrollHeight,
                        client: el.clientHeight
                    })
                    """
                )

                at_bottom = (
                    position["top"] +
                    position["client"] >=
                    position["height"] - 10
                )

            except Exception:

                at_bottom = False

            # --------------------------------------------
            # Nie kończymy od razu.
            #
            # Betclic potrafi potrzebować kilku chwil
            # na dociągnięcie kolejnych kart.
            # --------------------------------------------

            if at_bottom and stable_count >= 6:

                print()
                print(
                    "Osiągnięto koniec listy."
                )

                break

        # ====================================================
        # OSTATECZNA LICZBA KART
        # ====================================================

        cards = page.locator(
            "a.cardEvent[sports-events-event-card]"
        )

        count = cards.count()

        print()
        print("=" * 60)
        print(
            f"ZNALEZIONO ŁĄCZNIE KART: {count}"
        )
        print("=" * 60)

        # ====================================================
        # POBIERANIE MECZÓW
        # ====================================================

        for i in range(count):

            try:

                card = cards.nth(i)

                # ----------------------------------------
                # Przewiń konkretną kartę do widoku
                # ----------------------------------------

                try:

                    card.scroll_into_view_if_needed(
                        timeout=5000
                    )

                    page.wait_for_timeout(300)

                except Exception:
                    pass

                # ----------------------------------------
                # DRUŻYNY
                # ----------------------------------------

                home_team, away_team = get_teams(
                    card
                )

                if not home_team or not away_team:

                    print(
                        f"[{i}] Pomijam - "
                        f"nie znaleziono drużyn"
                    )

                    continue

                # ----------------------------------------
                # DATA
                # ----------------------------------------

                date_text = get_date(card)

                # ----------------------------------------
                # GODZINA
                # ----------------------------------------

                time_text = get_time(card)

                # ----------------------------------------
                # WYŚWIETLENIE
                # ----------------------------------------

                print()
                print(
                    f"[{i}] "
                    f"{date_text} "
                    f"{time_text} | "
                    f"{home_team} - {away_team}"
                )

                # ----------------------------------------
                # KURSY
                # ----------------------------------------

                odds = get_odds(
                    card,
                    retries=5
                )

                if len(odds) < 3:

                    print(
                        "-> NIE UDAŁO SIĘ POBRAĆ "
                        "3 KURSÓW"
                    )

                    continue

                print(
                    f"-> kursy: "
                    f"1: {odds[0]} | "
                    f"X: {odds[1]} | "
                    f"2: {odds[2]}"
                )

                # ----------------------------------------
                # KOLEJKA
                # ----------------------------------------

                kolejka = get_kolejka(
                    card,
                    retries=5
                )

                # ----------------------------------------
                # JEŚLI KOLEJKA PUSTA
                #
                # Spróbuj jeszcze raz po krótkim
                # przewinięciu karty.
                # ----------------------------------------

                if not kolejka:

                    try:

                        card.scroll_into_view_if_needed()

                        page.wait_for_timeout(1000)

                    except Exception:
                        pass

                    kolejka = get_kolejka(
                        card,
                        retries=3
                    )

                # ----------------------------------------
                # ZAPIS
                # ----------------------------------------

                match = {

                    "Data": date_text,

                    "Godzina": time_text,

                    "Mecz":
                        f"{home_team} - {away_team}",

                    "1": odds[0],

                    "X": odds[1],

                    "2": odds[2],

                    "Kolejka": kolejka
                }

                data.append(match)

                print(
                    f"[OK] "
                    f"1: {odds[0]} | "
                    f"X: {odds[1]} | "
                    f"2: {odds[2]} | "
                    f"{kolejka}"
                )

            except Exception as e:

                print(
                    f"[{i}] Błąd przy przetwarzaniu:",
                    repr(e)
                )

        # ====================================================
        # KONIEC
        # ====================================================

        browser.close()

    return data


# ============================================================
# URUCHOMIENIE
# ============================================================

if __name__ == "__main__":
    matches_data = scrape_betclic_premier_league()

    df = pd.DataFrame(matches_data)

    df.to_csv(
        OUTPUT_FILE,
        index=False,
        sep=";",
        encoding="utf-8-sig"
    )

    print()
    print("=" * 60)
    print(f"ZAPISANO: {len(df)} MECZÓW")
    print("=" * 60)

    if not df.empty:
        print()
        print(df.to_string(index=False))
        print()
        print(f"Plik CSV: {OUTPUT_FILE.absolute()}")
    else:
        print("UWAGA: Nie znaleziono żadnych meczów.")