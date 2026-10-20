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
    date_from, date_to: datetime.date objects - any month, the calendar is
        navigated forward/backward from whatever month the permalink
        defaults to.

    Returns a dict keyed by the exact insertion name as shown in Weborama
    -> {'impressions': int, 'clicks': int, 'insertion_name': str, 'format_guess': 'banner'|'video'|None}
    """
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': 1600, 'height': 1000})
        try:
            page.goto(permalink_url, wait_until='networkidle', timeout=60000)
            page.wait_for_timeout(1200)

            # Most permalinks need a click into "Insertions" to reach the
            # per-insertion table. Some (e.g. ones scoped to a single
            # Site/Offer) land directly on the Sites/Offers table instead,
            # with no "Insertions" tab at all - _parse_insertions_table
            # already has a fallback for that shape, so just skip the
            # click rather than failing outright.
            insertions_link = page.locator('text=Insertions').first
            if insertions_link.count() > 0:
                insertions_link.click()
                page.wait_for_timeout(1500)

            _set_date_range(page, date_from, date_to)

            page.wait_for_timeout(1500)
            return _read_grid_rows(page)
        finally:
            browser.close()


_MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June',
                'July', 'August', 'September', 'October', 'November', 'December']
_MONTH_LABEL_RE = re.compile(r'^([A-Za-z]+) (\d{4})$')


def _set_date_range(page, date_from, date_to):
    calendar_toggle = page.locator('text=Calendar From').first
    if calendar_toggle.count() == 0:
        raise WeboramaFetchError('Не найден элемент выбора дат в пермалинке')
    calendar_toggle.click()
    page.wait_for_timeout(800)

    # Each calendar (Start/End) is its own little ExtJS widget with its
    # own month header and its own prev/next arrows - ".x-datepicker-next"
    # etc. match both widgets at once, in DOM order (Start first, End
    # second), so nth(0)/nth(1) picks out the right one for each side.
    headers = page.locator('.x-btn-inner').filter(has_text=_MONTH_LABEL_RE)
    next_arrows = page.locator('.x-datepicker-next')
    prev_arrows = page.locator('.x-datepicker-prev')

    start_cal = page.locator('text=Start Date').locator('xpath=following::table[1]')
    end_cal = page.locator('text=End Date').locator('xpath=following::table[1]')

    # End MUST be set before Start: the Start picker disables every day
    # after whatever End is currently set to, so moving Start forward to
    # a month past the permalink's old default End date silently fails
    # (every day in the target month shows as disabled, the click is a
    # no-op, and Start is left wherever it happened to be) - Apply would
    # then submit a much narrower, wrong range with no visible error.
    _navigate_calendar_to_month(page, headers.nth(1), next_arrows.nth(1), prev_arrows.nth(1), date_to)
    _click_calendar_day(end_cal, date_to.day)
    page.wait_for_timeout(300)

    _navigate_calendar_to_month(page, headers.nth(0), next_arrows.nth(0), prev_arrows.nth(0), date_from)
    _click_calendar_day(start_cal, date_from.day)
    page.wait_for_timeout(300)

    apply_buttons = page.locator('button:visible, a:visible').filter(has_text=re.compile(r'^Apply$'))
    if apply_buttons.count() == 0:
        raise WeboramaFetchError('Не нашлась кнопка Apply в календаре')
    apply_buttons.first.click()

    # Checking for the loading overlay here races with it even appearing -
    # it can still be absent at the instant we check, before the AJAX call
    # starts. A flat wait is what actually worked reliably in testing.
    page.wait_for_timeout(6000)


def _navigate_calendar_to_month(page, header_locator, next_arrow, prev_arrow, target_date):
    """Click a calendar's prev/next month arrow until its header shows
    the target month - permalinks can default to a different month than
    the monitoring's own period, and a day-of-month cell only exists in
    whatever month the calendar currently has displayed."""
    target_label = f"{_MONTH_NAMES[target_date.month - 1]} {target_date.year}"
    for _ in range(36):  # hard cap so a parsing miss can't loop forever
        current_label = header_locator.inner_text().strip()
        if current_label == target_label:
            return
        match = _MONTH_LABEL_RE.match(current_label)
        if not match:
            raise WeboramaFetchError(f'Не удалось распознать заголовок календаря: "{current_label}"')
        current_month = _MONTH_NAMES.index(match.group(1)) + 1
        current_year = int(match.group(2))
        if (target_date.year, target_date.month) > (current_year, current_month):
            next_arrow.click()
        else:
            prev_arrow.click()
        page.wait_for_timeout(300)
    raise WeboramaFetchError(f'Не удалось долистать календарь до {target_label}')


def _click_calendar_day(calendar_locator, day):
    # Exact match on day number, excluding the grayed-out cells that
    # belong to the previous/next month's preview days in the same grid -
    # a plain has-text("1") would also match "31", "21", etc. as substrings.
    cell = calendar_locator.locator(
        'td:not(.x-datepicker-prevday):not(.x-datepicker-nextday)',
        has_text=re.compile(rf'^{day}$')
    )
    first = cell.first
    # A disabled cell (e.g. Start > current End, or vice versa) silently
    # ignores clicks instead of erroring - catching it here turns a wrong,
    # unnoticed date range into a loud failure instead.
    class_attr = first.get_attribute('class') or ''
    if 'disabled' in class_attr:
        raise WeboramaFetchError(f'День {day} недоступен для выбора в календаре пермалинка (disabled)')
    first.click()


def _read_grid_rows(page):
    """Read the per-row table (Insertions, or Sites/Offers for permalinks
    with no separate Insertions tab) straight from the ExtJS grid's DOM
    instead of scraping flattened page text. The grid always lists the
    row name first, then Impressions, then Clicks, as the first three
    cells after the row-checkbox column - true for both the Insertions
    shape and every Sites/Offers variant seen so far (they differ only
    in how many extra metric columns follow), so reading by fixed
    position avoids having to guess a per-shape column count.

    Returns a dict keyed by the exact row name as shown in Weborama
    -> {'impressions': int, 'clicks': int, 'insertion_name': str, 'format_guess': 'banner'|'video'|None}
    """
    rows = page.locator('.x-grid-data-row')
    row_count = rows.count()
    if row_count == 0:
        raise WeboramaFetchError('Не нашлась таблица Insertions или Sites/Offers на странице - возможно, нет данных за этот период')

    results = {}
    for i in range(row_count):
        cells = rows.nth(i).locator('.x-grid-cell')
        if cells.count() < 4:
            continue
        name = cells.nth(1).inner_text().strip()
        if not name or name in ('Total', 'Plot selected rows'):
            continue
        impressions = _parse_number(cells.nth(2).inner_text())
        clicks = _parse_number(cells.nth(3).inner_text())

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
