from modules.data_fetcher import (get_global_markets, get_commodities,
                                   get_financial_news, get_taiwan_stocks,
                                   get_macro_assets, get_watchlist_stocks)
from modules.technical import analyze_all_stocks
from modules.livermore import analyze_all_signals
from modules.candlestick import detect_patterns
from modules.ai_analyzer import (analyze_global_market, analyze_taiwan_market,
                                  analyze_macro_assets, analyze_watchlist_stock,
                                  get_sector_recommendations,
                                  analyze_weekly_global, analyze_weekly_taiwan,
                                  analyze_weekly_watchlist)
from modules.pdf_generator import generate_daily_report, generate_weekly_report
from modules.email_sender import send_report, send_weekly_report
from modules.watchlist import get_watchlist
from modules.report_scheduler import (get_report_type, get_week_range,
                                       get_report_description)

# ===== 判斷報表類型 =====
report_type = get_report_type()
report_desc = get_report_description(report_type)
print(f"📋 報表類型：{report_desc}")

# ===== 抓取資料（日報/週報共用）=====
print("📡 抓取全球市場資料...")
global_markets = get_global_markets()
commodities = get_commodities()
news = get_financial_news()
macro_data = get_macro_assets()

print("📡 抓取台股資料...")
taiwan_stocks = get_taiwan_stocks()

print("📊 進行技術分析...")
technical_results = analyze_all_stocks(taiwan_stocks)

print("⚡ 套用李佛摩法則...")
livermore_signals = analyze_all_signals(technical_results)

print("🕯️ 分析K線型態...")
for name, data in taiwan_stocks.items():
    if 'history' in data:
        technical_results[name]['patterns'] = detect_patterns(data['history'])

print("📈 分析美債/黃金/石油...")
macro_analysis = analyze_macro_assets(macro_data)

# ===== 持股追蹤分析（日報/週報共用）=====
print("💼 分析持股追蹤標的...")
watchlist = get_watchlist()
watchlist_analysis = []
monday, friday = get_week_range()
week_range = f'{monday.strftime("%Y/%m/%d")} ~ {friday.strftime("%Y/%m/%d")}'

if watchlist:
    watchlist_stocks = get_watchlist_stocks(watchlist)
    watch_tech = analyze_all_stocks(watchlist_stocks)
    for item in watchlist:
        name = item['name']
        symbol = item['symbol']
        if name in watch_tech:
            tech = watch_tech[name]
            hist = watchlist_stocks[name].get('history')
            patterns = detect_patterns(hist) if hist is not None else []
            stock_news = [n for n in news if name in n.get('title', '') or
                         item['symbol'].replace('.TW', '') in n.get('title', '')]
            if report_type == 'weekly':
                ai_advice = analyze_weekly_watchlist(
                    name, symbol, tech, patterns, stock_news,
                    week_range, cost=item.get('cost')
                )
            else:
                ai_advice = analyze_watchlist_stock(
                    name, symbol, tech, patterns, stock_news,
                    cost=item.get('cost')
                )
            tech['cost'] = item.get('cost')
            watchlist_analysis.append({
                'name': name, 'symbol': symbol,
                'technical': tech, 'patterns': patterns,
                'ai_advice': ai_advice
            })

print("🏭 取得產業推薦標的...")
sector_recommendations = get_sector_recommendations(
    global_markets, technical_results, macro_data
)

# ===== 依類型產生報表 =====
if report_type == 'daily':
    print("🤖 進行每日AI分析...")
    global_analysis = analyze_global_market(global_markets, commodities, news)
    taiwan_analysis = analyze_taiwan_market(global_analysis, technical_results, livermore_signals)

    print("📄 產生每日報表...")
    report_path = generate_daily_report(
        global_markets, commodities, news,
        global_analysis, taiwan_analysis,
        technical_results, livermore_signals,
        macro_data, macro_analysis,
        watchlist_analysis, sector_recommendations
    )
    print("📧 寄送 Email...")
    send_report(report_path)

else:
    print("🤖 進行週報AI分析...")
    global_weekly_analysis = analyze_weekly_global(
        global_markets, commodities, news, macro_data, week_range
    )
    taiwan_weekly_analysis = analyze_weekly_taiwan(
        global_weekly_analysis, technical_results, livermore_signals, week_range
    )

    print("📄 產生週報...")
    report_path = generate_weekly_report(
        global_markets, commodities, news,
        global_weekly_analysis, taiwan_weekly_analysis,
        technical_results, livermore_signals,
        macro_data, macro_analysis,
        watchlist_analysis, sector_recommendations,
        week_range
    )
    print("📧 寄送週報 Email...")
    send_weekly_report(report_path)

print(f"✅ 完成！報表位置：{report_path}")