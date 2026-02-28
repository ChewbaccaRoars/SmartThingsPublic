"""
strategy.py
-----------
Cross-references clipped coupons against weekly-ad deals and computes
the best final price for each item.

Output — a list of StrategyItem dicts:
    {
        "name":             str,
        "description":      str,
        "category":         str,
        "regular_price":    float | None,   # shelf price
        "sale_price":       float | None,   # weekly-ad sale price (pre-coupon)
        "coupon_discount":  float | None,   # dollar value of applied coupon
        "final_price":      float | None,   # sale_price − coupon_discount
        "savings":          float | None,   # regular_price − final_price
        "savings_pct":      float | None,   # savings / regular_price * 100
        "sale_label":       str,
        "deal_type":        str,
        "coupon_title":     str,            # "" if no coupon matched
        "coupon_discount_label": str,       # e.g. "$2.00 off" or ""
        "has_coupon":       bool,
        "has_sale":         bool,
        "valid_thru":       str,
        "image_url":        str | None,
        "match_reason":     str,            # how the coupon↔deal match was found
    }

Also returns a summary dict:
    {
        "total_items":           int,
        "items_with_deals":      int,
        "items_with_coupons":    int,
        "items_with_both":       int,
        "estimated_regular_total": float,
        "estimated_sale_total":    float,
        "estimated_final_total":   float,
        "estimated_total_savings": float,
        "coupons_clipped":        int,
    }
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def build_strategy(
    coupons: list[dict],
    deals: list[dict],
) -> tuple[list[dict], dict]:
    """
    Match coupons to weekly-ad deals and compute final prices.

    Args:
        coupons: Output of coupon_clipper.clip_all_coupons()
        deals:   Output of weekly_specials.fetch_weekly_specials()

    Returns:
        (strategy_items, summary)
    """
    strategy_items = []

    for deal in deals:
        matched_coupon, match_reason = _find_best_coupon(deal, coupons)
        item = _compute_item(deal, matched_coupon, match_reason)
        strategy_items.append(item)

    # Also surface coupons that have no matching weekly-ad deal
    # (still clipped and available for regular-priced items)
    deal_names_lower = {d["name"].lower() for d in deals}
    orphan_coupons = [
        c for c in coupons
        if not _name_matches_any(c.get("title", ""), deal_names_lower)
    ]
    for coupon in orphan_coupons:
        item = _coupon_only_item(coupon)
        strategy_items.append(item)

    # Sort: highest savings first, then items with both a sale AND a coupon
    strategy_items.sort(
        key=lambda x: (
            -(x["has_sale"] and x["has_coupon"]),   # both = top priority
            -(x["savings"] or 0),
        )
    )

    summary = _build_summary(strategy_items, coupons)

    logger.info(
        "Strategy built: %d items, %d with coupons, est. savings $%.2f",
        summary["total_items"],
        summary["items_with_coupons"],
        summary["estimated_total_savings"],
    )
    return strategy_items, summary


# ---------------------------------------------------------------------------
# Matching logic
# ---------------------------------------------------------------------------

def _find_best_coupon(deal: dict, coupons: list[dict]) -> tuple[Optional[dict], str]:
    """
    Return the coupon that best matches this deal item, plus a reason string.
    Priority:
      1. Exact brand/product name match (case-insensitive)
      2. Partial word overlap (≥2 significant words in common)
      3. Category match
    """
    deal_name = deal.get("name", "").lower()
    deal_desc = deal.get("description", "").lower()
    deal_cat = deal.get("category", "").lower()
    deal_words = _significant_words(deal_name + " " + deal_desc)

    best_coupon = None
    best_score = 0
    best_reason = ""

    for coupon in coupons:
        coupon_text = (
            coupon.get("title", "") + " "
            + coupon.get("description", "") + " "
            + coupon.get("brand", "")
        ).lower()

        # 1. Direct name substring
        if deal_name and deal_name in coupon_text:
            score = 100
            reason = "exact name match"
        elif coupon.get("brand", "").lower() in deal_name and coupon.get("brand"):
            score = 90
            reason = "brand match"
        else:
            # 2. Word overlap
            coupon_words = _significant_words(coupon_text)
            overlap = deal_words & coupon_words
            score = len(overlap) * 10
            reason = f"keyword overlap ({', '.join(sorted(overlap))})" if overlap else ""

        # 3. Category bonus
        coupon_cat = coupon.get("category", "").lower()
        if deal_cat and coupon_cat and (deal_cat in coupon_cat or coupon_cat in deal_cat):
            score += 5
            reason = reason or "category match"

        if score > best_score:
            best_score = score
            best_coupon = coupon
            best_reason = reason

    # Require a minimum match quality
    if best_score < 10:
        return None, ""

    return best_coupon, best_reason


def _significant_words(text: str) -> set[str]:
    """Return meaningful words (length ≥ 4, not stop words) from text."""
    stop = {
        "with", "from", "that", "this", "each", "your", "have",
        "been", "will", "also", "more", "than", "when", "only",
        "pack", "size", "item", "count", "ounce", "fluid",
    }
    words = re.findall(r"[a-z]{4,}", text.lower())
    return {w for w in words if w not in stop}


def _name_matches_any(name: str, name_set: set[str]) -> bool:
    """Check if a coupon title has meaningful overlap with any deal name."""
    words = _significant_words(name)
    for deal_name in name_set:
        deal_words = _significant_words(deal_name)
        if words & deal_words:
            return True
    return False


# ---------------------------------------------------------------------------
# Price computation
# ---------------------------------------------------------------------------

def _compute_item(deal: dict, coupon: Optional[dict], match_reason: str) -> dict:
    """Build a StrategyItem dict from a deal and an optional matched coupon."""
    regular_price = deal.get("regular_price")
    sale_price = deal.get("sale_price")

    # Extract numeric coupon discount
    coupon_discount: Optional[float] = None
    coupon_discount_label = ""
    if coupon:
        coupon_discount, coupon_discount_label = _parse_coupon_value(
            coupon.get("discount", "") or coupon.get("title", "")
        )

    # Compute effective price after coupon
    base_price = sale_price if sale_price is not None else regular_price
    if base_price is not None and coupon_discount is not None:
        final_price = max(0.0, round(base_price - coupon_discount, 2))
    else:
        final_price = base_price  # no coupon or no price info

    # Savings = difference from regular shelf price to final price
    savings: Optional[float] = None
    if regular_price is not None and final_price is not None:
        savings = round(regular_price - final_price, 2)

    savings_pct: Optional[float] = None
    if regular_price and savings is not None and regular_price > 0:
        savings_pct = round(savings / regular_price * 100, 1)

    return {
        "name": deal.get("name", ""),
        "description": deal.get("description", ""),
        "category": deal.get("category", ""),
        "regular_price": regular_price,
        "sale_price": sale_price,
        "coupon_discount": coupon_discount,
        "final_price": final_price,
        "savings": savings,
        "savings_pct": savings_pct,
        "sale_label": deal.get("sale_label", ""),
        "deal_type": deal.get("deal_type", ""),
        "coupon_title": coupon.get("title", "") if coupon else "",
        "coupon_discount_label": coupon_discount_label,
        "has_coupon": coupon is not None,
        "has_sale": sale_price is not None,
        "valid_thru": deal.get("valid_thru", ""),
        "image_url": deal.get("image_url"),
        "match_reason": match_reason,
    }


def _coupon_only_item(coupon: dict) -> dict:
    """Build a StrategyItem for a coupon that has no matching weekly-ad deal."""
    coupon_discount, coupon_discount_label = _parse_coupon_value(
        coupon.get("discount", "") or coupon.get("title", "")
    )
    return {
        "name": coupon.get("title", coupon.get("brand", "Unknown")),
        "description": coupon.get("description", ""),
        "category": coupon.get("category", ""),
        "regular_price": None,
        "sale_price": None,
        "coupon_discount": coupon_discount,
        "final_price": None,
        "savings": coupon_discount,          # savings = coupon value itself
        "savings_pct": None,
        "sale_label": "",
        "deal_type": "COUPON_ONLY",
        "coupon_title": coupon.get("title", ""),
        "coupon_discount_label": coupon_discount_label,
        "has_coupon": True,
        "has_sale": False,
        "valid_thru": coupon.get("expires", ""),
        "image_url": None,
        "match_reason": "coupon only (no weekly deal)",
    }


def _parse_coupon_value(text: str) -> tuple[Optional[float], str]:
    """
    Extract a dollar-off value from coupon text.

    Handles:
        "$2.00 off"      → (2.00, "$2.00 off")
        "Save $1.50"     → (1.50, "Save $1.50")
        "50¢ off"        → (0.50, "50¢ off")
        "BOGO"           → (None, "BOGO")
        "Buy 2 Get 1"    → (None, "Buy 2 Get 1 Free")
    """
    # Dollar-off patterns
    dollar_match = re.search(
        r"(?:save\s*)?\$\s*(\d+(?:\.\d{1,2})?)\s*(?:off|each)?",
        text,
        re.IGNORECASE,
    )
    if dollar_match:
        val = float(dollar_match.group(1))
        return val, text.strip()

    # Cents-off
    cents_match = re.search(r"(\d+)\s*[¢c]\s*off", text, re.IGNORECASE)
    if cents_match:
        val = float(cents_match.group(1)) / 100
        return val, text.strip()

    # % off — convert to None (we can't apply without a price)
    pct_match = re.search(r"(\d+)\s*%\s*off", text, re.IGNORECASE)
    if pct_match:
        # Store as a negative sentinel so callers know it's percentage-based
        return None, text.strip()

    return None, text.strip() if text.strip() else ""


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def _build_summary(items: list[dict], coupons: list[dict]) -> dict:
    items_with_deals = sum(1 for i in items if i["has_sale"])
    items_with_coupons = sum(1 for i in items if i["has_coupon"])
    items_with_both = sum(1 for i in items if i["has_sale"] and i["has_coupon"])

    priced_items = [i for i in items if i["final_price"] is not None]
    regular_priced = [i for i in items if i["regular_price"] is not None]

    estimated_regular_total = sum(
        i["regular_price"] for i in regular_priced if i["regular_price"]
    )
    estimated_sale_total = sum(
        i["sale_price"] for i in priced_items if i["sale_price"]
    )
    estimated_final_total = sum(
        i["final_price"] for i in priced_items if i["final_price"]
    )
    estimated_total_savings = round(
        estimated_regular_total - estimated_final_total, 2
    ) if estimated_regular_total else 0.0

    return {
        "total_items": len(items),
        "items_with_deals": items_with_deals,
        "items_with_coupons": items_with_coupons,
        "items_with_both": items_with_both,
        "estimated_regular_total": round(estimated_regular_total, 2),
        "estimated_sale_total": round(estimated_sale_total, 2),
        "estimated_final_total": round(estimated_final_total, 2),
        "estimated_total_savings": estimated_total_savings,
        "coupons_clipped": len(coupons),
    }
