# CVS Coupon Strategy Builder

Automatically clips every available digital coupon to your CVS ExtraCare card,
scrapes the week's specials, then generates an HTML report showing the best
deal per item — including regular price, sale price, coupon discount, final
price, and total estimated savings.

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Set up credentials

```bash
cp .env.example .env
# Edit .env and fill in CVS_EMAIL and CVS_PASSWORD
```

### 3. Run

```bash
python main.py --open
```

The `--open` flag automatically opens the report in your browser when done.

---

## Options

| Flag | Default | Description |
|---|---|---|
| `--report-path FILE` | `cvs_coupon_report.html` | Output path for the HTML report |
| `--headless` | on | Run browser invisibly |
| `--no-headless` | — | Show the browser window |
| `--no-clip` | off | Skip clipping (analyse already-clipped coupons) |
| `--deals-only` | off | Only scrape weekly deals, skip coupon clipping |
| `--open` | off | Open the report in your browser when done |
| `--save-json FILE` | — | Also save raw data as JSON |
| `--verbose` | off | Enable debug logging |

### Examples

```bash
# Headless run, open report automatically
python main.py --open

# Show the browser while it runs (good for debugging)
python main.py --no-headless

# Only look at weekly deals without logging in
python main.py --deals-only --open

# Save raw data for custom analysis
python main.py --save-json strategy.json --open
```

---

## Project Structure

```
cvs-coupons/
├── main.py             # Entry point & CLI
├── coupon_clipper.py   # Logs in and clips all digital coupons
├── weekly_specials.py  # Scrapes the CVS weekly ad (list view)
├── strategy.py         # Matches coupons to deals, computes prices
├── report.py           # Generates the HTML report
├── requirements.txt
├── .env.example        # Credential template
├── .gitignore
└── README.md
```

---

## HTML Report Contents

- **Summary banner** — total savings, final total, coupons clipped
- **Best Deals** — items where a weekly sale AND a clipped coupon both apply
- **Sale + Coupon table** — sortable table of all matched items
- **Weekly Sales table** — all weekly deals (even without a coupon)
- **Coupon-only section** — clipped coupons that have no current weekly deal

---

## Notes

- Credentials are stored only in your local `.env` file and are never committed.
- The tool respects the CVS site by adding small delays between actions (`slow_mo`).
- CVS may change their website markup at any time; if scraping breaks, the
  selectors in `coupon_clipper.py` and `weekly_specials.py` may need updating.
- This tool is for **personal use only**. Do not use it for commercial purposes
  or in ways that violate CVS's Terms of Service.
