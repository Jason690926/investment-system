"""
run_weekly_report.py
GitHub Actions 每週六 09:00 台灣時間（UTC 01:00）執行。
1. 抓大盤（^TWII）+ 全球市場 + 商品行情
2. 抓台股財經新聞（Google News RSS）
3. AI 分析：大盤週報 + 產業指標股
4. 存 WeeklyReport DB（本週已存在則跳過）
5. Email 通知
"""
import os
import time
import smtplib
from datetime import date, datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from dotenv import load_dotenv
load_dotenv()

from modules.database import SessionLocal, init_db
from modules.models import User, WeeklyReport
from modules.data_enricher import get_full_stock_data
from modules.data_fetcher import get_global_markets, get_commodities, get_tw_news_rss
from modules.ai_analyzer_v2 import analyze_weekly_taiwan_v2, get_industry_indicator_stocks

TW = timezone(timedelta(hours=8))


def build_global_summary(global_markets: dict, commodities: dict) -> str:
    lines = []
    for name, data in global_markets.items():
        if data and data.get('price'):
            chg = data.get('change', 0) or 0
            arrow = '▲' if chg > 0 else ('▼' if chg < 0 else '—')
            lines.append(f"{name}: {data['price']} ({arrow}{abs(chg):.2f}%)")
    for name, data in commodities.items():
        if data and data.get('price'):
            chg = data.get('change', 0) or 0
            arrow = '▲' if chg > 0 else ('▼' if chg < 0 else '—')
            lines.append(f"{name}: {data['price']} ({arrow}{abs(chg):.2f}%)")
    return '\n'.join(lines)


def send_weekly_notification(users: list, app_url: str, week_range: str):
    sender = os.getenv('EMAIL_SENDER')
    password = os.getenv('EMAIL_PASSWORD')
    if not sender or not password:
        print("[weekly] EMAIL_SENDER/EMAIL_PASSWORD 未設定，跳過通知")
        return

    for user in users:
        try:
            msg = MIMEMultipart()
            msg['From'] = sender
            msg['To'] = user.email
            msg['Subject'] = f'【投資週報】{week_range} 產業週報已就緒'
            body = (
                f'您好 {user.name}，\n\n'
                f'本週（{week_range}）產業週報已完成，請點連結查看：\n\n'
                f'{app_url}/weekly-report\n\n'
                f'本報表由自動化系統產生，僅供學習參考，不構成實際投資建議。\n\n'
                f'祝投資順利！'
            )
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            with smtplib.SMTP('smtp.gmail.com', 587) as server:
                server.starttls()
                server.login(sender, password)
                server.sendmail(sender, user.email, msg.as_string())
            print(f"[weekly] ✉ 通知已寄送：{user.email}")
        except Exception as e:
            print(f"[weekly] ✉ 寄送失敗 {user.email}: {e}")


def main():
    print(f"[weekly] 開始 — {datetime.now(TW).strftime('%Y-%m-%d %H:%M')} 台灣時間")
    init_db()

    today = date.today()
    week_start = today - timedelta(days=today.weekday())  # 本週一
    week_end = today
    week_range = f"{week_start.strftime('%Y/%m/%d')} ~ {week_end.strftime('%Y/%m/%d')}"

    db = SessionLocal()
    try:
        existing = db.query(WeeklyReport).filter_by(week_start=week_start).first()
        if existing:
            print(f"[weekly] 本週週報已存在（{week_range}），跳過")
            return

        # 1. 大盤資料
        print("[weekly] 抓取大盤（^TWII）資料...")
        twii = get_full_stock_data('^TWII')
        if twii is None:
            print("[weekly] ⚠ 無法取得 ^TWII 資料，結束")
            return

        # 2. 全球市場
        print("[weekly] 抓取全球市場與商品行情...")
        global_markets = get_global_markets()
        commodities = get_commodities()
        global_summary = build_global_summary(global_markets, commodities)

        # 3. 財經新聞
        print("[weekly] 抓取台股財經新聞（RSS）...")
        news = get_tw_news_rss(n=15)
        print(f"[weekly] 取得 {len(news)} 則新聞")

        # 4. AI 分析
        print("[weekly] AI 大盤週報分析...")
        html_market = analyze_weekly_taiwan_v2(twii, global_summary, week_range)
        time.sleep(3)

        print("[weekly] AI 產業指標股分析...")
        html_industry = get_industry_indicator_stocks(news, global_summary)

        # 5. 存 DB
        db.add(WeeklyReport(
            week_start=week_start,
            week_end=week_end,
            html_market=html_market,
            html_industry=html_industry,
        ))
        db.commit()
        print(f"[weekly] ✅ 週報已存入 DB（{week_range}）")

        # 6. Email 通知
        app_url = os.getenv('APP_URL', 'https://investment-system-lxq5.onrender.com')
        notify_users = db.query(User).filter_by(email_notify=True).all()
        if notify_users:
            send_weekly_notification(notify_users, app_url, week_range)
        else:
            print("[weekly] 無需通知的用戶")

    finally:
        db.close()

    print(f"[weekly] 結束 — {datetime.now(TW).strftime('%Y-%m-%d %H:%M')} 台灣時間")


if __name__ == '__main__':
    main()
