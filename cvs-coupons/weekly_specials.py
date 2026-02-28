"""
weekly_specials.py
------------------
Scrapes the CVS Weekly Ad (list view) and returns structured deal data.

Returns a list of dicts:
    {
        "name":          str,   # product name
        "description":   str,   # full product details / size / quantity
        "regular_price": float | None,
        "sale_price":    float | None,
        "sale_label":    str,   # e.g. "2/$5", "Buy 2 Get 1 Free", "$3.99"
        "deal_type":     str,   # "SALE" | "BOGO" | "MULTI_BUY" | "EXTRACARE" | "OTHER"
        "category":      str,
        "valid_thru":    str,   # date range text from the ad
        "image_url":     str | None,
    }
"""

import logging
import re
from typing import Optional

from playwright.sync_api import Page, sync_playwright

logger = logging.getLogger(__name__)

CVS_WEEKLY_AD_URL = "https://www.cvs.com/weekly-ad"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def fetch_weekly_specials(
    headless: bool = True,
    slow_mo: int = 200,
    timeout: int = 30_000,
) -> list[dict]:
    """
    Open the CVS weekly ad in list view and scrape all deal items.

    Authentication is NOT required to view the weekly ad.

    Args:
        headless:  Run browser without a visible window when True
        slow_mo:   Milliseconds to slow Playwright actions
        timeout:   Default timeout in ms

    Returns:
        List of deal dicts.
    """
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless, slow_mo=slow_mo)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )
        page = context.new_page()
        page.set_default_timeout(timeout)

        try:
            deals = _scrape_weekly_ad(page)
        finally:
            browser.close()

    logger.info("Weekly specials fetched. Total deals: %d", len(deals))
    return deals


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _scrape_weekly_ad(page: Page) -> list[dict]:
    """Navigate to the weekly ad and extract all deal items."""
    logger.info("Loading CVS weekly ad…")
    page.goto(CVS_WEEKLY_AD_URL, wait_until="networkidle")

    _dismiss_overlays(page)
    _switch_to_list_view(page)
    _load_all_deals(page)

    return _parse_deals(page)


def _switch_to_list_view(page: Page) -> None:
    """
    CVS weekly ad has both a circular (image) view and a list view.
    Prefer the list view — it's easier to scrape and contains structured text.
    """
    list_view_selectors = [
        'button:has-text("List View")',
        'button[aria-label*="list" i]',
        '[data-testid="list-view-btn"]',
        'button[title*="List"]',
        'a:has-text("List View")',
    ]
    for sel in list_view_selectors:
        try:
            btn = page.query_selector(sel)
            if btn and btn.is_visible():
                btn.click()
                page.wait_for_timeout(1_500)
                logger.debug("Switched to list view.")
                return
        except Exception:  # noqa: BLE001
            pass
    logger.debug("Could not find a list-view toggle; continuing with default view.")


def _load_all_deals(page: Page) -> None:
    """Scroll and click 'Load More' until all deals are visible."""
    previous_count = 0
    stall_rounds = 0

    while stall_rounds < 4:
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1_200)

        load_more = page.query_selector(
            'button:has-text("Load More"), '
            'button:has-text("See More"), '
            'button:has-text("Show More"), '
            'a:has-text("Load More")'
        )
        if load_more and load_more.is_visible():
            load_more.click()
            page.wait_for_timeout(2_000)

        # Count any deal card we can find
        current_count = len(
            page.query_selector_all(
                '[class*="deal-card"], [class*="DealCard"], '
                '[class*="weekly-ad-item"], [class*="product-card"], '
                '[class*="ad-item"], [data-testid*="deal"]'
            )
        )
        if current_count == previous_count:
            stall_rounds += 1
        else:
            stall_rounds = 0
            previous_count = current_count
            logger.debug("Loaded %d deal cards so far…", current_count)


def _parse_deals(page: Page) -> list[dict]:
    """Extract deal data from all cards in the current page DOM."""
    card_selectors = [
        '[class*="deal-card"]',
        '[class*="DealCard"]',
        '[class*="weekly-ad-item"]',
        '[class*="ad-item"]',
        '[class*="product-card"]',
        '[data-testid*="deal"]',
        '[data-testid*="product"]',
    ]

    cards = []
    for sel in card_selectors:
        found = page.query_selector_all(sel)
        if found:
            cards = found
            logger.debug(
                "Matched %d deal cards with selector: %s", len(found), sel
            )
            break

    if not cards:
        logger.warning(
            "No deal cards found. CVS may have changed their markup. "
            "Attempting full-page text fallback…"
        )
        return _fallback_parse(page)

    deals = []
    valid_thru = _extract_valid_dates(page)

    for card in cards:
        try:
            deal = _extract_deal_data(card, valid_thru)
            deals.append(deal)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Skipping a deal card: %s", exc)

    return deals


def _extract_deal_data(card, valid_thru: str) -> dict:
    """Pull fields from a single deal card element."""

    def text(selector: str) -> str:
        el = card.query_selector(selector)
        return el.inner_text().strip() if el else ""

    name = (
        text('[class*="product-name"]')
        or text('[class*="item-name"]')
        or text('[class*="title"]')
        or text('h3')
        or text('h4')
        or text('strong')
        or ""
    )

    description = (
        text('[class*="description"]')
        or text('[class*="details"]')
        or text('p')
        or ""
    )

    # Sale label is often rendered as the big promo text
    sale_label = (
        text('[class*="price-label"]')
        or text('[class*="promo-price"]')
        or text('[class*="deal-price"]')
        or text('[class*="sale-price"]')
        or text('[class*="price"]')
        or ""
    )

    category = text('[class*="category"]') or text('[class*="tag"]') or ""

    # Try to grab the product image src
    img_el = card.query_selector("img")
    image_url = img_el.get_attribute("src") if img_el else None

    regular_price, sale_price = _parse_prices(sale_label, card)
    deal_type = _classify_deal(sale_label)

    return {
        "name": name,
        "description": description,
        "regular_price": regular_price,
        "sale_price": sale_price,
        "sale_label": sale_label,
        "deal_type": deal_type,
        "category": category,
        "valid_thru": valid_thru,
        "image_url": image_url,
    }


def _parse_prices(sale_label: str, card) -> tuple[Optional[float], Optional[float]]:
    """
    Attempt to extract numeric regular and sale prices from text.

    Handles patterns like:
        "$3.99"           → (None, 3.99)
        "2 for $5"        → (None, 2.50)   (per-unit estimate)
        "Was $5.99 $2.99" → (5.99, 2.99)
        "BOGO"            → (None, None)
    """
    regular_price: Optional[float] = None
    sale_price: Optional[float] = None

    # Look for a "was" / "regular" / "original" price
    was_match = re.search(
        r"(?:was|reg(?:ular)?|orig(?:inal)?)[:\s]*\$?\s*(\d+(?:\.\d{1,2})?)",
        sale_label,
        re.IGNORECASE,
    )
    if was_match:
        regular_price = float(was_match.group(1))

    # Try from a dedicated element on the card
    if regular_price is None:
        def text(sel: str) -> str:
            el = card.query_selector(sel)
            return el.inner_text().strip() if el else ""

        reg_text = (
            text('[class*="regular-price"]')
            or text('[class*="original-price"]')
            or text('[class*="was-price"]')
        )
        if reg_text:
            m = re.search(r"\$?\s*(\d+(?:\.\d{1,2})?)", reg_text)
            if m:
                regular_price = float(m.group(1))

    # Extract sale price
    # "2 for $5" → per-unit $2.50
    multi_match = re.search(
        r"(\d+)\s+(?:for|\/)\s+\$?\s*(\d+(?:\.\d{1,2})?)", sale_label, re.IGNORECASE
    )
    if multi_match:
        qty = int(multi_match.group(1))
        total = float(multi_match.group(2))
        sale_price = round(total / qty, 2)
    else:
        # Simple single price
        price_matches = re.findall(r"\$?\s*(\d+(?:\.\d{1,2})?)", sale_label)
        prices = [float(p) for p in price_matches if float(p) > 0]
        if prices:
            # If we already have a regular price, the smaller one is sale
            if regular_price and len(prices) > 1:
                sale_price = min(prices)
            elif prices:
                sale_price = prices[-1]  # last price tends to be the sale price

    return regular_price, sale_price


def _classify_deal(label: str) -> str:
    """Return a deal-type category based on the promo label text."""
    label_lower = label.lower()
    if any(k in label_lower for k in ("bogo", "buy one", "buy 1", "b1g1")):
        return "BOGO"
    if any(k in label_lower for k in ("for $", "/$", " for only", "/2", "/3")):
        return "MULTI_BUY"
    if "extracare" in label_lower or "extra care" in label_lower:
        return "EXTRACARE"
    if re.search(r"\$\d", label):
        return "SALE"
    return "OTHER"


def _extract_valid_dates(page: Page) -> str:
    """Try to find the weekly-ad validity date range from the page header."""
    selectors = [
        '[class*="valid-date"]',
        '[class*="ad-date"]',
        '[class*="date-range"]',
        '[class*="valid-thru"]',
        'span:has-text("Valid")',
        'p:has-text("Valid")',
    ]
    for sel in selectors:
        el = page.query_selector(sel)
        if el:
            return el.inner_text().strip()
    return ""


def _fallback_parse(page: Page) -> list[dict]:
    """
    If structured selectors find nothing, parse the full page text
    looking for price patterns. Returns a minimal deal list.
    This is a last-resort heuristic.
    """
    logger.warning("Using fallback text parser — results may be incomplete.")
    deals = []
    paragraphs = page.query_selector_all("p, li, span")
    current = {}

    price_re = re.compile(r"\$\s*\d+(?:\.\d{1,2})?")

    for el in paragraphs:
        txt = el.inner_text().strip()
        if not txt or len(txt) > 300:
            continue

        if price_re.search(txt):
            # Treat as a potential deal line
            _, sale_price = _parse_prices(txt, el)
            deals.append({
                "name": txt[:80],
                "description": txt,
                "regular_price": None,
                "sale_price": sale_price,
                "sale_label": txt,
                "deal_type": _classify_deal(txt),
                "category": "",
                "valid_thru": "",
                "image_url": None,
            })

    return deals


def _dismiss_overlays(page: Page) -> None:
    """Attempt to close cookie / promo modals."""
    selectors = [
        'button:has-text("Accept")',
        'button:has-text("Accept All")',
        'button:has-text("Got It")',
        'button:has-text("Close")',
        'button[aria-label="Close"]',
    ]
    for sel in selectors:
        try:
            btn = page.query_selector(sel)
            if btn and btn.is_visible():
                btn.click()
                page.wait_for_timeout(500)
        except Exception:  # noqa: BLE001
            pass
