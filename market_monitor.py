#!/usr/bin/env python3
"""
美股下殺事件監控器
偵測前夜 SOX / NASDAQ 是否大跌，自動記錄台股連動情況
"""

import yfinance as yf
import json
import os
from datetime import datetime

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

    print(f"\n  ⚠ 觸發！開始抓台股資料...\n")

    today_str  = datetime.now().strftime("%Y/%m/%d")
    sheet_rows = []
    event_data = {"date": today_str, "sox": sox_chg,
                  "nasdaq": nas_chg, "stocks": []}

    for ticker, name in STOCKS.items():
        chg  = get_pct_change(ticker)
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
    log = []
    if os.path.exists(LOCAL_LOG):
        with open(LOCAL_LOG, "r", encoding="utf-8") as f:
            log = json.load(f)
    log.append(event_data)
    with open(LOCAL_LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
    print(f"\n  已存至本地 event_log.json")

    push_to_sheets(sheet_rows)
    print()


if __name__ == "__main__":
    main()
