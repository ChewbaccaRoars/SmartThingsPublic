"""
main.py
-------
Orchestrates the full CVS coupon strategy pipeline:

  1. Clip all digital coupons to your ExtraCare card
  2. Scrape the weekly specials (list view)
  3. Cross-reference to find the best deal per item
  4. Generate an HTML report

Usage:
    python main.py [--report-path OUTPUT.html] [--headless] [--no-clip] [--deals-only]

Environment variables (set in .env or export manually):
    CVS_EMAIL     – your CVS.com account email
    CVS_PASSWORD  – your CVS.com account password
"""

import argparse
import json
import logging
import os
import sys
import webbrowser
from pathlib import Path

from dotenv import load_dotenv

from coupon_clipper import clip_all_coupons
from weekly_specials import fetch_weekly_specials
from strategy import build_strategy
from report import generate_html_report

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="CVS coupon strategy — clip, scan, and optimise your savings.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--report-path",
        default="cvs_coupon_report.html",
        metavar="FILE",
        help="Output HTML report path (default: cvs_coupon_report.html)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=True,
        help="Run the browser in headless mode (default: True)",
    )
    parser.add_argument(
        "--no-headless",
        dest="headless",
        action="store_false",
        help="Show the browser window while running",
    )
    parser.add_argument(
        "--no-clip",
        action="store_true",
        default=False,
        help="Skip coupon clipping (use already-clipped coupons only)",
    )
    parser.add_argument(
        "--deals-only",
        action="store_true",
        default=False,
        help="Only scrape weekly deals — skip coupon clipping entirely",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        default=False,
        help="Open the HTML report in your default browser when done",
    )
    parser.add_argument(
        "--save-json",
        metavar="FILE",
        default=None,
        help="Also save raw strategy data as a JSON file",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Enable debug-level logging",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------

def load_credentials() -> tuple[str, str]:
    """
    Load CVS account credentials from environment / .env file.
    Prompts the user if not found.
    """
    load_dotenv()

    email = os.getenv("CVS_EMAIL", "").strip()
    password = os.getenv("CVS_PASSWORD", "").strip()

    if not email:
        email = input("CVS account email: ").strip()
    if not password:
        import getpass
        password = getpass.getpass("CVS account password: ")

    if not email or not password:
        logger.error("CVS credentials are required. Set CVS_EMAIL and CVS_PASSWORD in .env")
        sys.exit(1)

    return email, password


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    print()
    print("=" * 60)
    print("  CVS Coupon Strategy Builder")
    print("=" * 60)
    print()

    # ── Step 1: Clip coupons ────────────────────────────────────────────────
    coupons: list[dict] = []

    if args.deals_only:
        logger.info("--deals-only flag set. Skipping coupon clipping.")
    else:
        email, password = load_credentials()
        logger.info("Step 1/3 — Clipping all available coupons…")
        try:
            coupons = clip_all_coupons(
                email=email,
                password=password,
                headless=args.headless,
            )
            # Strip internal-only keys before storing
            for c in coupons:
                c.pop("_clip_button", None)
            logger.info("  Done. %d coupons clipped/found.", len(coupons))
        except Exception as exc:
            logger.error("Coupon clipping failed: %s", exc)
            logger.warning("Continuing with 0 coupons — deals-only mode.")

    # ── Step 2: Fetch weekly specials ───────────────────────────────────────
    logger.info("Step 2/3 — Fetching weekly specials…")
    try:
        deals = fetch_weekly_specials(headless=args.headless)
        logger.info("  Done. %d weekly deals found.", len(deals))
    except Exception as exc:
        logger.error("Failed to fetch weekly specials: %s", exc)
        sys.exit(1)

    # ── Step 3: Build strategy ──────────────────────────────────────────────
    logger.info("Step 3/3 — Computing best coupon strategy…")
    strategy_items, summary = build_strategy(coupons, deals)

    # ── Print summary to terminal ───────────────────────────────────────────
    print()
    print("  RESULTS SUMMARY")
    print("  " + "-" * 40)
    print(f"  Total items analysed:       {summary['total_items']}")
    print(f"  Items with a weekly deal:   {summary['items_with_deals']}")
    print(f"  Items with a coupon:        {summary['items_with_coupons']}")
    print(f"  Items with BOTH:            {summary['items_with_both']}")
    print()
    print(f"  Regular price total:        ${summary['estimated_regular_total']:.2f}")
    print(f"  After sale prices:          ${summary['estimated_sale_total']:.2f}")
    print(f"  After coupons (FINAL):      ${summary['estimated_final_total']:.2f}")
    print(f"  Estimated savings:          ${summary['estimated_total_savings']:.2f}")
    print()

    # Print top 10 best deals
    best = [i for i in strategy_items if i["has_sale"] and i["has_coupon"]]
    if best:
        print("  TOP DEALS (sale + coupon):")
        print("  " + "-" * 40)
        for item in best[:10]:
            final = f"${item['final_price']:.2f}" if item["final_price"] is not None else "N/A"
            savings = f"(save ${item['savings']:.2f})" if item["savings"] else ""
            print(f"  • {item['name'][:45]:<45}  {final}  {savings}")
        print()

    # ── Generate HTML report ────────────────────────────────────────────────
    report_path = generate_html_report(
        strategy_items=strategy_items,
        summary=summary,
        output_path=args.report_path,
    )
    print(f"  HTML report saved to: {report_path}")

    # ── Optionally save JSON ────────────────────────────────────────────────
    if args.save_json:
        json_path = os.path.abspath(args.save_json)
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(
                {"summary": summary, "items": strategy_items, "coupons": coupons},
                fh,
                indent=2,
                default=str,
            )
        print(f"  JSON data saved to:   {json_path}")

    # ── Optionally open report ──────────────────────────────────────────────
    if args.open:
        webbrowser.open(f"file://{report_path}")

    print()
    print("  Done! Happy savings.")
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()
