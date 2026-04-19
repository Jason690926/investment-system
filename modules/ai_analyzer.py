import anthropic
import config
from concurrent.futures import ThreadPoolExecutor, as_completed

client = anthropic.Anthropic(api_key=config.CLAUDE_API_KEY)

def _generate(prompt):
    try:
        message = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text
    except Exception as e:
        return f"AI分析失敗: {e}"

def analyze_global_market(global_markets, commodities, news):
    markets_text = '\n'.join([
        f"{name}: {data['price']} ({'+' if data['change']>0 else ''}{data['change']}%)"
        for name, data in global_markets.items()
    ])
    commodities_text = '\n'.join([
        f"{name}: {data['price']} ({'+' if data['change']>0 else ''}{data['change']}%)"
        for name, data in commodities.items()
    ])
    news_text = '\n'.join([f"- {a['title']} ({a['source']})" for a in news[:8]])
    prompt = f"""
你是一位專業的全球財經分析師，請根據以下資料提供今日市場分析。

【全球股市表現】
{markets_text}

【大宗商品與匯率】
{commodities_text}

【重要財經新聞】
{news_text}

請提供：
1. 今日全球市場重點摘要（3-5點，每點2-3句話）
2. 主要風險與機會
3. 對亞太市場的影響評估
4. 整體市場情緒判斷（偏多/中性/偏空）

請用繁體中文回答，條列式呈現，專業但易懂。
"""
    return _generate(prompt)

def analyze_taiwan_market(global_analysis, technical_results, livermore_signals, twii_data=None):
    tech_text = '\n'.join([
        f"{name}: 趨勢={data.get('trend')} RSI={data.get('RSI')} MA5={data.get('MA5')} MA20={data.get('MA20')}"
        for name, data in technical_results.items()
    ])
    signal_text = '\n'.join([
        f"{name}: {sig['recommendation']} (分數:{sig['score']}) 停損:{sig.get('stop_loss')} 目標:{sig.get('target')}"
        for name, sig in livermore_signals['all'].items()
    ])

    if twii_data:
        twii_text = f"""【台灣加權指數（^TWII）— 程式計算真實數據，必須使用這些數字】
現價：{twii_data.get('price')} 點
今日漲跌：{twii_data.get('change')}%
趨勢：{twii_data.get('trend')}
MA5：{twii_data.get('MA5')} 點
MA20：{twii_data.get('MA20')} 點
MA60：{twii_data.get('MA60')} 點
RSI：{twii_data.get('RSI')}
近20日支撐：{twii_data.get('support')} 點
近20日壓力：{twii_data.get('resistance')} 點"""
    else:
        twii_text = "【台灣加權指數】資料暫無，請勿自行推算任何指數點位。"

    prompt = f"""
你是一位專業的台股分析師，熟悉李佛摩投資法則。請根據以下【真實數據】分析台灣股市。

⚠️ 嚴格規定：
- 大盤加權指數的所有點位數字，只能使用下方「台灣加權指數」區塊中提供的數字
- 嚴禁自行推算、估計或捏造任何指數點位
- 若資料不足，請直接說「資料不足」，不可填入未經提供的數字

{twii_text}

【全球市場分析摘要】
{global_analysis[:800]}

【台股個股技術面資料】
{tech_text}

【李佛摩法則訊號】
{signal_text}

請提供：
1. 全球情勢對台股今日影響評估
2. 台股加權指數技術面分析（只用上方提供的真實數字，不可自行推算）
3. 短期投資建議（1-5天）：列出2-3檔最值得關注標的，說明理由
4. 中期投資建議（1-3個月）：列出2-3檔潛力標的，說明理由
5. 今日操作策略建議
6. 需要注意的風險

請用繁體中文，套用以下HTML格式：
短期標題：<span class="short-term-title">▶ 短期建議（1-5天）</span>
中期標題：<span class="mid-term-title">▶ 中期建議（1-3個月）</span>
目標價：<span class="target-price">目標價：XXX元</span>
停損價：<span class="stop-loss">停損：XXX元</span>
支撐：<span class="support-level">支撐：XXXX點</span>
壓力：<span class="resistance-level">壓力：XXXX點</span>
現價：<span class="close-price">XXX元</span>
股票代號後附中文名稱，例如：2330台積電

重要規定：大盤支撐壓力只能使用上方提供的真實數字，每檔標的都要有目標價和停損價。
重要提醒：以上為模擬分析，不構成實際投資建議。
"""
    return _generate(prompt)

def analyze_macro_assets(macro_data):
    macro_text = '\n'.join([
        f"{name}: {data['price']} ({'+' if data['change']>0 else ''}{data['change']}%)"
        for name, data in macro_data.items()
    ])
    prompt = f"""
你是一位專門教新手投資的老師，請用完全白話、新手聽得懂的方式解釋以下資產數據。

【今日數據】
{macro_text}

請提供：
1. 美國公債殖利率今天的變化代表什麼意思？（用生活化比喻說明）
2. 黃金今天的走勢代表市場情緒如何？
3. 原油今天的變化對台灣/全球有什麼影響？
4. 這三個資產今天互相影響的邏輯是什麼？（用故事方式說明）
5. 綜合以上，對今天台股有什麼啟示？

重要要求：完全不用專業術語，像跟朋友解釋一樣輕鬆，請用繁體中文。
"""
    return _generate(prompt)

def analyze_watchlist_stock(name, symbol, technical_data, patterns, news_list, cost=None):
    pattern_descs = '\n'.join([f"- {p['name']}：{p['desc']}" for p in patterns]) if patterns else '無明顯型態'
    news_text = '\n'.join([f"- {n['title']}" for n in news_list[:5]]) if news_list else '暫無相關新聞'
    cost_info = f'持股成本：{cost}元' if cost else '（未設定成本）'
    prompt = f"""
你是一位專業的台股分析師。請針對以下個股給出詳細分析與建議。

【股票資訊】
股票：{name}（{symbol}）
{cost_info}
現價：{technical_data.get('price')}
今日漲跌：{technical_data.get('change')}%
趨勢：{technical_data.get('trend')}
RSI：{technical_data.get('RSI')}
MA5：{technical_data.get('MA5')} MA20：{technical_data.get('MA20')} MA60：{technical_data.get('MA60')}
支撐一：{technical_data.get('support')} 支撐二：{technical_data.get('support2')}
壓力一：{technical_data.get('resistance2')} 壓力二：{technical_data.get('resistance')}

【K線型態】
{pattern_descs}

【近期相關新聞】
{news_text}

每檔股票分析必須包含以下結構：
一、今日走勢簡評（2-3點）
二、K線型態解讀
三、短期操作建議
四、價位資訊（給出具體數字）：
   - <span class="support-level">支撐一：XXX元</span>
   - <span class="support-level">支撐二：XXX元</span>
   - <span class="resistance-level">壓力一：XXX元</span>
   - <span class="resistance-level">壓力二：XXX元</span>
   - <span class="close-price">進場：XXX~XXX元</span>
   - <span class="target-price">目標一：XXX元</span>
   - <span class="target-price">目標二：XXX元</span>
   - <span class="stop-loss">停損：XXX元</span>
五、特別注意事項

重要規定：所有價位必須是具體數字，不可用百分比。
重要提醒：以上為模擬分析，不構成實際投資建議。
"""
    return _generate(prompt)

# ── 平行分析所有持股（核心優化）────────────────────────────
def analyze_watchlist_parallel(watchlist, watchlist_stocks, watch_tech, news,
                                week_range=None, is_weekly=False):
    """同時對所有持股發出 AI 分析請求，速度提升數倍"""
    from modules.candlestick import detect_patterns

    def _analyze_one(item):
        name = item['name']
        symbol = item['symbol']
        if name not in watch_tech:
            return None
        tech = watch_tech[name]
        hist = watchlist_stocks[name].get('history')
        patterns = detect_patterns(hist) if hist is not None else []
        stock_news = [n for n in news if str(name) in str(n.get('title', ''))]
        if is_weekly:
            ai_advice = analyze_weekly_watchlist(name, symbol, tech, patterns, stock_news, week_range, item.get('cost'))
        else:
            ai_advice = analyze_watchlist_stock(name, symbol, tech, patterns, stock_news, item.get('cost'))
        tech['cost'] = item.get('cost')
        return {'name': name, 'symbol': symbol, 'technical': tech, 'patterns': patterns, 'ai_advice': ai_advice}

    results = []
    with ThreadPoolExecutor(max_workers=min(len(watchlist), 5)) as ex:
        futures = {ex.submit(_analyze_one, item): item['name'] for item in watchlist}
        for f in as_completed(futures):
            r = f.result()
            if r:
                results.append(r)
    # 依原始順序排列
    order = {item['name']: i for i, item in enumerate(watchlist)}
    results.sort(key=lambda x: order.get(x['name'], 99))
    return results

def get_sector_recommendations(global_markets, technical_results, macro_data):
    markets_text = '\n'.join([
        f"{name}: {data['price']} ({'+' if data['change']>0 else ''}{data['change']}%)"
        for name, data in global_markets.items()
    ])
    tech_text = '\n'.join([
        f"{name}: 趨勢={data.get('trend')} RSI={data.get('RSI')}"
        for name, data in technical_results.items()
    ])
    macro_text = '\n'.join([
        f"{name}: {data['price']} ({'+' if data['change']>0 else ''}{data['change']}%)"
        for name, data in macro_data.items()
    ])
    prompt = f"""
你是一位專業的台股選股分析師。請根據目前大盤趨勢推薦適合投資的標的。

【全球市場概況】
{markets_text}

【總體資產走勢】
{macro_text}

【目前追蹤標的技術面】
{tech_text}

請提供：
1. 目前大盤最強勢的2-3個產業（說明為何強勢）
2. 每個產業推薦1-2檔台股標的（共5檔以內）

每檔推薦標的格式：
股票名稱（代號）
- 推薦理由（2-3點）
- <span class="close-price">進場：XXX~XXX元</span>
- <span class="target-price">目標一：XXX元</span>
- <span class="target-price">目標二：XXX元</span>
- <span class="stop-loss">停損：XXX元</span>

短期標題：<span class="short-term-title">▶ 短期推薦</span>
中期標題：<span class="mid-term-title">▶ 中期布局</span>

重要規定：所有價位必須是具體數字，不可用百分比。
重要提醒：以上為模擬分析，不構成實際投資建議。
"""
    return _generate(prompt)

def analyze_weekly_global(global_markets, commodities, news, macro_data, week_range):
    markets_text = '\n'.join([
        f"{name}: {data['price']} ({'+' if data['change']>0 else ''}{data['change']}%)"
        for name, data in global_markets.items()
    ])
    macro_text = '\n'.join([
        f"{name}: {data['price']} ({'+' if data['change']>0 else ''}{data['change']}%)"
        for name, data in macro_data.items()
    ])
    news_text = '\n'.join([f"- {a['title']}" for a in news[:10]])
    prompt = f"""
你是一位專業的全球財經週報分析師。請根據以下資料提供本週市場總結與下週展望。

【本週全球股市收盤狀況】
{markets_text}

【本週美債/黃金/石油】
{macro_text}

【本週重要財經新聞】
{news_text}

【分析週期】{week_range}

請提供：
1. 本週全球市場重點回顧（3-5點）
2. 本週最重要的3個國際事件及其影響
3. 美債/黃金/石油本週走勢白話解析（新手易懂）
4. 下週全球市場展望與潛在風險
5. 整體市場情緒評估（偏多/中性/偏空）及原因

請用繁體中文，條列式呈現，專業但易懂。
"""
    return _generate(prompt)

def analyze_weekly_taiwan(global_weekly_analysis, technical_results, livermore_signals, week_range, twii_data=None):
    tech_text = '\n'.join([
        f"{name}: 趨勢={data.get('trend')} RSI={data.get('RSI')} MA5={data.get('MA5')} MA20={data.get('MA20')}"
        for name, data in technical_results.items()
    ])
    signal_text = '\n'.join([
        f"{name}: {sig['recommendation']} 分數:{sig['score']}"
        for name, sig in livermore_signals['all'].items()
    ])
    if twii_data:
        twii_text = f"""【台灣加權指數（^TWII）— 程式計算真實數據，必須使用這些數字】
本週收盤：{twii_data.get('price')} 點
本週漲跌：{twii_data.get('change')}%
趨勢：{twii_data.get('trend')}
MA5：{twii_data.get('MA5')} 點
MA20：{twii_data.get('MA20')} 點
MA60：{twii_data.get('MA60')} 點
RSI：{twii_data.get('RSI')}
近20日支撐：{twii_data.get('support')} 點
近20日壓力：{twii_data.get('resistance')} 點"""
    else:
        twii_text = "【台灣加權指數】資料暫無，請勿自行推算任何指數點位。"

    prompt = f"""
你是一位專業的台股週報分析師，熟悉李佛摩投資法則與技術分析。請根據以下【真實數據】分析台灣股市。

⚠️ 嚴格規定：
- 大盤加權指數的所有點位數字，只能使用下方「台灣加權指數」區塊中提供的數字
- 嚴禁自行推算、估計或捏造任何指數點位
- 若資料不足，請直接說「資料不足」，不可填入未經提供的數字

{twii_text}

【全球市場本週概況】
{global_weekly_analysis[:600]}

【台股本週個股技術面】
{tech_text}

【李佛摩法則訊號】
{signal_text}

【分析週期】{week_range}

請提供：
1. 台股本週走勢回顧（3點，使用上方真實數字）
2. 全球情勢對下週台股的影響評估
3. 下週台股技術面展望（支撐/壓力只用上方提供的真實數字）
4. 下週短期操作建議：推薦2-3檔標的及理由
5. 下週中期布局建議：推薦2-3檔標的及理由
6. 下週需要特別注意的風險與事件

請用繁體中文，套用以下HTML格式：
短期標題：<span class="short-term-title">▶ 下週短期建議（1-5天）</span>
中期標題：<span class="mid-term-title">▶ 下週中期建議（1-3個月）</span>
目標價：<span class="target-price">目標價：XXX元</span>
停損價：<span class="stop-loss">停損：XXX元</span>
支撐：<span class="support-level">支撐：XXXX點</span>
壓力：<span class="resistance-level">壓力：XXXX點</span>
現價：<span class="close-price">XXX元</span>
股票代號後附中文名稱，例如：2330台積電

重要規定：大盤支撐壓力只能使用上方提供的真實數字，每檔標的都要有目標價和停損價。
重要提醒：以上為模擬分析，不構成實際投資建議。
"""
    return _generate(prompt)

def analyze_weekly_watchlist(name, symbol, technical_data, patterns, news_list, week_range, cost=None):
    pattern_descs = '\n'.join([f"- {p['name']}：{p['desc']}" for p in patterns]) if patterns else '無明顯型態'
    news_text = '\n'.join([f"- {n['title']}" for n in news_list[:5]]) if news_list else '暫無相關新聞'
    cost_info = f'持股成本：{cost}元' if cost else '（未設定成本）'
    prompt = f"""
你是一位專業的台股分析師。請針對以下個股提供本週回顧與下週建議。

【股票資訊】
股票：{name}（{symbol}）
{cost_info}
現價：{technical_data.get('price')}
本週漲跌：{technical_data.get('change')}%
趨勢：{technical_data.get('trend')}
RSI：{technical_data.get('RSI')}
MA5：{technical_data.get('MA5')} MA20：{technical_data.get('MA20')}
支撐一：{technical_data.get('support')} 支撐二：{technical_data.get('support2')}
壓力一：{technical_data.get('resistance2')} 壓力二：{technical_data.get('resistance')}

【本週K線型態】
{pattern_descs}

【本週相關新聞】
{news_text}

【分析週期】{week_range}

每檔股票分析必須包含以下結構：
一、本週走勢簡評（2-3點）
二、K線型態對下週的啟示
三、下週操作建議
四、價位資訊（給出具體數字）：
   - <span class="support-level">支撐一：XXX元</span>
   - <span class="support-level">支撐二：XXX元</span>
   - <span class="resistance-level">壓力一：XXX元</span>
   - <span class="resistance-level">壓力二：XXX元</span>
   - <span class="close-price">進場：XXX~XXX元</span>
   - <span class="target-price">目標一：XXX元</span>
   - <span class="target-price">目標二：XXX元</span>
   - <span class="stop-loss">停損：XXX元</span>
五、特別注意事項

重要規定：所有價位必須是具體數字，不可用百分比。
重要提醒：以上為模擬分析，不構成實際投資建議。
"""
    return _generate(prompt)
