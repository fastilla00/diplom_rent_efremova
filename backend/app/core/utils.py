# EcomProfit Guard — utils
import re


def spreadsheet_id_from_url(url: str) -> str | None:
    """Извлекает идентификатор Google Sheets из URL вида `.../spreadsheets/d/<ID>/...`."""
    if not url or not url.strip():
        return None
    # https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit...
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", url.strip())
    return m.group(1) if m else None
