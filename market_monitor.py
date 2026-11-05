#!/usr/bin/env python3
"""
美股下殺事件監控器
偵測前夜 SOX / NASDAQ 是否大跌，自動記錄台股當天收盤連動情況
（排程 14:30／16:00，台股收盤後才跑）
"""

import yfinance as yf
import json
import os
from datetime import datetime, date

# ── 設定（可自行調整） ─────────────────────────────────
SOX_THRESHOLD  = -2.0   # SOX 跌幅門檻（%），超過才記錄
SPREADSHEET_ID = "19MN6Y95304W95Ad2dzQorKAJiJNvCXsRer_cYm58nu8"
LOG_SHEET      = "下殺事件日誌"
# ──────────────────────────────────────────────────────

BASE_DIR             = os.path.dirname(os.path.abspath(__file__))
LOCAL_LOG            = os.path.join(BASE_DIR, "event_log.json")
SERVICE_ACCOUNT_FILE = os.path.join(BASE_DIR, "service_account.json")

STOCKS = {
    "2330.TW" : "台積電",
    "2454.TW" : "聯發科",
    "3711.TW" : "日月光投控",
    "5274.TWO": "信驊",
    "6533.TW" : "矽力-KY",
    "2382.TW" : "廣達",
    "6669.TW" : "緯穎",
    "6230.TW" : "超眾",
    "3324.TWO": "双鴻",
    "2308.TW" : "台達電",
    "3008.TW" : "大立光",
    "4938.TW" : "和碩",
    "2474.TW" : "可成",
    "2354.TW" : "鴻準",
    "2345.TW" : "智邦",
    "5388.TW" : "中磊",
}


def get_pct_change(ticker):
    try:
        hist = yf.download(ticker, period="5d", interval="1d",
                           progress=False, auto_adjust=True)
        if hist.empty or len(hist) < 2:
            return None
        close = hist["Close"].dropna()
        if len(close) < 2:
            return None
        prev = float(close.iloc[-2])
        last = float(close.iloc[-1])
        return round((last - prev) / prev * 100, 2)
    except Exception:
        return None


def get_tw_change_on(ticker, day: date, period="1mo"):
    """台股在 day 當天收盤 vs 前一交易日收盤；當天還沒有日 K 就回 None"""
    try:
        hist = yf.download(ticker, period=period, interval="1d",
                           progress=False, auto_adjust=True)
        close = hist["Close"].dropna()
        if hasattr(close, "columns"):
            close = close.iloc[:, 0]
        days = [d.date() for d in close.index]
        if day not in days:
            return None
        i = days.index(day)
        if i == 0:
            return None
        prev = float(close.iloc[i - 1])
        last = float(close.iloc[i])
        return round((last - prev) / prev * 100, 2)
    except Exception:
        return None


def push_to_sheets(rows):
    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        print("  [Sheets] service_account.json 未設定，略過")
        return
    try:
        import gspread
        gc = gspread.service_account(filename=SERVICE_ACCOUNT_FILE)
        ws = gc.open_by_key(SPREADSHEET_ID).worksheet(LOG_SHEET)
        ws.append_rows(rows, value_input_option="USER_ENTERED")
        print(f"  [Sheets] 已寫入 {len(rows)} 筆 ✓")
    except Exception as e:
        print(f"  [Sheets] 寫入失敗：{e}")


def main():
    print(f"\n{'='*52}")
    print(f"  美股下殺監控 — {datetime.now().strftime('%Y/%m/%d %H:%M')}")
    print('='*52)

    sox_chg = get_pct_change("^SOX")
    nas_chg = get_pct_change("^IXIC")

    if sox_chg is None:
        print("無法取得 SOX 資料，請確認網路連線")
        return

    print(f"  SOX: {sox_chg:+.1f}%   NASDAQ: {nas_chg:+.1f}%")

    if sox_chg > SOX_THRESHOLD:
        print(f"  SOX 跌幅未達門檻（{SOX_THRESHOLD}%），今日無需記錄\n")
        return

    today_str  = datetime.now().strftime("%Y/%m/%d")

    # 補跑與排程同一天可能各跑一次，已記錄就不再寫入（避免日誌與 Sheets 重複）
    log = []
    if os.path.exists(LOCAL_LOG):
        with open(LOCAL_LOG, "r", encoding="utf-8") as f:
            log = json.load(f)
    if any(e.get("date") == today_str for e in log):
        print(f"  {today_str} 已記錄過，略過\n")
        return

    # 開機 RunAtLoad 可能在盤中觸發，盤中日 K 不是收盤價
    if datetime.now().hour < 14:
        print("  台股尚未收盤，等 14:30 排程\n")
        return

    if get_tw_change_on("2330.TW", datetime.now().date()) is None:
        print("  台股今日收盤資料尚未更新（或休市），等下一輪\n")
        return

    print(f"\n  ⚠ 觸發！開始抓台股資料...\n")

    sheet_rows = []
    event_data = {"date": today_str, "sox": sox_chg,
                  "nasdaq": nas_chg, "stocks": []}

    for ticker, name in STOCKS.items():
        chg  = get_tw_change_on(ticker, datetime.now().date())
        code = ticker.split(".")[0]

        if chg is not None:
            beta     = round(chg / sox_chg, 2) if sox_chg != 0 else None
            chg_str  = f"{chg:+.1f}%"
            beta_str = str(beta)
        else:
            chg_str = beta_str = "N/A"
            beta    = None

        print(f"  {code} {name:<10} {chg_str:>8}   beta {beta_str}")

        sheet_rows.append([
            today_str, "",
            f"{sox_chg:+.1f}%",
            f"{nas_chg:+.1f}%" if nas_chg else "N/A",
            code, name, chg_str, beta_str, "", "",
        ])
        event_data["stocks"].append(
            {"code": code, "name": name, "chg": chg, "beta": beta})

    # 本地 JSON 備份
    log.append(event_data)
    with open(LOCAL_LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
    print(f"\n  已存至本地 event_log.json")

    push_to_sheets(sheet_rows)
    print()


if __name__ == "__main__":
    main()
