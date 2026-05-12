"""
ai_analyzer_v2.py
三大宗師 AI 分析框架
主從結構：威科夫（骨幹 月線+5日+日線）→ 本間宗久（確認 日K+週K）→ 李佛摩（時機 月線+5日均）
數據來源：data_enricher.get_full_stock_data()
"""
import os
import re
import time
import anthropic
from dotenv import load_dotenv
from modules.candlestick import detect_from_bars, label_bars, calc_pnf_target

load_dotenv()

_client = None

def _get_client():
    global _client
    if _client is None:
        api_key = os.getenv('CLAUDE_API_KEY')
        if not api_key:
            try:
                import config
                api_key = config.CLAUDE_API_KEY
            except ImportError:
                pass
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def _generate(content, max_tokens: int = 2500, retries: int = 1) -> str:
    client = _get_client()
    for attempt in range(retries + 1):
        try:
            msg = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=max_tokens,
                timeout=90,
                messages=[{"role": "user", "content": content}]
            )
            return msg.content[0].text
        except Exception as e:
            err = str(e)
            if attempt < retries:
                wait = 15 if 'rate_limit' in err or '429' in err else 5
                print(f'[v2] AI 請求失敗（第{attempt+1}次），{wait}秒後重試: {err[:100]}')
                time.sleep(wait)
            else:
                return f"AI分析失敗: {err}"


def _fmt_bars(bars: list, label: str, n: int, pattern_labels: dict = None) -> str:
    if not bars:
        return f"【{label}】：資料不足"
    rows = bars[-n:]

    # 20-bar baselines for 特徵 computation
    ref        = bars[-20:]
    vol_list   = [float(b.get('volume_zhang', 0) or 0) for b in ref]
    vol_avg    = sum(vol_list) / len(vol_list) if vol_list else 0
    range_high = max(float(b['high']) for b in ref) if ref else 0
    range_low  = min(float(b['low'])  for b in ref) if ref else 0

    lines = []
    for idx, b in enumerate(rows):
        abs_idx = len(bars) - len(rows) + idx

        # 量能
        vol = float(b.get('volume_zhang', 0) or 0)
        if vol_avg > 0:
            r = vol / vol_avg
            vol_feat = '放量' if r >= 1.5 else ('縮量' if r <= 0.7 else '均量')
        else:
            vol_feat = '均量'

        # 位置（收盤在20根高低範圍中的相對位置）
        close = float(b['close'])
        if range_high > range_low:
            pos = (close - range_low) / (range_high - range_low)
            pos_feat = ('極高位' if pos >= 0.85 else
                        '高位'   if pos >= 0.65 else
                        '中段'   if pos >= 0.35 else
                        '低位'   if pos >= 0.15 else '極低位')
        else:
            pos_feat = '中段'

        # 跳空（開盤 vs 前根收盤 ±1%）
        gap_feat = ''
        if abs_idx > 0:
            prev_close = float(bars[abs_idx - 1]['close'])
            open_ = float(b['open'])
            if open_ > prev_close * 1.01:
                gap_feat = '·跳空高開'
            elif open_ < prev_close * 0.99:
                gap_feat = '·跳空低開'

        feat = f"【特徵={vol_feat}·{pos_feat}{gap_feat}】"
        line = (f"{b['date']}  O={b['open']} H={b['high']} L={b['low']} C={b['close']}  "
                f"量={b['volume_zhang']}張  {feat}")
        if pattern_labels and b['date'] in pattern_labels:
            line += f"  ▶{pattern_labels[b['date']]}"
        lines.append(line)
    return f"【{label}（最近{len(rows)}根）】\n" + "\n".join(lines)


def _clean_html_output(raw: str) -> str:
    """
    清理 AI 回應：
    1. 移除完整 HTML document 結構（<head>/<style>/<body> 等），防止 CSS 注入污染頁面
    2. 移除 markdown 代碼塊圍欄 ```html ... ```（AI 偶爾會把 HTML 包進去）
    3. 移除頂部結構化標記行（RISK_PCT: ... 等）
    4. 剝除所有 inline style 屬性，讓 CSS 統一控制深色主題
    """
    # ── 步驟1：剝除會污染頁面的 HTML document 結構 ──────────
    # <style>/<head> 最危險：注入後直接改變全頁背景/字色，且「未閉合」會吃掉後續內容
    # 先處理完整對：
    raw = re.sub(r'<style\b[^>]*>.*?</style>', '', raw, flags=re.IGNORECASE | re.DOTALL)
    raw = re.sub(r'<head\b[^>]*>.*?</head>',   '', raw, flags=re.IGNORECASE | re.DOTALL)
    # 再砍「殘破未閉合」的：從 tag 開始一路到字串尾（AI 偶爾把 max_tokens 全花在 CSS 上會發生）
    raw = re.sub(r'<style\b[^>]*>.*$', '', raw, flags=re.IGNORECASE | re.DOTALL)
    raw = re.sub(r'<head\b[^>]*>.*$',  '', raw, flags=re.IGNORECASE | re.DOTALL)
    # <!DOCTYPE>, <html>, <body>, <script> 標籤
    raw = re.sub(r'<!DOCTYPE[^>]*>', '', raw, flags=re.IGNORECASE)
    raw = re.sub(r'</?(?:html|body)\b[^>]*>', '', raw, flags=re.IGNORECASE)
    raw = re.sub(r'<script\b[^>]*>.*?</script>', '', raw, flags=re.IGNORECASE | re.DOTALL)
    raw = re.sub(r'<script\b[^>]*>.*$', '', raw, flags=re.IGNORECASE | re.DOTALL)

    # ── 步驟2：剝除 markdown 代碼塊圍欄（任意位置） ─────────
    # 整行 ```html / ```xml / ``` 都當分隔符移除（保留中間內容）
    raw = re.sub(r'^\s*```\s*[a-zA-Z]*\s*$', '', raw, flags=re.MULTILINE)
    raw = re.sub(r'^\s*```\s*$', '', raw, flags=re.MULTILINE)
    # 移除頂部 markdown H1/H2 標題（AI 自加的 "# 台股週報..." 之類）
    raw = re.sub(r'^\s*#{1,3}\s+.*$', '', raw, count=1, flags=re.MULTILINE)

    # ── 步驟3：跳過頂部 metadata 行 ──────────────────────────
    lines = raw.split('\n')
    content_lines = []
    skip_header = True
    tag_prefixes = (
        'RISK_PCT:', 'SUPPORT:', 'RESISTANCE:', 'TARGET_PNF:', 'TARGET_PRICE:',
        'WYCKOFF_PHASE:', '---', '```',
    )
    for line in lines:
        s = line.strip().upper()
        if skip_header:
            if (any(s.startswith(t) for t in tag_prefixes)
                    or s == ''
                    or re.match(r'^[A-Z_]+\s*:\s*\S', s)):
                continue
            skip_header = False
        content_lines.append(line)
    html = '\n'.join(content_lines).strip()

    # ── 步驟4：剝除所有 inline style 屬性 ────────────────────
    html = re.sub(r'\s+style\s*=\s*(?:"[^"]*"|\'[^\']*\')', '', html, flags=re.IGNORECASE)
    return html


def _parse_tagged(raw: str, tag: str, default):
    """從 AI 回應中解析 TAG: value 格式"""
    for line in raw.split('\n'):
        line = line.strip()
        if line.upper().startswith(tag.upper() + ':'):
            val = line.split(':', 1)[1].strip()
            return val
    return default


# ── 個股三宗師分析 ────────────────────────────────────────────

def analyze_stock_three_masters(
    name: str,
    symbol: str,
    enriched_data: dict,
    status: str,
    avg_cost: float = None,
    total_zhang: float = None,
    news_list: list = None,
) -> dict:
    """
    三大宗師框架分析一支股票。

    Returns dict:
        html        : str   — HTML 分析內容（含操作建議）
        risk_pct    : int   — 風險係數 0-100
        support     : float | None
        resistance  : float | None
        target_pnf  : float | None  — P&F 概念目標價
        wyckoff_phase : str
    """
    from datetime import datetime, timezone, timedelta
    TW = timezone(timedelta(hours=8))
    today = datetime.now(TW).strftime('%Y/%m/%d')

    price     = enriched_data.get('price', '--')
    ma5       = enriched_data.get('ma5',  '--')
    ma20      = enriched_data.get('ma20', '--')
    ma60      = enriched_data.get('ma60', '--')
    macd      = enriched_data.get('macd') or {}
    vol_today = enriched_data.get('volume_zhang', '--')
    vol_5avg  = enriched_data.get('volume_5d_avg_zhang', '--')

    # 持倉資訊
    if status == 'holding' and avg_cost:
        try:
            pnl = round((float(price) - float(avg_cost)) / float(avg_cost) * 100, 2)
            position_block = (
                f"持倉狀態：已持有 {total_zhang or '--'} 張\n"
                f"平均成本：{avg_cost} 元\n"
                f"目前損益：{pnl:+.2f}%"
            )
        except Exception:
            position_block = f"持倉狀態：已持有\n平均成本：{avg_cost} 元"
    elif status == 'watching':
        position_block = "持倉狀態：觀察中（尚未持有）"
    else:
        position_block = "持倉狀態：已持有"

    _monthly_labels = label_bars(enriched_data.get('monthly_bars', []))
    _weekly_labels  = label_bars(enriched_data.get('weekly_bars', []))
    _daily_labels   = label_bars(enriched_data.get('daily_bars', []))
    monthly_text = _fmt_bars(enriched_data.get('monthly_bars', []), "月K", 6, _monthly_labels)
    weekly_text  = _fmt_bars(enriched_data.get('weekly_bars',  []), "週K", 8, _weekly_labels)
    daily_text   = _fmt_bars(enriched_data.get('daily_bars',   []), "日K", 15, _daily_labels)

    # P&F 等幅量度目標（程式計算，優先用週K；無週K則用日K）
    try:
        _price_f = float(price) if price != '--' else None
    except (TypeError, ValueError):
        _price_f = None
    _pnf = calc_pnf_target(enriched_data.get('weekly_bars', []), lookback=12, current_price=_price_f)
    if not _pnf:
        _pnf = calc_pnf_target(enriched_data.get('daily_bars', []), lookback=20, current_price=_price_f)
    pnf_str = f'{_pnf:.0f}' if _pnf else '—（尚未接近突破點）'

    # 威科夫突破量能門檻（程式計算，禁止 AI 更改）
    try:
        _v5 = float(vol_5avg)
        _vol_breakout = f'{round(_v5 * 1.5):,}'
        _vol_spring   = f'{round(_v5 * 1.2):,}'
    except (TypeError, ValueError):
        _vol_breakout = '—'
        _vol_spring   = '—'

    news_text = (
        '\n'.join([f"- {n['title']}" for n in (news_list or [])[:5]])
        or '暫無相關新聞'
    )

    # 持倉狀態對應的建議區塊
    if status == 'holding':
        action_section = f"""### 五、操作建議（已持有）
- <span class="short-term-title">▶ 短期（1-5日）</span>：根據上方分析給出具體建議
- 加碼條件：突破何種壓力，且量超過 {_vol_breakout} 張（5日均量×1.5，程式計算，禁止更改）
- 減碼 / 停利條件：（達到何種目標 or 出現何種警訊）
- <span class="stop-loss">停損：XX 元（跌破請執行，不要猶豫）</span>"""
    else:
        action_section = f"""### 五、操作建議（觀察中）
- <span class="short-term-title">▶ 短線介入條件（1-5日）</span>：突破 XX 元且量超過 {_vol_breakout} 張（5日均量×1.5，程式計算，禁止更改）
- <span class="mid-term-title">▶ 中線布局條件（月線角度）</span>：威科夫積累完成確認，Spring 縮量需達 {_vol_spring} 張
- <span class="stop-loss">預設停損：XX 元（買進後若跌破立即出場）</span>
- 目前是否適合介入？說明理由"""

    static_block = f"""你是融合三大宗師智慧的台股分析師。分析日期：{today}

⚠️ 重要：請在回應的**第一行**先輸出以下結構化標記（純數字），再輸出分析內容：
RISK_PCT: [0到100整數]
SUPPORT: [支撐價]
RESISTANCE: [壓力價]
WYCKOFF_PHASE: [積累|上漲|派發|下跌|再積累|再派發|不明]
---


## 三大宗師主從架構
1. 【威科夫】（骨幹）：月K定趨勢方向 → 日K量價驗證 → 5日均線確認動能
2. 【本間宗久】（確認）：週K型態 → 日K蠟燭 → 方向是否一致
3. 【李佛摩】（時機）：月線位階 + 5日均趨勢 → 是否為介入時機

⚠️ 上位優先：威科夫月K趨勢為最高骨幹，若本間/李佛摩短線訊號與月線方向衝突，以月線為準，短線機會屬高風險操作，需特別說明。

## 風險係數評分原則（0=低風險 100=高風險）
- 威科夫月K明確下跌趨勢中日線試圖反彈 → +25
- MACD 柱狀線方向與近期價格趨勢背離 → +15
- 價格低於 MA60（位於長期均線下方）→ +20
- 本間週K出現明確頂部反轉型態（如黃昏之星/吊人）→ +15
- 本間週K出現底部反轉型態（如晨星/鎚子）→ -15
- 威科夫量縮無力創高（努力大於結果）→ +10
- 李佛摩5日均線下彎且遠離月線支撐 → +15
- 已持有且目前虧損超過 10% → +10（心理壓力加權）
- 三宗師方向完全一致（多頭排列）→ -20

## 請用繁體中文 + HTML 格式輸出以下分析：

### 一、威科夫骨幹分析
- 月K階段：目前處於哪個威科夫階段？（積累/上漲/派發/下跌/再積累/再派發）說明依據
- 量價關係：近期放量/縮量與價格方向的「努力 vs 結果」解析
- 從月K/日K推導：<span class="support-level">關鍵支撐：XX 元</span> 與 <span class="resistance-level">關鍵壓力：XX 元</span>

### 二、本間宗久K線確認
⚠️ K棒資料中 ▶型態名稱 為程式依數學公式精確計算，禁止更改或自行重新命名。請直接使用標注的型態並解讀其在當前趨勢下的含意。
⚠️ 禁止只憑單根紅/綠顏色判斷多空，必須結合【特徵=...】的量能·位置分析含意。
- 週K型態（最近3根）：引用 ▶標注 的型態名稱，結合【特徵=...】量能·位置解讀含意
- 日K型態（最近5根）：引用 ▶標注 的型態名稱，結合【特徵=...】量能·位置解讀含意
- K線序列：連續3-5根量能·位置的變化趨勢，說明多空動能是否增強或衰退
- 週K ↔ 日K 方向是否一致確認？

### 三、李佛摩時機判斷
- 月線位階：距離關鍵支撐/壓力的距離，是否為「自然反彈/回落」
- 5日均線動能：上揚/持平/下彎，是否形成加速或衰竭訊號
- 當前是否為介入時機？說明原因

### 四、三宗師融合結論
三個框架方向是否一致？有衝突時說明主從優先級與衝突程度。

⚠️ P&F概念目標已由程式以等幅量度法計算（整理區高點 + 整理區間高度），數值在股票資料區的【P&F等幅量度目標】欄位提供，**禁止更改此數字**，輸出格式：<span class="target-price">P&F概念目標：[數值]元（等幅量度）</span>"""

    dynamic_block = f"""## 股票資料

股票：{name}（{symbol}）
現價：{price} 元
{position_block}

均線：MA5={ma5} | MA20={ma20} | MA60={ma60}
MACD：DIF={macd.get('macd','--')} | DEA={macd.get('signal','--')} | 柱狀={macd.get('histogram','--')}
成交量：今日 {vol_today} 張 ｜ 5日均量 {vol_5avg} 張
【突破最低量能門檻（程式計算，禁止更改）】突破：{_vol_breakout} 張（5日均量×1.5）｜ 春天/測試：{_vol_spring} 張（5日均量×1.2）

【P&F等幅量度目標（程式計算，禁止更改）】{pnf_str} 元

{monthly_text}

{weekly_text}

{daily_text}

【近期相關新聞】
{news_text}

---

{action_section}

重要提醒：以上為模擬分析，不構成實際投資建議。"""

    raw = _generate(
        [
            {"type": "text", "text": static_block, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": dynamic_block},
        ],
        max_tokens=2500,
    )

    result = {
        'html':          _clean_html_output(raw),
        'risk_pct':      50,
        'support':       None,
        'resistance':    None,
        'target_pnf':    _pnf,   # 程式計算值，不再解析 AI 輸出
        'wyckoff_phase': '未知',
    }
    try:
        rp = _parse_tagged(raw, 'RISK_PCT', None)
        if rp:
            result['risk_pct'] = max(0, min(100, int(rp)))
        sp = _parse_tagged(raw, 'SUPPORT', None)
        if sp and sp != '0':
            result['support'] = float(sp)
        rs = _parse_tagged(raw, 'RESISTANCE', None)
        if rs and rs != '0':
            result['resistance'] = float(rs)
        wp = _parse_tagged(raw, 'WYCKOFF_PHASE', None)
        if wp:
            result['wyckoff_phase'] = wp
    except Exception as e:
        print(f"[ai_analyzer_v2] 解析結構化輸出失敗: {e}")

    return result


# ── 每日財經新聞摘要 + 明日方向 ────────────────────────────────

def analyze_daily_news(news_list: list, twii_price=None, twii_change_pct=None) -> str:
    """
    今日重大財經新聞摘要 + 明日需關注方向。
    供平日印表報表頂部替代週報區塊使用。
    twii_price: 今日收盤點位（float）
    twii_change_pct: 今日漲跌幅百分比（float，如 +2.01 或 -1.30）
    """
    from datetime import datetime, timezone, timedelta
    TW = timezone(timedelta(hours=8))
    now_tw = datetime.now(TW)
    today = now_tw.strftime('%Y/%m/%d')
    tomorrow = (now_tw + timedelta(days=1)).strftime('%m/%d')

    news_text = '\n'.join([
        f"- {n['title']} （{n.get('source', '')}）"
        for n in (news_list or [])[:15]
    ]) or '今日無財經新聞資料'

    if twii_price and twii_change_pct is not None:
        direction = '上漲' if twii_change_pct >= 0 else '下跌'
        twii_block = (
            f"\n【今日大盤資訊（必須依此數值描述，嚴禁使用訓練資料中的歷史數值）】\n"
            f"台灣加權指數收盤：{twii_price:.0f} 點，{direction} {abs(twii_change_pct):.2f}%\n"
        )
    else:
        twii_block = ''

    prompt = f"""你是台股財經分析師。根據以下今日財經新聞標題，輸出三個區塊。
分析日期：{today}{twii_block}
【今日財經新聞標題】
{news_text}

請用繁體中文純 HTML 格式輸出：

<h3>今日重大財經重點</h3>
挑選 3-5 條最重要的新聞，每條一句話說明對台股的影響方向。
<ul><li>...</li></ul>

<h3>{tomorrow} 隔日方向注意</h3>
根據今日新聞，列出隔日 2-3 個具體關注點，包含可能受影響族群、關鍵價位或需驗證的條件。
<ul><li>...</li></ul>

<h3>操作建議（依新聞評估）</h3>
根據今日新聞評估，給出 2-3 條具體觀點：哪些族群或方向適合觀察布局、哪些需要迴避或減碼、整體市場偏多/偏空/觀望。
<ul><li>...</li></ul>

輸出格式鐵律：
- 只輸出純 HTML 片段，禁止 <head>/<style>/<html>/<body>
- 禁止 markdown 語法與 ``` 代碼塊
- 每條 bullet 不超過 30 字
- 若提及大盤點位或漲跌幅，必須使用上方【今日大盤資訊】的數值
- 嚴禁引用訓練資料中的歷史特定漲跌事件數字（如「1778點大漲」「突破3萬點」「創歷史新高點位」等），這些屬模型幻覺，非今日實際新聞
- 若新聞標題含此類描述，需核實是否今日實際發生；無法核實則跳過，不得直接引用或擴寫
- 若無法判斷影響，說明「需觀察」而非憑空杜撰"""

    return _clean_html_output(_generate(prompt, max_tokens=800))


# ── 第一段：客觀市場分析（跨用戶共用快取）──────────────────────

def analyze_market_only(
    name: str,
    symbol: str,
    enriched_data: dict,
    news_list: list = None,
) -> dict:
    """
    客觀市場分析，不含個人持倉資訊，結果跨用戶共用。
    存入 StockAnalysis.html_content。
    回傳 dict 與 analyze_stock_three_masters 同格式。
    """
    from datetime import datetime, timezone, timedelta
    TW = timezone(timedelta(hours=8))
    today = datetime.now(TW).strftime('%Y/%m/%d')

    price     = enriched_data.get('price', '--')
    ma5       = enriched_data.get('ma5',  '--')
    ma20      = enriched_data.get('ma20', '--')
    ma60      = enriched_data.get('ma60', '--')
    macd      = enriched_data.get('macd') or {}
    vol_today = enriched_data.get('volume_zhang', '--')
    vol_5avg  = enriched_data.get('volume_5d_avg_zhang', '--')

    _monthly_labels = label_bars(enriched_data.get('monthly_bars', []))
    _weekly_labels  = label_bars(enriched_data.get('weekly_bars', []))
    _daily_labels   = label_bars(enriched_data.get('daily_bars', []))
    monthly_text = _fmt_bars(enriched_data.get('monthly_bars', []), "月K", 6, _monthly_labels)
    weekly_text  = _fmt_bars(enriched_data.get('weekly_bars',  []), "週K", 8, _weekly_labels)
    daily_text   = _fmt_bars(enriched_data.get('daily_bars',   []), "日K", 30, _daily_labels)

    try:
        _price_f = float(price) if price != '--' else None
    except (TypeError, ValueError):
        _price_f = None
    _pnf = calc_pnf_target(enriched_data.get('weekly_bars', []), lookback=12, current_price=_price_f)
    if not _pnf:
        _pnf = calc_pnf_target(enriched_data.get('daily_bars', []), lookback=20, current_price=_price_f)
    pnf_str = f'{_pnf:.0f}' if _pnf else '—（尚未接近突破點）'

    try:
        _v5 = float(vol_5avg)
        _vol_breakout = f'{round(_v5 * 1.5):,}'
        _vol_spring   = f'{round(_v5 * 1.2):,}'
    except (TypeError, ValueError):
        _vol_breakout = '—'
        _vol_spring   = '—'

    news_text = (
        '\n'.join([f"- {n['title']}" for n in (news_list or [])[:5]])
        or '暫無相關新聞'
    )

    detected_patterns = detect_from_bars(enriched_data.get('daily_bars', []))
    _header = "【Rule-based K線型態偵測結果（最新一根）】\n"
    if detected_patterns:
        _body = '\n'.join(f"- {p['name']}（{p['type']}）：{p['desc']}" for p in detected_patterns[:5])
        _footer = "（上方K棒資料中 ▶型態 已標注各根，此為最新一根的詳細說明，供補充解讀）"
    else:
        _body = "- 最新一根無明顯單根/雙根/三根型態"
        _footer = "（各根歷史型態請參閱上方K棒資料的 ▶標注）"
    pattern_block = f"{_header}{_body}\n{_footer}"

    static_block = f"""你是融合三大宗師智慧的台股分析師。分析日期：{today}

⚠️ 重要：請在回應的**第一行**先輸出以下結構化標記（純數字），再輸出分析內容：
RISK_PCT: [0到100整數]
SUPPORT: [支撐價]
RESISTANCE: [壓力價]
WYCKOFF_PHASE: [積累|上漲|派發|下跌|再積累|再派發|不明]
---

## 三大宗師主從架構
1. 【威科夫】（骨幹）：月K定趨勢方向 → 日K量價驗證 → 5日均線確認動能
2. 【本間宗久】（確認）：週K型態 → 日K蠟燭 → 方向是否一致
3. 【李佛摩】（時機）：月線位階 + 5日均趨勢 → 是否為介入時機

⚠️ 上位優先：威科夫月K趨勢為最高骨幹，若本間/李佛摩短線訊號與月線方向衝突，以月線為準。

## 風險係數評分原則（0=低風險 100=高風險）
- 威科夫月K明確下跌趨勢中日線試圖反彈 → +25
- MACD 柱狀線方向與近期價格趨勢背離 → +15
- 價格低於 MA60（位於長期均線下方）→ +20
- 本間週K出現明確頂部反轉型態（如黃昏之星/吊人）→ +15
- 本間週K出現底部反轉型態（如晨星/鎚子）→ -15
- 威科夫量縮無力創高（努力大於結果）→ +10
- 李佛摩5日均線下彎且遠離月線支撐 → +15
- 三宗師方向完全一致（多頭排列）→ -20

## ⚠️ 輸出格式鐵律（違者輸出無效）
1. **嚴禁散文段落**：所有分析點以「- 」bullet 輸出，不得有連續句子段落
2. **每條 bullet ≤ 20 中文字**（數字與標點不計），超過必須拆分或刪減
3. **禁用詞**：「然而」「因此」「綜合以上」「由此可見」「值得注意的是」
4. **每個 ### 小節**：3～5 條 bullet + 結尾 1 條 `<span class="key-point">小節核心結論（≤15字）</span>`
5. **全文 key-point 上限：4 個**（四個小節各 1 個），禁止在 bullet 內部嵌套使用
6. **第二節 K 線必須輸出 HTML table**（週K 3根 + 日K 5根各一張表），格式見下方範例
7. 其他語意 span 照舊：`support-level` / `resistance-level` / `target-price`

## K 線 table 輸出範例（第二節專用）
<table><thead><tr><th>日期</th><th>型態</th><th>開</th><th>高</th><th>低</th><th>收</th><th>特徵</th></tr></thead>
<tbody><tr><td>YYYY-MM-DD</td><td>錘子</td><td>150</td><td>153</td><td>148</td><td>152</td><td>放量·高位</td></tr></tbody></table>

## 請輸出以下分析（不含操作建議）：

### 一、威科夫骨幹分析
- 月K階段：[積累/上漲/派發/下跌/再積累/再派發] + 3個具體依據（各一條 bullet）
- 量價關係：近期主要放量/縮量事件，「努力 vs 結果」是否背離
- <span class="support-level">支撐：XX元（理由≤10字）</span>
- <span class="resistance-level">壓力：XX元（理由≤10字）</span>
<span class="key-point">威科夫核心結論（≤15字）</span>

### 二、本間宗久K線確認（⚠️ 必須輸出 HTML table）
⚠️ 【K線型態命名鐵律】K棒資料中 ▶型態名稱 為程式依數學公式精確計算，禁止更改或自行重新命名。table 的「型態」欄必須直接使用 ▶標注 的名稱，你的任務是解讀含意，不是命名型態。
⚠️ 【特徵欄鐵律】table 的「特徵」欄必須直接抄 K棒資料中 【特徵=...】 的值，禁止自行判斷，禁止只因陽線/陰線填寫看漲/看跌。
K棒型態含意速查（僅供解讀參考，必須結合特徵欄的量能·位置）：
錘子（下影≥實體2倍/低位看漲·高位需謹慎）、吊人（錘子型/高位看跌訊號）、射擊之星（上影≥實體2倍/高位看跌）、
早晨之星（長黑+小K+長紅/底部反轉）、黃昏之星（長紅+小K+長黑/頂部反轉）、
多頭吞噬（陽線吞陰線）、空頭吞噬（陰線吞陽線）、十字星（開收相等/高位→頂部訊號·低位→底部訊號·中段→觀望）

【週K最近3根 table】（輸出如範例格式）
【日K最近5根 table】（輸出如範例格式）
- K線序列：依「特徵」欄的量能·位置變化，說明多空動能是否增強或衰退（禁止靠單根顏色判斷方向）
- 週K ↔ 日K 方向：一致多頭 / 一致空頭 / 訊號分歧（分歧時說明以哪個為準）
<span class="key-point">K線核心結論（≤15字）</span>

### 三、李佛摩時機判斷
- 月線位階：距支撐/壓力 XX%，屬於自然反彈/自然回落/突破走勢
- 5日均動能：上揚/持平/下彎，說明斜率變化
- Pivot Point：近期有無關鍵轉折？突破前高/跌破前低？
- 等待條件：需等待什麼才適合行動（量能引用【突破最低量能門檻】欄位數值/價格/K棒，具體說明）
- 今日時機：**立刻可行動 / 等待確認 / 不宜行動**（一個明確判斷）
<span class="key-point">李佛摩核心結論（≤15字）</span>

### 四、三宗師融合結論
- 三框架方向：一致多頭 / 一致空頭 / 分歧（分歧時說明主從優先）
- 衝突點：[若有，說明哪兩個框架衝突及原因]
- ⚠️ P&F概念目標已由程式以等幅量度法計算，數值在股票資料區的【P&F等幅量度目標】欄位提供，**禁止更改此數字**，直接引用格式：<span class="target-price">P&F概念目標：[數值]元（等幅量度）</span>
<span class="key-point">融合核心結論（≤15字）</span>

重要提醒：以上為模擬分析，不構成實際投資建議。"""

    dynamic_block = f"""## 股票資料

股票：{name}（{symbol}）
現價：{price} 元
均線：MA5={ma5} | MA20={ma20} | MA60={ma60}
MACD：DIF={macd.get('macd','--')} | DEA={macd.get('signal','--')} | 柱狀={macd.get('histogram','--')}
成交量：今日 {vol_today} 張 ｜ 5日均量 {vol_5avg} 張
【突破最低量能門檻（程式計算，禁止更改）】突破：{_vol_breakout} 張（5日均量×1.5）｜ 春天/測試：{_vol_spring} 張（5日均量×1.2）

【P&F等幅量度目標（程式計算，禁止更改）】{pnf_str} 元

{monthly_text}

{weekly_text}

{daily_text}

{pattern_block}

【近期相關新聞】
{news_text}"""

    raw = _generate(
        [
            {"type": "text", "text": static_block, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": dynamic_block},
        ],
        max_tokens=2000,
    )

    result = {
        'html':              _clean_html_output(raw),
        'risk_pct':          50,
        'support':           None,
        'resistance':        None,
        'target_pnf':        _pnf,   # 程式計算值，不再解析 AI 輸出
        'detected_patterns': detected_patterns,
        'wyckoff_phase': '未知',
    }
    try:
        rp = _parse_tagged(raw, 'RISK_PCT', None)
        if rp: result['risk_pct'] = max(0, min(100, int(rp)))
        sp = _parse_tagged(raw, 'SUPPORT', None)
        if sp and sp != '0': result['support'] = float(sp)
        rs = _parse_tagged(raw, 'RESISTANCE', None)
        if rs and rs != '0': result['resistance'] = float(rs)
        wp = _parse_tagged(raw, 'WYCKOFF_PHASE', None)
        if wp: result['wyckoff_phase'] = wp
    except Exception as e:
        print(f"[ai_analyzer_v2] 解析結構化輸出失敗: {e}")

    return result


# ── 第二段：個人化操作建議（各用戶獨立，不快取）──────────────────

def generate_personal_recommendation(
    name: str,
    symbol: str,
    current_price,
    wyckoff_phase: str,
    risk_pct: int,
    support,
    resistance,
    target_pnf,
    status: str,
    avg_cost=None,
    total_zhang=None,
    recent_bars: list = None,
) -> str:
    """
    基於第一段的結構化快取資料，針對個人持倉給出操作建議。
    不儲存（每次重新產生）。
    """
    if status == 'holding' and avg_cost:
        try:
            pnl = round((float(current_price) - float(avg_cost)) / float(avg_cost) * 100, 2)
            pnl_str = f"{pnl:+.2f}%"
            position_info = (
                f"已持有 {total_zhang or '--'} 張，"
                f"平均成本 {avg_cost} 元，目前損益 {pnl_str}"
            )
        except Exception:
            pnl_str = '--'
            position_info = f"已持有，平均成本 {avg_cost} 元"
    elif status == 'watching':
        pnl_str = None
        position_info = "觀察中（尚未買入）"
    else:
        pnl_str = None
        position_info = "已持有（無成本資料）"

    # 近期 K 棒摘要
    bars_text = ''
    if recent_bars:
        lines = [
            f"{b['date']}  O={b['open']} H={b['high']} L={b['low']} C={b['close']}  量={b.get('volume_zhang','--')}張"
            for b in recent_bars[-5:]
        ]
        bars_text = "【近期日K（最後5根）】\n" + "\n".join(lines)

    market_summary = (
        f"威科夫階段：{wyckoff_phase} | 風險係數：{risk_pct}%\n"
        f"關鍵支撐：{support or '--'} 元 | 關鍵壓力：{resistance or '--'} 元 | P&F目標：{target_pnf or '--'} 元"
    )

    if status == 'holding':
        action_template = """<h3>▶ 整體判斷</h3>
<p>（只選一個）<strong>續抱 / 加碼 / 減碼 / 出場</strong> — 說明理由（不超過40字）</p>

<h3>▶ 加碼機會</h3>
<ul>
  <li>加碼觸發：突破 ___元 + 量超過 ___張（5日均量的___倍）</li>
  <li>加碼最高位：不超過 ___元，避免追高</li>
  <li>加碼後停損：跌回 ___元則全部停損</li>
</ul>

<h3>▶ 停利／減碼計劃</h3>
<ul>
  <li>第一減碼點：___元（獲利約___% 時，減碼___成）</li>
  <li>最終目標：___元（P&F概念目標，預期獲利___% ）</li>
</ul>

<h3>▶ 停損（最重要）</h3>
<span class="stop-loss">⚠ 停損位：___元 — 跌破請執行，不要猶豫（距現價約-___% ）</span>
<p>設在支撐位 ___元 下方約2-3%</p>

<h3>▶ 今日K棒提醒</h3>
<p>（結合最後一根K棒型態+量能，一句話說明當下最值得注意的盤面訊號）</p>"""
    else:
        action_template = """<h3>▶ 現在適合進場嗎？</h3>
<p>（只選一個）<span class="short-term-title"><strong>立刻可入 / 等待確認 / 不建議進場</strong></span> — 理由（不超過40字）</p>

<h3>▶ 短線介入條件（1-5日）</h3>
<ul>
  <li>進場觸發：突破 ___元，且量超過 ___張（5日均量的___倍）</li>
  <li>首批建倉位：___元附近，建議 ___張</li>
  <li>短線目標：___元（約+___% ）</li>
  <li><span class="stop-loss">⚠ 進場後停損：___元（跌破立即出場，損失約-___% ）</span></li>
</ul>

<h3>▶ 中線布局條件</h3>
<ul>
  <li>等待信號：___（K線型態 / 量能條件 / 支撐確認，擇一說明）</li>
  <li>理想建倉區：___元 ~ ___元（支撐帶附近）</li>
  <li>中線目標：___元（P&F概念目標）</li>
</ul>

<h3>▶ 李佛摩「等待」原則</h3>
<p>目前需要等什麼確認才進場？（具體說明條件，達到前不輕易出手）</p>

<h3>▶ 風險提示</h3>
<p>（根據風險係數 {risk_pct}% 說明最主要潛在風險，不超過2句）</p>""".replace('{risk_pct}', str(risk_pct))

    prompt = f"""你是台股操作顧問，提供具體、有數字、可執行的操作策略。
每個建議都必須有具體價格數字，絕不說「視情況而定」。

股票：{name}（{symbol}）現價：{current_price} 元

【市場分析摘要】
{market_summary}

{bars_text}

【投資人持倉狀況】
{position_info}

請用繁體中文 + 純 HTML 格式輸出以下建議（務必填入所有具體數字）：

⚠️ 格式鐵律：
- 禁止使用任何 Markdown 語法：禁止 **粗體**、禁止 ### 標題、禁止 --- 分隔線、禁止 `code`
- 標題用 <h3>，粗體用 <strong>，條列用 <ul><li>，段落用 <p>
- 用 <span class="key-point">...</span> 標記最關鍵的 1-2 句（整體判斷句或停損句），禁止濫用

{action_template}

⚠️ 不構成實際投資建議，投資人需自行評估風險。"""

    return _generate(prompt, max_tokens=1200)


# ── 平行分析所有持股（v2）────────────────────────────────────

def analyze_stocks_parallel_v2(
    stock_records: list,
    news: list,
) -> list:
    """
    stock_records: list of dict，每筆包含
        symbol, name, status, avg_cost, total_zhang
    news: 全域新聞清單（各股自行篩選）

    Returns list of dict:
        symbol, name, status, enriched, analysis(dict from analyze_stock_three_masters)
    """
    from modules.data_enricher import get_full_stock_data

    results = []
    for i, rec in enumerate(stock_records):
        symbol = rec['symbol']
        name   = rec['name']
        print(f"[v2] 分析 {i+1}/{len(stock_records)}: {name}（{symbol}）")

        enriched = get_full_stock_data(symbol)
        if enriched is None:
            print(f"[v2] 無法取得 {symbol} 資料，跳過")
            continue

        stock_news = [n for n in news if name in n.get('title', '') or symbol in n.get('title', '')]

        analysis = analyze_stock_three_masters(
            name         = name,
            symbol       = symbol,
            enriched_data= enriched,
            status       = rec.get('status', 'watching'),
            avg_cost     = rec.get('avg_cost'),
            total_zhang  = rec.get('total_zhang'),
            news_list    = stock_news,
        )

        results.append({
            'symbol':   symbol,
            'name':     name,
            'status':   rec.get('status', 'watching'),
            'enriched': enriched,
            'analysis': analysis,
        })

        if i < len(stock_records) - 1:
            time.sleep(2)

    return results


# ── 台股大盤（每日簡化版）────────────────────────────────────

def analyze_taiwan_market_v2(twii_enriched: dict, global_summary: str) -> str:
    """
    每日大盤：走勢回顧 + K線 + 量能分析 + 全球情勢對台股影響 + 技術面展望
    移除「大盤操作策略」，保持精簡
    """
    price = twii_enriched.get('price', '--')
    ma5   = twii_enriched.get('ma5',  '--')
    ma20  = twii_enriched.get('ma20', '--')
    ma60  = twii_enriched.get('ma60', '--')
    macd  = twii_enriched.get('macd') or {}
    vol   = twii_enriched.get('volume_zhang', '--')
    vol5  = twii_enriched.get('volume_5d_avg_zhang', '--')

    _daily_labels  = label_bars(twii_enriched.get('daily_bars', []))
    _weekly_labels = label_bars(twii_enriched.get('weekly_bars', []))
    daily_text   = _fmt_bars(twii_enriched.get('daily_bars',   []), "加權指數日K", 10, _daily_labels)
    weekly_text  = _fmt_bars(twii_enriched.get('weekly_bars',  []), "加權指數週K",  5, _weekly_labels)

    prompt = f"""你是台股技術分析師。請根據以下數據提供今日台股簡要分析，風格精練、重點明確。

台灣加權指數（^TWII）
現值：{price} 點
均線：MA5={ma5} | MA20={ma20} | MA60={ma60}
MACD：DIF={macd.get('macd','--')} | DEA={macd.get('signal','--')} | 柱狀={macd.get('histogram','--')}
成交量：今日 {vol} 億（張換算） ｜ 5日均量 {vol5} 億

{daily_text}

{weekly_text}

【全球市場摘要】
{global_summary[:600]}

請用繁體中文 HTML 輸出以下三個區塊（每區塊 2-3 點，簡潔）：

### 一、今日走勢回顧
結合近期走勢脈絡解讀今日表現，說明今日漲跌在近10日中的意義。

### 二、K線與量能分析
- 最近5根日K型態描述（名稱 + 含意）
- 今日量能（{vol}張）vs 5日均量（{vol5}張）：放量/縮量/持平，代表什麼
- <span class="support-level">近期支撐：XX 點</span>
- <span class="resistance-level">近期壓力：XX 點</span>

### 三、全球情勢對台股影響 + 技術面展望
- 全球市場環境對台股的主要影響（1-2點）
- 台股技術面近期展望（偏多/中性/偏空，附條件）

【數據鐵律】
- 只依據以上提供的數據（收盤點位 {price} 點、均線、MACD、量能、K棒）描述今日走勢
- 嚴禁引用訓練資料中的歷史特定事件數字（例：「1778點」「突破3萬點」「創史上最高」「史高」等）
- 這些描述屬模型訓練資料幻覺，非今日實際資料；違反者輸出無效
- 若今日確為近期高點，以「現值 {price} 點，創近N日高」描述，禁止引用特定歷史漲跌幅

重要提醒：以上為模擬分析，不構成實際投資建議。"""

    return _clean_html_output(_generate(prompt, max_tokens=1200))


# ── 產業指標股（從新聞擷取）─────────────────────────────────

def get_industry_indicator_stocks(news: list, global_summary: str) -> str:
    """
    分析財經新聞中被正面提及的產業，
    列出各產業的指標性股票（3-5支），不做 AI 分析推薦。
    """
    news_text = '\n'.join([f"- {n['title']}" for n in news[:15]]) or '無新聞資料'

    prompt = f"""你是台股產業分析師。請根據以下財經新聞，找出被正面提及的產業，並列出各產業的指標性股票。

【財經新聞標題】
{news_text}

【全球市場背景】
{global_summary[:400]}

任務：
1. 識別新聞中被正面提及的台股產業（只取正面消息的產業）
2. 每個產業列出 3-5 支台灣指標性股票（依市值/知名度，非推薦）
3. 每支股票僅列出：代號 + 名稱，不做任何操作建議

格式（HTML，繁體中文）：
#### 正面新聞涉及產業與指標股

**[產業名稱]**（新聞依據：一句話說明）
- 2330 台積電
- 2454 聯發科
- ...

**[另一產業]**（新聞依據：...）
- XXXX XXXX
...

⚠️ 這些股票僅為產業代表，不代表推薦買進，請自行評估。

【嚴格輸出規定】
- 直接輸出純 HTML 片段內容，不要包在 ```html ... ``` markdown 代碼塊
- 禁止輸出 <head>、<style>、<script>、<title>、<!DOCTYPE>、<html>、<body> 等 document 結構標籤（網站已自帶樣式）
- 禁止在開頭加 # / ## / ### markdown 標題
- 只輸出實際內容區塊（<div>、<p>、<ul>、<strong>、<span class="..."> 等）"""

    return _clean_html_output(_generate(prompt, max_tokens=800))


# ── 週報：台股（簡化版）─────────────────────────────────────

def analyze_weekly_taiwan_v2(twii_enriched: dict, global_weekly_summary: str, week_range: str) -> str:
    """
    週報版台股分析：走勢回顧 + K線量能 + 全球情勢影響 + 下週技術面展望
    """
    price = twii_enriched.get('price', '--')
    ma5   = twii_enriched.get('ma5',  '--')
    ma20  = twii_enriched.get('ma20', '--')
    ma60  = twii_enriched.get('ma60', '--')
    macd  = twii_enriched.get('macd') or {}
    vol   = twii_enriched.get('volume_zhang', '--')
    vol5  = twii_enriched.get('volume_5d_avg_zhang', '--')

    _weekly_labels  = label_bars(twii_enriched.get('weekly_bars', []))
    _monthly_labels = label_bars(twii_enriched.get('monthly_bars', []))
    weekly_text  = _fmt_bars(twii_enriched.get('weekly_bars',  []), "加權指數週K",  8, _weekly_labels)
    monthly_text = _fmt_bars(twii_enriched.get('monthly_bars', []), "加權指數月K",  4, _monthly_labels)

    prompt = f"""你是台股週報技術分析師。分析週期：{week_range}

台灣加權指數
本週收盤：{price} 點
均線：MA5={ma5} | MA20={ma20} | MA60={ma60}
MACD：DIF={macd.get('macd','--')} | DEA={macd.get('signal','--')} | 柱狀={macd.get('histogram','--')}
本週末量：{vol} 張 ｜ 5日均量 {vol5} 張

{weekly_text}

{monthly_text}

【全球市場本週摘要】
{global_weekly_summary[:600]}

請用繁體中文 HTML 輸出（每區塊 2-3 點）：

### 一、本週走勢回顧
本週表現在近期月K趨勢中的意義（非孤立看單週）。

### 二、週K型態與量能
- 本週K棒型態 + 前2根週K的組合意涵
- 本週量能 vs 5日均量：放量/縮量，代表市場意志
- <span class="support-level">關鍵支撐：XX 點</span>
- <span class="resistance-level">關鍵壓力：XX 點</span>

### 三、全球情勢對下週台股影響

### 四、下週技術面展望
偏多/中性/偏空，附出現條件（若突破XX點且量能...則...）

【數據鐵律】
- 只依據以上提供的數據（本週收盤 {price} 點、均線、MACD、量能、K棒）描述本週走勢
- 嚴禁引用訓練資料中的歷史特定事件數字（例：「1778點」「突破3萬點」「創史上最高」「史高」等）
- 這些描述屬模型訓練資料幻覺，非本週實際資料；違反者輸出無效
- 若本週確為近期高點，以「本週收盤 {price} 點，創近N週高」描述，禁止引用特定歷史漲跌幅

重要提醒：以上為模擬分析，不構成實際投資建議。

【嚴格輸出規定】
- 直接輸出純 HTML 片段內容，不要包在 ```html ... ``` markdown 代碼塊
- 禁止輸出 <head>、<style>、<script>、<title>、<!DOCTYPE>、<html>、<body> 等 document 結構標籤（網站已自帶樣式）
- 禁止在開頭加 # 標題（用 ### 或 <h3> 即可）
- 只輸出實際分析內容（標題與段落，可用 <span class="support-level"> / <span class="resistance-level"> 等網站既有 class）"""

    return _clean_html_output(_generate(prompt, max_tokens=1200))
