"""
coupon_clipper.py
-----------------
Logs in to cvs.com and clips every available digital coupon
to the ExtraCare card on the account.

Returns a list of dicts describing each clipped coupon:
    {
        "title":       str,   # coupon headline
        "description": str,   # full coupon details
        "discount":    str,   # e.g. "$2.00 off" or "BOGO"
        "brand":       str,
        "expires":     str,   # raw expiry text from page
        "category":    str,
        "already_clipped": bool,  # True if it was clipped before we ran
    }
"""

import logging
import os
import re
import time
from typing import Optional

from playwright.sync_api import Page, sync_playwright

logger = logging.getLogger(__name__)

CVS_LOGIN_URL = "https://www.cvs.com/account/login/index.jsp"
CVS_COUPONS_URL = "https://www.cvs.com/extracare/couponCenter.jsp"
CVS_COUPONS_ALT_URL = "https://www.cvs.com/account/coupons"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def clip_all_coupons(
    email: str,
    password: str,
    headless: bool = True,
    slow_mo: int = 300,
    timeout: int = 30_000,
) -> list[dict]:
    """
    Launch a browser, log in, and clip every unclipped coupon.

    Args:
        email:     CVS account email address (from .env)
        password:  CVS account password (from .env)
        headless:  Run browser without a visible window when True
        slow_mo:   Milliseconds to slow Playwright actions (be polite to server)
        timeout:   Default navigation/selector timeout in ms

    Returns:
        List of coupon dicts (clipped + already-clipped).
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
            _login(page, email, password)
            coupons = _collect_and_clip(page)
        finally:
            browser.close()

    logger.info("Coupon clipping complete. Total coupons found: %d", len(coupons))
    return coupons


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _login(page: Page, email: str, password: str) -> None:
    """Navigate to CVS login page and authenticate."""
    logger.info("Navigating to CVS login page…")
    page.goto(CVS_LOGIN_URL, wait_until="networkidle")

    # Dismiss cookie/GDPR banners if present
    _dismiss_overlays(page)

    # Fill credentials
    page.fill('input[id="LoginId"], input[name="LoginId"], input[type="email"]', email)
    page.fill('input[id="password"], input[name="password"], input[type="password"]', password)

    # Click sign-in button
    page.click(
        'button[type="submit"], '
        'input[type="submit"], '
        'button:has-text("Sign In"), '
        'button:has-text("Log In")'
    )

    # Wait until we land somewhere other than the login page
    page.wait_for_url(re.compile(r"(?!.*login).*cvs\.com.*"), timeout=20_000)
    logger.info("Login successful.")


def _collect_and_clip(page: Page) -> list[dict]:
    """Go to the coupon centre, load all coupons, and clip each one."""
    logger.info("Navigating to coupon centre…")
    page.goto(CVS_COUPONS_URL, wait_until="networkidle")

    # If the direct URL redirects to something else, try the alternative
    if "coupon" not in page.url.lower() and "extracare" not in page.url.lower():
        logger.info("Trying alternate coupon URL…")
        page.goto(CVS_COUPONS_ALT_URL, wait_until="networkidle")

    _dismiss_overlays(page)
    _load_all_coupons(page)

    coupons = _parse_coupons(page)
    logger.info("Found %d total coupons on page.", len(coupons))

    clipped_count = 0
    already_clipped = 0
    for coupon in coupons:
        if coupon["already_clipped"]:
            already_clipped += 1
        else:
            _click_clip_button(page, coupon["_clip_button"])
            clipped_count += 1
            # Be polite — small random-ish delay between clips
            time.sleep(0.4 + (clipped_count % 3) * 0.2)

    logger.info(
        "Clipped %d new coupons. %d were already clipped.",
        clipped_count,
        already_clipped,
    )
    return coupons


def _load_all_coupons(page: Page) -> None:
    """
    Scroll and click "Load More" until every coupon is visible.
    CVS lazy-loads coupons as the user scrolls.
    """
    previous_count = 0
    stall_rounds = 0

    while stall_rounds < 3:
        # Scroll to bottom
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1_500)

        # Click any "Load More" / "See More" button
        load_more = page.query_selector(
            'button:has-text("Load More"), '
            'button:has-text("See More"), '
            'button:has-text("Show More"), '
            'a:has-text("Load More")'
        )
        if load_more and load_more.is_visible():
            load_more.click()
            page.wait_for_timeout(2_000)

        current_count = len(
            page.query_selector_all(
                '[class*="coupon-card"], [class*="CouponCard"], '
                '[data-testid*="coupon"], [class*="coupon-tile"]'
            )
        )
        if current_count == previous_count:
            stall_rounds += 1
        else:
            stall_rounds = 0
            previous_count = current_count
            logger.debug("Loaded %d coupons so far…", current_count)


def _parse_coupons(page: Page) -> list[dict]:
    """
    Extract coupon metadata from all loaded coupon cards on the page.
    Returns a list of dicts including a reference to the clip button element.
    """
    # Try several common selectors CVS has used across site redesigns
    card_selectors = [
        '[class*="coupon-card"]',
        '[class*="CouponCard"]',
        '[data-testid*="coupon"]',
        '[class*="coupon-tile"]',
        '[class*="coupon-item"]',
        '.coupon',
    ]

    cards = []
    for sel in card_selectors:
        found = page.query_selector_all(sel)
        if found:
            cards = found
            logger.debug("Matched %d coupon cards with selector: %s", len(found), sel)
            break

    if not cards:
        logger.warning("No coupon cards found. CVS may have changed their markup.")
        return []

    coupons = []
    for card in cards:
        try:
            coupon = _extract_coupon_data(card)
            coupons.append(coupon)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Skipping a card due to parse error: %s", exc)

    return coupons


def _extract_coupon_data(card) -> dict:
    """Pull text fields and clip button from a single coupon card element."""

    def text(selector: str) -> str:
        el = card.query_selector(selector)
        return el.inner_text().strip() if el else ""

    # Discount / headline — the big bold value (e.g. "$2.00 off", "BOGO")
    discount = (
        text('[class*="coupon-value"]')
        or text('[class*="coupon-discount"]')
        or text('[class*="savings"]')
        or text('[class*="headline"]')
        or text('strong')
        or text('h3')
        or text('h4')
        or ""
    )

    title = (
        text('[class*="coupon-title"]')
        or text('[class*="title"]')
        or text('h3')
        or text('h4')
        or text('p')
        or ""
    )

    description = (
        text('[class*="coupon-description"]')
        or text('[class*="description"]')
        or text('[class*="details"]')
        or text('p')
        or ""
    )

    brand = text('[class*="brand"]') or text('[class*="manufacturer"]') or ""
    expires = text('[class*="expir"]') or text('[class*="valid"]') or ""
    category = text('[class*="category"]') or text('[class*="tag"]') or ""

    # Determine whether already clipped
    clipped_button = card.query_selector(
        'button:has-text("Clipped"), '
        'button:has-text("Added"), '
        'button[disabled]:has-text("Clip"), '
        '[class*="clipped"]'
    )
    already_clipped = clipped_button is not None

    # Find the clip button (may not exist if already clipped)
    clip_button = None
    if not already_clipped:
        clip_button = card.query_selector(
            'button:has-text("Clip"), '
            'button:has-text("Add to Card"), '
            'button:has-text("Add Coupon"), '
            'button[aria-label*="clip" i], '
            'button[aria-label*="add" i]'
        )

    return {
        "title": title,
        "description": description,
        "discount": discount,
        "brand": brand,
        "expires": expires,
        "category": category,
        "already_clipped": already_clipped,
        "_clip_button": clip_button,  # internal — not in final output
    }


def _click_clip_button(page: Page, button) -> None:
    """Click a coupon clip button and wait for the UI confirmation."""
    if button is None:
        return
    try:
        button.scroll_into_view_if_needed()
        button.click()
        # Wait briefly for the button state to change (no hard assertion)
        page.wait_for_timeout(600)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Could not click clip button: %s", exc)


def _dismiss_overlays(page: Page) -> None:
    """Attempt to close common cookie consent / promo overlays."""
    overlay_selectors = [
        'button:has-text("Accept")',
        'button:has-text("Accept All")',
        'button:has-text("Got It")',
        'button:has-text("Close")',
        'button[aria-label="Close"]',
        '[id*="cookie"] button',
        '[class*="modal-close"]',
        '[class*="overlay-close"]',
    ]
    for sel in overlay_selectors:
        try:
            btn = page.query_selector(sel)
            if btn and btn.is_visible():
                btn.click()
                page.wait_for_timeout(500)
        except Exception:  # noqa: BLE001
            pass
