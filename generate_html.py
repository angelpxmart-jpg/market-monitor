#!/usr/bin/env python3
"""
美股下殺台股觀察網頁 — HTML 生成器
輸出 index.html，可直接用瀏覽器開啟或部署至 GitHub Pages
M5：點擊股票代號展開財報 panel（EPS / 毛利率 / D/E / 外資動向）
M6：美股觀察名單 Tab（yfinance .info 財報；預設顯示美股）
"""

import yfinance as yf
import json
import os
from datetime import datetime

BASE_DIR       = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE    = os.path.join(BASE_DIR, "stocks_config.json")
LOG_FILE       = os.path.join(BASE_DIR, "event_log.json")
OUTPUT_FILE    = os.path.join(BASE_DIR, "index.html")
FINANCIAL_FILE  = os.path.join(BASE_DIR, "financial_data.json")
DOWNGRADE_FILE  = os.path.join(BASE_DIR, "downgrade_state.json")

INDUSTRY_COLORS = {
    "AI/半導體":        "#6366f1",
    "伺服器/散熱/電源": "#0ea5e9",
    "蘋果供應鏈":       "#10b981",
    "網通":             "#f59e0b",
    "AI/科技核心":      "#7c3aed",
    "半導體供應鏈":     "#0891b2",
}

# ── M5 財報 panel CSS（插入 <style> 內）──
FIN_CSS = """
  /* ── 財報展開 panel ── */
  .code-btn { cursor: pointer; user-select: none; }
  .code-btn:hover { opacity: .75; }
  .fin-panel-row td { padding: 0 !important; border: none; }
  .fin-panel-row:hover td { background: inherit !important; }
  .fin-panel { padding: 12px 14px; background: var(--header-bg); border-top: 1px solid var(--border); }
  .fin-empty { color: var(--muted); font-style: italic; font-size: 12px; padding: 4px 0; }
  .fin-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 10px 16px;
  }
  .fin-block { font-size: 12px; }
  .fin-hd {
    font-weight: 700; font-size: 10px; text-transform: uppercase;
    letter-spacing: .5px; color: var(--accent); margin-bottom: 5px;
  }
  .fin-stat { color: var(--text); margin: 2px 0; font-size: 12px; }
  .fin-tbl { border-collapse: collapse; width: 100%; margin-bottom: 5px; font-size: 11px; }
  .fin-tbl th, .fin-tbl td {
    padding: 2px 5px; border: 1px solid var(--border); text-align: right;
  }
  .fin-tbl th:first-child, .fin-tbl td:first-child { text-align: left; }
  .fin-qs { display: flex; flex-wrap: wrap; gap: 3px 8px; font-size: 11px; color: var(--muted); margin-top: 3px; }
  .fin-pass { color: var(--green); font-weight: 700; }
  .fin-fail { color: var(--red);   font-weight: 700; }
  .fin-warn { color: var(--amber); font-weight: 700; }
  .fin-unk  { color: var(--muted); }
  .fn-buy  { color: var(--green); font-weight: 600; }
  .fn-sell { color: var(--red);   font-weight: 600; }
  .fin-muted { color: var(--muted); font-size: 11px; }
  .fin-seg-warn {
    display: inline-block;
    background: rgba(180,83,9,.1); color: var(--amber);
    padding: 2px 8px; border-radius: 4px;
    font-size: 11px; margin-bottom: 8px;
  }
  .arrow { font-style: normal; }
  /* ── 財報 panel 深色背景覆蓋 ── */
  .fin-panel { border-top: 1px solid rgba(253,240,213,0.12); }
  .fin-panel .fin-hd  { color: #669BBC; }
  .fin-panel .fin-stat { color: #FDF0D5; }
  .fin-panel .fin-qs  { color: rgba(253,240,213,0.5); }
  .fin-panel .fin-muted { color: rgba(253,240,213,0.4); }
  .fin-panel .fin-empty { color: rgba(253,240,213,0.5); }
  .fin-panel .fin-unk  { color: rgba(253,240,213,0.4); }
  .fin-panel .fin-pass { color: #4ade80; }
  .fin-panel .fin-fail { color: #f87171; }
  .fin-panel .fin-warn { color: #fbbf24; }
  .fin-panel .fn-buy  { color: #4ade80; }
  .fin-panel .fn-sell { color: #f87171; }
  .fin-panel .fin-tbl th,
  .fin-panel .fin-tbl td { border-color: rgba(253,240,213,0.15); }
  .fin-panel .fin-seg-warn { background: rgba(180,83,9,.25); color: #fbbf24; }
"""

# ── 候選區 CSS ──
CANDIDATE_CSS = """
  /* ── 候選區 ── */
  .candidate-title {
    font-size: 11px; font-weight: 700;
    color: var(--red); text-transform: uppercase;
    letter-spacing: 1px; margin: 28px 0 6px;
  }
  .candidate-note {
    font-size: 11px; color: var(--muted);
    background: rgba(120,0,0,.04);
    border: 1px solid rgba(120,0,0,.18);
    border-radius: 6px;
    padding: 7px 12px;
    margin-bottom: 12px;
  }
  .candidate-note code {
    font-family: 'SF Mono', monospace;
    font-size: 11px;
    background: rgba(0,0,0,.06);
    padding: 1px 4px; border-radius: 3px;
  }
  .tech-warn-badge {
    display: inline-block; font-size: 9px; font-weight: 700;
    padding: 1px 4px; border-radius: 3px;
    background: rgba(120,0,0,.12); color: var(--red);
    margin-left: 3px; vertical-align: middle;
  }
  .fund-warn-badge {
    display: inline-block; font-size: 9px; font-weight: 700;
    padding: 1px 4px; border-radius: 3px;
    background: rgba(180,83,9,.12); color: var(--amber);
    margin-left: 3px; vertical-align: middle;
  }
"""

# ── Tab CSS ──
TAB_CSS = """
  /* ── Tab 切換 ── */
  .tab-bar {
    display: flex;
    margin: 0 0 24px;
    border-bottom: 2px solid var(--border);
  }
  .tab-btn {
    padding: 8px 22px;
    border: none; border-radius: 0;
    background: none; cursor: pointer;
    font-size: 14px; font-weight: 600;
    color: var(--muted);
    border-bottom: 2px solid transparent;
    margin-bottom: -2px;
  }
  .tab-btn.active { color: var(--accent); border-bottom-color: var(--accent); }
  .tab-content { display: none; }
"""

# ── JavaScript：財報 panel toggle + Tab 切換 ──
FIN_JS = """<script>
function toggleFin(code) {
  var row = document.getElementById('fin-' + code);
  var btn = document.getElementById('btn-' + code);
  var open = row.style.display === 'table-row';
  row.style.display = open ? 'none' : 'table-row';
  var arrows = btn.querySelectorAll('.arrow');
  if (arrows.length) arrows[0].textContent = open ? ' ▸' : ' ▾';
}
function switchTab(tab) {
  document.querySelectorAll('.tab-content').forEach(function(el) {
    el.style.display = 'none';
  });
  document.querySelectorAll('.tab-btn').forEach(function(el) {
    el.classList.remove('active');
  });
  document.getElementById('tab-' + tab).style.display = 'block';
  document.querySelector('.tab-btn[data-tab="' + tab + '"]').classList.add('active');
}
</script>"""


# ────────────── 美股 yfinance .info 抓取 ──────────────

def fetch_us_stock_info(ticker: str) -> dict:
    try:
        info = yf.Ticker(ticker).info
        return {
            "trailing_eps":    info.get("trailingEps"),
            "revenue_growth":  info.get("revenueGrowth"),
            "gross_margin":    info.get("grossMargins"),
            "institution_pct": info.get("institutionPercentHeld"),
            "trailing_pe":     info.get("trailingPE"),
            "de_ratio":        info.get("debtToEquity"),
            "current_ratio":   info.get("currentRatio"),
        }
    except Exception as e:
        print(f"  [{ticker}] .info 抓取失敗：{e}")
        return {}


def us_fin_panel_html(code: str, info: dict) -> str:
    if not info:
        return ('<div class="fin-panel"><p class="fin-empty">'
                'yfinance .info 資料尚未載入</p></div>')

    def _pct(v):
        return "—" if v is None else f"{v * 100:.1f}%"

    def _num(v, d=2):
        return "—" if v is None else f"{v:,.{d}f}"

    eps      = info.get("trailing_eps")
    rev_g    = info.get("revenue_growth")
    gm       = info.get("gross_margin")
    inst_pct = info.get("institution_pct")
    pe       = info.get("trailing_pe")
    de       = info.get("de_ratio")
    cr       = info.get("current_ratio")

    rev_cls = "fin-pass" if (rev_g is not None and rev_g > 0) else "fin-fail"
    rev_arrow = "↑" if (rev_g is not None and rev_g > 0) else "↓"

    inst_ok = inst_pct is not None and inst_pct > 0.5
    cr_ok   = cr is not None and cr > 1.5

    eps_str = "—" if eps is None else f"${eps:.2f}"
    pe_str  = "—" if pe is None else f"{pe:.1f}"
    de_str  = "—" if de is None else f"{de:.1f}"

    return (
        f'<div class="fin-panel">'
        f'<div class="fin-grid">'
        f'<div class="fin-block">'
        f'<div class="fin-hd">EPS（TTM）</div>'
        f'<div class="fin-stat">{eps_str}</div>'
        f'<div class="fin-hd" style="margin-top:8px">營收成長（YoY）'
        f'<span class="{rev_cls}">{rev_arrow}</span></div>'
        f'<div class="fin-stat">{_pct(rev_g)}</div>'
        f'</div>'
        f'<div class="fin-block">'
        f'<div class="fin-hd">毛利率</div>'
        f'<div class="fin-stat">{_pct(gm)}</div>'
        f'<div class="fin-hd" style="margin-top:8px">P/E（trailing）</div>'
        f'<div class="fin-stat">{pe_str}</div>'
        f'</div>'
        f'<div class="fin-block">'
        f'<div class="fin-hd">D/E（yfinance）</div>'
        f'<div class="fin-stat">{de_str}</div>'
        f'<div class="fin-hd" style="margin-top:8px">流動比 {_badge(cr_ok)}</div>'
        f'<div class="fin-stat">{_num(cr)}</div>'
        f'</div>'
        f'<div class="fin-block">'
        f'<div class="fin-hd">機構持股 {_badge(inst_ok)}</div>'
        f'<div class="fin-stat">{_pct(inst_pct)}</div>'
        f'</div>'
        f'</div></div>'
    )


# ────────────── 財報資料載入 ──────────────

def load_financial_data() -> dict:
    if not os.path.exists(FINANCIAL_FILE):
        return {}
    try:
        with open(FINANCIAL_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("stocks", {})
    except Exception:
        return {}


# ────────────── 財報 panel HTML ──────────────

def _badge(ok, yes="✓", no="✗", unk="?") -> str:
    if ok is True:  return f'<span class="fin-pass">{yes}</span>'
    if ok is False: return f'<span class="fin-fail">{no}</span>'
    return f'<span class="fin-unk">{unk}</span>'


def _valbadge(v, good_fn) -> str:
    """顯示數值 + 通過/失敗 badge"""
    if v is None:
        return "—"
    badge = '<span class="fin-pass">✓</span>' if good_fn(v) else '<span class="fin-fail">✗</span>'
    return f"{v} {badge}"


def fin_panel_html(code: str, fin) -> str:
    if not fin:
        return ('<div class="fin-panel"><p class="fin-empty">'
                '財報資料尚未載入，請執行：<code>python3 fetch_financials.py</code>'
                '</p></div>')

    seg = ('<span class="fin-seg-warn">⚠️ 相關營收佔比 ≥40% 待人工確認</span>'
           if fin.get("segment_warning") else "")

    # ─ EPS ─
    eps_ok = fin.get("eps_yoy_ok")
    annual = fin.get("eps_annual", [])
    qtrs   = fin.get("eps_quarterly", [])

    ann_rows = ""
    for i, a in enumerate(annual):
        yoy = "—"
        if i > 0 and annual[i-1]["eps"]:
            chg = (a["eps"] - annual[i-1]["eps"]) / abs(annual[i-1]["eps"]) * 100
            yoy = f'{chg:+.1f}%'
        ann_rows += f'<tr><td>{a["year"]}</td><td>{a["eps"]}</td><td>{yoy}</td></tr>'

    eps_table = (
        "<table class='fin-tbl'><tr><th>年度</th><th>EPS</th><th>YoY</th></tr>"
        + ann_rows + "</table>" if ann_rows else '<p class="fin-empty">無 EPS 資料</p>'
    )
    q_html = "　".join(f'{q["q"]}: {q["eps"]}' for q in qtrs) if qtrs else ""

    # ─ 毛利率 ─
    gpm_ok  = fin.get("gpm_ok")
    gpm_lat = fin.get("gpm_latest")
    gpm_prv = fin.get("gpm_prev")
    gpm_d   = fin.get("gpm_delta")

    if gpm_d is not None:
        cls = "fin-pass" if gpm_d >= 0 else ("fin-fail" if gpm_d < -3 else "fin-warn")
        gpm_d_html = f'<span class="{cls}">{gpm_d:+.1f} ppt</span>'
    else:
        gpm_d_html = "—"

    # ─ 財務結構 ─
    de  = fin.get("de_ratio")
    cr  = fin.get("current_ratio")
    bal = fin.get("balance_ok")

    # ─ 外資持股 ─
    fh_pct = fin.get("foreign_hold_pct")
    fh_ok  = fin.get("foreign_hold_ok")
    fh_str = f"{fh_pct:.1f}%" if fh_pct is not None else "—"

    # ─ P/E ─
    pe     = fin.get("pe")
    pe_str = str(pe) if pe is not None else '— <span class="fin-muted">（M6 同業比較）</span>'

    # ─ 外資近 5 日 ─
    net5     = fin.get("foreign_net_5d", [])
    buy_days = fin.get("foreign_buy_days")
    if net5:
        bars = []
        for n in net5:
            cls   = "fn-buy" if n > 0 else "fn-sell"
            label = f"+{n//1000}K" if n >= 0 else f"{n//1000}K"
            bars.append(f'<span class="{cls}">{label}</span>')
        net5_html = " ".join(bars)
        if buy_days is not None:
            net5_html += f' <span class="fin-muted">（{buy_days}/5 買超）</span>'
    else:
        net5_html = "—"

    return (
        f'<div class="fin-panel">{seg}'
        f'<div class="fin-grid">'

        # EPS block
        f'<div class="fin-block">'
        f'<div class="fin-hd">EPS 全年成長 {_badge(eps_ok)}</div>'
        f'{eps_table}'
        f'<div class="fin-qs">{q_html}</div>'
        f'</div>'

        # 毛利率 block
        f'<div class="fin-block">'
        f'<div class="fin-hd">毛利率健檢 {_badge(gpm_ok)}</div>'
        f'<div class="fin-stat">最新季：{"—" if gpm_lat is None else f"{gpm_lat:.1f}%"}</div>'
        f'<div class="fin-stat">前年同季：{"—" if gpm_prv is None else f"{gpm_prv:.1f}%"}</div>'
        f'<div class="fin-stat">△：{gpm_d_html}</div>'
        f'</div>'

        # 財務結構 block
        f'<div class="fin-block">'
        f'<div class="fin-hd">財務結構 {_badge(bal)}</div>'
        f'<div class="fin-stat">D/E：{_valbadge(de, lambda x: x < 1)}</div>'
        f'<div class="fin-stat">流動比：{_valbadge(cr, lambda x: x > 1.5)}</div>'
        f'</div>'

        # 外資 block
        f'<div class="fin-block">'
        f'<div class="fin-hd">外資持股 {_badge(fh_ok)}</div>'
        f'<div class="fin-stat">{fh_str}</div>'
        f'<div class="fin-hd" style="margin-top:8px">P/E（trailing）</div>'
        f'<div class="fin-stat">{pe_str}</div>'
        f'<div class="fin-hd" style="margin-top:8px">外資近 5 日</div>'
        f'<div class="fin-stat">{net5_html}</div>'
        f'</div>'

        f'</div></div>'
    )


# ────────────── 股價資料 ──────────────

def fetch_stock_data(ticker: str) -> dict:
    try:
        hist = yf.download(ticker, period="7mo", interval="1d",
                           progress=False, auto_adjust=True)
        if hist.empty or len(hist) < 2:
            return {}
        close  = hist["Close"].squeeze().dropna()
        volume = hist["Volume"].squeeze().dropna()
        price = round(float(close.iat[-1]), 1)
        ma60  = round(float(close.tail(60).mean()), 1) if len(close) >= 60 else None
        ma120 = round(float(close.tail(120).mean()), 1) if len(close) >= 120 else None

        slope = "—"
        if ma120 and len(close) >= 125:
            ma120_5d = float(close.iloc[-125:-5].mean())
            diff_pct = (ma120 - ma120_5d) / ma120_5d * 100
            slope = "↑" if diff_pct > 0.1 else ("↓" if diff_pct < -0.1 else "→")
        elif ma120:
            slope = "→"

        vol_ok = None
        if len(volume) >= 20:
            today_vol = float(volume.iat[-1])
            avg_vol20 = float(volume.tail(20).mean())
            vol_ok = today_vol >= avg_vol20 * 0.8

        return {"price": price, "ma60": ma60, "ma120": ma120,
                "slope": slope, "vol_ok": vol_ok}
    except Exception as e:
        print(f"  [{ticker}] 抓取失敗：{e}")
        return {}


# ────────────── 工具函數 ──────────────

def parse_target(target_str: str):
    if not target_str or "~" not in target_str:
        return None, None
    parts = target_str.replace("，", "~").replace(",", "~").split("~")
    try:
        return float(parts[0].strip()), float(parts[1].strip())
    except (ValueError, IndexError):
        return None, None


def calc_distance(price: float, low: float, high: float) -> str:
    if low <= price <= high:
        return '<span class="dist-in">在目標區</span>'
    elif price > high:
        dist = round((price - high) / high * 100, 1)
        return f'<span class="dist-high">高出 {dist}%</span>'
    else:
        dist = round((low - price) / low * 100, 1)
        return f'<span class="dist-low">低於 {dist}%</span>'


def row_status(price: float, low, high) -> str:
    if low is None:
        return ""
    if low <= price <= high:
        return "in-zone"
    if price > high:
        # 偏高側：距目標區上緣 ≤10% → 黃色
        if (price - high) / high * 100 <= 10:
            return "near-zone"
        return ""
    # 偏低側：距目標區下緣 ≤10% → 黃色
    if (low - price) / low * 100 <= 10:
        return "near-zone"
    return ""


def load_event_log() -> list:
    if not os.path.exists(LOG_FILE):
        return []
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# ────────────── 降級狀態管理 ──────────────

def load_downgrade_state() -> dict:
    if not os.path.exists(DOWNGRADE_FILE):
        return {}
    try:
        with open(DOWNGRADE_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("states", {})
    except Exception:
        return {}


def save_downgrade_state(states: dict):
    with open(DOWNGRADE_FILE, "w", encoding="utf-8") as f:
        json.dump({"updated": datetime.now().strftime("%Y-%m-%d"), "states": states},
                  f, ensure_ascii=False, indent=2)


def check_downgrade(code: str, market: str, data: dict,
                    fin_data: dict, us_info_data: dict,
                    state: dict, today_str: str) -> dict:
    """評估單支股票的降級條件，回傳更新後的 state。"""
    price = data.get("price")
    ma120 = data.get("ma120")
    slope = data.get("slope", "—")

    # 技術面：MA120斜率↓ 或 跌破 ×0.80
    tech_trigger = bool(price and ma120) and (
        slope == "↓" or price < ma120 * 0.80
    )

    # 基本面：EPS 轉負 且 毛利率惡化
    fund_trigger = False
    if market == "US":
        info = (us_info_data or {}).get(code, {})
        eps  = info.get("trailing_eps")
        fund_trigger = eps is not None and eps < 0
    else:
        fin = (fin_data or {}).get(code)
        if fin:
            annual = fin.get("eps_annual", [])
            latest_eps = annual[-1].get("eps") if annual else None
            eps_negative = latest_eps is not None and latest_eps < 0
            gpm_bad = fin.get("gpm_ok") is False
            fund_trigger = eps_negative and gpm_bad

    # manual_restore 旗標：Angel 手動設定後暫停自動降級
    if state.get("manual_restore"):
        if not tech_trigger and not fund_trigger:
            state["manual_restore"] = False  # 條件消失才解除
        state["tech_trigger_current"]  = tech_trigger
        state["fund_trigger_current"]  = fund_trigger
        return state

    # 更新基本面警告起始日
    if fund_trigger:
        if not state.get("fundamental_flag_since"):
            state["fundamental_flag_since"] = today_str
    else:
        state["fundamental_flag_since"] = None

    # 基本面持續 ≥14 天才降級
    fund_demote = False
    if fund_trigger and state.get("fundamental_flag_since"):
        try:
            flag_dt  = datetime.strptime(state["fundamental_flag_since"], "%Y-%m-%d")
            today_dt = datetime.strptime(today_str, "%Y-%m-%d")
            fund_demote = (today_dt - flag_dt).days >= 14
        except ValueError:
            pass

    if tech_trigger or fund_demote:
        state["status"] = "candidate"

    state["tech_trigger_current"] = tech_trigger
    state["fund_trigger_current"] = fund_trigger
    return state


def fmt(val, suffix="") -> str:
    if val is None:
        return "—"
    return f"{val:,.1f}{suffix}"


def slope_html(slope: str) -> str:
    if slope == "↑":
        return '<span class="slope-up">↑</span>'
    elif slope == "↓":
        return '<span class="slope-down">↓</span>'
    elif slope == "→":
        return '<span class="slope-flat">→</span>'
    return '<span class="slope-flat">—</span>'


def vol_html(vol_ok) -> str:
    if vol_ok is True:
        return '<span class="vol-ok">✓ 量足</span>'
    elif vol_ok is False:
        return '<span class="vol-low">✗ 量不足</span>'
    return '<span class="vol-na">—</span>'


# ────────────── 表格列（含財報 panel）──────────────

def build_stock_rows(stocks_data: list, fin_data: dict, us_info_data: dict = None,
                     states: dict = None) -> str:
    rows = []
    for s in stocks_data:
        market = s.get("market", "TW")
        d      = s.get("data", {})
        price  = d.get("price")
        ma60   = d.get("ma60")
        ma120  = d.get("ma120")
        slope  = d.get("slope", "—")
        vol_ok = d.get("vol_ok")
        target = s.get("target", "")
        code   = s["code"]

        # 美股目標區由 MA120 × 0.80~0.95 動態計算
        if market == "US" and not target and ma120:
            target = f"{ma120 * 0.80:.2f}~{ma120 * 0.95:.2f}"

        low, high = parse_target(target)
        status = row_status(price, low, high) if price else ""
        dist   = calc_distance(price, low, high) if (price and low) else "N/A"
        css    = f' class="{status}"' if status else ""

        # 警告 badge（降級觸發指示）
        st = (states or {}).get(code, {})
        badge_html = ""
        if st.get("tech_trigger_current"):
            badge_html = '<span class="tech-warn-badge">技術↓</span>'
        elif st.get("fund_trigger_current"):
            since = st.get("fundamental_flag_since")
            if since:
                try:
                    days = (datetime.now() - datetime.strptime(since, "%Y-%m-%d")).days
                    badge_html = f'<span class="fund-warn-badge">⚠️ {days}d</span>'
                except ValueError:
                    badge_html = '<span class="fund-warn-badge">⚠️</span>'
            else:
                badge_html = '<span class="fund-warn-badge">⚠️</span>'

        # 代號 cell：可點擊展開 panel
        code_cell = (
            f'<span id="btn-{code}" class="code code-btn" '
            f'onclick="toggleFin(\'{code}\')">'
            f'{code}{badge_html}<span class="arrow"> ▸</span></span>'
        )

        if market == "US":
            info  = (us_info_data or {}).get(code, {})
            panel = us_fin_panel_html(code, info)
        else:
            fin   = fin_data.get(code) if fin_data else None
            panel = fin_panel_html(code, fin)

        rows.append(f"""
        <tr{css}>
          <td>{code_cell}</td>
          <td>{s['name']}</td>
          <td>{fmt(price)}</td>
          <td>{fmt(ma60)}</td>
          <td>{fmt(ma120)}</td>
          <td style="text-align:center">{slope_html(slope)}</td>
          <td style="text-align:center">{vol_html(vol_ok)}</td>
          <td class="target-cell">{target if target else '<span class="na">N/A</span>'}</td>
          <td class="dist-cell">{dist}</td>
        </tr>
        <tr id="fin-{code}" class="fin-panel-row" style="display:none">
          <td colspan="9">{panel}</td>
        </tr>""")
    return "\n".join(rows)


def build_industry_sections(stocks_data: list, fin_data: dict,
                            us_info_data: dict = None, states: dict = None) -> str:
    industries: dict = {}
    for s in stocks_data:
        ind = s.get("industry", "其他")
        if ind not in industries:
            industries[ind] = []
        industries[ind].append(s)

    sections = []
    for ind, stocks in industries.items():
        rows  = build_stock_rows(stocks, fin_data, us_info_data, states)
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
          <th>趨勢</th><th>量能</th>
          <th>觀察目標區</th><th>距目標區</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
</section>""")
    return "\n".join(sections)


def build_candidate_section(stocks_data: list, fin_data: dict,
                            us_info_data: dict, states: dict) -> str:
    if not stocks_data:
        return ""
    sections_html = build_industry_sections(stocks_data, fin_data, us_info_data, states)
    note = (
        '此區股票已自動觸發降級條件（技術面 或 基本面持續 14 天）。'
        '確認回升後，在 <code>downgrade_state.json</code> 將該代號的 '
        '<code>manual_restore</code> 設為 <code>true</code>，重跑腳本即升回主名單。'
    )
    return (
        f'<p class="candidate-title">候選區（降級觀察）— {len(stocks_data)} 檔</p>'
        f'<div class="candidate-note">{note}</div>'
        f'{sections_html}'
    )


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


# ────────────── HTML 組裝 ──────────────

def build_html(tw_stocks_data: list, us_stocks_data: list,
               tw_candidate_data: list, us_candidate_data: list,
               events: list, generated_at: str,
               fin_data: dict, us_info_data: dict, states: dict) -> str:
    tw_sections       = build_industry_sections(tw_stocks_data, fin_data, states=states)
    us_sections       = build_industry_sections(us_stocks_data, fin_data, us_info_data, states=states)
    tw_candidate_html = build_candidate_section(tw_candidate_data, fin_data, None, states)
    us_candidate_html = build_candidate_section(us_candidate_data, fin_data, us_info_data, states)
    event_rows        = build_event_rows(events)
    fin_updated = ""
    if fin_data:
        try:
            with open(FINANCIAL_FILE, "r", encoding="utf-8") as f:
                fin_meta = json.load(f)
            fin_updated = f'財報資料：{fin_meta.get("updated", "—")} | '
        except Exception:
            pass

    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='5' fill='%23003049'/%3E%3Ccircle cx='16' cy='16' r='10' fill='none' stroke='%23C1121F' stroke-width='2.5'/%3E%3Ccircle cx='16' cy='16' r='4' fill='%23C1121F'/%3E%3C/svg%3E">
<title>美股下殺台股觀察</title>
<style>
  :root {{
    --bg:        #FDF0D5;
    --card:      #ffffff;
    --header-bg: #003049;
    --border:    rgba(0,48,73,0.15);
    --text:      #003049;
    --muted:     #669BBC;
    --green:     #15803d;
    --amber:     #b45309;
    --red:       #780000;
    --accent:    #C1121F;
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
    color: var(--muted); font-size: 13px; margin-bottom: 20px;
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
    border-bottom: 1px solid rgba(253,240,213,0.12);
  }}
  .industry-dot {{
    width: 8px; height: 8px;
    border-radius: 50%; flex-shrink: 0;
  }}
  .industry-name {{
    font-size: 13px; font-weight: 700;
    color: #FDF0D5; letter-spacing: .2px;
  }}
  .industry-count {{
    font-size: 12px; color: rgba(253,240,213,0.55); margin-left: auto;
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
  tr:hover td {{ background: rgba(0,48,73,0.04); }}
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
  .dist-in   {{ color: var(--green); font-weight: 600; }}
  .dist-high {{ color: var(--muted); }}
  .dist-low  {{ color: var(--amber); }}
  .target-cell {{ font-size: 13px; color: var(--muted); }}
  .slope-up   {{ color: var(--green); font-weight: 700; }}
  .slope-flat {{ color: var(--muted); }}
  .slope-down {{ color: var(--red);   font-weight: 700; }}
  .vol-ok  {{ color: var(--green); font-size: 12px; }}
  .vol-low {{ color: var(--red);   font-size: 12px; }}
  .vol-na  {{ color: var(--muted); font-size: 12px; font-style: italic; }}

  /* ── 事件日誌卡 ── */
  .log-card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 10px;
    overflow: hidden;
    box-shadow: 0 1px 3px rgba(15,23,42,.05);
  }}

  /* ── 選股標準 v2 ── */
  .criteria-card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 14px 18px;
    margin-bottom: 14px;
    box-shadow: 0 1px 3px rgba(15,23,42,.05);
  }}
  .criteria-layer {{
    display: flex; align-items: baseline; gap: 10px;
    padding: 6px 0;
    border-bottom: 1px solid var(--border);
    font-size: 12px;
  }}
  .criteria-layer:last-child {{ border-bottom: none; }}
  .criteria-layer-label {{
    min-width: 110px; font-weight: 700;
    color: var(--accent); flex-shrink: 0; font-size: 11px;
    text-transform: uppercase; letter-spacing: .4px;
  }}
  .criteria-layer-items {{
    color: var(--muted); flex: 1;
    display: flex; flex-wrap: wrap; gap: 4px 12px;
  }}
  .ci {{ display: flex; align-items: center; gap: 4px; white-space: nowrap; }}
  .ci::before {{ content: "·"; color: var(--accent); font-weight: 700; }}
  .ci-m5 {{ opacity: .65; font-style: italic; }}
  .ci-m5::before {{ content: "·"; color: var(--muted); }}

  /* ── 出場規則 ── */
  .exit-card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 12px 18px;
    margin-bottom: 14px;
    box-shadow: 0 1px 3px rgba(15,23,42,.05);
    display: flex; gap: 24px; flex-wrap: wrap;
  }}
  .exit-item {{ display: flex; align-items: center; gap: 8px; font-size: 13px; }}
  .exit-badge {{
    font-size: 11px; font-weight: 700;
    padding: 2px 7px; border-radius: 4px;
    white-space: nowrap;
  }}
  .exit-badge.stop-loss  {{ background: rgba(120,0,0,.1);  color: var(--red); }}
  .exit-badge.take-profit {{ background: rgba(21,128,61,.1);  color: var(--green); }}
  .exit-rule {{ color: var(--muted); font-size: 12px; }}

  .updated {{
    color: var(--muted); font-size: 12px;
    margin-top: 24px; text-align: right;
  }}

  @media (max-width: 600px) {{
    body {{ font-size: 13px; padding: 12px; }}
    td, th {{ padding: 7px 8px; }}
    .dist-cell, .target-cell {{ font-size: 12px; }}
  }}
{FIN_CSS}
{TAB_CSS}
{CANDIDATE_CSS}
</style>
</head>
<body>

<h1>美股下殺台股觀察</h1>
<p class="subtitle">SOX 跌幅 ≥ 2% 時自動記錄，追蹤體質健康的台股連動情況</p>

<div class="tab-bar">
  <button class="tab-btn active" data-tab="us" onclick="switchTab('us')">美股</button>
  <button class="tab-btn" data-tab="tw" onclick="switchTab('tw')">台股</button>
</div>

<!-- ── 美股 Tab ── -->
<div id="tab-us" class="tab-content" style="display:block">

<p class="section-title">選股 SOP（美股）</p>
<div class="criteria-card">
  <div class="criteria-layer">
    <span class="criteria-layer-label">市場 &amp; 流動性</span>
    <span class="criteria-layer-items">
      <span class="ci">NYSE / NASDAQ 上市</span>
      <span class="ci">市值 ≥ 500 億美元</span>
    </span>
  </div>
  <div class="criteria-layer">
    <span class="criteria-layer-label">產業曝險</span>
    <span class="criteria-layer-items">
      <span class="ci">AI 核心 或 半導體供應鏈</span>
      <span class="ci">主要業務直接相關</span>
    </span>
  </div>
  <div class="criteria-layer">
    <span class="criteria-layer-label">基本面</span>
    <span class="criteria-layer-items">
      <span class="ci ci-m5">EPS YoY 正成長</span>
      <span class="ci ci-m5">毛利率未大幅下滑</span>
      <span class="ci ci-m5">機構持股 % 顯示</span>
    </span>
  </div>
  <div class="criteria-layer">
    <span class="criteria-layer-label">技術進場</span>
    <span class="criteria-layer-items">
      <span class="ci">MA120 斜率向上（↑）</span>
      <span class="ci">股價在 MA120 × 0.80 ～ 0.95</span>
      <span class="ci">量 ≥ 近 20MA × 0.8</span>
    </span>
  </div>
</div>

<p class="section-title">出場規則</p>
<div class="exit-card">
  <div class="exit-item">
    <span class="exit-badge stop-loss">停損</span>
    <span class="exit-rule">收盤跌破 MA120 × 0.80 → 出場</span>
  </div>
  <div class="exit-item">
    <span class="exit-badge take-profit">停利</span>
    <span class="exit-rule">股價站上 MA120 × 1.20 → 分批減碼</span>
  </div>
</div>

<p class="section-title">觀察名單（美股）</p>
{us_sections}
{us_candidate_html}

</div><!-- /tab-us -->

<!-- ── 台股 Tab ── -->
<div id="tab-tw" class="tab-content">

<p class="section-title">選股 SOP（台股）</p>
<div class="criteria-card">
  <div class="criteria-layer">
    <span class="criteria-layer-label">市場 &amp; 流動性</span>
    <span class="criteria-layer-items">
      <span class="ci">TWSE / OTC 上市</span>
      <span class="ci">市值 ≥ 100 億</span>
    </span>
  </div>
  <div class="criteria-layer">
    <span class="criteria-layer-label">產業曝險</span>
    <span class="criteria-layer-items">
      <span class="ci">主要營收 AI / 蘋果 / 網通 ≥ 40%</span>
      <span class="ci">同產業持股上限 4 支</span>
    </span>
  </div>
  <div class="criteria-layer">
    <span class="criteria-layer-label">基本面（M5）</span>
    <span class="criteria-layer-items">
      <span class="ci ci-m5">EPS 連續 YoY 成長</span>
      <span class="ci ci-m5">毛利率未較前年同期 -3ppt</span>
      <span class="ci ci-m5">外資持股 &gt; 20%</span>
      <span class="ci ci-m5">D/E &lt; 1 或流動比 &gt; 1.5</span>
      <span class="ci ci-m5">P/E ≤ 同業均值 × 1.5</span>
    </span>
  </div>
  <div class="criteria-layer">
    <span class="criteria-layer-label">技術進場</span>
    <span class="criteria-layer-items">
      <span class="ci">MA120 斜率向上（↑）</span>
      <span class="ci">股價在 MA120 × 0.85 ～ 0.95</span>
      <span class="ci">量 ≥ 近 20MA × 0.8</span>
    </span>
  </div>
</div>

<p class="section-title">出場規則</p>
<div class="exit-card">
  <div class="exit-item">
    <span class="exit-badge stop-loss">停損</span>
    <span class="exit-rule">收盤跌破 MA120 × 0.80 → 出場</span>
  </div>
  <div class="exit-item">
    <span class="exit-badge take-profit">停利</span>
    <span class="exit-rule">股價站上 MA120 × 1.20 → 分批減碼</span>
  </div>
</div>

<p class="section-title">觀察名單（台股）</p>
{tw_sections}
{tw_candidate_html}

</div><!-- /tab-tw -->

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

<p class="updated">{fin_updated}最後更新：{generated_at}</p>

{FIN_JS}
</body>
</html>"""


def main():
    print(f"\n{'='*52}")
    print(f"  美股下殺觀察網頁生成器 — {datetime.now().strftime('%Y/%m/%d %H:%M')}")
    print(f"{'='*52}\n")

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)

    tw_config = [s for s in config if s.get("market", "TW") != "US"]
    us_config = [s for s in config if s.get("market") == "US"]

    fin_data = load_financial_data()
    if fin_data:
        print(f"  ✓ 台股財報資料已載入（{len(fin_data)} 支）\n")
    else:
        print(f"  ⚠  financial_data.json 未找到，台股財報 panel 顯示提示訊息\n")

    # 台股股價
    print(f"  抓取台股 {len(tw_config)} 檔股票資料...\n")
    tw_stocks_data = []
    for s in tw_config:
        print(f"  {s['code']} {s['name']}...", end=" ", flush=True)
        d = fetch_stock_data(s["ticker"])
        if d:
            print(f"  ✓  現價 {d.get('price', '—')}")
        else:
            print("  ✗  無資料")
        tw_stocks_data.append({**s, "data": d})

    # 美股股價
    print(f"\n  抓取美股 {len(us_config)} 檔股票資料...\n")
    us_stocks_data = []
    for s in us_config:
        print(f"  {s['code']} {s['name']}...", end=" ", flush=True)
        d = fetch_stock_data(s["ticker"])
        if d:
            print(f"  ✓  現價 {d.get('price', '—')}")
        else:
            print("  ✗  無資料")
        us_stocks_data.append({**s, "data": d})

    # 美股財報（yfinance .info）
    print(f"\n  抓取美股 .info 財報資料...\n")
    us_info_data = {}
    for s in us_config:
        print(f"  {s['code']} {s['name']} .info...", end=" ", flush=True)
        info = fetch_us_stock_info(s["ticker"])
        if info:
            print("  ✓")
        else:
            print("  ✗")
        us_info_data[s["code"]] = info

    events = load_event_log()
    print(f"\n  讀取事件日誌：{len(events)} 筆")

    # ── M7：降級條件檢查 ──
    print(f"\n  檢查降級條件（M7）...")
    downgrade_states = load_downgrade_state()
    today_str = datetime.now().strftime("%Y-%m-%d")
    for s in tw_stocks_data + us_stocks_data:
        code   = s["code"]
        market = s.get("market", "TW")
        state  = downgrade_states.get(code, {"status": "watchlist"})
        downgrade_states[code] = check_downgrade(
            code, market, s.get("data", {}), fin_data, us_info_data, state, today_str
        )
        if downgrade_states[code].get("status") == "candidate":
            print(f"  [{code}] → 候選區")
    save_downgrade_state(downgrade_states)

    tw_watchlist  = [s for s in tw_stocks_data
                     if downgrade_states.get(s["code"], {}).get("status", "watchlist") == "watchlist"]
    tw_candidates = [s for s in tw_stocks_data
                     if downgrade_states.get(s["code"], {}).get("status", "watchlist") == "candidate"]
    us_watchlist  = [s for s in us_stocks_data
                     if downgrade_states.get(s["code"], {}).get("status", "watchlist") == "watchlist"]
    us_candidates = [s for s in us_stocks_data
                     if downgrade_states.get(s["code"], {}).get("status", "watchlist") == "candidate"]
    print(f"  台股 主名單 {len(tw_watchlist)} / 候選區 {len(tw_candidates)}")
    print(f"  美股 主名單 {len(us_watchlist)} / 候選區 {len(us_candidates)}")

    generated_at = datetime.now().strftime("%Y/%m/%d %H:%M")
    html = build_html(tw_watchlist, us_watchlist, tw_candidates, us_candidates,
                      events, generated_at, fin_data, us_info_data, downgrade_states)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n  ✅ 輸出完成 → {OUTPUT_FILE}")
    print(f"     開啟：open '{OUTPUT_FILE}'\n")


if __name__ == "__main__":
    main()
