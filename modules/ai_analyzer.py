import anthropic
import config
from concurrent.futures import ThreadPoolExecutor, as_completed

client = anthropic.Anthropic(api_key=config.CLAUDE_API_KEY)

def _generate(prompt, max_tokens=2000, retries=1):
    """呼叫 Claude API，失敗時自動重試一次"""
    import time
    for attempt in range(retries + 1):
        try:
            message = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=max_tokens,
                timeout=90,
                messages=[{"role": "user", "content": prompt}]
            )
            return message.content[0].text
        except Exception as e:
            err = str(e)
            if attempt < retries:
                # rate limit 等久一點再重試
                wait = 15 if 'rate_limit' in err or '429' in err else 5
                print(f'AI 請求失敗（第{attempt+1}次），{wait}秒後重試: {err[:100]}')
                time.sleep(wait)
            else:
                return f"AI分析失敗: {err}"

def analyze_global_market(global_markets, commodities, news):
    def fmt(v):
        if v is None: return 'N/A'
        return f"{'+' if v>0 else ''}{v}%"

    markets_text = '\n'.join([
        f"{name}: 今日={fmt(d.get('change'))} | 7日={fmt(d.get('change_7d'))} | 30日={fmt(d.get('change_30d'))} | 60日={fmt(d.get('change_60d'))} | 現價={d.get('price')}"
        for name, d in global_markets.items()
    ])
    commodities_text = '\n'.join([
        f"{name}: 今日={fmt(d.get('change'))} | 7日={fmt(d.get('change_7d'))} | 30日={fmt(d.get('change_30d'))} | 現價={d.get('price')}"
        for name, d in commodities.items()
    ])
    news_text = '\n'.join([f"- {a['title']} ({a['source']})" for a in news[:8]])

    prompt = f"""
你是一位專業的全球財經分析師，請根據以下多時間維度數據提供今日市場分析。

⚠️ 分析原則（非常重要）：
- 今日漲跌必須放在7日、30日、60日的整體走勢脈絡下解讀
- 若某市場60日已漲30%，今日小跌2%只是正常回檔，不代表轉弱
- 若某市場60日已跌20%，今日再跌3%才是持續下跌的警訊
- 禁止因單日小幅波動就用「恐慌」「崩跌」「急跌」等誇大詞彙
- 要說明「今日漲跌在近期走勢中的相對意義"
- ⚠️ 嚴禁自行描述歷史起始價格（如「從XXXX點漲到YYYY點」），只能用上方提供的百分比描述走勢

【全球股市（今日/7日/30日/60日漲跌幅）】
{markets_text}

【大宗商品與匯率（今日/7日/30日漲跌幅）】
{commodities_text}

【重要財經新聞】
{news_text}

請提供：
1. 今日全球市場重點摘要（結合近期走勢背景解讀，3-5點）
2. 主要風險與機會（基於中長期趨勢判斷）
3. 對亞太市場的影響評估
4. 整體市場情緒判斷（偏多/中性/偏空）— 基於整體走勢，非單日表現

請用繁體中文回答，條列式呈現，專業但易懂。
"""
    return _generate(prompt)

def analyze_taiwan_market(global_analysis, technical_results, livermore_signals, twii_data=None):
    # 帶入完整真實個股價格
    tech_text = '\n'.join([
        f"{name}（{data.get('symbol','')}）: 現價={data.get('price')} 趨勢={data.get('trend')} RSI={data.get('RSI')} MA5={data.get('MA5')} MA20={data.get('MA20')} 支撐={data.get('support')} 壓力={data.get('resistance')} 進場={data.get('entry_low')}~{data.get('entry_high')} 目標一={data.get('target1')} 目標二={data.get('target2')} 停損={data.get('stop_loss_price')}"
        for name, data in technical_results.items()
    ])
    signal_text = '\n'.join([
        f"{name}: {sig['recommendation']} (分數:{sig['score']}) 停損:{sig.get('stop_loss')} 目標:{sig.get('target')}"
        for name, sig in livermore_signals['all'].items()
    ])

    def fmt(v):
        if v is None: return 'N/A'
        return f"{'+' if v>0 else ''}{v}%"

    if twii_data:
        twii_text = f"""【台灣加權指數（^TWII）— 程式計算真實數據，必須使用這些數字】
現價：{twii_data.get('price')} 點
今日漲跌：{fmt(twii_data.get('change'))}
7日漲跌：{fmt(twii_data.get('change_7d'))}
30日漲跌：{fmt(twii_data.get('change_30d'))}
60日漲跌：{fmt(twii_data.get('change_60d'))}
趨勢：{twii_data.get('trend')}
MA5：{twii_data.get('MA5')} 點 | MA20：{twii_data.get('MA20')} 點 | MA60：{twii_data.get('MA60')} 點
RSI：{twii_data.get('RSI')}
近20日支撐：{twii_data.get('support')} 點
近20日壓力：{twii_data.get('resistance')} 點"""
    else:
        twii_text = "【台灣加權指數】資料暫無，請勿自行推算任何指數點位。"

    prompt = f"""
你是一位專業的台股分析師，熟悉李佛摩投資法則。現在是台股收盤後，請根據今日收盤後的【真實數據】分析台灣股市，所有建議方向為明日（下一個交易日）的操作。

⚠️ 大格局分析原則：
- 大盤今日漲跌須結合7日、30日、60日走勢脈絡解讀
- 不因單日小幅波動誇大判斷，例如60日漲15%後今日跌1%屬正常回檔

⚠️ 嚴格規定（所有數字必須來自下方提供的真實數據）：
- 大盤支撐、壓力、點位：只能使用「台灣加權指數」區塊的數字
- 個股現價、進場、目標、停損：只能使用「台股個股技術面資料」中對應股票的數字
- 嚴禁自行推算、估計或捏造任何價位或點位
- 推薦標的只能從下方清單中選取，不可推薦清單以外的股票
- 若資料不足，請直接說「資料不足」
- ⚠️ 嚴禁自行描述歷史起始價格（如「大盤從XX000點漲到YY000點」），只能用上方提供的百分比描述走勢

{twii_text}

【全球市場分析摘要】
{global_analysis[:800]}

【台股個股技術面資料（所有個股價位必須從此取用）】
{tech_text}

【李佛摩法則訊號】
{signal_text}

請提供：
1. 全球情勢對台股今日影響評估
2. 台股加權指數技術面分析（只用上方提供的真實數字）
3. 今日大盤操作策略方向（多空判斷、強弱區間）
4. 需要注意的風險與明日觀察重點
（注意：不要推薦個股，個股分析已在持股追蹤區塊單獨呈現）

請用繁體中文，套用以下HTML格式：
短期標題：<span class="short-term-title">▶ 短期建議（1-5天）</span>
中期標題：<span class="mid-term-title">▶ 中期建議（1-3個月）</span>
目標價：<span class="target-price">目標價：XXX元（來自真實數據）</span>
停損價：<span class="stop-loss">停損：XXX元（來自真實數據）</span>
支撐：<span class="support-level">支撐：XXXX點</span>
壓力：<span class="resistance-level">壓力：XXXX點</span>
現價：<span class="close-price">XXX元</span>
股票代號後附中文名稱，例如：2330台積電

重要規定：所有價位必須直接使用上方提供的真實數字，嚴禁自行推算。
重要提醒：以上為模擬分析，不構成實際投資建議。
"""
    return _generate(prompt)

def analyze_macro_assets(macro_data):
    def fmt(v):
        if v is None:
            return 'N/A'
        return f"{'+' if v > 0 else ''}{v}%"

    macro_text = '\n'.join([
        f"{name}：今日={fmt(data.get('change'))} | 7日={fmt(data.get('change_7d'))} | 14日={fmt(data.get('change_14d'))} | 30日={fmt(data.get('change_30d'))} | 60日={fmt(data.get('change_60d'))} | 現價={data.get('price')}"
        for name, data in macro_data.items()
    ])

    prompt = f"""
你是一位專門教新手投資的老師，請用完全白話、新手聽得懂的方式解釋以下資產數據。

【資產多時間維度數據（今日/7日/14日/30日/60日漲跌幅）】
{macro_text}

重要分析原則：
- 今日漲跌必須放在中長期趨勢的脈絡下解讀
- 例如：若30日漲幅已達+30%，今日小跌-1%只是正常回檔，不代表轉弱
- 例如：若60日跌幅達-20%，今日再跌-2%代表跌勢持續，需特別警示
- 不要孤立看單日數字，要說明「這個漲跌在近期走勢中算什麼程度」
- ⚠️ 嚴禁自行描述歷史起始價格（例如「從60元漲到100元」這種說法）
- 只能使用上方提供的「7日/14日/30日/60日漲跌幅百分比」來描述走勢
- 若說漲跌幅，必須用上方數字，例如「近30日漲幅+XX%」，不可自行換算成絕對價格

請提供：
1. 美國公債殖利率：近期整體走勢如何？今日變化在這個背景下代表什麼？
2. 黃金：近期是漲是跌？今日走勢是延續還是反轉訊號？
3. 原油：近期走勢背景下，今日變化對台灣/全球的影響？
4. 三個資產的互動邏輯（用故事方式，說明近期大環境）
5. 綜合以上，對今日台股有什麼啟示？

重要要求：完全不用專業術語，像跟朋友解釋一樣輕鬆，請用繁體中文。
"""
    return _generate(prompt)

def analyze_watchlist_stock(name, symbol, technical_data, patterns, news_list, cost=None):
    from datetime import datetime, timezone, timedelta
    TW = timezone(timedelta(hours=8))
    today = datetime.now(TW).strftime('%Y/%m/%d')
    pattern_descs = '\n'.join([f"- {p['name']}：{p['desc']}" for p in patterns]) if patterns else '無明顯型態'
    news_text = '\n'.join([f"- {n['title']}" for n in news_list[:5]]) if news_list else '暫無相關新聞'
    cost_info = f'持股成本：{cost}元' if cost else '（未設定成本）'
    pnl_info = ''
    if cost and technical_data.get('price'):
        try:
            pnl = ((float(technical_data.get('price')) - float(cost)) / float(cost)) * 100
            pnl_info = f'目前損益：{pnl:+.2f}%'
        except:
            pass

    def fmt(v):
        if v is None: return 'N/A'
        return f"{'+' if v>0 else ''}{v}%"

    s1  = technical_data.get('support', '--')
    s2  = technical_data.get('support2', '--')
    r1  = technical_data.get('resistance2', '--')
    r2  = technical_data.get('resistance', '--')
    el  = technical_data.get('entry_low', '--')
    eh  = technical_data.get('entry_high', '--')
    t1  = technical_data.get('target1', '--')
    t2  = technical_data.get('target2', '--')
    sl  = technical_data.get('stop_loss_price', '--')

    chg_1d  = fmt(technical_data.get('change'))
    chg_5d  = fmt(technical_data.get('change_5d'))
    chg_20d = fmt(technical_data.get('change_20d'))

    vol       = technical_data.get('volume', 0)
    vol_yest  = technical_data.get('volume_yest', 0)
    vol_avg   = technical_data.get('volume_5d_avg', 0)
    vs_yest   = technical_data.get('volume_vs_yest')
    vs_avg    = technical_data.get('volume_vs_avg')

    if vs_yest and vs_avg:
        if vs_yest >= 2.0:
            vol_trend = f"爆量（較昨日+{round((vs_yest-1)*100)}%）"
        elif vs_yest >= 1.3:
            vol_trend = f"放量（較昨日+{round((vs_yest-1)*100)}%）"
        elif vs_yest <= 0.5:
            vol_trend = f"急縮量（較昨日-{round((1-vs_yest)*100)}%）"
        elif vs_yest <= 0.7:
            vol_trend = f"縮量（較昨日-{round((1-vs_yest)*100)}%）"
        else:
            vol_trend = "量能持平"
        vol_desc = (f"今日量={vol:,} | 昨日量={vol_yest:,} | 5日均量={vol_avg:,} | "
                    f"量能變化：{vol_trend}（今日/昨日={vs_yest}倍，今日/均量={vs_avg}倍）")
    else:
        vol_desc = "量能資料不足"

    prompt = (
        f"你是一位專業的台股分析師。{today} 收盤後，請根據今日收盤數據給出明日（下一個交易日）的操作建議。\n\n"
        f"⚠️ 分析原則：\n"
        f"- 今日漲跌必須結合5日、20日走勢背景解讀，不因單日波動誇大或輕描\n"
        f"- 所有價位只能使用下方提供的真實數字，嚴禁捏造\n"
        f"- ⚠️ 嚴禁自行描述歷史起始價格（如從XX元漲到YY元），只能用上方1日/5日/20日百分比描述走勢\n\n"
        f"【多時間維度表現（真實數據）】\n"
        f"股票：{name}（{symbol}）\n"
        f"{cost_info}\n"
        f"{pnl_info}\n"
        f"今日收盤價：{technical_data.get('price')} 元\n"
        f"1日漲跌：{chg_1d} ｜ 5日漲跌：{chg_5d} ｜ 20日漲跌：{chg_20d}\n"
        f"今日量能：{vol_desc}\n\n"
        f"【技術指標】\n"
        f"趨勢：{technical_data.get('trend')}\n"
        f"RSI(14)：{technical_data.get('RSI')}\n"
        f"MA5：{technical_data.get('MA5')} ｜ MA20：{technical_data.get('MA20')} ｜ MA60：{technical_data.get('MA60')}\n"
        f"近20日支撐一：{s1} 元 ｜ 支撐二：{s2} 元\n"
        f"近20日壓力一：{r1} 元 ｜ 壓力二：{r2} 元\n"
        f"建議進場：{el}~{eh} 元 ｜ 目標一：{t1} 元 ｜ 目標二：{t2} 元 ｜ 停損：{sl} 元\n\n"
        f"【今日K線型態】\n{pattern_descs}\n\n"
        f"【近期相關新聞】\n{news_text}\n\n"
        f"請提供明日完整操作建議，格式如下：\n\n"
        f"一、今日走勢 + K線型態解讀（結合1日/5日/20日背景，2-3點）\n"
        f"   - 今日表現在近期走勢中屬於強/弱/中性？\n"
        f"   - 量能是放大、縮量還是平量？代表什麼意義？\n"
        f"   - K線型態對明日的啟示\n\n"
        f"二、明日操作策略（條件式，明確說明每種情境的對應做法）\n"
        f"   格式：如果開盤/盤中 [條件]：[建議做法，含進場價位]\n\n"
        f"三、明日關鍵價位（直接使用上方提供的數字，不可修改）：\n"
        f'   - <span class="support-level">支撐一：{s1} 元</span>\n'
        f'   - <span class="support-level">支撐二：{s2} 元</span>\n'
        f'   - <span class="resistance-level">壓力一：{r1} 元</span>\n'
        f'   - <span class="resistance-level">壓力二：{r2} 元</span>\n'
        f'   - <span class="close-price">明日進場：{el}~{eh} 元</span>\n'
        f'   - <span class="target-price">目標一：{t1} 元</span>\n'
        f'   - <span class="target-price">目標二：{t2} 元</span>\n'
        f'   - <span class="stop-loss">停損：{sl} 元</span>\n\n'
        f"四、持倉者建議（已持有者明日如何操作：加碼/減碼/續抱/停利）\n\n"
        f"五、特別注意事項（明日需觀察的關鍵訊號，1-2點）\n\n"
        f"重要提醒：以上為模擬分析，不構成實際投資建議。"
    )
    return _generate(prompt, max_tokens=1500)


# ── 平行分析所有持股（核心優化）────────────────────────────
def analyze_watchlist_parallel(watchlist, watchlist_stocks, watch_tech, news,
                                week_range=None, is_weekly=False):
    """同時對所有持股發出 AI 分析請求，速度提升數倍"""
    from modules.candlestick import detect_patterns
    from modules.stock_names import get_sector

    def _analyze_one(item):
        name = item['name']
        symbol = item['symbol']
        if name not in watch_tech:
            return None
        tech = watch_tech[name]
        hist = watchlist_stocks[name].get('history')
        patterns = detect_patterns(hist) if hist is not None else []
        stock_news = [n for n in news if str(name) in str(n.get('title', ''))]
        # 自動取得產業分類
        sector = get_sector(symbol, name)
        if is_weekly:
            ai_advice = analyze_weekly_watchlist(name, symbol, tech, patterns, stock_news, week_range, item.get('cost'))
        else:
            ai_advice = analyze_watchlist_stock(name, symbol, tech, patterns, stock_news, item.get('cost'))
        tech['cost'] = item.get('cost')
        return {'name': name, 'symbol': symbol, 'technical': tech, 'patterns': patterns, 'ai_advice': ai_advice, 'sector': sector}

    import time
    results = []
    # 分批執行，每批 5 支，避免超過 API rate limit
    batch_size = 5
    for i in range(0, len(watchlist), batch_size):
        batch = watchlist[i:i+batch_size]
        with ThreadPoolExecutor(max_workers=batch_size) as ex:
            futures = {ex.submit(_analyze_one, item): item['name'] for item in batch}
            for f in as_completed(futures):
                r = f.result()
                if r:
                    results.append(r)
        # 批次間等待 2 秒，避免超過 rate limit
        if i + batch_size < len(watchlist):
            time.sleep(2)
    # 依原始順序排列
    order = {item['name']: i for i, item in enumerate(watchlist)}
    results.sort(key=lambda x: order.get(x['name'], 99))
    return results

def get_sector_recommendations(global_markets, technical_results, macro_data, watchlist_analysis=None):
    """推薦投資產業方向（不推薦個股，只給大方向）"""
    markets_text = '\n'.join([
        f"{name}: {data['price']} ({'+' if data['change']>0 else ''}{data['change']}%)"
        for name, data in global_markets.items()
    ])
    macro_text = '\n'.join([
        f"{name}: {data['price']} ({'+' if data['change']>0 else ''}{data['change']}%)"
        for name, data in macro_data.items()
    ])
    # 追蹤清單的產業分布
    if watchlist_analysis:
        from modules.stock_names import get_sector
        sector_summary = {}
        for item in watchlist_analysis:
            sector = item.get('sector') or get_sector(item.get('symbol',''), item.get('name',''))
            trend = item['technical'].get('trend', '--')
            rsi = item['technical'].get('RSI', '--')
            if sector not in sector_summary:
                sector_summary[sector] = []
            sector_summary[sector].append(f"{item['name']}（趨勢:{trend} RSI:{rsi}）")
        watchlist_sector_text = '\n'.join([
            f"{sector}：{', '.join(stocks)}"
            for sector, stocks in sector_summary.items()
        ])
    else:
        watchlist_sector_text = '（無追蹤標的）'

    prompt = f"""
你是一位專業的台股產業分析師。請根據目前全球市場環境，給出產業投資方向建議。

【全球市場概況】
{markets_text}

【總體資產走勢（美債/黃金/石油）】
{macro_text}

【目前追蹤標的的產業分布】
{watchlist_sector_text}

請提供：
1. 目前全球市場環境下，最看好的 3 個台股產業（說明原因）
2. 需要迴避的 1-2 個產業（說明風險）
3. 追蹤清單中哪些產業與當前市場趨勢最吻合（參考上方追蹤清單）

格式要求：
- 只給產業方向，不要推薦個股
- 每個產業說明 2-3 個看好/看空的理由
- 用繁體中文，條列式呈現

短期看好：<span class="short-term-title">▶ 短期看好產業</span>
中期布局：<span class="mid-term-title">▶ 中期布局產業</span>
需要迴避：<span class="stop-loss">⚠️ 近期迴避產業</span>

重要提醒：以上為模擬分析，不構成實際投資建議。
"""
    return _generate(prompt)

def analyze_weekly_global(global_markets, commodities, news, macro_data, week_range):
    def fmt(v):
        if v is None: return 'N/A'
        return f"{'+' if v>0 else ''}{v}%"

    markets_text = '\n'.join([
        f"{name}: 本週={fmt(d.get('change'))} | 30日={fmt(d.get('change_30d'))} | 60日={fmt(d.get('change_60d'))} | 現價={d.get('price')}"
        for name, d in global_markets.items()
    ])
    macro_text = '\n'.join([
        f"{name}: 本週={fmt(d.get('change'))} | 14日={fmt(d.get('change_14d'))} | 30日={fmt(d.get('change_30d'))} | 60日={fmt(d.get('change_60d'))} | 現價={d.get('price')}"
        for name, d in macro_data.items()
    ])
    news_text = '\n'.join([f"- {a['title']}" for a in news[:10]])

    prompt = f"""
你是一位專業的全球財經週報分析師。請根據以下多時間維度數據提供本週市場總結與下週展望。

⚠️ 分析原則：
- 本週漲跌須結合30日、60日走勢背景解讀
- 基於整體趨勢判斷市場強弱，不因單週波動誇大解讀
- 要說明「本週表現在近期走勢中屬於正常範圍還是異常"
- ⚠️ 嚴禁自行描述歷史起始價格，只能用上方提供的百分比描述走勢

【本週全球股市（本週/30日/60日漲跌幅）】
{markets_text}

【本週美債/黃金/石油（本週/14日/30日/60日漲跌幅）】
{macro_text}

【本週重要財經新聞】
{news_text}

【分析週期】{week_range}

請提供：
1. 本週全球市場重點回顧（結合近期走勢背景，3-5點）
2. 本週最重要的3個國際事件及其影響
3. 美債/黃金/石油本週走勢白話解析（新手易懂，結合近期趨勢）
4. 下週全球市場展望與潛在風險
5. 整體市場情緒評估（偏多/中性/偏空）— 基於整體走勢判斷

請用繁體中文，條列式呈現，專業但易懂。
"""
    return _generate(prompt)

def analyze_weekly_taiwan(global_weekly_analysis, technical_results, livermore_signals, week_range, twii_data=None):
    tech_text = '\n'.join([
        f"{name}（{data.get('symbol','')}）: 現價={data.get('price')} 趨勢={data.get('trend')} RSI={data.get('RSI')} MA5={data.get('MA5')} MA20={data.get('MA20')} 支撐={data.get('support')} 壓力={data.get('resistance')} 進場={data.get('entry_low')}~{data.get('entry_high')} 目標一={data.get('target1')} 目標二={data.get('target2')} 停損={data.get('stop_loss_price')}"
        for name, data in technical_results.items()
    ])
    signal_text = '\n'.join([
        f"{name}: {sig['recommendation']} 分數:{sig['score']}"
        for name, sig in livermore_signals['all'].items()
    ])
    def fmt(v):
        if v is None: return 'N/A'
        return f"{'+' if v>0 else ''}{v}%"

    if twii_data:
        twii_text = f"""【台灣加權指數（^TWII）— 程式計算真實數據，必須使用這些數字】
本週收盤：{twii_data.get('price')} 點
本週漲跌：{fmt(twii_data.get('change'))}
14日漲跌：{fmt(twii_data.get('change_14d'))}
30日漲跌：{fmt(twii_data.get('change_30d'))}
60日漲跌：{fmt(twii_data.get('change_60d'))}
趨勢：{twii_data.get('trend')}
MA5：{twii_data.get('MA5')} 點 | MA20：{twii_data.get('MA20')} 點 | MA60：{twii_data.get('MA60')} 點
RSI：{twii_data.get('RSI')}
近20日支撐：{twii_data.get('support')} 點
近20日壓力：{twii_data.get('resistance')} 點"""
    else:
        twii_text = "【台灣加權指數】資料暫無，請勿自行推算任何指數點位。"

    prompt = f"""
你是一位專業的台股週報分析師，熟悉李佛摩投資法則與技術分析。請根據以下【真實數據】分析台灣股市。

⚠️ 大格局分析原則：
- 本週漲跌須結合14日、30日、60日走勢脈絡解讀
- 不因單週波動誇大判斷市場強弱
- ⚠️ 嚴禁自行描述歷史起始價格（如「大盤從XX000點漲到YY000點」），只能用上方提供的百分比描述走勢

⚠️ 嚴格規定（所有數字必須來自下方提供的真實數據）：
- 大盤支撐、壓力、點位：只能使用「台灣加權指數」區塊的數字
- 個股現價、進場、目標、停損：只能使用「台股個股技術面」中對應股票的數字
- 嚴禁自行推算、估計或捏造任何價位或點位
- 推薦標的只能從下方清單中選取，不可推薦清單以外的股票
- 若資料不足，請直接說「資料不足」

{twii_text}

【全球市場本週概況】
{global_weekly_analysis[:600]}

【台股本週個股技術面（所有個股價位必須從此取用）】
{tech_text}

【李佛摩法則訊號】
{signal_text}

【分析週期】{week_range}

請提供：
1. 台股本週走勢回顧（3點，使用上方真實數字）
2. 全球情勢對下週台股的影響評估
3. 下週台股技術面展望（支撐/壓力只用上方提供的真實數字）
4. 下週大盤操作策略方向（多空判斷、強弱區間）
5. 下週需要特別注意的風險與事件
（注意：不要推薦個股，個股分析已在持股追蹤區塊單獨呈現）

請用繁體中文，套用以下HTML格式：
短期標題：<span class="short-term-title">▶ 下週短期建議（1-5天）</span>
中期標題：<span class="mid-term-title">▶ 下週中期建議（1-3個月）</span>
目標價：<span class="target-price">目標價：XXX元（來自真實數據）</span>
停損價：<span class="stop-loss">停損：XXX元（來自真實數據）</span>
支撐：<span class="support-level">支撐：XXXX點</span>
壓力：<span class="resistance-level">壓力：XXXX點</span>
現價：<span class="close-price">XXX元</span>
股票代號後附中文名稱，例如：2330台積電

重要規定：所有價位必須直接使用上方提供的真實數字，嚴禁自行推算。
重要提醒：以上為模擬分析，不構成實際投資建議。
"""
    return _generate(prompt)

def analyze_weekly_watchlist(name, symbol, technical_data, patterns, news_list, week_range, cost=None):
    from datetime import datetime, timezone, timedelta
    TW = timezone(timedelta(hours=8))
    pattern_descs = '\n'.join([f"- {p['name']}：{p['desc']}" for p in patterns]) if patterns else '無明顯型態'
    news_text = '\n'.join([f"- {n['title']}" for n in news_list[:5]]) if news_list else '暫無相關新聞'
    cost_info = f'持股成本：{cost}元' if cost else '（未設定成本）'
    pnl_info = ''
    if cost and technical_data.get('price'):
        try:
            pnl = ((float(technical_data.get('price')) - float(cost)) / float(cost)) * 100
            pnl_info = f'本週損益：{pnl:+.2f}%'
        except:
            pass

    def fmt(v):
        if v is None: return 'N/A'
        return f"{'+' if v>0 else ''}{v}%"

    s1  = technical_data.get('support', '--')
    s2  = technical_data.get('support2', '--')
    r1  = technical_data.get('resistance2', '--')
    r2  = technical_data.get('resistance', '--')
    el  = technical_data.get('entry_low', '--')
    eh  = technical_data.get('entry_high', '--')
    t1  = technical_data.get('target1', '--')
    t2  = technical_data.get('target2', '--')
    sl  = technical_data.get('stop_loss_price', '--')

    chg_1d  = fmt(technical_data.get('change'))
    chg_5d  = fmt(technical_data.get('change_5d'))
    chg_20d = fmt(technical_data.get('change_20d'))

    vol       = technical_data.get('volume', 0)
    vol_yest  = technical_data.get('volume_yest', 0)
    vol_avg   = technical_data.get('volume_5d_avg', 0)
    vs_yest   = technical_data.get('volume_vs_yest')
    vs_avg    = technical_data.get('volume_vs_avg')

    if vs_yest and vs_avg:
        if vs_yest >= 2.0:
            vol_trend = f"爆量（較前日+{round((vs_yest-1)*100)}%）"
        elif vs_yest >= 1.3:
            vol_trend = f"放量（較前日+{round((vs_yest-1)*100)}%）"
        elif vs_yest <= 0.5:
            vol_trend = f"急縮量（較前日-{round((1-vs_yest)*100)}%）"
        elif vs_yest <= 0.7:
            vol_trend = f"縮量（較前日-{round((1-vs_yest)*100)}%）"
        else:
            vol_trend = "量能持平"
        vol_desc = (f"本週末量={vol:,} | 前日量={vol_yest:,} | 5日均量={vol_avg:,} | "
                    f"量能變化：{vol_trend}（末日/前日={vs_yest}倍，末日/均量={vs_avg}倍）")
    else:
        vol_desc = "量能資料不足"

    prompt = (
        f"你是一位專業的台股分析師。分析週期 {week_range}，請根據本週收盤數據給出下週操作建議。\n\n"
        f"⚠️ 嚴格規定：所有價位只能使用下方提供的真實數字，嚴禁捏造\n"
        f"⚠️ 嚴禁自行描述歷史起始價格（如從XX元漲到YY元），只能用上方1日/5日/20日百分比描述走勢\n\n"
        f"【多時間維度表現（真實數據）】\n"
        f"股票：{name}（{symbol}）\n"
        f"{cost_info}\n"
        f"{pnl_info}\n"
        f"本週收盤價：{technical_data.get('price')} 元\n"
        f"1日漲跌：{chg_1d} ｜ 5日漲跌：{chg_5d} ｜ 20日漲跌：{chg_20d}\n"
        f"本週量能：{vol_desc}\n\n"
        f"【技術指標】\n"
        f"趨勢：{technical_data.get('trend')}\n"
        f"RSI(14)：{technical_data.get('RSI')}\n"
        f"MA5：{technical_data.get('MA5')} ｜ MA20：{technical_data.get('MA20')} ｜ MA60：{technical_data.get('MA60')}\n"
        f"近20日支撐一：{s1} 元 ｜ 支撐二：{s2} 元\n"
        f"近20日壓力一：{r1} 元 ｜ 壓力二：{r2} 元\n"
        f"建議進場：{el}~{eh} 元 ｜ 目標一：{t1} 元 ｜ 目標二：{t2} 元 ｜ 停損：{sl} 元\n\n"
        f"【本週K線型態】\n{pattern_descs}\n\n"
        f"【本週相關新聞】\n{news_text}\n\n"
        f"請提供下週完整操作建議，格式如下：\n\n"
        f"一、本週走勢 + K線型態解讀（結合1日/5日/20日背景，2-3點）\n"
        f"   - 本週表現在近期走勢中屬於強/弱/中性？\n"
        f"   - 量能是放大、縮量還是平量？代表什麼意義？\n"
        f"   - K線型態對下週的啟示\n\n"
        f"二、下週操作策略（條件式，明確說明每種情境的對應做法）\n"
        f"   格式：如果開盤/盤中 [條件]：[建議做法，含進場價位]\n\n"
        f"三、下週關鍵價位（直接使用上方提供的數字，不可修改）：\n"
        f'   - <span class="support-level">支撐一：{s1} 元</span>\n'
        f'   - <span class="support-level">支撐二：{s2} 元</span>\n'
        f'   - <span class="resistance-level">壓力一：{r1} 元</span>\n'
        f'   - <span class="resistance-level">壓力二：{r2} 元</span>\n'
        f'   - <span class="close-price">下週進場：{el}~{eh} 元</span>\n'
        f'   - <span class="target-price">目標一：{t1} 元</span>\n'
        f'   - <span class="target-price">目標二：{t2} 元</span>\n'
        f'   - <span class="stop-loss">停損：{sl} 元</span>\n\n'
        f"四、持倉者建議（已持有者下週如何操作：加碼/減碼/續抱/停利）\n\n"
        f"五、特別注意事項（下週需觀察的關鍵訊號，1-2點）\n\n"
        f"重要提醒：以上為模擬分析，不構成實際投資建議。"
    )
    return _generate(prompt, max_tokens=1500)

