from datetime import datetime, date, timedelta
import yfinance as yf

# 台灣國定假日（每年需更新）
TAIWAN_HOLIDAYS_2026 = {
    date(2026, 1, 1),   # 元旦
    date(2026, 1, 26),  # 春節補假
    date(2026, 1, 27),  # 春節
    date(2026, 1, 28),  # 春節
    date(2026, 1, 29),  # 春節
    date(2026, 1, 30),  # 春節
    date(2026, 2, 28),  # 和平紀念日
    date(2026, 4, 3),   # 兒童節補假
    date(2026, 4, 4),   # 兒童節/清明節
    date(2026, 5, 1),   # 勞動節
    date(2026, 6, 19),  # 端午節
    date(2026, 9, 23),  # 中秋節補假
    date(2026, 9, 24),  # 中秋節
    date(2026, 10, 9),  # 國慶日補假
    date(2026, 10, 10), # 國慶日
}

TAIWAN_HOLIDAYS_2025 = {
    date(2025, 1, 1),
    date(2025, 1, 27),
    date(2025, 1, 28),
    date(2025, 1, 29),
    date(2025, 1, 30),
    date(2025, 1, 31),
    date(2025, 2, 28),
    date(2025, 4, 3),
    date(2025, 4, 4),
    date(2025, 5, 1),
    date(2025, 6, 2),
    date(2025, 10, 10),
}

ALL_HOLIDAYS = TAIWAN_HOLIDAYS_2025 | TAIWAN_HOLIDAYS_2026

def is_taiwan_holiday(check_date=None):
    if check_date is None:
        check_date = date.today()
    if isinstance(check_date, datetime):
        check_date = check_date.date()
    return check_date in ALL_HOLIDAYS

def is_weekend(check_date=None):
    if check_date is None:
        check_date = date.today()
    if isinstance(check_date, datetime):
        check_date = check_date.date()
    return check_date.weekday() >= 5  # 5=週六, 6=週日

def is_market_closed(check_date=None):
    if check_date is None:
        check_date = date.today()
    if isinstance(check_date, datetime):
        check_date = check_date.date()
    # 嘗試從 yfinance 確認台股是否有交易資料
    try:
        ticker = yf.Ticker('^TWII')
        hist = ticker.history(start=check_date.strftime('%Y-%m-%d'),
                              end=(check_date + timedelta(days=1)).strftime('%Y-%m-%d'))
        return len(hist) == 0
    except:
        return False

def get_report_type(force=None):
    """
    判斷應該產生日報還是週報
    force: 'daily' 或 'weekly' 可強制指定
    """
    if force in ('daily', 'weekly'):
        return force

    today = date.today()

    # 週六或週日
    if is_weekend(today):
        return 'weekly'

    # 台灣國定假日
    if is_taiwan_holiday(today):
        return 'weekly'

    # 台股休市（排除假日已判斷的狀況）
    if is_market_closed(today):
        return 'weekly'

    return 'daily'

def is_friday_after_close():
    """判斷是否為週五收盤後（13:30之後）"""
    now = datetime.now()
    return now.weekday() == 4 and now.hour >= 13 and now.minute >= 30

def get_last_n_trading_days(n=5):
    """取得最近N個交易日的日期"""
    trading_days = []
    check = date.today()
    while len(trading_days) < n:
        check -= timedelta(days=1)
        if check.weekday() < 5 and not is_taiwan_holiday(check):
            trading_days.append(check)
    return trading_days

def get_week_range():
    """取得本週的開始和結束日期"""
    today = date.today()
    # 本週一
    monday = today - timedelta(days=today.weekday())
    # 本週五
    friday = monday + timedelta(days=4)
    return monday, friday

def get_report_description(report_type):
    """取得報表說明文字"""
    now = datetime.now()
    today = date.today()
    
    if report_type == 'weekly':
        monday, friday = get_week_range()
        return f'週報（{monday.strftime("%m/%d")} ~ {friday.strftime("%m/%d")}）'
    else:
        # 收盤後（13:30後）顯示今天，否則顯示前一交易日
        if now.hour > 13 or (now.hour == 13 and now.minute >= 30):
            data_date = today
        else:
            data_date = today - timedelta(days=1)
            while data_date.weekday() >= 5 or is_taiwan_holiday(data_date):
                data_date -= timedelta(days=1)
        return f'日報（{data_date.strftime("%m/%d")} 收盤分析）'