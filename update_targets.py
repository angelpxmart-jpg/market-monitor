#!/usr/bin/env python3
"""
一次性腳本：為全部 40 支股票抓 MA120，寫入 stocks_config.json
target = f"{MA120*0.85:.0f}~{MA120*0.95:.0f}"
"""
import yfinance as yf
import json, os

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "stocks_config.json")

ALL_STOCKS = [
    # AI/半導體
    {"code": "2330", "ticker": "2330.TW",  "name": "台積電",    "industry": "AI/半導體"},
    {"code": "2454", "ticker": "2454.TW",  "name": "聯發科",    "industry": "AI/半導體"},
    {"code": "3711", "ticker": "3711.TW",  "name": "日月光投控","industry": "AI/半導體"},
    {"code": "5274", "ticker": "5274.TWO", "name": "信驊",      "industry": "AI/半導體"},
    {"code": "6533", "ticker": "6533.TW",  "name": "矽力-KY",   "industry": "AI/半導體"},
    {"code": "2303", "ticker": "2303.TW",  "name": "聯電",      "industry": "AI/半導體"},
    {"code": "2379", "ticker": "2379.TW",  "name": "瑞昱",      "industry": "AI/半導體"},
    {"code": "6488", "ticker": "6488.TW",  "name": "環球晶",    "industry": "AI/半導體"},
    {"code": "2408", "ticker": "2408.TW",  "name": "南亞科",    "industry": "AI/半導體"},
    {"code": "4966", "ticker": "4966.TW",  "name": "譜瑞-KY",   "industry": "AI/半導體"},
    # 伺服器/散熱/電源
    {"code": "2382", "ticker": "2382.TW",  "name": "廣達",      "industry": "伺服器/散熱/電源"},
    {"code": "6669", "ticker": "6669.TW",  "name": "緯穎",      "industry": "伺服器/散熱/電源"},
    {"code": "6230", "ticker": "6230.TW",  "name": "超眾",      "industry": "伺服器/散熱/電源"},
    {"code": "3324", "ticker": "3324.TWO", "name": "双鴻",      "industry": "伺服器/散熱/電源"},
    {"code": "2308", "ticker": "2308.TW",  "name": "台達電",    "industry": "伺服器/散熱/電源"},
    {"code": "3017", "ticker": "3017.TW",  "name": "奇鋐",      "industry": "伺服器/散熱/電源"},
    {"code": "2356", "ticker": "2356.TW",  "name": "英業達",    "industry": "伺服器/散熱/電源"},
    {"code": "3231", "ticker": "3231.TW",  "name": "緯創",      "industry": "伺服器/散熱/電源"},
    {"code": "2301", "ticker": "2301.TW",  "name": "光寶科",    "industry": "伺服器/散熱/電源"},
    {"code": "2421", "ticker": "2421.TW",  "name": "建準",      "industry": "伺服器/散熱/電源"},
    # 蘋果供應鏈
    {"code": "3008", "ticker": "3008.TW",  "name": "大立光",    "industry": "蘋果供應鏈"},
    {"code": "4938", "ticker": "4938.TW",  "name": "和碩",      "industry": "蘋果供應鏈"},
    {"code": "2474", "ticker": "2474.TW",  "name": "可成",      "industry": "蘋果供應鏈"},
    {"code": "2354", "ticker": "2354.TW",  "name": "鴻準",      "industry": "蘋果供應鏈"},
    {"code": "2317", "ticker": "2317.TW",  "name": "鴻海",      "industry": "蘋果供應鏈"},
    {"code": "3034", "ticker": "3034.TW",  "name": "聯詠",      "industry": "蘋果供應鏈"},
    {"code": "3037", "ticker": "3037.TW",  "name": "欣興",      "industry": "蘋果供應鏈"},
    {"code": "3044", "ticker": "3044.TW",  "name": "健鼎",      "industry": "蘋果供應鏈"},
    {"code": "2360", "ticker": "2360.TW",  "name": "致茂",      "industry": "蘋果供應鏈"},
    {"code": "2385", "ticker": "2385.TW",  "name": "群光",      "industry": "蘋果供應鏈"},
    # 網通
    {"code": "2345", "ticker": "2345.TW",  "name": "智邦",      "industry": "網通"},
    {"code": "5388", "ticker": "5388.TW",  "name": "中磊",      "industry": "網通"},
    {"code": "2332", "ticker": "2332.TW",  "name": "友訊",      "industry": "網通"},
    {"code": "6277", "ticker": "6277.TW",  "name": "宏正",      "industry": "網通"},
    {"code": "4906", "ticker": "4906.TWO", "name": "正文",      "industry": "網通"},
    {"code": "3491", "ticker": "3491.TWO", "name": "昇銳",      "industry": "網通"},
    {"code": "6213", "ticker": "6213.TW",  "name": "聯茂",      "industry": "網通"},
    {"code": "3706", "ticker": "3706.TW",  "name": "神達",      "industry": "網通"},
    {"code": "3085", "ticker": "3085.TWO", "name": "碩天",      "industry": "網通"},
    {"code": "4977", "ticker": "4977.TWO", "name": "眾達-KY",   "industry": "網通"},
]


def fetch_ma120(ticker: str):
    try:
        hist = yf.download(ticker, period="7mo", interval="1d",
                           progress=False, auto_adjust=True)
        if hist.empty or len(hist) < 2:
            return None
        close = hist["Close"].squeeze().dropna()
        if len(close) < 120:
            print(f"    警告：{ticker} 歷史資料不足 120 日（{len(close)} 日），用全部資料計算")
        ma120 = round(float(close.tail(120).mean()), 1)
        return ma120
    except Exception as e:
        print(f"  [{ticker}] 抓取失敗：{e}")
        return None


def main():
    print(f"\n{'='*52}")
    print(f"  MA120 目標區計算 — 全部 {len(ALL_STOCKS)} 支")
    print(f"{'='*52}\n")

    result = []
    failed = []
    for s in ALL_STOCKS:
        print(f"  {s['code']} {s['name']}...", end=" ", flush=True)
        ma120 = fetch_ma120(s["ticker"])
        if ma120:
            low  = round(ma120 * 0.85)
            high = round(ma120 * 0.95)
            target = f"{int(low)}~{int(high)}"
            print(f"MA120={ma120}  →  target={target}")
            result.append({**s, "target": target})
        else:
            print("失敗，target 設為空字串")
            result.append({**s, "target": ""})
            failed.append(s["code"])

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n  ✅ stocks_config.json 已更新（{len(result)} 筆）")
    if failed:
        print(f"  ⚠️  抓取失敗：{failed}（target 為空，需手動填入）")
    print()


if __name__ == "__main__":
    main()
