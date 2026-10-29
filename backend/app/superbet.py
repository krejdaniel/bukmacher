from playwright.sync_api import sync_playwright
import pandas as pd
from datetime import datetime
import re

def scrape_superbet_premier_league():
    data = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        })
        page.goto("https://superbet.pl/zaklady-bukmacherskie/pilka-nozna/anglia/premier-league/wszystko?ct=m", timeout=90000)

        previous_height = 0
        for _ in range(10):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(2000)
            current_height = page.evaluate("document.body.scrollHeight")
            if current_height == previous_height:
                break
            previous_height = current_height

        events = page.locator(".single-event").all()
        print(f"Znaleziono wydarzeń: {len(events)}")

        for e in events:
            try:
                teams = [
                    e.locator(".event-competitor__name").nth(0).text_content().strip(),
                    e.locator(".event-competitor__name").nth(1).text_content().strip()
                ]
                datetime_text = e.locator(".event-time span").first.text_content().strip()
                match = re.search(r'(\d{1,2}\.?\d{0,2})[, ]+(\d{1,2}:\d{2})', datetime_text)
                if match:
                    day_month = match.group(1)
                    time_text = match.group(2)
                else:
                    day_month = datetime_text
                    time_text = ""

                if '.' not in day_month:
                    day_month_fmt = f"{int(day_month):02d}.{datetime.now().month:02d}"
                else:
                    day_month_fmt = day_month
                date_str = f"{day_month_fmt}-{datetime.now().year}"

                odds_elements = []
                odds_buttons = e.locator(".odd-button__odd-value span").all_text_contents()
                for o in odds_buttons:
                    odd = o.replace(',', '.').strip()
                    if odd.replace('.', '', 1).isdigit():
                        odds_elements.append(odd)

                if len(odds_elements) >= 3:
                    data.append({
                        "Data": date_str,
                        "Godzina": time_text,
                        "Mecz": f"{teams[0]} - {teams[1]}",
                        "1": odds_elements[0],
                        "X": odds_elements[1],
                        "2": odds_elements[2]
                    })
            except Exception as me:
                print(" Błąd przy meczu:", me)

        browser.close()
    return data

if __name__ == "__main__":
    matches_data = scrape_superbet_premier_league()
    df = pd.DataFrame(matches_data)
    df.to_csv("superbet_premier_league.csv", index=False, encoding="utf-8-sig")
    print(f" Zapisano do superbet_premier_league.csv, liczba meczów: {len(df)}")
    print(df.head())