from playwright.sync_api import sync_playwright
import pandas as pd
from pathlib import Path
import re


# ============================================================
# KONFIGURACJA
# ============================================================

URL = (
    "https://www.sts.pl/zaklady-bukmacherskie/"
    "pilka-nozna/anglia/premier-league/1/1/17"
)

OUTPUT_FILE = Path("sts_premier_league.csv")

# Jak daleko przesuwamy właściwy wewnętrzny scroller
SCROLL_STEP = 450

# Maksymalna liczba przewinięć
MAX_SCROLLS = 50

# Czas oczekiwania po przewinięciu
SCROLL_WAIT = 450


# ============================================================
# POMOCNICZE
# ============================================================

def clean_text(text):
    if not text:
        return ""

    return " ".join(text.split()).strip()


# ============================================================
# PRAWDZIWE KARTY MECZÓW
# ============================================================

def get_match_cards(page):
    """
    STS używa virtualizacji.

    W DOM może być np. tylko 6 prawdziwych kart,
    mimo że na stronie jest znacznie więcej meczów.

    NIE używamy:
        [class*='match-tile']

    bo ten selektor łapie również elementy znajdujące
    się wewnątrz karty.

    Używamy wyłącznie:
        a.one-ticket-match-tile-link
    """

    return page.locator(
        "a.one-ticket-match-tile-link"
    )


# ============================================================
# DRUŻYNY
# ============================================================

def extract_teams(card):

    home_team = ""
    away_team = ""

    # --------------------------------------------------------
    # GOSPODARZ
    # --------------------------------------------------------

    selectors_home = [
        ".one-ticket-match-tile-event-details-desktop__team-home span",
        ".one-ticket-match-tile-event-details-desktop__team-home",
    ]

    for selector in selectors_home:

        try:

            locator = card.locator(selector)

            if locator.count() > 0:

                text = clean_text(
                    locator.first.inner_text()
                )

                if text:
                    home_team = text
                    break

        except Exception:
            pass

    # --------------------------------------------------------
    # GOŚĆ
    # --------------------------------------------------------

    selectors_away = [
        ".one-ticket-match-tile-event-details-desktop__team-away span",
        ".one-ticket-match-tile-event-details-desktop__team-away",
    ]

    for selector in selectors_away:

        try:

            locator = card.locator(selector)

            if locator.count() > 0:

                text = clean_text(
                    locator.first.inner_text()
                )

                if text:
                    away_team = text
                    break

        except Exception:
            pass

    # --------------------------------------------------------
    # FALLBACK - ARIA LABEL
    # --------------------------------------------------------

    if not home_team or not away_team:

        try:

            aria = card.get_attribute("aria-label")

            if aria:

                # np.:
                # Arsenal - Coventry City

                if " - " in aria:

                    parts = aria.split(
                        " - ",
                        1
                    )

                    if len(parts) == 2:

                        if not home_team:
                            home_team = clean_text(
                                parts[0]
                            )

                        if not away_team:
                            away_team = clean_text(
                                parts[1]
                            )

        except Exception:
            pass

    return home_team, away_team


# ============================================================
# DATA + GODZINA
# ============================================================

def extract_date_time(card):

    date_text = ""
    time_text = ""

    # --------------------------------------------------------
    # DATA
    # --------------------------------------------------------

    date_selectors = [
        ".match-tile-start-time__date",
        "[class*='match-tile-start-time__date']",
    ]

    for selector in date_selectors:

        try:

            locator = card.locator(selector)

            if locator.count() > 0:

                text = clean_text(
                    locator.first.inner_text()
                )

                if text:
                    date_text = text
                    break

        except Exception:
            pass

    # --------------------------------------------------------
    # GODZINA
    # --------------------------------------------------------

    time_selectors = [
        ".match-tile-start-time__time",
        "[class*='match-tile-start-time__time']",
    ]

    for selector in time_selectors:

        try:

            locator = card.locator(selector)

            if locator.count() > 0:

                text = clean_text(
                    locator.first.inner_text()
                )

                if text:
                    time_text = text
                    break

        except Exception:
            pass

    return date_text, time_text


# ============================================================
# KURSY 1X2
# ============================================================

def extract_odds(card):

    selectors = [
        ".odds-button__odd-value",
        "[class*='odds-button'][class*='odd-value']",
    ]

    for selector in selectors:

        try:

            elements = card.locator(selector)

            count = elements.count()

            if count < 3:
                continue

            odds = []

            for i in range(count):

                try:

                    text = clean_text(
                        elements.nth(i).inner_text()
                    )

                    text = text.replace(
                        ",",
                        "."
                    )

                    match = re.search(
                        r"\d+(?:\.\d+)?",
                        text
                    )

                    if not match:
                        continue

                    value = match.group(0)

                    try:

                        float(value)

                        odds.append(value)

                    except ValueError:
                        pass

                except Exception:
                    pass

            if len(odds) >= 3:

                return odds[:3]

        except Exception:
            pass

    return []


# ============================================================
# KOLEJKA
# ============================================================

def extract_round(card):

    try:

        text = clean_text(
            card.inner_text()
        )

        match = re.search(
            r"(Kolejka\s+\d+)",
            text,
            re.IGNORECASE
        )

        if match:

            return match.group(1)

    except Exception:
        pass

    return ""


# ============================================================
# UNIKALNY KLUCZ MECZU
# ============================================================

def make_match_key(
    home_team,
    away_team,
    date_text,
    time_text
):
    """
    NIE używamy href.

    W STS różne elementy tej samej karty mogą mieć
    ten sam albo nietypowy href.

    Najbezpieczniej identyfikować mecz przez:

        data
        godzina
        gospodarz
        gość
    """

    return (
        f"{date_text}|"
        f"{time_text}|"
        f"{home_team}|"
        f"{away_team}"
    ).lower().strip()


# ============================================================
# ZNALEZIENIE WŁAŚCIWEGO SCROLLERA
# ============================================================

def find_scroll_container(page):

    print()
    print("Szukam właściwego scroller'a STS...")

    selectors = [
        "bo-prematch-match-tiles-list",
        "[class*='prematch']",
        "[class*='match-tiles']",
        "[class*='matches-list']",
        "[class*='event-list']",
    ]

    best = None
    best_score = -1

    for selector in selectors:

        try:

            elements = page.locator(selector)

            count = elements.count()

            if count == 0:
                continue

            for i in range(
                min(count, 20)
            ):

                element = elements.nth(i)

                try:

                    info = element.evaluate(
                        """
                        (el) => ({
                            scrollHeight: el.scrollHeight,
                            clientHeight: el.clientHeight,
                            cards: el.querySelectorAll(
                                'a.one-ticket-match-tile-link'
                            ).length
                        })
                        """
                    )

                    scroll_height = info[
                        "scrollHeight"
                    ]

                    client_height = info[
                        "clientHeight"
                    ]

                    cards = info["cards"]

                    # Element musi być faktycznie
                    # przewijalny.

                    if (
                        scroll_height
                        <= client_height + 50
                    ):
                        continue

                    score = 0

                    # Najważniejsze:
                    # wewnątrz muszą znajdować się
                    # prawdziwe karty.

                    if cards > 0:
                        score += 1000

                    # Im większa różnica wysokości,
                    # tym bardziej prawdopodobne,
                    # że to właściwy kontener.

                    score += min(
                        scroll_height
                        - client_height,
                        1000
                    )

                    if score > best_score:

                        best_score = score
                        best = element

                except Exception:
                    pass

        except Exception:
            pass

    if best is None:

        print(
            "NIE znaleziono właściwego scroller'a."
        )

        return None

    try:

        info = best.evaluate(
            """
            (el) => ({
                scrollTop: el.scrollTop,
                scrollHeight: el.scrollHeight,
                clientHeight: el.clientHeight,
                cards: el.querySelectorAll(
                    'a.one-ticket-match-tile-link'
                ).length
            })
            """
        )

        print(
            "Znaleziono właściwy wewnętrzny scroller STS."
        )

        print(
            f"scrollTop: {info['scrollTop']}"
        )

        print(
            f"scrollHeight: {info['scrollHeight']}"
        )

        print(
            f"clientHeight: {info['clientHeight']}"
        )

        print(
            f"Karty aktualnie w DOM: {info['cards']}"
        )

    except Exception:
        pass

    return best


# ============================================================
# ZBIERANIE AKTUALNIE WIDOCZNYCH MECZÓW
# ============================================================

def collect_current_matches(
    page,
    found_matches
):

    cards = get_match_cards(page)

    count = cards.count()

    new_count = 0

    for i in range(count):

        try:

            card = cards.nth(i)

            # ------------------------------------------------
            # DRUŻYNY
            # ------------------------------------------------

            home_team, away_team = extract_teams(
                card
            )

            if not home_team or not away_team:
                continue

            # ------------------------------------------------
            # DATA / GODZINA
            # ------------------------------------------------

            date_text, time_text = (
                extract_date_time(card)
            )

            # ------------------------------------------------
            # KLUCZ
            # ------------------------------------------------

            key = make_match_key(
                home_team,
                away_team,
                date_text,
                time_text
            )

            # ------------------------------------------------
            # JEŻELI JUŻ MAMY
            # ------------------------------------------------

            if key in found_matches:
                continue

            # ------------------------------------------------
            # KURSY
            # ------------------------------------------------

            odds = extract_odds(card)

            if len(odds) < 3:

                # Karta może być jeszcze
                # w trakcie renderowania.

                continue

            # ------------------------------------------------
            # KOLEJKA
            # ------------------------------------------------

            kolejka = extract_round(
                card
            )

            # ------------------------------------------------
            # ZAPIS
            # ------------------------------------------------

            found_matches[key] = {

                "Data": date_text,

                "Godzina": time_text,

                "Mecz":
                    f"{home_team} - {away_team}",

                "1": odds[0],

                "X": odds[1],

                "2": odds[2],

                "Kolejka": kolejka
            }

            new_count += 1

            print(
                f"[NOWY] "
                f"{date_text} "
                f"{time_text} | "
                f"{home_team} - {away_team} | "
                f"1: {odds[0]} | "
                f"X: {odds[1]} | "
                f"2: {odds[2]}"
            )

        except Exception as e:

            print(
                f"Błąd karty {i}:",
                repr(e)
            )

    return new_count


# ============================================================
# PRZEWIJANIE
# ============================================================

def load_all_matches(page):

    print()
    print("=" * 60)
    print("ŁADOWANIE WSZYSTKICH MECZÓW")
    print("=" * 60)

    found_matches = {}

    # --------------------------------------------------------
    # ZNAJDŹ WŁAŚCIWY SCROLLER
    # --------------------------------------------------------

    scroll_container = find_scroll_container(
        page
    )

    if scroll_container is None:

        return found_matches

    # --------------------------------------------------------
    # ZBIERZ PIERWSZY ZESTAW
    # --------------------------------------------------------

    new_matches = collect_current_matches(
        page,
        found_matches
    )

    print(
        f"Pierwszy zestaw: "
        f"{new_matches} nowych | "
        f"łącznie: {len(found_matches)}"
    )

    last_scroll_top = -1

    stable_bottom_checks = 0

    # ========================================================
    # GŁÓWNA PĘTLA
    # ========================================================

    for step in range(
        MAX_SCROLLS
    ):

        # ----------------------------------------------------
        # ODCZYT STANU
        # ----------------------------------------------------

        try:

            state = scroll_container.evaluate(
                """
                (el) => ({
                    scrollTop: el.scrollTop,
                    scrollHeight: el.scrollHeight,
                    clientHeight: el.clientHeight
                })
                """
            )

        except Exception as e:

            print(
                "Nie można odczytać scroller'a:",
                repr(e)
            )

            break

        scroll_top = state[
            "scrollTop"
        ]

        scroll_height = state[
            "scrollHeight"
        ]

        client_height = state[
            "clientHeight"
        ]

        # ----------------------------------------------------
        # SPRAWDŹ CZY JEST DÓŁ
        # ----------------------------------------------------

        at_bottom = (
            scroll_top
            + client_height
            >= scroll_height - 5
        )

        print()
        print(
            f"Pozycja {step + 1}/{MAX_SCROLLS} | "
            f"scrollTop: {scroll_top:.0f} | "
            f"scrollHeight: {scroll_height:.0f} | "
            f"widoczne karty: "
            f"{get_match_cards(page).count()} | "
            f"łącznie meczów: "
            f"{len(found_matches)}"
        )

        # ----------------------------------------------------
        # JEŻELI DÓŁ
        # ----------------------------------------------------

        if at_bottom:

            print(
                "-> jesteśmy na dole."
            )

            # Poczekaj krótko, bo STS może jeszcze
            # przeliczać/renderować ostatnie elementy.

            current_new = collect_current_matches(
                page,
                found_matches
            )

            if current_new > 0:

                stable_bottom_checks = 0

                print(
                    f"-> znaleziono jeszcze "
                    f"{current_new} meczów."
                )

                # Jeśli wysokość listy się zwiększyła,
                # pętla będzie kontynuowana.

            else:

                stable_bottom_checks += 1

                print(
                    f"-> brak nowych meczów "
                    f"({stable_bottom_checks}/2)"
                )

            # Ponownie odczytujemy wysokość.

            try:

                state_after = (
                    scroll_container.evaluate(
                        """
                        (el) => ({
                            scrollTop: el.scrollTop,
                            scrollHeight: el.scrollHeight,
                            clientHeight: el.clientHeight
                        })
                        """
                    )
                )

                new_scroll_height = (
                    state_after[
                        "scrollHeight"
                    ]
                )

            except Exception:

                new_scroll_height = (
                    scroll_height
                )

            # Jeśli nadal jesteśmy na dole
            # i dwa razy nic nie przybyło,
            # kończymy.

            if (
                stable_bottom_checks >= 2
                and new_scroll_height
                <= scroll_height + 5
            ):

                print(
                    "-> brak kolejnych meczów."
                )

                break

        # ----------------------------------------------------
        # PRZEWIJANIE
        # ----------------------------------------------------

        target_scroll = min(
            scroll_top + SCROLL_STEP,
            scroll_height - client_height
        )

        # ====================================================
        # WAŻNE:
        #
        # NIE używamy page.mouse.wheel().
        #
        # NIE przewijamy window.
        #
        # Przesuwamy WYŁĄCZNIE właściwy element STS.
        # ====================================================

        try:

            scroll_container.evaluate(
                """
                (el, target) => {
                    el.scrollTop = target;
                }
                """,
                target_scroll
            )

        except Exception as e:

            print(
                "Błąd przewijania:",
                repr(e)
            )

            break

        # ----------------------------------------------------
        # CZEKAJ NA VIRTUALIZACJĘ
        # ----------------------------------------------------

        page.wait_for_timeout(
            SCROLL_WAIT
        )

        # ----------------------------------------------------
        # CZEKAJ, AŻ SCROLLER FAKTYCZNIE SIĘ PRZESUNIE
        # ----------------------------------------------------

        try:

            page.wait_for_function(
                """
                ([element, oldPosition]) =>
                    element.scrollTop !== oldPosition
                """,
                arg=[
                    scroll_container,
                    scroll_top
                ],
                timeout=800
            )

        except Exception:
            pass

        # ----------------------------------------------------
        # ZBIERAMY NOWE KARTY
        # ----------------------------------------------------

        new_matches = collect_current_matches(
            page,
            found_matches
        )

        # ----------------------------------------------------
        # SPRAWDZENIE CZY SCROLLER SIĘ PRZESUNĄŁ
        # ----------------------------------------------------

        try:

            new_scroll_top = (
                scroll_container.evaluate(
                    "(el) => el.scrollTop"
                )
            )

        except Exception:

            new_scroll_top = scroll_top

        print(
            f"-> przesunięto do: "
            f"{new_scroll_top:.0f} | "
            f"nowych: {new_matches} | "
            f"łącznie: {len(found_matches)}"
        )

        # ----------------------------------------------------
        # ZABEZPIECZENIE
        # ----------------------------------------------------

        if (
            new_scroll_top == last_scroll_top
            and new_matches == 0
        ):

            print(
                "-> scroller nie zmienił pozycji."
            )

        last_scroll_top = new_scroll_top

    # ========================================================
    # OSTATNIE KARTY
    # ========================================================

    collect_current_matches(
        page,
        found_matches
    )

    print()
    print("=" * 60)
    print(
        f"ŁĄCZNIE ZEBRANO: "
        f"{len(found_matches)} UNIKALNYCH MECZÓW"
    )
    print("=" * 60)

    return found_matches


# ============================================================
# GŁÓWNY SCRAPER
# ============================================================

def scrape_sts_premier_league():

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

            locale="pl-PL",

            timezone_id="Europe/Warsaw"
        )

        page = context.new_page()

        # ====================================================
        # OTWARCIE
        # ====================================================

        print(
            "Otwieranie STS..."
        )

        page.goto(
            URL,
            wait_until="domcontentloaded",
            timeout=90000
        )

        print(
            "Strona załadowana."
        )

        # ====================================================
        # COOKIES
        # ====================================================

        try:

            cookie_button = page.locator(
                "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll"
            )

            if (
                cookie_button.count() > 0
                and cookie_button.first.is_visible()
            ):

                cookie_button.first.click()

                print(
                    "Cookies zaakceptowane"
                )

                page.wait_for_timeout(
                    1000
                )

        except Exception:
            pass

        # ====================================================
        # CZEKAJ NA PIERWSZE KARTY
        # ====================================================

        print(
            "Czekam na pierwsze mecze..."
        )

        cards = get_match_cards(
            page
        )

        found = False

        for attempt in range(15):

            count = cards.count()

            print(
                f"Próba {attempt + 1}/15 "
                f"-> prawdziwych kart: {count}"
            )

            if count > 0:

                found = True

                break

            page.wait_for_timeout(
                500
            )

        if not found:

            print()
            print(
                "NIE ZNALEZIONO KART MECZÓW."
            )

            try:

                page.screenshot(
                    path="sts_debug.png",
                    full_page=True
                )

                Path(
                    "sts_debug.html"
                ).write_text(
                    page.content(),
                    encoding="utf-8"
                )

            except Exception:
                pass

            browser.close()

            return []

        print()
        print(
            f"Pierwsze mecze znalezione: "
            f"{cards.count()}"
        )

        # ====================================================
        # ŁADOWANIE WSZYSTKICH
        # ====================================================

        found_matches = load_all_matches(
            page
        )

        data = list(
            found_matches.values()
        )

        # ====================================================
        # KONIEC
        # ====================================================

        print()
        print("=" * 60)
        print(
            f"POPRAWNIE POBRANO: "
            f"{len(data)} MECZÓW"
        )
        print("=" * 60)

        browser.close()

        return data


# ============================================================
# URUCHOMIENIE
# ============================================================

if __name__ == "__main__":
    matches_data = scrape_sts_premier_league()

    df = pd.DataFrame(matches_data)

    df.to_csv(
        OUTPUT_FILE,
        index=False,
        sep=";",
        encoding="utf-8-sig"
    )

    print()
    print("=" * 60)
    print(f"ZAPISANO DO: {OUTPUT_FILE}")
    print(f"LICZBA MECZÓW: {len(df)}")
    print("=" * 60)

    if not df.empty:
        print()
        print(df.to_string(index=False))
    else:
        print("UWAGA: Nie znaleziono żadnych meczów.")