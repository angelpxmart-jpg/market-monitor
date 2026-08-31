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
    """回傳 CSS class：green / yellow / ''"""
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
    stock_rows = build_stock_rows(stocks_data)
    event_rows = build_event_rows(events)
    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>美股下殺台股觀察</title>
<style>
  :root {{
    --bg: #0f1117;
    --card: #1a1d26;
    --border: #2d3148;
    --text: #e2e8f0;
    --muted: #94a3b8;
    --green: #22c55e;
    --yellow: #eab308;
    --red: #ef4444;
    --accent: #6366f1;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, 'SF Pro Text', 'Helvetica Neue', sans-serif;
    font-size: 14px;
    padding: 16px;
    max-width: 900px;
    margin: 0 auto;
  }}
  h1 {{ font-size: 20px; font-weight: 700; margin-bottom: 4px; }}
  .subtitle {{ color: var(--muted); font-size: 13px; margin-bottom: 20px; }}
  h2 {{ font-size: 15px; font-weight: 600; color: var(--accent);
        margin: 24px 0 10px; letter-spacing: .5px; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th {{
    background: var(--card);
    color: var(--muted);
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: .5px;
    padding: 8px 10px;
    text-align: right;
    border-bottom: 1px solid var(--border);
  }}
  th:first-child, th:nth-child(2) {{ text-align: left; }}
  td {{
    padding: 9px 10px;
    border-bottom: 1px solid var(--border);
    text-align: right;
  }}
  td:first-child, td:nth-child(2) {{ text-align: left; }}
  tr:last-child td {{ border-bottom: none; }}
  tr.in-zone td {{ background: rgba(34,197,94,.08); }}
  tr.in-zone td:first-child {{ border-left: 3px solid var(--green); }}
  tr.near-zone td {{ background: rgba(234,179,8,.06); }}
  tr.near-zone td:first-child {{ border-left: 3px solid var(--yellow); }}
  .code {{ font-family: monospace; color: var(--accent); font-weight: 600; }}
  .na {{ color: var(--muted); font-style: italic; }}
  .neg {{ color: var(--red); }}
  .empty-log {{ text-align: center; color: var(--muted); padding: 20px; font-style: italic; }}
  .dist-cell {{ font-size: 13px; }}
  .target-cell {{ font-size: 13px; }}
  .updated {{ color: var(--muted); font-size: 12px; margin-top: 28px; text-align: right; }}
  @media (max-width: 600px) {{
    body {{ font-size: 13px; padding: 12px; }}
    td, th {{ padding: 7px 6px; }}
    .dist-cell, .target-cell {{ font-size: 12px; }}
  }}
</style>
</head>
<body>

<h1>美股下殺台股觀察</h1>
<p class="subtitle">SOX 跌幅 ≥ 2% 時自動記錄，追蹤體質健康的台股連動情況</p>

<h2>▸ 觀察名單</h2>
<table>
  <thead>
    <tr>
      <th>代號</th>
      <th>名稱</th>
      <th>現價</th>
      <th>MA60</th>
      <th>MA120</th>
      <th>觀察目標區</th>
      <th>距目標區</th>
    </tr>
  </thead>
  <tbody>
    {stock_rows}
  </tbody>
</table>

<h2>▸ 下殺事件日誌</h2>
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
