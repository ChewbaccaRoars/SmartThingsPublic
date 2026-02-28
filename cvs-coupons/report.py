"""
report.py
---------
Generates a self-contained HTML report summarising the CVS coupon strategy.

The report includes:
  - Summary banner (total items, savings, etc.)
  - Highlighted "best deals" section (items with both a sale AND a coupon)
  - Full sortable table of all strategy items
  - Coupon-only section (clipped coupons with no current weekly deal)
"""

import html
import os
from datetime import datetime
from typing import Optional


def generate_html_report(
    strategy_items: list[dict],
    summary: dict,
    output_path: str = "cvs_coupon_report.html",
) -> str:
    """
    Write the HTML report to *output_path* and return the file path.

    Args:
        strategy_items: Output of strategy.build_strategy()
        summary:        Summary dict from the same call
        output_path:    Where to save the report

    Returns:
        Absolute path to the written HTML file.
    """
    best_deals = [
        i for i in strategy_items if i["has_sale"] and i["has_coupon"]
    ]
    sale_only = [
        i for i in strategy_items if i["has_sale"] and not i["has_coupon"]
    ]
    coupon_only = [
        i for i in strategy_items if i["deal_type"] == "COUPON_ONLY"
    ]
    # Everything else — deals where we matched nothing special
    other_deals = [
        i for i in strategy_items
        if not (i["has_sale"] and i["has_coupon"])
        and i["deal_type"] != "COUPON_ONLY"
        and not (i["has_sale"] and not i["has_coupon"])
    ]

    generated_at = datetime.now().strftime("%B %d, %Y at %I:%M %p")

    html_content = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CVS Coupon Strategy Report</title>
<style>
  :root {{
    --red:    #cc0000;
    --dark:   #1a1a2e;
    --mid:    #2d2d44;
    --accent: #e94560;
    --green:  #00b894;
    --yellow: #fdcb6e;
    --text:   #f0f0f0;
    --muted:  #a0a0b0;
    --card:   #252540;
    --border: #3d3d5c;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: var(--dark);
    color: var(--text);
    line-height: 1.5;
  }}
  a {{ color: var(--accent); text-decoration: none; }}

  /* ── Header ── */
  header {{
    background: var(--red);
    padding: 24px 32px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 12px;
  }}
  header h1 {{ font-size: 1.8rem; letter-spacing: 1px; }}
  header p  {{ font-size: 0.85rem; opacity: 0.85; }}

  /* ── Summary cards ── */
  .summary-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 16px;
    padding: 28px 32px;
    background: var(--mid);
  }}
  .stat-card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 18px 20px;
    text-align: center;
  }}
  .stat-card .value {{
    font-size: 2rem;
    font-weight: 700;
    color: var(--green);
  }}
  .stat-card .value.red  {{ color: var(--accent); }}
  .stat-card .value.gold {{ color: var(--yellow); }}
  .stat-card .label {{
    font-size: 0.78rem;
    color: var(--muted);
    margin-top: 4px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }}

  /* ── Sections ── */
  main {{ padding: 28px 32px; max-width: 1400px; margin: 0 auto; }}
  section {{ margin-bottom: 40px; }}
  section h2 {{
    font-size: 1.25rem;
    margin-bottom: 16px;
    padding-bottom: 8px;
    border-bottom: 2px solid var(--border);
    display: flex;
    align-items: center;
    gap: 10px;
  }}
  .badge {{
    background: var(--accent);
    color: #fff;
    border-radius: 12px;
    font-size: 0.7rem;
    font-weight: 700;
    padding: 2px 8px;
    text-transform: uppercase;
  }}
  .badge.green {{ background: var(--green); color: var(--dark); }}
  .badge.gold  {{ background: var(--yellow); color: var(--dark); }}

  /* ── Item table ── */
  .table-wrap {{ overflow-x: auto; border-radius: 10px; border: 1px solid var(--border); }}
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.88rem;
  }}
  thead th {{
    background: var(--mid);
    padding: 12px 14px;
    text-align: left;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    color: var(--muted);
    white-space: nowrap;
    cursor: pointer;
    user-select: none;
  }}
  thead th:hover {{ color: var(--text); }}
  tbody tr {{ border-top: 1px solid var(--border); }}
  tbody tr:hover {{ background: rgba(255,255,255,0.03); }}
  tbody td {{
    padding: 12px 14px;
    vertical-align: top;
  }}
  .item-name  {{ font-weight: 600; }}
  .item-desc  {{ font-size: 0.78rem; color: var(--muted); margin-top: 2px; }}
  .price      {{ font-variant-numeric: tabular-nums; white-space: nowrap; }}
  .price-reg  {{ text-decoration: line-through; color: var(--muted); font-size: 0.82rem; }}
  .price-sale {{ color: var(--yellow); font-weight: 600; }}
  .price-final {{ color: var(--green); font-weight: 700; font-size: 1rem; }}
  .savings-val {{ color: var(--accent); font-weight: 600; }}
  .coupon-tag {{
    display: inline-block;
    background: rgba(0, 184, 148, 0.15);
    border: 1px solid var(--green);
    color: var(--green);
    border-radius: 4px;
    font-size: 0.72rem;
    padding: 2px 6px;
    white-space: nowrap;
  }}
  .deal-tag {{
    display: inline-block;
    background: rgba(253, 203, 110, 0.15);
    border: 1px solid var(--yellow);
    color: var(--yellow);
    border-radius: 4px;
    font-size: 0.72rem;
    padding: 2px 6px;
    white-space: nowrap;
  }}
  .na {{ color: var(--muted); font-size: 0.8rem; }}

  /* ── Best deals highlight cards ── */
  .best-deals-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 16px;
  }}
  .best-card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-top: 3px solid var(--green);
    border-radius: 10px;
    padding: 18px;
  }}
  .best-card .product {{ font-weight: 700; font-size: 0.95rem; margin-bottom: 6px; }}
  .best-card .detail  {{ font-size: 0.78rem; color: var(--muted); margin-bottom: 10px; }}
  .best-card .pricing {{ display: flex; flex-direction: column; gap: 4px; margin-bottom: 10px; }}
  .best-card .coupon-label {{
    font-size: 0.78rem;
    background: rgba(0,184,148,0.12);
    border-left: 3px solid var(--green);
    padding: 4px 8px;
    border-radius: 0 4px 4px 0;
    margin-bottom: 8px;
  }}
  .best-card .final-row {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-top: 10px;
    border-top: 1px solid var(--border);
  }}
  .best-card .final-price {{ font-size: 1.35rem; font-weight: 800; color: var(--green); }}
  .best-card .savings-pill {{
    background: var(--accent);
    color: #fff;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 700;
    padding: 3px 10px;
  }}
  .no-items {{ color: var(--muted); font-style: italic; padding: 12px 0; }}

  /* ── Footer ── */
  footer {{
    text-align: center;
    padding: 24px;
    font-size: 0.78rem;
    color: var(--muted);
    border-top: 1px solid var(--border);
    margin-top: 20px;
  }}

  /* ── Sort indicator ── */
  .sort-asc::after  {{ content: " ▲"; color: var(--accent); }}
  .sort-desc::after {{ content: " ▼"; color: var(--accent); }}
</style>
</head>
<body>

<header>
  <div>
    <h1>CVS Coupon Strategy</h1>
    <p>Generated {generated_at}</p>
  </div>
  <div style="text-align:right">
    <div style="font-size:0.85rem;opacity:0.8">{summary['coupons_clipped']} coupons clipped to your card</div>
  </div>
</header>

{_summary_html(summary)}

<main>
  {_best_deals_section(best_deals)}
  {_table_section("Weekly Sale + Coupon Match", sale_only, "gold", show_coupon=True)}
  {_table_section("Sale Deals (no coupon match)", sale_only, "gold", show_coupon=False)}
  {_table_section("Coupon-Only Items (no weekly deal)", coupon_only, "green", show_coupon=True, coupon_only_mode=True)}
</main>

<footer>
  <p>This report is for personal use only. Prices and availability may vary by store location.</p>
  <p style="margin-top:6px">CVS ExtraCare savings strategy &bull; {generated_at}</p>
</footer>

<script>
// Simple client-side table sort
document.querySelectorAll('thead th[data-col]').forEach(th => {{
  th.addEventListener('click', () => {{
    const table = th.closest('table');
    const tbody = table.querySelector('tbody');
    const col = +th.dataset.col;
    const numeric = th.dataset.numeric === 'true';
    const rows = [...tbody.querySelectorAll('tr')];

    const currentDir = th.classList.contains('sort-asc') ? 'asc' : 'desc';
    const newDir = currentDir === 'asc' ? 'desc' : 'asc';

    table.querySelectorAll('thead th').forEach(h => {{
      h.classList.remove('sort-asc', 'sort-desc');
    }});
    th.classList.add(newDir === 'asc' ? 'sort-asc' : 'sort-desc');

    rows.sort((a, b) => {{
      const aText = a.cells[col]?.dataset.val ?? a.cells[col]?.innerText ?? '';
      const bText = b.cells[col]?.dataset.val ?? b.cells[col]?.innerText ?? '';
      if (numeric) {{
        const aNum = parseFloat(aText) || 0;
        const bNum = parseFloat(bText) || 0;
        return newDir === 'asc' ? aNum - bNum : bNum - aNum;
      }}
      return newDir === 'asc'
        ? aText.localeCompare(bText)
        : bText.localeCompare(aText);
    }});
    rows.forEach(r => tbody.appendChild(r));
  }});
}});
</script>

</body>
</html>
"""

    abs_path = os.path.abspath(output_path)
    with open(abs_path, "w", encoding="utf-8") as fh:
        fh.write(html_content)

    return abs_path


# ---------------------------------------------------------------------------
# HTML block builders
# ---------------------------------------------------------------------------

def _summary_html(summary: dict) -> str:
    def fmt_price(val: float) -> str:
        return f"${val:,.2f}" if val else "$0.00"

    cards = [
        (fmt_price(summary["estimated_total_savings"]), "red", "Estimated Total Savings"),
        (fmt_price(summary["estimated_final_total"]), "gold", "Est. Final Total"),
        (fmt_price(summary["estimated_regular_total"]), "", "Regular Price Total"),
        (str(summary["items_with_both"]), "green", "Items with Sale + Coupon"),
        (str(summary["items_with_coupons"]), "", "Items with Coupon"),
        (str(summary["items_with_deals"]), "", "Items on Weekly Sale"),
        (str(summary["coupons_clipped"]), "", "Coupons Clipped"),
        (str(summary["total_items"]), "", "Total Items"),
    ]

    inner = ""
    for value, cls, label in cards:
        inner += f"""
        <div class="stat-card">
          <div class="value {cls}">{html.escape(str(value))}</div>
          <div class="label">{html.escape(label)}</div>
        </div>"""

    return f'<div class="summary-grid">{inner}</div>'


def _best_deals_section(items: list[dict]) -> str:
    if not items:
        return ""

    cards_html = ""
    for item in items[:20]:  # cap at 20 highlight cards
        reg = _price_str(item["regular_price"])
        sale = _price_str(item["sale_price"])
        final = _price_str(item["final_price"])
        savings = _price_str(item["savings"])
        pct = f" ({item['savings_pct']:.0f}% off)" if item["savings_pct"] else ""

        cards_html += f"""
        <div class="best-card">
          <div class="product">{html.escape(item['name'])}</div>
          <div class="detail">{html.escape(item['description'][:120] if item['description'] else '')}</div>
          <div class="pricing">
            {f'<span class="price-reg">Reg {reg}</span>' if item['regular_price'] else ''}
            {f'<span class="price-sale">Sale {sale}</span>' if item['sale_price'] else ''}
          </div>
          {f'<div class="coupon-label">Coupon: {html.escape(item["coupon_discount_label"])}</div>' if item['coupon_discount_label'] else ''}
          <div class="final-row">
            <span class="final-price">{final if final != "—" else sale}</span>
            <span class="savings-pill">Save {savings}{html.escape(pct)}</span>
          </div>
        </div>"""

    return f"""
    <section>
      <h2>
        Best Deals — Sale + Coupon Applied
        <span class="badge green">{len(items)} items</span>
      </h2>
      <div class="best-deals-grid">{cards_html}</div>
    </section>"""


def _table_section(
    title: str,
    items: list[dict],
    badge_class: str,
    show_coupon: bool = True,
    coupon_only_mode: bool = False,
) -> str:
    if not items:
        return ""

    rows_html = ""
    for item in items:
        coupon_cell = ""
        if show_coupon:
            coupon_cell = (
                f'<span class="coupon-tag">{html.escape(item["coupon_discount_label"])}</span>'
                if item["coupon_discount_label"]
                else '<span class="na">—</span>'
            )

        rows_html += f"""
        <tr>
          <td>
            <div class="item-name">{html.escape(item['name'])}</div>
            <div class="item-desc">{html.escape(item['description'][:100] if item['description'] else '')}</div>
          </td>
          <td class="price" data-val="{item['regular_price'] or ''}">
            {f'<span class="price-reg">${item["regular_price"]:.2f}</span>' if item['regular_price'] is not None else '<span class="na">—</span>'}
          </td>
          <td class="price" data-val="{item['sale_price'] or ''}">
            {f'<span class="price-sale">{html.escape(item["sale_label"])}</span>' if item['sale_label'] else '<span class="na">—</span>'}
          </td>
          <td>{coupon_cell}</td>
          <td class="price" data-val="{item['final_price'] or ''}">
            {f'<span class="price-final">${item["final_price"]:.2f}</span>' if item['final_price'] is not None else '<span class="na">—</span>'}
          </td>
          <td class="price" data-val="{item['savings'] or ''}">
            {f'<span class="savings-val">${item["savings"]:.2f}</span>' if item['savings'] is not None else '<span class="na">—</span>'}
          </td>
          <td><span class="na">{html.escape(item['category'] or item['deal_type'] or '')}</span></td>
          <td><span class="na" style="font-size:0.75rem">{html.escape(item['valid_thru'])}</span></td>
        </tr>"""

    coupon_header = '<th data-col="3">Coupon</th>' if show_coupon else '<th data-col="3">Coupon</th>'

    return f"""
    <section>
      <h2>
        {html.escape(title)}
        <span class="badge {badge_class}">{len(items)}</span>
      </h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th data-col="0">Product</th>
              <th data-col="1" data-numeric="true">Regular Price</th>
              <th data-col="2">Sale / Deal</th>
              {coupon_header}
              <th data-col="4" data-numeric="true">Final Price ▼</th>
              <th data-col="5" data-numeric="true">You Save</th>
              <th data-col="6">Category</th>
              <th data-col="7">Valid Thru</th>
            </tr>
          </thead>
          <tbody>
            {rows_html}
          </tbody>
        </table>
      </div>
    </section>"""


def _price_str(val: Optional[float]) -> str:
    if val is None:
        return "—"
    return f"${val:.2f}"
