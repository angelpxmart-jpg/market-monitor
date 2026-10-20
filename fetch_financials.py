#!/usr/bin/env python3
"""
M5 財報抓取：FinMind API + TWSE Open Data
資料來源：
  - FinMind: EPS / 毛利率 / D/E / 流動比 / 外資持股% / 近5日外資買賣超
  - TWSE: 備用（目前以 FinMind 為主）

執行：python3 fetch_financials.py
排程：每週日 10:00 cron（run_fetch_financials.sh）
輸出：financial_data.json

FinMind 免費帳號申請：https://finmindtrade.com/analysis
設定方式：在 .env 加入 FINMIND_TOKEN=xxxx
未設定 token 時仍可用，但每日上限 600 次（40 股 × 4 呼叫 = 160 次，免費足夠）
"""

import json
import os
import time
import requests
from datetime import datetime, timedelta

BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE   = os.path.join(BASE_DIR, "stocks_config.json")
OUTPUT_FILE   = os.path.join(BASE_DIR, "financial_data.json")
FINMIND_URL   = "https://api.finmindtrade.com/api/v4/data"
FINMIND_TOKEN = os.environ.get("FINMIND_TOKEN", "")

# 6 支邊緣股：相關營收 ≥ 40% 待 Angel 人工確認年報
SEGMENT_WARNINGS = {"2301", "2308", "3706", "3085", "4977", "2332"}


# ─────────────────── FinMind 通用呼叫 ───────────────────

def finmind_get(dataset: str, data_id: str, start_date: str) -> list:
    params = {"dataset": dataset, "data_id": data_id, "start_date": start_date}
    if FINMIND_TOKEN:
        params["token"] = FINMIND_TOKEN
    for attempt in range(3):
        try:
            r = requests.get(FINMIND_URL, params=params, timeout=30)
            r.raise_for_status()
            j = r.json()
            if j.get("status") == 200:
                return j.get("data", [])
            print(f"    [{dataset}/{data_id}] API msg: {j.get('msg', '?')}")
            return []
        except requests.RequestException as e:
            print(f"    [{dataset}/{data_id}] attempt {attempt+1} failed: {e}")
            time.sleep(2 ** attempt)
    return []


# ─────────────────── EPS + 毛利率 ───────────────────

def process_eps_gpm(code: str) -> dict:
    """TaiwanStockFinancialStatements → EPS YoY + 毛利率健檢"""
    start = (datetime.now() - timedelta(days=365 * 4)).strftime("%Y-%m-%d")
    rows = finmind_get("TaiwanStockFinancialStatements", code, start)

    eps_by_q   = {}  # "2024Q1" -> float
    gross_by_q = {}  # "2024Q1" -> float
    rev_by_q   = {}  # "2024Q1" -> float

    for r in rows:
        d = r.get("date", "")
        if len(d) < 7:
            continue
        yr = d[:4]
        mo = int(d[5:7])
        q  = (mo - 1) // 3 + 1
        qk = f"{yr}Q{q}"
        t  = r.get("type", "")
        v  = float(r.get("value", 0) or 0)
        if t == "EPS":
            eps_by_q[qk] = v
        elif t == "GrossProfit":
            gross_by_q[qk] = v
        elif t == "Revenue":
            rev_by_q[qk] = v

    # ── EPS 年度加總 ──
    annual: dict = {}
    for qk, v in eps_by_q.items():
        yr = qk[:4]
        annual[yr] = round(annual.get(yr, 0) + v, 2)
    annual_list = sorted(annual.items())
    annual_out  = [{"year": int(y), "eps": v} for y, v in annual_list[-3:]]

    # 近 2 年全年 YoY 是否正成長
    eps_yoy_ok = None
    if len(annual_list) >= 2:
        pairs = annual_list[-2:]
        yoys  = [pairs[i][1] > pairs[i-1][1] for i in range(1, len(pairs))]
        eps_yoy_ok = all(yoys) if yoys else None

    # 近 6 季明細
    q_detail = [{"q": k, "eps": v} for k, v in sorted(eps_by_q.items())[-6:]]

    # ── 毛利率：近一季 vs 前一年同季 ──
    common_q = sorted(set(gross_by_q) & set(rev_by_q))
    gpm_latest = gpm_prev = gpm_delta = gpm_ok = None
    if common_q:
        lq = common_q[-1]
        if rev_by_q.get(lq):
            gpm_latest = round(gross_by_q[lq] / rev_by_q[lq] * 100, 2)
        lq_idx = common_q.index(lq)
        if lq_idx >= 4:
            pq = common_q[lq_idx - 4]
            if rev_by_q.get(pq):
                gpm_prev = round(gross_by_q[pq] / rev_by_q[pq] * 100, 2)
        if gpm_latest is not None and gpm_prev is not None:
            gpm_delta = round(gpm_latest - gpm_prev, 2)
            gpm_ok    = gpm_delta >= -3.0

    return {
        "eps_yoy_ok":    eps_yoy_ok,
        "eps_annual":    annual_out,
        "eps_quarterly": q_detail,
        "gpm_latest":    gpm_latest,
        "gpm_prev":      gpm_prev,
        "gpm_delta":     gpm_delta,
        "gpm_ok":        gpm_ok,
    }


# ─────────────────── 資產負債表 ───────────────────

def process_balance(code: str) -> dict:
    """TaiwanStockBalanceSheet → D/E 比 + 流動比"""
    start = (datetime.now() - timedelta(days=365 * 2)).strftime("%Y-%m-%d")
    rows  = finmind_get("TaiwanStockBalanceSheet", code, start)
    if not rows:
        return {"de_ratio": None, "current_ratio": None, "balance_ok": None}

    by_date: dict = {}
    for r in rows:
        by_date.setdefault(r["date"], {})[r["type"]] = float(r.get("value", 0) or 0)
    d = by_date.get(sorted(by_date)[-1], {})

    equity  = d.get("TotalEquity") or d.get("StockholdersEquity")
    # 有息負債（短債 + 長債；FinMind 欄位名以實際 API 為準）
    debt = (d.get("ShortTermBorrowings", 0) or 0) + \
           (d.get("LongTermBorrowingsAndBondsPayable", 0) or
            d.get("LongTermBorrowings", 0) or 0)
    cur_a = d.get("CurrentAssets")
    cur_l = d.get("CurrentLiabilities")

    de = round(debt / equity, 2) if (equity and equity > 0) else None
    cr = round(cur_a / cur_l, 2) if (cur_a and cur_l and cur_l > 0) else None

    ok = None
    if de is not None or cr is not None:
        ok = (de is not None and de < 1) or (cr is not None and cr > 1.5)

    return {"de_ratio": de, "current_ratio": cr, "balance_ok": ok}


# ─────────────────── 外資持股 % ───────────────────

def process_foreign_hold(code: str) -> dict:
    """TaiwanStockShareholding → 外資持股比例"""
    start = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
    rows  = finmind_get("TaiwanStockShareholding", code, start)
    if not rows:
        return {"foreign_hold_pct": None, "foreign_hold_ok": None}

    rows.sort(key=lambda x: x.get("date", ""))
    last = rows[-1]
    pct = last.get("ForeignInvestmentSharesRatio")
    if pct is None:
        return {"foreign_hold_pct": None, "foreign_hold_ok": None}

    pct = round(float(pct), 2)
    return {"foreign_hold_pct": pct, "foreign_hold_ok": pct > 20}


# ─────────────────── 外資近 5 日買賣超 ───────────────────

def process_institutional(code: str) -> dict:
    """TaiwanStockInstitutionalInvestorsBuySell → 外資近 5 日淨買賣超（張）"""
    start = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")
    rows  = finmind_get("TaiwanStockInstitutionalInvestorsBuySell", code, start)

    foreign = [r for r in rows if r.get("name") == "Foreign_Investor"]
    foreign.sort(key=lambda x: x.get("date", ""))

    net_5d = []
    for r in foreign[-5:]:
        buy  = float(r.get("buy", 0) or 0)
        sell = float(r.get("sell", 0) or 0)
        net_5d.append(int(buy - sell))

    buy_days = sum(1 for n in net_5d if n > 0) if net_5d else None
    return {"foreign_net_5d": net_5d, "foreign_buy_days": buy_days}


# ─────────────────── 整合單股 ───────────────────

def fetch_one(code: str) -> dict:
    eps_gpm = process_eps_gpm(code);   time.sleep(0.5)
    balance = process_balance(code);   time.sleep(0.5)
    fh      = process_foreign_hold(code); time.sleep(0.5)
    inst    = process_institutional(code); time.sleep(0.5)
    return {
        **eps_gpm,
        **balance,
        **fh,
        **inst,
        "pe": None,               # M6：P/E 同業比較
        "segment_warning": code in SEGMENT_WARNINGS,
    }


# ─────────────────── main ───────────────────

def main():
    print(f"\n{'='*54}")
    print(f"  M5 財報抓取 — {datetime.now().strftime('%Y/%m/%d %H:%M')}")
    print(f"  FinMind token: {'✓ 已設定' if FINMIND_TOKEN else '✗ 未設定（免費限速 600次/日）'}")
    print(f"{'='*54}\n")

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)

    result = {}
    total  = len(config)
    for i, s in enumerate(config, 1):
        code = s["code"]
        print(f"  [{i:02d}/{total}] {code} {s['name']}...", end=" ", flush=True)
        try:
            result[code] = fetch_one(code)
            print("✓")
        except Exception as e:
            print(f"✗ ({e})")
            result[code] = {"error": str(e), "segment_warning": code in SEGMENT_WARNINGS}

    output = {
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "stocks":  result,
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n  ✅ 完成 → {OUTPUT_FILE}\n")


if __name__ == "__main__":
    main()
