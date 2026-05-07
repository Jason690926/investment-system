"""
run_daily_report.py
GitHub Actions 每日 14:30（UTC 06:30）執行。
1. 掃所有用戶追蹤的股票，依重疊性排序（重疊最多優先）
2. 逐支分析：今日快取存在則跳過，否則呼叫 AI（第一段：客觀市場分析）
3. 通知有開啟 email_notify 的用戶
"""
import bisect
import os
import time
import smtplib
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import func
from modules.database import SessionLocal, init_db
from modules.models import User, Stock, StockAnalysis, PatternHistory, DailyMarketSummary
from modules.data_enricher import get_full_stock_data
from modules.ai_analyzer_v2 import analyze_market_only, analyze_daily_news
from modules.data_fetcher import get_tw_news_rss, get_global_markets

TW = timezone(timedelta(hours=8))


def _save_patterns(db, symbol: str, detected_patterns: list, close_price, today: date):
    existing_names = {
        row.pattern_name
        for row in db.query(PatternHistory.pattern_name).filter_by(
            symbol=symbol, detected_date=today
        ).all()
    }
    for p in detected_patterns:
        if p['name'] in existing_names:
            continue
        db.add(PatternHistory(
            symbol=symbol,
            detected_date=today,
            pattern_name=p['name'],
            direction=p['type'],
            candle_count=p.get('candle_count', 1),
            close_price=float(close_price) if close_price else None,
        ))
    db.commit()


def _backfill_patterns(db, symbol: str, daily_bars: list, today: date):
    pending = db.query(PatternHistory).filter(
        PatternHistory.symbol == symbol,
        PatternHistory.return_10d.is_(None),
        PatternHistory.detected_date <= today - timedelta(days=3),
    ).all()
    if not pending:
        return

    price_by_date = {}
    for b in daily_bars:
        try:
            price_by_date[date.fromisoformat(b['date'])] = float(b['close'])
        except Exception:
            pass
    sorted_dates = sorted(price_by_date.keys())

    for p in pending:
        idx = bisect.bisect_right(sorted_dates, p.detected_date)
        future = sorted_dates[idx:]
        base = float(p.close_price) if p.close_price else None
        if not base:
            continue
        if p.return_3d is None and len(future) >= 3:
            p.return_3d = round((price_by_date[future[2]] - base) / base * 100, 2)
        if p.return_5d is None and len(future) >= 5:
            p.return_5d = round((price_by_date[future[4]] - base) / base * 100, 2)
        if p.return_10d is None and len(future) >= 10:
            p.return_10d = round((price_by_date[future[9]] - base) / base * 100, 2)
    db.commit()


def get_symbols_by_overlap(db) -> list[tuple[str, str, int]]:
    """回傳 [(symbol, name, user_count), ...] 依重疊人數降冪排列"""
    rows = (
        db.query(Stock.symbol, Stock.name, func.count(Stock.user_id).label('cnt'))
        .group_by(Stock.symbol, Stock.name)
        .order_by(func.count(Stock.user_id).desc())
        .all()
    )
    return [(r.symbol, r.name, r.cnt) for r in rows]


def is_cached_today(db, symbol: str) -> bool:
    return db.query(StockAnalysis).filter_by(
        symbol=symbol, analysis_date=date.today(), analysis_type='daily'
    ).count() > 0


def cache_market_analysis(db, symbol: str, name: str) -> bool:
    enriched = get_full_stock_data(symbol)
    if enriched is None:
        print(f"[batch] [!] 無法取得 {symbol} 資料，跳過")
        return False

    today = date.today()
    daily_bars = enriched.get('daily_bars', [])
    _backfill_patterns(db, symbol, daily_bars, today)

    result = analyze_market_only(name=name, symbol=symbol, enriched_data=enriched)
    existing = db.query(StockAnalysis).filter_by(
        symbol=symbol, analysis_date=today, analysis_type='daily'
    ).first()

    if existing:
        existing.html_content     = result['html']
        existing.risk_pct         = result['risk_pct']
        existing.support_price    = Decimal(str(result['support']))    if result['support']    else None
        existing.resistance_price = Decimal(str(result['resistance'])) if result['resistance'] else None
        existing.target_price     = Decimal(str(result['target_pnf'])) if result['target_pnf'] else None
        existing.wyckoff_phase    = result['wyckoff_phase']
        existing.generated_at     = datetime.utcnow()
    else:
        db.add(StockAnalysis(
            symbol=symbol, analysis_date=today, analysis_type='daily',
            html_content=result['html'],
            risk_pct=result['risk_pct'],
            support_price=Decimal(str(result['support']))    if result['support']    else None,
            resistance_price=Decimal(str(result['resistance'])) if result['resistance'] else None,
            target_price=Decimal(str(result['target_pnf'])) if result['target_pnf'] else None,
            wyckoff_phase=result['wyckoff_phase'],
        ))
    db.commit()

    detected = result.get('detected_patterns', [])
    if detected:
        _save_patterns(db, symbol, detected, enriched.get('price'), today)

    return True


def send_notification(users: list, app_url: str):
    sender   = os.getenv('EMAIL_SENDER')
    password = os.getenv('EMAIL_PASSWORD')
    if not sender or not password:
        print("[batch] EMAIL_SENDER / EMAIL_PASSWORD 未設定，跳過通知")
        return

    today_str = datetime.now(TW).strftime('%Y/%m/%d')

    for user in users:
        try:
            msg = MIMEMultipart()
            msg['From']    = sender
            msg['To']      = user.email
            msg['Subject'] = f'【投資建議】{today_str} 今日分析已就緒'

            body = (
                f'您好 {user.name}，\n\n'
                f'今日（{today_str}）三大宗師分析已完成，請點連結查看：\n\n'
                f'{app_url}/dashboard\n\n'
                f'本報表由自動化系統產生，僅供學習參考，不構成實際投資建議。\n\n'
                f'祝投資順利！'
            )
            msg.attach(MIMEText(body, 'plain', 'utf-8'))

            with smtplib.SMTP('smtp.gmail.com', 587) as server:
                server.starttls()
                server.login(sender, password)
                server.sendmail(sender, user.email, msg.as_string())

            print(f"[batch] ✉ 通知已寄送：{user.email}")
        except Exception as e:
            print(f"[batch] ✉ 寄送失敗 {user.email}: {e}")


def main():
    print(f"[batch] 開始 — {datetime.now(TW).strftime('%Y-%m-%d %H:%M')} 台灣時間")
    init_db()

    db = SessionLocal()
    try:
        symbols = get_symbols_by_overlap(db)
        if not symbols:
            print("[batch] 沒有任何追蹤股票，結束")
            return

        total    = len(symbols)
        analyzed = 0
        skipped  = 0

        for i, (symbol, name, user_count) in enumerate(symbols, 1):
            if is_cached_today(db, symbol):
                print(f"[batch] {i}/{total} {symbol} 今日已有快取，跳過")
                skipped += 1
                continue

            print(f"[batch] {i}/{total} 分析 {name}（{symbol}）— {user_count} 人追蹤")
            ok = cache_market_analysis(db, symbol, name)
            if ok:
                analyzed += 1

            # 避免 rate limit，兩支之間稍作間隔
            if i < total:
                time.sleep(3)

        print(f"[batch] 完成：分析 {analyzed} 支，快取命中 {skipped} 支，共 {total} 支")

        # 每日財經新聞摘要（平日印表報表用）
        today = datetime.now(TW).date()
        news_exists = db.query(DailyMarketSummary).filter_by(summary_date=today).first()
        if not news_exists:
            print("[batch] 產生今日財經新聞摘要...")
            try:
                news = get_tw_news_rss(15)
                twii_price, twii_change_pct = None, None
                try:
                    markets = get_global_markets()
                    twii_data = markets.get('台灣加權', {})
                    twii_price = twii_data.get('price')
                    twii_change_pct = twii_data.get('change')
                except Exception as _e:
                    print(f"[batch] TWII 資料抓取失敗，新聞摘要將無大盤數值: {_e}")
                html_news = analyze_daily_news(news, twii_price=twii_price, twii_change_pct=twii_change_pct)
                db.add(DailyMarketSummary(summary_date=today, html_content=html_news))
                db.commit()
                print("[batch] [OK] 今日財經新聞摘要已儲存")
            except Exception as e:
                print(f"[batch] [!] 財經新聞摘要產生失敗: {e}")
        else:
            print("[batch] 今日財經新聞摘要已存在，跳過")

        # Email 通知
        app_url = os.getenv('APP_URL', 'https://investment-system-lxq5.onrender.com')
        notify_users = db.query(User).filter_by(email_notify=True).all()
        if notify_users:
            send_notification(notify_users, app_url)
        else:
            print("[batch] 無需通知的用戶")

    finally:
        db.close()

    print(f"[batch] 結束 — {datetime.now(TW).strftime('%Y-%m-%d %H:%M')} 台灣時間")


if __name__ == '__main__':
    main()
