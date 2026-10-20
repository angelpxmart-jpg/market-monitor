#!/usr/bin/env python3
"""
每日觀察網頁重點摘要信 — 讀 mail_summary.json，寄到 Gmail
由 run_market_web.sh 在網頁更新 push 後呼叫；平日一天只寄一次（--force 可略過檢查）
"""

import html
import json
import os
import smtplib
import sys
from datetime import datetime
from email.mime.text import MIMEText

import yfinance as yf

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
SUMMARY_FILE = os.path.join(BASE_DIR, "mail_summary.json")
SENT_FILE    = os.path.join(BASE_DIR, "logs", "mail_sent.txt")
# Gmail 應用程式密碼與盤後摘要共用同一份 .env
DIGEST_ENV   = os.path.join(os.path.dirname(BASE_DIR), "daily-market-digest", ".env")

# 寄件／收件地址放在本機 .env（repo 公開，不寫進程式）
LOCAL_ENV  = os.path.join(BASE_DIR, ".env")


def read_env(path: str, key: str) -> str:
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith(key + "="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


GMAIL_USER = read_env(LOCAL_ENV, "MAIL_FROM")
TO_LIST    = [a.strip() for a in read_env(LOCAL_ENV, "MAIL_TO").split(",") if a.strip()]
PAGE_URL   = "https://angelpxmart-jpg.github.io/market-monitor/"

NAVY, RED, AMBER, GREEN, MUTED = "#003049", "#C1121F", "#b45309", "#15803d", "#669BBC"


def load_app_pw() -> str:
    pw = os.environ.get("GMAIL_APP_PW", "")
    if not pw and os.path.exists(DIGEST_ENV):
        with open(DIGEST_ENV, encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("GMAIL_APP_PW="):
                    pw = line.split("=", 1)[1].strip().strip('"').strip("'")
    return pw.replace("\xa0", "").replace(" ", "")


def fetch_sox_change():
    try:
        close = yf.download("^SOX", period="5d", interval="1d",
                            progress=False, auto_adjust=True)["Close"].squeeze().dropna()
        if len(close) < 2:
            return None
        return round((float(close.iat[-1]) / float(close.iat[-2]) - 1) * 100, 2)
    except Exception as e:
        print(f"  SOX 抓取失敗：{e}")
        return None


def stock_table(items: list, color: str, show_dist: bool) -> str:
    if not items:
        return f'<p style="margin:4px 0 0;color:{MUTED};font-size:14px;">無</p>'
    rows = []
    for e in items:
        mk = "美" if e["market"] == "US" else "台"
        extra = e["dist"] if (show_dist and e.get("dist")) else f'目標 {e["target"]}'
        if e.get("signal") == "check":
            extra = e["signal_label"].replace("價位到・", "缺：")
        desc = (f'<div style="font-size:12px;color:{MUTED};white-space:normal;margin-top:2px;">{e["desc"]}</div>'
                if e.get("desc") else "")
        rows.append(
            f'<tr><td style="padding:6px 8px 6px 0;font-size:14px;vertical-align:top;">'
            f'<span style="color:{MUTED};font-size:12px;">{mk}</span> '
            f'<b style="color:{NAVY};">{e["code"]}</b> {e["name"]}{desc}</td>'
            f'<td style="padding:6px 0;font-size:14px;text-align:right;white-space:nowrap;vertical-align:top;">{e["price"]}</td>'
            f'<td style="padding:6px 0 6px 10px;font-size:13px;color:{color};text-align:right;white-space:nowrap;vertical-align:top;">{extra}</td></tr>'
        )
    return f'<table style="width:100%;border-collapse:collapse;">{"".join(rows)}</table>'


def section(title: str, color: str, body: str) -> str:
    return (f'<div style="margin:18px 0 0;">'
            f'<div style="font-size:15px;font-weight:bold;color:{color};border-bottom:2px solid {color};padding-bottom:4px;">{title}</div>'
            f'{body}</div>')


def briefing_block(text: str) -> str:
    if not text:
        return ""
    return (f'<div style="margin:14px 0 0;padding:12px 14px;background:#f8fafc;border-left:4px solid {RED};'
            f'font-size:14px;line-height:1.8;">'
            f'<div style="font-weight:bold;color:{RED};font-size:13px;margin-bottom:4px;">昨日解說</div>'
            f'{html.escape(text)}'
            f'<div style="font-size:11px;color:{MUTED};margin-top:6px;">由 Claude 依當日數據撰寫，只描述數字、不推測原因，不構成投資建議</div></div>')


def split_in_zone(s: dict):
    go    = [e for e in s["in_zone"] if e.get("signal") == "go"]
    check = [e for e in s["in_zone"] if e.get("signal") != "go"]
    return go, check


def build_html(s: dict, sox) -> str:
    go, check = split_in_zone(s)
    if sox is None:
        sox_txt = "SOX：未取得"
    else:
        sox_color = RED if sox < 0 else GREEN
        trigger = "（下殺觸發）" if sox <= -2 else ""
        sox_txt = f'SOX 前一交易日 <b style="color:{sox_color};">{sox:+.2f}%</b>{trigger}'
    return f"""<div style="font-family:-apple-system,'PingFang TC','Microsoft JhengHei',sans-serif;max-width:560px;margin:0 auto;padding:16px;background:#ffffff;color:{NAVY};">
<div style="font-size:18px;font-weight:bold;">美股下殺台股觀察｜{datetime.now().strftime('%m/%d')}</div>
<div style="font-size:14px;margin-top:6px;">{sox_txt}</div>
{briefing_block(s.get("briefing", ""))}
{section(f"可進場：三個條件都符合（{len(go)}）", GREEN, stock_table(go, GREEN, False))}
{section(f"價位到了，但條件還沒齊（{len(check)}）", AMBER, stock_table(check, AMBER, False))}
{section(f"接近目標區 ≤10%（{len(s['near_zone'])}）", MUTED, stock_table(s["near_zone"], MUTED, True))}
{section(f"候選區（{len(s['candidates'])}）", RED, stock_table(s["candidates"], RED, True))}
<div style="margin-top:22px;"><a href="{PAGE_URL}" style="display:inline-block;background:{NAVY};color:#ffffff;text-decoration:none;padding:10px 18px;border-radius:6px;font-size:14px;">打開完整觀察網頁</a></div>
<div style="margin-top:14px;font-size:12px;color:{MUTED};">資料更新：{s['generated_at']}</div>
</div>"""


def main():
    force = "--force" in sys.argv
    today = datetime.now().strftime("%Y-%m-%d")

    if not force:
        if datetime.now().weekday() >= 5:
            print("  週末不寄信")
            return
        if os.path.exists(SENT_FILE) and open(SENT_FILE).read().strip() == today:
            print("  今日已寄過，略過")
            return

    with open(SUMMARY_FILE, encoding="utf-8") as f:
        summary = json.load(f)
    if not summary["generated_at"].startswith(datetime.now().strftime("%Y/%m/%d")):
        print(f"  ERROR: mail_summary.json 不是今天的資料（{summary['generated_at']}），不寄出")
        sys.exit(1)

    if not GMAIL_USER or not TO_LIST:
        print("  ERROR: .env 缺少 MAIL_FROM / MAIL_TO")
        sys.exit(1)
    pw = load_app_pw()
    if not pw:
        print("  ERROR: 找不到 GMAIL_APP_PW")
        sys.exit(1)

    sox = summary["sox"] if summary.get("sox") is not None else fetch_sox_change()
    body = build_html(summary, sox)
    go, check = split_in_zone(summary)
    subject = (f"觀察名單 {datetime.now().strftime('%m/%d')}｜"
               f"可進場 {len(go)}・價位到 {len(check)}・接近 {len(summary['near_zone'])}")
    msg = MIMEText(body, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"]    = GMAIL_USER
    msg["To"]      = ", ".join(TO_LIST)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, pw)
        server.sendmail(GMAIL_USER, TO_LIST, msg.as_string())

    os.makedirs(os.path.dirname(SENT_FILE), exist_ok=True)
    with open(SENT_FILE, "w") as f:
        f.write(today)
    print(f"  已寄出：{subject} → {', '.join(TO_LIST)}")


if __name__ == "__main__":
    main()
