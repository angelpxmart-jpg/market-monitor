#!/usr/bin/env python3
"""
美股下殺台股觀察網頁 — HTML 生成器
輸出 index.html，可直接用瀏覽器開啟或部署至 GitHub Pages
"""

import yfinance as yf
import json
import os
from datetime import datetime

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "stocks_config.json")
LOG_FILE    = os.path.join(BASE_DIR, "event_log.json")
OUTPUT_FILE = os.path.join(BASE_DIR, "index.html")

INDUSTRY_COLORS = {
    "AI/半導體":        "#6366f1",
    "伺服器/散熱/電源": "#0ea5e9",
    "蘋果供應鏈":       "#10b981",
    "網通":             "#f59e0b",
}


def fetch_stock_data(ticker: str) -> dict:
    try:
        hist = yf.download(ticker, period="7mo", interval="1d",
                           progress=False, auto_adjust=True)
        if hist.empty or len(hist) < 2:
            return {}
        close = hist["Close"].squeeze().dropna()
        price = round(float(close.iat[-1]), 1)
        ma60  = round(float(close.tail(60).mean()), 1) if len(close) >= 60 else None
        ma120 = round(float(close.tail(120).mean()), 1) if len(close) >= 120 else None
        return {"price": price, "ma60": ma60, "ma120": ma120}
    except Exception as e:
        print(f"  [{ticker}] 抓取失敗：{e}")
        return {}


def parse_target(target_str: str):
    """解析 '2150~2300' 格式，回傳 (low, high) 或 (None, None)"""
    if not target_str or "~" not in target_str:
        return None, None
    parts = target_str.replace("，", "~").replace(",", "~").split("~")
    try:
        return float(parts[0].strip()), float(parts[1].strip())
    except (ValueError, IndexError):
        return None, None


def calc_distance(price: float, low: float, high: float) -> str:
    """計算現價距目標區距離，已在區內回傳 '✅ 在目標區'"""
    if low <= price <= high:
        return "✅ 在目標區"
    elif price > high:
        dist = round((price - high) / high * 100, 1)
        return f"-{dist}%（偏高）"
    else:
        dist = round((low - price) / low * 100, 1)
        return f"+{dist}%（尚早）"


def row_status(price: float, low, high) -> str:
    """回傳 CSS class：in-zone / near-zone / ''"""
    if low is None:
        return ""
    if low <= price <= high:
        return "in-zone"
    if price > high * 0.9 and price <= high * 1.0:
        return ""
    gap = (low - price) / low * 100
    if 0 < gap <= 10:
        return "near-zone"
    return ""


def load_event_log() -> list:
    if not os.path.exists(LOG_FILE):
        return []
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def fmt(val, suffix="") -> str:
    if val is None:
        return "—"
    return f"{val:,.1f}{suffix}"


def build_stock_rows(stocks_data: list) -> str:
    rows = []
    for s in stocks_data:
        d      = s.get("data", {})
        price  = d.get("price")
        ma60   = d.get("ma60")
        ma120  = d.get("ma120")
        target = s.get("target", "")
        low, high = parse_target(target)

        status = row_status(price, low, high) if price else ""
        dist   = calc_distance(price, low, high) if (price and low) else "N/A"

        css = f' class="{status}"' if status else ""
        rows.append(f"""
        <tr{css}>
          <td><span class="code">{s['code']}</span></td>
          <td>{s['name']}</td>
          <td>{fmt(price)}</td>
          <td>{fmt(ma60)}</td>
          <td>{fmt(ma120)}</td>
          <td class="target-cell">{target if target else '<span class="na">N/A</span>'}</td>
          <td class="dist-cell">{dist}</td>
        </tr>""")
    return "\n".join(rows)


def build_industry_sections(stocks_data: list) -> str:
    industries: dict = {}
    for s in stocks_data:
        ind = s.get("industry", "其他")
        if ind not in industries:
            industries[ind] = []
        industries[ind].append(s)

    sections = []
    for ind, stocks in industries.items():
        rows  = build_stock_rows(stocks)
        color = INDUSTRY_COLORS.get(ind, "#94a3b8")
        sections.append(f"""
<section class="industry-section">
  <div class="industry-header">
    <span class="industry-dot" style="background:{color}"></span>
    <span class="industry-name">{ind}</span>
    <span class="industry-count">{len(stocks)} 檔</span>
  </div>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>代號</th><th>名稱</th><th>現價</th>
          <th>MA60</th><th>MA120</th>
          <th>觀察目標區</th><th>距目標區</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
</section>""")
    return "\n".join(sections)


def build_event_rows(events: list) -> str:
    if not events:
        return '<tr><td colspan="5" class="empty-log">目前無觸發記錄</td></tr>'
    rows = []
    for ev in reversed(events):
        date     = ev.get("date", "—")
        sox      = ev.get("sox", 0)
        nas      = ev.get("nasdaq", 0)
        stocks   = ev.get("stocks", [])
        avg_chg  = round(sum(s["chg"] for s in stocks if s.get("chg")) / len(stocks), 1) if stocks else None
        worst    = min(stocks, key=lambda x: x.get("chg", 0)) if stocks else None
        rows.append(f"""
        <tr>
          <td>{date}</td>
          <td class="neg">{sox:+.1f}%</td>
          <td>{nas:+.1f}% (Nasdaq)</td>
          <td>{fmt(avg_chg, '%') if avg_chg else '—'}</td>
          <td>{worst['name'] + ' ' + str(worst['chg']) + '%' if worst else '—'}</td>
        </tr>""")
    return "\n".join(rows)


def build_html(stocks_data: list, events: list, generated_at: str) -> str:
    industry_sections = build_industry_sections(stocks_data)
    event_rows        = build_event_rows(events)
    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>美股下殺台股觀察</title>
<style>
  :root {{
    --bg:        #fdfcf9;
    --card:      #ffffff;
    --header-bg: #f8f3ec;
    --border:    #ede8df;
    --text:      #2c231a;
    --muted:     #9e8f7e;
    --green:     #15803d;
    --amber:     #b45309;
    --red:       #dc2626;
    --accent:    #8b6435;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, 'SF Pro Text', 'Helvetica Neue', sans-serif;
    font-size: 14px;
    padding: 20px 16px;
    max-width: 960px;
    margin: 0 auto;
  }}
  h1 {{
    font-size: 22px; font-weight: 700;
    color: var(--text); margin-bottom: 4px;
  }}
  .subtitle {{
    color: var(--muted); font-size: 13px; margin-bottom: 28px;
  }}
  .section-title {{
    font-size: 11px; font-weight: 700;
    color: var(--muted); text-transform: uppercase;
    letter-spacing: 1px; margin: 28px 0 12px;
  }}

  /* ── 產業卡片 ── */
  .industry-section {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 10px;
    margin-bottom: 14px;
    overflow: hidden;
    box-shadow: 0 1px 3px rgba(15,23,42,.05);
  }}
  .industry-header {{
    display: flex; align-items: center; gap: 8px;
    padding: 10px 14px;
    background: var(--header-bg);
    border-bottom: 1px solid var(--border);
  }}
  .industry-dot {{
    width: 8px; height: 8px;
    border-radius: 50%; flex-shrink: 0;
  }}
  .industry-name {{
    font-size: 13px; font-weight: 700;
    color: var(--text); letter-spacing: .2px;
  }}
  .industry-count {{
    font-size: 12px; color: var(--muted); margin-left: auto;
  }}
  .table-wrap {{ overflow-x: auto; }}

  /* ── 表格通用 ── */
  table {{ width: 100%; border-collapse: collapse; }}
  th {{
    color: var(--muted);
    font-size: 11px; font-weight: 700;
    text-transform: uppercase; letter-spacing: .6px;
    padding: 8px 12px; text-align: right;
    border-bottom: 1px solid var(--border);
    white-space: nowrap; background: transparent;
  }}
  th:first-child, th:nth-child(2) {{ text-align: left; }}
  td {{
    padding: 9px 12px;
    border-bottom: 1px solid var(--border);
    text-align: right; white-space: nowrap;
  }}
  td:first-child, td:nth-child(2) {{ text-align: left; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: #faf6f0; }}
  tr.in-zone td {{ background: rgba(22,163,74,.07); }}
  tr.in-zone td:first-child {{ border-left: 3px solid var(--green); }}
  tr.near-zone td {{ background: rgba(180,83,9,.06); }}
  tr.near-zone td:first-child {{ border-left: 3px solid var(--amber); }}

  .code {{
    font-family: 'SF Mono', 'Menlo', monospace;
    color: var(--accent); font-weight: 700; font-size: 13px;
  }}
  .na {{ color: var(--muted); font-style: italic; }}
  .neg {{ color: var(--red); font-weight: 600; }}
  .empty-log {{
    text-align: center; color: var(--muted);
    padding: 24px; font-style: italic;
  }}
  .dist-cell {{ font-size: 13px; }}
  .target-cell {{ font-size: 13px; color: var(--muted); }}

  /* ── 事件日誌卡 ── */
  .log-card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 10px;
    overflow: hidden;
    box-shadow: 0 1px 3px rgba(15,23,42,.05);
  }}

  .updated {{
    color: var(--muted); font-size: 12px;
    margin-top: 24px; text-align: right;
  }}

  @media (max-width: 600px) {{
    body {{ font-size: 13px; padding: 12px; }}
    td, th {{ padding: 7px 8px; }}
    .dist-cell, .target-cell {{ font-size: 12px; }}
  }}
</style>
</head>
<body>

<h1>美股下殺台股觀察</h1>
<p class="subtitle">SOX 跌幅 ≥ 2% 時自動記錄，追蹤體質健康的台股連動情況</p>

<p class="section-title">觀察名單</p>
{industry_sections}

<p class="section-title">下殺事件日誌</p>
<div class="log-card">
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th style="text-align:left">日期</th>
          <th style="text-align:left">SOX 跌幅</th>
          <th style="text-align:left">美股指數</th>
          <th>台股平均跌幅</th>
          <th>跌最多</th>
        </tr>
      </thead>
      <tbody>
        {event_rows}
      </tbody>
    </table>
  </div>
</div>

<p class="updated">最後更新：{generated_at}</p>

</body>
</html>"""


def main():
    print(f"\n{'='*52}")
    print(f"  美股下殺觀察網頁生成器 — {datetime.now().strftime('%Y/%m/%d %H:%M')}")
    print(f"{'='*52}\n")

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)

    print(f"  抓取 {len(config)} 檔股票資料...\n")
    stocks_data = []
    for s in config:
        print(f"  {s['code']} {s['name']}...", end=" ", flush=True)
        d = fetch_stock_data(s["ticker"])
        if d:
            print(f"  ✓  現價 {d.get('price', '—')}")
        else:
            print("  ✗  無資料")
        stocks_data.append({**s, "data": d})

    events = load_event_log()
    print(f"\n  讀取事件日誌：{len(events)} 筆")

    generated_at = datetime.now().strftime("%Y/%m/%d %H:%M")
    html = build_html(stocks_data, events, generated_at)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n  ✅ 輸出完成 → {OUTPUT_FILE}")
    print(f"     開啟：open '{OUTPUT_FILE}'\n")


if __name__ == "__main__":
    main()
