"""
Weborama guest-permalink client.

Weborama's guest "reportcenter/permalink/link/hash/<hash>" links establish
a session cookie that then lets the underlying Angular dashboard render -
but only through real UI navigation (clicking into "Insertions"), not by
jumping straight to a constructed dashboard URL, which the server rejects
with "Unauthorized parameters!". The date range baked into the permalink
can be widened through the calendar control, but not via URL params either.

So this drives a real (headless) browser through the same clicks a human
would make: open the permalink, click into Insertions, set the date range
via the calendar, read the resulting per-insertion table. Each row's name
tells us video vs banner directly (e.g. "Sape_Banner_X" / "Sape_Video_X").
"""
import re
from playwright.sync_api import sync_playwright


class WeboramaFetchError(Exception):
    pass


def fetch_insertions(permalink_url, date_from, date_to):
    """
    permalink_url: a https://adap-interface.wbrm.ru/.../permalink/link/hash/<hash> URL
    date_from, date_to: datetime.date objects, must fall within a month
        currently reachable without cross-month calendar navigation
        (the permalink's own default range's month is used as the anchor).

    Returns a dict keyed by the exact insertion name as shown in Weborama
    -> {'impressions': int, 'clicks': int, 'insertion_name': str, 'format_guess': 'banner'|'video'|None}
    """
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': 1600, 'height': 1000})
        try:
            page.goto(permalink_url, wait_until='networkidle', timeout=30000)
            page.wait_for_timeout(1200)

            insertions_link = page.locator('text=Insertions').first
            if insertions_link.count() == 0:
                raise WeboramaFetchError('Не найден раздел "Insertions" в пермалинке - возможно, другая структура отчёта')
            insertions_link.click()
            page.wait_for_timeout(1500)

            _set_date_range(page, date_from, date_to)

            page.wait_for_timeout(1500)
            body_text = page.inner_text('body')

            return _parse_insertions_table(body_text)
        finally:
            browser.close()


def _set_date_range(page, date_from, date_to):
    calendar_toggle = page.locator('text=Calendar From').first
    if calendar_toggle.count() == 0:
        raise WeboramaFetchError('Не найден элемент выбора дат в пермалинке')
    calendar_toggle.click()
    page.wait_for_timeout(800)

    start_cal = page.locator('text=Start Date').locator('xpath=following::table[1]')
    start_cal.locator(f'td:has-text("{date_from.day}")').first.click()
    page.wait_for_timeout(300)

    end_cal = page.locator('text=End Date').locator('xpath=following::table[1]')
    end_cal.locator(f'td:has-text("{date_to.day}")').first.click()
    page.wait_for_timeout(300)

    apply_buttons = page.locator('button:visible, a:visible').filter(has_text=re.compile(r'^Apply$'))
    if apply_buttons.count() == 0:
        raise WeboramaFetchError('Не нашлась кнопка Apply в календаре')
    apply_buttons.first.click()

    # Checking for the loading overlay here races with it even appearing -
    # it can still be absent at the instant we check, before the AJAX call
    # starts. A flat wait is what actually worked reliably in testing.
    page.wait_for_timeout(6000)


def _parse_insertions_table(body_text):
    """Parse lines like:
        Sape_Banner_Lyovushka
        1,062,146
        201,325
        18.95%
        ...
    into {'Sape_Banner_Lyovushka': {...}, 'Sape_Video_Lyovushka': {...}} - keyed
    by the exact insertion name, so callers match on an explicitly chosen
    name rather than a guessed banner/video category (which breaks once
    there's more than one insertion of the same format, or naming that
    doesn't contain "banner"/"video" at all).

    Not every Weborama campaign is split into separate Insertions per
    format - some (e.g. a campaign that only ever ran one format) only
    go one level up, to a "Sites/Offers" table with a single combined
    row (commonly named "SAPE"). _parse_sites_offers_table handles that
    shape as a fallback, so a mapping can still be pointed at it by name.
    """
    idx = body_text.find('Insertions\nImp.')
    if idx != -1:
        return _parse_rows(body_text, idx, header_count=9)

    idx = body_text.find('Sites/Offers\nImp.')
    if idx != -1:
        return _parse_rows(body_text, idx, header_count=5)

    raise WeboramaFetchError('Не нашлась таблица Insertions или Sites/Offers на странице - возможно, нет данных за этот период')


def _parse_rows(body_text, idx, header_count):
    """Generic "name, Imp, Clicks, ...(fixed extra columns)" table parser
    shared by the Insertions (9 columns) and Sites/Offers (5 columns)
    table shapes - both list Imp. and Clicks right after the row name."""
    lines = [l.strip() for l in body_text[idx:].split('\n') if l.strip()]
    rows = lines[header_count:]
    row_width = header_count  # name + the same number of data columns as the header

    results = {}
    i = 0
    while i < len(rows):
        name = rows[i]
        if name in ('Total', 'Plot selected rows') or name.startswith('Page'):
            break
        if i + 2 >= len(rows):
            break
        impressions = _parse_number(rows[i + 1])
        clicks = _parse_number(rows[i + 2])

        name_lower = name.lower()
        if 'banner' in name_lower:
            format_guess = 'banner'
        elif 'video' in name_lower:
            format_guess = 'video'
        else:
            format_guess = None

        results[name] = {
            'impressions': impressions,
            'clicks': clicks,
            'insertion_name': name,
            'format_guess': format_guess,
        }
        i += row_width

    if not results:
        raise WeboramaFetchError('Не удалось распознать строки с данными в таблице')

    return results


def _parse_number(raw):
    raw = raw.strip()
    if raw in ('-', '', 'N/A'):
        return 0
    cleaned = raw.replace(',', '').replace('%', '')
    try:
        return int(float(cleaned))
    except ValueError:
        return 0
