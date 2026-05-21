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
from modules.data_enricher import compute_monthly_structure

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


def _dedup_bars_by_date(bars: list) -> list:
    """按 date 去重，保留同 date 最末出現項（防 yfinance / merge 偶發同日重複）。"""
    if not bars:
        return []
    seen_idx: dict = {}
    for i, b in enumerate(bars):
        d = b.get('date')
        if d is not None:
            seen_idx[d] = i
    return [bars[i] for i in sorted(seen_idx.values())]


def _fmt_bars(bars: list, label: str, n: int, pattern_labels: dict = None) -> str:
    if not bars:
        return f"【{label}】：資料不足"
    # 防呆 dedup：避免下游 prompt 看到同日重複行（用戶 2026-05-19 報表 5 支股
    # 日K 表出現「2026-05-19 同日列兩次」+「(補充)」「(最新)」標記）
    bars = _dedup_bars_by_date(bars)
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
        'WYCKOFF_PHASE:', 'DIRECTION:', '---', '```',
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
    # ── 步驟5：砍字串尾端殘破未閉合標籤（Bug1：max_tokens 截斷在 <span ...）──
    html = re.sub(r'<[a-zA-Z][^>]*$', '', html).rstrip()
    return html


def _parse_tagged(raw: str, tag: str, default):
    """從 AI 回應中解析 TAG: value 格式"""
    for line in raw.split('\n'):
        line = line.strip()
        if line.upper().startswith(tag.upper() + ':'):
            val = line.split(':', 1)[1].strip()
            return val
    return default


# 威科夫相位 → 結構方向（E-2/E-3 共用，避免新增 DB 欄位）
_LONG_PHASES  = ('積累', '上漲', '再積累')
_SHORT_PHASES = ('派發', '下跌', '再派發')

def phase_to_direction(phase) -> str:
    """威科夫相位字串 → 'long' | 'short' | 'neutral'。
    AI 的 DIRECTION 判定本質即此相位之函數，故持久化/渲染以相位反推，
    可免在 StockAnalysis 新增欄位（零 migration）。"""
    if not phase:
        return 'neutral'
    p = str(phase)
    if any(k in p for k in _SHORT_PHASES):
        return 'short'
    if any(k in p for k in _LONG_PHASES):
        return 'long'
    return 'neutral'


def _dual_pnf(enriched_data: dict, price_f):
    """同時算多方（突破箱頂向上）與空方（跌破箱底向下）等幅量度目標。
    優先週K（lookback=12），無有效箱則退日K（lookback=20）。
    回傳 (pnf_long, pnf_short, block_text)。"""
    wk = enriched_data.get('weekly_bars', [])
    dk = enriched_data.get('daily_bars', [])
    pnf_long  = (calc_pnf_target(wk, lookback=12, current_price=price_f, direction='long')
                 or calc_pnf_target(dk, lookback=20, current_price=price_f, direction='long'))
    pnf_short = (calc_pnf_target(wk, lookback=12, current_price=price_f, direction='short')
                 or calc_pnf_target(dk, lookback=20, current_price=price_f, direction='short'))
    long_str  = f'{pnf_long:.0f} 元（突破箱頂適用）'  if pnf_long  else '—（尚未接近突破點）'
    short_str = f'{pnf_short:.0f} 元（跌破箱底適用）' if pnf_short else '—（尚未接近跌破點）'
    block = (
        f"【P&F等幅量度目標·多方（程式計算，禁止更改）】{long_str}\n"
        f"【P&F等幅量度目標·空方（程式計算，禁止更改）】{short_str}\n"
        f"依你判定的 DIRECTION 引用對應目標：long→多方目標、short→空方目標、"
        f"neutral→說明目前尚無明確方向目標。"
    )
    return pnf_long, pnf_short, block


def _resolve_swing_anchors(enriched_data: dict, price_f, direction: str) -> dict:
    """依方向取對應 swing_levels，回傳 DB 寫入用的 anchor dict（B 組 2026-05-20）。

    回傳 keys（資料不足時對應值為 None，呼叫端可 fallback 至 AI tag）：
      - support_anchor    : long=range_low（真支撐），short=range_low（下方=空方目標）
      - resistance_anchor : long=range_high（真壓力），short=range_high（回測壓力=空進）
      - target_anchor     : swing.target（long P&F 上行 / short P&F 下行）
      - stop_loss_anchor  : short=range_high × 1.03（前高之上 3% 失效）；long/neutral=None

    語意設計：support/resistance/target 三欄永遠中性（箱底/箱頂/measured target），
    stop_loss 新欄位（B1c 路徑，零語意污染）。pill render 對 short 翻牌
    label：撐→空標、壓→空進、stop_loss→空停。
    """
    from modules.candlestick import calc_swing_levels
    dk = enriched_data.get('daily_bars', [])
    sl = calc_swing_levels(dk, direction, price_f) if direction in ('long', 'short') else None
    out = {
        'support_anchor':    sl.get('range_low')  if sl else None,
        'resistance_anchor': sl.get('range_high') if sl else None,
        'target_anchor':     sl.get('target')     if sl else None,
        'stop_loss_anchor':  None,
    }
    if direction == 'short':
        rh = sl.get('range_high') if sl else None
        if rh:
            # 空停 = 前高 × 1.03（3% buffer above 失效點）
            out['stop_loss_anchor'] = round(float(rh) * 1.03, 1 if rh < 100 else 0)
        elif len(dk) >= 20:
            # Bug4 fallback：swing 算不出但日K 充足 → 用近 20 日最高 × 1.03 補空停
            highs = [float(b['high']) for b in dk[-20:] if b.get('high') is not None]
            if highs:
                rhf = max(highs)
                out['stop_loss_anchor'] = round(rhf * 1.03, 1 if rhf < 100 else 0)
    return out


def _dual_swing_block(enriched_data: dict, price_f) -> str:
    """波段操作錨點注入塊（鏡像 _dual_pnf）：同時算 long/short/neutral
    三組程式鎖定錨點，AI 依其判定的 DIRECTION 取對應組。資料不足→誠實提示。"""
    from modules.candlestick import calc_swing_levels
    dk = enriched_data.get('daily_bars', [])
    sl_long  = calc_swing_levels(dk, 'long',    price_f)
    sl_short = calc_swing_levels(dk, 'short',   price_f)
    sl_neu   = calc_swing_levels(dk, 'neutral', price_f)
    if not (sl_long or sl_short or sl_neu):
        return "【波段操作錨點】本期資料不足，不給波段框架（誠實 > 錯誤）。"

    def _f(v):
        return f'{v:.2f}' if isinstance(v, (int, float)) else '—'

    # E 組 2026-05-20：計算「進場區距現價%」— short 看 entry_high vs cur、
    # long 看 cur vs entry_low；< 3% 視為過近（華星光 5/19 收 523 / 進場區
    # 551 只差 5.4%、臻鼎差 1.6% → 反彈一日就觸發停損的真實案例）。
    def _entry_proximity_warning(direction: str, sl: dict, cur) -> str:
        if not sl or not cur:
            return ''
        try:
            cur_f = float(cur)
            if cur_f <= 0:
                return ''
            if direction == 'short':
                entry_high = sl['entry_zone'][1]
                gap = (float(entry_high) - cur_f) / cur_f * 100
                if 0 < gap < 3:
                    return (f"⚠️ short 進場區上緣 {entry_high:.2f} 距現價僅 "
                            f"{gap:+.2f}%（< 3% 過近），反彈一日即觸發停損機率高，"
                            f"優先標 neutral 觀望或等更明確反彈訊號")
            else:  # long
                entry_low = sl['entry_zone'][0]
                gap = (cur_f - float(entry_low)) / cur_f * 100
                if 0 < gap < 3:
                    return (f"⚠️ long 進場區下緣 {entry_low:.2f} 距現價僅 "
                            f"{gap:+.2f}%（< 3% 過近），跌破一日即觸發停損機率高，"
                            f"優先標 neutral 觀望或等更明確支撐確認")
        except (KeyError, TypeError, ValueError, IndexError):
            pass
        return ''

    lines = ["【波段操作錨點（程式計算，禁止更改）｜依你判定的 DIRECTION 取對應組】"]
    if sl_long:
        ez = sl_long['entry_zone']
        lines.append(
            f"· long：失效/停損 {_f(sl_long['invalidation'])} ｜ 加碼觸發 "
            f"{_f(sl_long['add_trigger'])} ｜ 進場區 {_f(ez[0])}~{_f(ez[1])} ｜ "
            f"波段目標 {_f(sl_long['target'])}")
        w = _entry_proximity_warning('long', sl_long, price_f)
        if w:
            lines.append(w)
    if sl_short:
        ez = sl_short['entry_zone']
        lines.append(
            f"· short：失效/回補 {_f(sl_short['invalidation'])} ｜ 加空觸發 "
            f"{_f(sl_short['add_trigger'])} ｜ 放空區 {_f(ez[0])}~{_f(ez[1])} ｜ "
            f"下行目標 {_f(sl_short['target'])}")
        w = _entry_proximity_warning('short', sl_short, price_f)
        if w:
            lines.append(w)
    if sl_neu:
        lines.append(
            f"· neutral：區間 {_f(sl_neu['range_low'])}~{_f(sl_neu['range_high'])}"
            f"（突破上緣+量轉多 / 跌破下緣+量轉空，區間內不操作）")
    return "\n".join(lines)


def _twii_close_on_or_before(twii: dict, date_str: str):
    """twii: {YYYY-MM-DD: close} 舊→新。回傳該日或最近較早交易日收盤，無則 None。"""
    if not twii:
        return None
    if date_str in twii:
        return twii[date_str]
    best = None
    for d, c in twii.items():       # 插入序由舊到新
        if d <= date_str:
            best = c
        else:
            break
    return best


def _market_rs_block(daily_bars: list) -> str:
    """Bug D：個股 vs 大盤(TWII)同期相對強度，注入 dynamic_block 為鎖定值。
    TWII 取得失敗 / 個股 bar 不足 → 回 ''（不注入，誠實 > 錯誤）。"""
    if not daily_bars or len(daily_bars) < 6:
        return ''
    try:
        from modules.data_fetcher import get_index_daily_closes
        twii = get_index_daily_closes('^TWII', lookback=40)
    except Exception:
        twii = {}
    if not twii:
        return ''
    lines = []
    for w in (5, 20):
        if len(daily_bars) <= w:
            continue
        cur, past = daily_bars[-1], daily_bars[-1 - w]
        try:
            sc, sp = float(cur['close']), float(past['close'])
            if sp <= 0:
                continue
            stock_chg = (sc / sp - 1) * 100
            tc = _twii_close_on_or_before(twii, str(cur.get('date', '')))
            tp = _twii_close_on_or_before(twii, str(past.get('date', '')))
            if tc is None or tp is None or tp <= 0:
                continue
            twii_chg = (tc / tp - 1) * 100
            rs = stock_chg - twii_chg
            if rs > 0.3:
                tag = '跑贏大盤' if stock_chg >= 0 else '抗跌'
            elif rs < -0.3:
                tag = '落後大盤'
            else:
                tag = '與大盤同步'
            lines.append(
                f"個股{w}日 {stock_chg:+.1f}% vs TWII{w}日 {twii_chg:+.1f}%"
                f" → 相對強度 {rs:+.1f}pp（{tag}）"
            )
        except (TypeError, ValueError, KeyError):
            continue
    if not lines:
        return ''
    body = '\n'.join(lines)
    return (
        f"【大盤對比（程式計算，禁止更改）】\n{body}\n"
        f"⚠️【大盤對比鐵律】判斷個股強弱前先扣除大盤同期漲跌幅；個股與大盤"
        f"同向且幅度相近時，不得歸因為個股獨立訊號（beta 連動非 alpha）。"
        f"相對強度欄為程式精確計算，禁止自行推估。"
    )


def _oversold_warning_block(daily_bars: list) -> str:
    """A 組 2026-05-20：短期超賣警示（程式計算，注入 dynamic_block）。

    用戶 5/19→5/20 觀察：大盤前日跌 -1.75% 後 8 支股大反彈，AI 報表卻仍給
    short 進場區、進場區距現價過近被均值回歸觸發停損。

    觸發條件（任一）：
    - 大盤(TWII) 前一交易日跌 ≥ 1.5%
    - 個股 5 日累跌 ≥ 5%

    資料不足 / TWII 抓不到 → 回 ''（誠實 > 錯誤）。
    """
    if not daily_bars or len(daily_bars) < 6:
        return ''

    triggers = []
    # 1) 個股 5 日累跌
    try:
        cur = float(daily_bars[-1]['close'])
        ref = float(daily_bars[-6]['close'])
        if ref > 0:
            stk_5d = (cur / ref - 1) * 100
            if stk_5d <= -5:
                triggers.append(f"個股 5 日累跌 {stk_5d:+.1f}%（≥5% 超賣）")
    except (KeyError, TypeError, ValueError, IndexError):
        pass

    # 2) 大盤 TWII 前一交易日漲跌幅
    try:
        from modules.data_fetcher import get_index_daily_closes
        twii = get_index_daily_closes('^TWII', lookback=10)
    except Exception:
        twii = {}
    if twii:
        try:
            items = sorted(twii.items())  # [(date, close), ...] 由舊到新
            if len(items) >= 2:
                prev_close, last_close = items[-2][1], items[-1][1]
                if prev_close > 0:
                    twii_1d = (last_close / prev_close - 1) * 100
                    if twii_1d <= -1.5:
                        triggers.append(
                            f"大盤(TWII) 前日 {twii_1d:+.2f}%（≥-1.5% 急跌）"
                        )
        except (KeyError, TypeError, ValueError, IndexError):
            pass

    if not triggers:
        return ''

    return (
        f"【短期超賣警示（程式計算，禁止忽略）】\n"
        f"觸發條件：{' / '.join(triggers)}\n"
        f"⚠️【超賣警示鐵律】當前處於短期超賣期，**均值回歸反彈機率偏高**：\n"
        f"- short 場景：禁止把『等回測壓力放空』寫成『現在可放空』；放空進場\n"
        f"  必須**等回測壓力**後**確認反彈失敗**（如壓力線縮量觸及+轉黑K確認）才動手\n"
        f"- 「結構空方」屬波段定位（2 週-1 個月），**不代表明日續跌**；可能 1-3\n"
        f"  週內出現反彈，反彈期間放空應**更耐心**等回測壓力區\n"
        f"- 若進場區距現價過近（< 3%），優先標 neutral 觀望，禁急著給空方框架"
    )


def _structure_block(enriched_data: dict, price_f) -> str:
    """【月線結構客觀事實】prompt 區塊（結構閘）。

    spec: docs/superpowers/specs/2026-05-21-wyckoff-phase-gate-design.md
    資料不足回 '' （誠實 > 錯誤）。
    """
    ms = compute_monthly_structure(
        enriched_data.get('monthly_bars', []),
        enriched_data.get('weekly_bars', []),
        price_f,
        enriched_data.get('ma60'),
    )
    flag = ms['structure_flag']
    if flag == '資料不足':
        return ''
    gate_hint = {
        '結構未轉弱': '→ 禁止標派發/再派發/下跌，相位只能在 積累/上漲/再積累/不明',
        '結構轉折中': '→ 可標派發，但須在分析附具體量價證據',
        '結構已轉弱': '→ 允許標空方相位（仍須量價證據佐證）',
    }.get(flag, '')
    dd = ms['drawdown_from_peak']
    dd_txt = f'{dd:+.1f}%' if dd is not None else '—'
    hold = '是' if ms['weekly_hold_support'] else '否'
    return (
        "【月線結構客觀事實】（程式計算，禁止 AI 推翻）\n"
        f"- 月K結構（近3根已收盤）：{ms['monthly_structure']}\n"
        f"- 連續月陰線：{ms['consecutive_bear_months']}\n"
        f"- 距峰值回落：{dd_txt}\n"
        f"- 現價 vs 季線MA60：{ms['price_vs_ma60']}\n"
        f"- 結構旗標：{flag} {gate_hint}\n"
        f"- 週K近期動能（唯讀，供時機判斷）：{ms['weekly_momentum']}"
        f" ｜ 守穩支撐：{hold}"
    )


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

    _monthly_labels = label_bars(enriched_data.get('monthly_bars', []), timeframe='monthly')
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
    _pnf_long, _pnf_short, pnf_block = _dual_pnf(enriched_data, _price_f)
    _rs_block = _market_rs_block(enriched_data.get('daily_bars', []))
    _rs_section = f"\n\n{_rs_block}" if _rs_block else ""
    _oversold_block = _oversold_warning_block(enriched_data.get('daily_bars', []))
    _oversold_section = f"\n\n{_oversold_block}" if _oversold_block else ""
    _swing_block = _dual_swing_block(enriched_data, _price_f)
    _structure_block_text = _structure_block(enriched_data, _price_f)

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
        action_section = f"""### 五、波段操作框架（2週-1個月+，依 DIRECTION）
⚠️ 所有價位必須引用上方【波段操作錨點】鎖定值，禁止自行估算或改數字。
- 波段論點：一句話說明本波段做多/做空/觀望的核心理由（≤30字）
- long：續抱/加碼/減碼擇一；short：減碼/出場/反手放空擇一（依方向）
- <span class="stop-loss">▶ 失效/停損價：[錨點 invalidation] 元 — 跌破(long)/站回(short)即論點作廢，執行不猶豫</span>
- ▶ 加碼觸發：突破[錨點 add_trigger](long) / 跌破[錨點 add_trigger](short) 且量 > {_vol_breakout} 張（程式計算，禁止更改）
- ▶ 波段目標：[錨點 target] 元（等幅量度，可能為 — 表示尚無）
- neutral：明講無波段方向，[range_low]~[range_high] 區間內不操作，僅標突破/跌破轉向條件"""
    else:
        action_section = f"""### 五、波段操作框架（2週-1個月+，依 DIRECTION）
⚠️ 所有價位必須引用上方【波段操作錨點】鎖定值，禁止自行估算或改數字。
- 波段論點：一句話說明本波段做多/做空/觀望的核心理由（≤30字）
- ▶ 進場區：[錨點 entry_zone] 元；觸發須量 > {_vol_breakout} 張（程式計算，禁止更改）
- <span class="stop-loss">▶ 失效/停損價：[錨點 invalidation] 元 — 跌破(long)/站回(short)即論點作廢</span>
- ▶ 加碼觸發：[錨點 add_trigger] 元　▶ 波段目標：[錨點 target] 元
- long/short：說明目前是否到進場區及理由（波段角度，非當日）
- neutral：明講無波段方向，[range_low]~[range_high] 區間內不操作，僅標突破[range_high]+量轉多 / 跌破[range_low]+量轉空"""

    static_block = f"""你是融合三大宗師智慧的台股分析師。分析日期：{today}

⚠️ 重要：請在回應的**第一行**先輸出以下結構化標記（純數字），再輸出分析內容：
RISK_PCT: [0到100整數]
SUPPORT: [支撐價]
RESISTANCE: [壓力價]
WYCKOFF_PHASE: [積累|上漲|派發|下跌|再積累|再派發|不明]
DIRECTION: [long|short|neutral]
---

## ⚠️ 結構方向判定（最優先，決定全篇多空視角）
先由威科夫月K相位判定本次分析方向，DIRECTION 標記須與此一致：
- 積累 / 上漲 / 再積累 → DIRECTION=long（多方：突破箱頂進場、向上等幅目標）
- 派發 / 下跌 / 再派發 → DIRECTION=short（空方：跌破箱底放空、回測壓力線、向下等幅目標）
- 不明 / 多空交戰 / **派發+短期超賣+進場區距現價過近 / 結構空方但短期反彈風險高** → DIRECTION=neutral（觀望）

⚠️ **方向對稱鐵律（雙向，禁止任一方向預設）**：
- **禁止預設多頭**（積累期未確立前不寫 long）
- **禁止預設空頭**（派發期遇短期超賣 / 進場區距現價 <3% / 1-3 週內反彈風險高，**允許並建議標 neutral**，不必強行給空方框架）
- 派發/下跌相位**可寫「結構為空方但短期反彈風險高，本期觀望」**而非機械強行 short — 結構方向 ≠ 隔日方向
- 若上方資料區出現【短期超賣警示】或【進場區距現價過近】，**優先標 neutral**

⚠️ **結構閘（硬護欄，最優先，凌駕一切短線訊號）**：下方股票資料含【月線結構客觀事實】，其「結構旗標」由程式計算，**禁止 AI 推翻**：
- 結構旗標=`結構未轉弱` → **禁止**標派發/再派發/下跌，WYCKOFF_PHASE 只能在 積累/上漲/再積累/不明 之中選
- 結構旗標=`結構轉折中` → 可標派發，但須在「一、威科夫骨幹分析」列出具體派發訊號（高位量增不漲／高位放量收長黑或長上影／跌破前波明顯低點伴隨放量），**不得僅憑單月收陰+量縮**判派發
- 結構旗標=`結構已轉弱` → 允許標空方相位，仍須量價證據佐證
⚠️ **正向型態**：若【月線結構客觀事實】「守穩支撐=是」且回測時量縮、反彈時量增 → 屬吸籌/再積累的次級測試(SOT)，偏多，禁標派發。

⚠️ **「結構方向」≠「隔日方向」（用戶誤讀風險最高處）**：
- 「DIRECTION=short」= **波段（2 週-1 個月）結構偏空**，**不代表明日續跌**
- 派發相位股可能 1-3 週內出現反彈（均值回歸），反彈期間放空進場應**更耐心**等回測壓力區
- 報表結論禁出現「明日宜放空」「隔日繼續看跌」這類短線預測 — 只能說「波段結構為空方，等回測壓力 X 元確認反彈失敗才進場」

## 三大宗師主從架構（雙向，依 DIRECTION 套用）
1. 【威科夫】（骨幹）：月K定相位 → 多方看積累→上漲、空方看派發→下跌 → 日K量價驗證 → 5日均確認動能
2. 【本間宗久】（確認）：多方底部反轉（晨星/鎚子）；空方頂部反轉（黃昏之星/吊人/空頭吞噬）
3. 【李佛摩】（時機）：多方=突破前高+5日均上彎；空方=跌破前低+5日均下彎為 pivot
4. 【箱型理論｜Darvas Box】（區間）：辨識整理箱體（上緣=箱頂、下緣=箱底）。多方=突破箱頂為進場訊號；空方=跌破箱底為進場訊號；假突破須由量能否決（無量突破不算數）。⚠️ 跌破箱底為「空方進場訊號」，禁寫成「轉弱/觀望」（方向已由威科夫相位裁決）。

⚠️ 上位優先：威科夫月K相位為最高骨幹，若本間/李佛摩短線訊號與月線方向衝突，以月線為準，逆勢操作屬高風險，需特別說明。

## ⚠️ 兩層決策分工（方向 vs 時機，勿混淆）
- 第一層【方向】：由威科夫月K相位裁決（見上方結構方向判定），決定本篇做多/做空/觀望 — 此層最高，不可被任何短線訊號推翻。
- 第二層【時機】：方向既定後，進場時機的衝突仲裁順序為 趨勢(李佛摩) > 結構(箱型) > 訊號(K線) > 確認(量價)。此階梯只決定「何時動手」，不決定「做哪邊」。
白話：威科夫定往哪打，李佛摩階梯定何時扣扳機。

## ⚠️ 交易原則（融入操作判斷）
不預測只依訊號行動；沒突破不追價；沒設停損不進場；風險優先於報酬。

## ⚠️ 量價術語表（方向 qualify，禁混用）
- 「多方努力」= 上漲日的買盤量能 ↑
- 「空方努力」= 下跌日的賣壓量能 ↓
- 「努力大結果差」必須先 qualify 主體：
    · long 場景：多方努力大（上漲日放量）但結果差（收紅低） = 上攻乏力
    · short 場景：空方努力大（下跌日放量）= 賣方主動殺出（非「努力差」）
- 禁字面：「放量失敗」（修飾對象不明）。標準句型改用：
    · 「縮量回測 → 反彈乏力 → 放空確認」
    · 「即使放量仍守不住壓力 → 反彈失敗」
    · 「跌破伴隨放量 → 賣壓確認，空方有效」

## ⚠️ 波段論點穩定性（最高紀律，凌駕單日盤面）
本框架為 2 週-1 個月以上波段定位，不做當沖。失效價未被觸及前，方向與
進出場價維持不變；每日重跑只更新「現價距失效價還有多遠」，禁止因單日
紅綠或漲跌改變方向或重設價位。禁止輸出「今日宜/不宜進場」這類當日結論。

## 風險係數評分原則（0=低風險/順勢 100=高風險/逆勢）
⚠️ 風險 = 建議動作對抗主結構的程度，與多空無關：順勢操作（上漲做多 / 下跌放空）低分，逆勢操作（下跌搶反彈做多 / 上漲放空）高分。
- 建議方向與月K相位一致（順勢，含下跌相位放空）→ -20
- 明確趨勢中逆勢操作（如下跌相位卻建議做多搶反彈）→ +25
- MACD 柱狀線方向與近期價格趨勢背離 → +15
- 多方且價格低於 MA60 → +20；空方且價格仍高於 MA60（放空但位階偏高）→ +20
- 本間出現與建議方向相反的反轉型態（多方遇頂部/空方遇底部）→ +15
- 本間出現與建議方向一致的反轉型態 → -15
- 威科夫量價背離（努力大於結果）反對建議方向 → +10，支持 → -10
- 李佛摩5日均線斜率與建議方向相反 → +15
- 已持有且目前虧損超過 10% → +10（心理壓力加權）
- 三宗師方向與建議完全一致 → -20

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

### 三、李佛摩時機判斷（依 DIRECTION）
- 月線位階：距關鍵支撐/壓力距離，是否為「自然反彈/自然回落/突破/跌破」
- 5日均線動能：上揚/持平/下彎，是否加速或衰竭
- 當前是否為時機？short 時「時機」指賣空進場或回測壓力線放空，非做多

### 四、三宗師融合結論
- 本次方向：明確複述 DIRECTION（long 做多 / short 放空 / neutral 觀望）+ 依據
- 三框架方向是否一致？有衝突時說明主從優先級與衝突程度

⚠️ P&F概念目標已由程式以等幅量度法計算，依 DIRECTION 取股票資料區對應欄位（long→多方目標、short→空方目標、neutral→無方向目標），**禁止更改此數字**，格式：<span class="target-price">P&F概念目標：[數值]元（等幅量度）</span>"""

    dynamic_block = f"""## 股票資料

股票：{name}（{symbol}）
現價：{price} 元
{position_block}

均線：MA5={ma5} | MA20={ma20} | MA60={ma60}
MACD：DIF={macd.get('macd','--')} | DEA={macd.get('signal','--')} | 柱狀={macd.get('histogram','--')}
成交量：今日 {vol_today} 張 ｜ 5日均量 {vol_5avg} 張
【量能門檻（程式計算，禁止更改，依 DIRECTION 引用）】
- long：突破量 ≥ {_vol_breakout} 張（=5日均×1.5）｜ 彈簧(Spring)/測試量 ≥ {_vol_spring} 張（=5日均×1.2）
- short：跌破量/賣壓確認量 ≥ {_vol_breakout} 張（=5日均×1.5）｜ Upthrust(空方彈簧/假突破)反向量 ≥ {_vol_spring} 張
- ⚠️ 鐵律：long 用「突破量」、short 用「跌破量/賣壓確認量」術語，禁混用（修「放量跌破=突破門檻」語意倒置）
- ⚠️ 名詞鐵律：威科夫 Spring = 「彈簧」（測試箱底支撐後反彈），非「春天」/季節；Upthrust = 「假突破」（測試箱頂壓力後反轉）。報表禁出現「春天」一詞。

{pnf_block}{_rs_section}{_oversold_section}

{_swing_block}

{_structure_block_text}

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
        'target_pnf':    _pnf_long,   # 預設多方；下方依 DIRECTION 改寫
        'direction':     'neutral',
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
        dr = (_parse_tagged(raw, 'DIRECTION', '') or '').strip().lower()
        if dr not in ('long', 'short', 'neutral'):
            dr = phase_to_direction(result['wyckoff_phase'])
        result['direction'] = dr
        result['target_pnf'] = _pnf_short if dr == 'short' else _pnf_long
    except Exception as e:
        print(f"[ai_analyzer_v2] 解析結構化輸出失敗: {e}")

    # B 組 2026-05-20：依方向注入 swing anchor（覆寫 DB 寫入語意，AI tag 當 fallback）
    result.update(_resolve_swing_anchors(enriched_data, _price_f, result['direction']))

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

    _monthly_labels = label_bars(enriched_data.get('monthly_bars', []), timeframe='monthly')
    _weekly_labels  = label_bars(enriched_data.get('weekly_bars', []))
    _daily_labels   = label_bars(enriched_data.get('daily_bars', []))
    monthly_text = _fmt_bars(enriched_data.get('monthly_bars', []), "月K", 6, _monthly_labels)
    weekly_text  = _fmt_bars(enriched_data.get('weekly_bars',  []), "週K", 8, _weekly_labels)
    daily_text   = _fmt_bars(enriched_data.get('daily_bars',   []), "日K", 30, _daily_labels)

    try:
        _price_f = float(price) if price != '--' else None
    except (TypeError, ValueError):
        _price_f = None
    _pnf_long, _pnf_short, pnf_block = _dual_pnf(enriched_data, _price_f)
    _rs_block = _market_rs_block(enriched_data.get('daily_bars', []))
    _rs_section = f"\n\n{_rs_block}" if _rs_block else ""
    _oversold_block = _oversold_warning_block(enriched_data.get('daily_bars', []))
    _oversold_section = f"\n\n{_oversold_block}" if _oversold_block else ""
    _swing_block = _dual_swing_block(enriched_data, _price_f)
    _structure_block_text = _structure_block(enriched_data, _price_f)

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
DIRECTION: [long|short|neutral]
---

## ⚠️ 結構方向判定（最優先，決定全篇多空視角）
先由威科夫月K相位判定本次分析方向，DIRECTION 標記須與此一致，後續所有招式依此方向給建議，**禁止預設多頭**：
- 積累 / 上漲 / 再積累 → DIRECTION=long（多方視角：突破箱頂進場、向上等幅目標）
- 派發 / 下跌 / 再派發 → DIRECTION=short（空方視角：跌破箱底放空、回測壓力線、向下等幅目標）
- 不明 / 多空交戰 → DIRECTION=neutral（觀望，不強行給方向）
⚠️ 派發/下跌相位若已確立，須給出空方操作框架（賣空進場價、回補停損、下行目標）；但相位判定須先過下方結構閘。

⚠️ **結構閘（硬護欄，最優先，凌駕一切短線訊號）**：下方股票資料含【月線結構客觀事實】，其「結構旗標」由程式計算，**禁止 AI 推翻**：
- 結構旗標=`結構未轉弱` → **禁止**標派發/再派發/下跌，WYCKOFF_PHASE 只能在 積累/上漲/再積累/不明 之中選
- 結構旗標=`結構轉折中` → 可標派發，但須在「一、威科夫骨幹分析」列出具體派發訊號（高位量增不漲／高位放量收長黑或長上影／跌破前波明顯低點伴隨放量），**不得僅憑單月收陰+量縮**判派發
- 結構旗標=`結構已轉弱` → 允許標空方相位，仍須量價證據佐證
⚠️ **正向型態**：若【月線結構客觀事實】「守穩支撐=是」且回測時量縮、反彈時量增 → 屬吸籌/再積累的次級測試(SOT)，偏多，禁標派發。

## 三大宗師主從架構（雙向，依 DIRECTION 套用）
1. 【威科夫】（骨幹）：月K定相位 → 多方看積累→上漲、空方看派發→下跌 → 日K量價驗證 → 5日均確認動能
2. 【本間宗久】（確認）：多方底部反轉（晨星/鎚子）；空方頂部反轉（黃昏之星/吊人/空頭吞噬）
3. 【李佛摩】（時機）：多方=突破前高+5日均上彎；空方=跌破前低+5日均下彎為 pivot
4. 【箱型理論｜Darvas Box】（區間）：辨識整理箱體（上緣=箱頂、下緣=箱底）。多方=突破箱頂為進場訊號；空方=跌破箱底為進場訊號；假突破須由量能否決（無量突破不算數）。⚠️ 跌破箱底為「空方進場訊號」，禁寫成「轉弱/觀望」（方向已由威科夫相位裁決）。

⚠️ 上位優先：威科夫月K相位為最高骨幹，若本間/李佛摩短線訊號與月線方向衝突，以月線為準。

## ⚠️ 兩層決策分工（方向 vs 時機，勿混淆）
- 第一層【方向】：由威科夫月K相位裁決（見上方結構方向判定），決定本篇做多/做空/觀望 — 此層最高，不可被任何短線訊號推翻。
- 第二層【時機】：方向既定後，進場時機的衝突仲裁順序為 趨勢(李佛摩) > 結構(箱型) > 訊號(K線) > 確認(量價)。此階梯只決定「何時動手」，不決定「做哪邊」。
白話：威科夫定往哪打，李佛摩階梯定何時扣扳機。

## ⚠️ 交易原則（融入操作判斷）
不預測只依訊號行動；沒突破不追價；沒設停損不進場；風險優先於報酬。

## ⚠️ 量價術語表（方向 qualify，禁混用）
- 「多方努力」= 上漲日的買盤量能 ↑
- 「空方努力」= 下跌日的賣壓量能 ↓
- 「努力大結果差」必須先 qualify 主體：
    · long 場景：多方努力大（上漲日放量）但結果差（收紅低） = 上攻乏力
    · short 場景：空方努力大（下跌日放量）= 賣方主動殺出（非「努力差」）
- 禁字面：「放量失敗」（修飾對象不明）。標準句型改用：
    · 「縮量回測 → 反彈乏力 → 放空確認」
    · 「即使放量仍守不住壓力 → 反彈失敗」
    · 「跌破伴隨放量 → 賣壓確認，空方有效」

## ⚠️ 波段論點穩定性（最高紀律，凌駕單日盤面）
本分析為 2 週-1 個月以上波段定位，不做當沖。失效價未被觸及前，方向與
關鍵價位維持不變；每日重跑只更新「現價距失效價還有多遠」，禁止因單日
紅綠或漲跌改變方向或重設價位。禁止輸出「今日宜/不宜」這類當日結論。

## 風險係數評分原則（0=低風險/順勢 100=高風險/逆勢）
⚠️ 風險 = 建議動作對抗主結構的程度，與多空無關：順勢操作（上漲做多 / 下跌放空）低分，逆勢操作（下跌搶反彈做多 / 上漲放空）高分。
- 建議方向與月K相位一致（順勢，含下跌相位放空）→ -20
- 明確趨勢中逆勢操作（如下跌相位卻建議做多搶反彈）→ +25
- MACD 柱狀線方向與近期價格趨勢背離 → +15
- 多方且價格低於 MA60 → +20；空方且價格仍高於 MA60（放空但位階偏高）→ +20
- 本間出現與建議方向相反的反轉型態（多方遇頂部/空方遇底部）→ +15
- 本間出現與建議方向一致的反轉型態 → -15
- 威科夫量價背離（努力大於結果）反對建議方向 → +10，支持 → -10
- 李佛摩5日均線斜率與建議方向相反 → +15
- 三宗師方向與建議完全一致 → -20

## ⚠️ 輸出格式鐵律（違者輸出無效）
1. **嚴禁散文段落**：所有分析點以「- 」bullet 輸出，不得有連續句子段落
2. **每條 bullet ≤ 20 中文字**（數字與標點不計），超過必須拆分或刪減
3. **禁用詞**：「然而」「因此」「綜合以上」「由此可見」「值得注意的是」
4. **每個 ### 小節**：3～5 條 bullet + 結尾 1 條 `<span class="key-point">小節核心結論（≤15字）</span>`
5. **全文 key-point 上限：4 個**（四個小節各 1 個），禁止在 bullet 內部嵌套使用
6. **第二節 K 線必須輸出 HTML table**（月K 6根 + 週K 3根 + 日K 5根各一張表），格式見下方範例
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
⚠️ 【行數鐵律】每張 table 每行=一個獨立交易日，禁止輸出「(補充)/(最新)/(昨前)」等補充行或同日重複行。週K 取最近 3 個獨立交易週、日K 取最近 5 個獨立交易日；若上方 K棒資料實際少於該數量，照實少輸出（例：實際只有 3 日資料則表頭改寫「日K最近 3 根 table」+ 輸出 3 行，禁止用補充行湊滿 5 行）。
K棒型態含意速查（僅供解讀參考，必須結合特徵欄的量能·位置）：
錘子（下影≥實體2倍/低位看漲·高位需謹慎）、吊人（錘子型/高位看跌訊號）、射擊之星（上影≥實體2倍/高位看跌）、
早晨之星（長黑+小K+長紅/底部反轉）、黃昏之星（長紅+小K+長黑/頂部反轉）、
多頭吞噬（陽線吞陰線）、空頭吞噬（陰線吞陽線）、十字星（開收相等/高位→頂部訊號·低位→底部訊號·中段→觀望）

【月K最近6根 table】（輸出如範例格式，半年波段視野）
【週K最近3根 table】（輸出如範例格式）
【日K最近5根 table】（輸出如範例格式）
- K線序列：依「特徵」欄的量能·位置變化，說明多空動能是否增強或衰退（禁止靠單根顏色判斷方向）
- 週K ↔ 日K 方向：一致多頭 / 一致空頭 / 訊號分歧（分歧時說明以哪個為準）
<span class="key-point">K線核心結論（≤15字）</span>

### 三、李佛摩時機判斷（依 DIRECTION）
- 月線位階：距支撐/壓力 XX%，屬於自然反彈/自然回落/突破/跌破走勢
- 5日均動能：上揚/持平/下彎，說明斜率變化
- Pivot Point：多方看突破前高、空方看跌破前低，近期有無關鍵轉折？
- 波段確認條件：需等什麼結構訊號才確立波段（量能引用【突破最低量能門檻】+【波段操作錨點】價位/K棒）
- 波段定位：依【波段操作錨點】說明距失效價多遠、是否在進場區；short 指放空/回測壓力。禁輸出「今日宜/不宜」當日結論
<span class="key-point">李佛摩核心結論（≤15字）</span>

### 四、三宗師融合結論
- 本次方向：明確複述 DIRECTION（long 做多 / short 放空 / neutral 觀望）+ 一句依據
- 三框架方向：一致順勢 / 分歧（分歧時說明主從優先與衝突程度）
- 衝突點：[若有，說明哪兩個框架衝突及原因]
- ⚠️ P&F概念目標已由程式以等幅量度法計算，依 DIRECTION 取股票資料區對應欄位（long→多方目標、short→空方目標、neutral→說明無方向目標），**禁止更改此數字**，格式：<span class="target-price">P&F概念目標：[數值]元（等幅量度）</span>
<span class="key-point">融合核心結論（≤15字）</span>

### 五、操作框架（⚠️ 強制 schema，價位必須引用上方【波段操作錨點】鎖定值）
依 DIRECTION 必須輸出 3 個結構化 bullet（long/short/neutral 三組擇一輸出）：

⚠️ 鐵律：long 用「進場/停損/目標」、short 用「空進/空停/空標」、neutral 用「翻多條件/翻空條件/區間」術語，禁混用或省略 bullet。

【long 模板】（依【波段操作錨點】鎖定值）
<ul>
  <li>▶ 進場價：[entry_zone 區間] 元（觸發須量 ≥ 突破量門檻）</li>
  <li><span class="stop-loss">▶ 停損：[invalidation] 元 — 跌破即論點作廢</span></li>
  <li>▶ 目標：<span class="target-price">[target] 元（P&F 等幅量度）</span></li>
</ul>

【short 模板】（依【波段操作錨點】鎖定值）
<ul>
  <li>▶ 空進：[range_high 附近] 元（回測壓力，量 ≥ 跌破量門檻 = 賣壓確認）</li>
  <li><span class="stop-loss">▶ 空停：[range_high × 1.03 ≈ 前高之上] 元 — 站回即論點作廢</span></li>
  <li>▶ 空標：<span class="target-price">[target] 元（P&F 等幅量度下行）</span></li>
</ul>

【neutral 模板】
<ul>
  <li>▶ 翻多條件：突破 [range_high] 元 + 量 ≥ 突破量門檻</li>
  <li>▶ 翻空條件：跌破 [range_low] 元 + 量 ≥ 跌破量門檻</li>
  <li>▶ 區間：[range_low]~[range_high] 元（區間內不操作）</li>
</ul>

重要提醒：以上為模擬分析，不構成實際投資建議。"""

    dynamic_block = f"""## 股票資料

股票：{name}（{symbol}）
現價：{price} 元
均線：MA5={ma5} | MA20={ma20} | MA60={ma60}
MACD：DIF={macd.get('macd','--')} | DEA={macd.get('signal','--')} | 柱狀={macd.get('histogram','--')}
成交量：今日 {vol_today} 張 ｜ 5日均量 {vol_5avg} 張
【量能門檻（程式計算，禁止更改，依 DIRECTION 引用）】
- long：突破量 ≥ {_vol_breakout} 張（=5日均×1.5）｜ 彈簧(Spring)/測試量 ≥ {_vol_spring} 張（=5日均×1.2）
- short：跌破量/賣壓確認量 ≥ {_vol_breakout} 張（=5日均×1.5）｜ Upthrust(空方彈簧/假突破)反向量 ≥ {_vol_spring} 張
- ⚠️ 鐵律：long 用「突破量」、short 用「跌破量/賣壓確認量」術語，禁混用（修「放量跌破=突破門檻」語意倒置）
- ⚠️ 名詞鐵律：威科夫 Spring = 「彈簧」（測試箱底支撐後反彈），非「春天」/季節；Upthrust = 「假突破」（測試箱頂壓力後反轉）。報表禁出現「春天」一詞。

{pnf_block}{_rs_section}{_oversold_section}

{_swing_block}

{_structure_block_text}

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
        max_tokens=3000,
    )

    result = {
        'html':              _clean_html_output(raw),
        'risk_pct':          50,
        'support':           None,
        'resistance':        None,
        'target_pnf':        _pnf_long,   # 預設多方；下方依 DIRECTION 改寫
        'direction':         'neutral',
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
        # DIRECTION：以 AI 標記優先，缺漏/異常則由威科夫相位反推（零 migration）
        dr = (_parse_tagged(raw, 'DIRECTION', '') or '').strip().lower()
        if dr not in ('long', 'short', 'neutral'):
            dr = phase_to_direction(result['wyckoff_phase'])
        result['direction'] = dr
        # 目標價依方向取對應等幅量度值（short→空方下行目標）
        result['target_pnf'] = _pnf_short if dr == 'short' else _pnf_long
    except Exception as e:
        print(f"[ai_analyzer_v2] 解析結構化輸出失敗: {e}")

    # B 組 2026-05-20：依方向注入 swing anchor（覆寫 DB 寫入語意，AI tag 當 fallback）
    result.update(_resolve_swing_anchors(enriched_data, _price_f, result['direction']))

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

    _direction = phase_to_direction(wyckoff_phase)

    from modules.candlestick import calc_swing_levels
    try:
        _cp = float(current_price)
    except (TypeError, ValueError):
        _cp = None
    _sl = calc_swing_levels(recent_bars or [], _direction, _cp)
    if _sl and _direction in ('long', 'short'):
        _ez = _sl['entry_zone']
        _tg = f"{_sl['target']:.2f}" if isinstance(_sl['target'], (int, float)) else '—'
        _swing_line = (
            f"\n【波段錨點（程式計算，禁止更改，價位須引用）】"
            f"失效/停損 {_sl['invalidation']:.2f} ｜ 加碼觸發 {_sl['add_trigger']:.2f} ｜ "
            f"進場區 {_ez[0]:.2f}~{_ez[1]:.2f} ｜ 波段目標 {_tg}"
        )
    elif _sl and _direction == 'neutral':
        _swing_line = (
            f"\n【波段錨點】無波段方向，區間 {_sl['range_low']:.2f}~"
            f"{_sl['range_high']:.2f}（突破上緣轉多/跌破下緣轉空，區間內不操作）"
        )
    else:
        _swing_line = "\n【波段錨點】資料不足，本期不給波段框架（誠實 > 錯誤）"

    market_summary = (
        f"威科夫階段：{wyckoff_phase} | 風險係數：{risk_pct}%\n"
        f"關鍵支撐：{support or '--'} 元 | 關鍵壓力：{resistance or '--'} 元 | P&F目標：{target_pnf or '--'} 元"
        f"{_swing_line}"
    )
    if _direction == 'short':
        _dir_note = (
            f"⚠️ 本股結構為空方（威科夫 {wyckoff_phase}）。建議須為空方框架："
            f"放空/回補/減碼/出場；禁止建議加碼買進或逢低承接（逆勢高風險）。\n"
        )
    else:
        _dir_note = ""

    if _direction == 'short' and status == 'holding':
        # A 組 2026-05-20：方向衝突診斷段（明確 3 bullets）+ 既有減碼/停損段
        action_template = """<h3>▶ 持倉診斷（方向衝突警示）</h3>
<ul>
  <li><span class="key-point">⚠ 您持有多單，但分析結構為空方派發/下跌</span> — 成本方向與當前結構衝突，需立即評估</li>
  <li>出場條件：跌破 ___元（程式版波段低/失效價）立即減碼 ___成；反彈至 ___元（程式版波段高/回測壓力）全數出場</li>
  <li>續抱條件：站穩 ___元（波段高×1.02）上方且量超過 ___張（5日均量×1.5）— 方向反轉訊號出現才可續抱</li>
</ul>

<h3>▶ 整體判斷</h3>
<p>（只選一個）<strong>減碼 / 出場 / 觀望持有</strong> — 結構為空方，說明理由（不超過40字）</p>

<h3>▶ 減碼／出場計劃</h3>
<ul>
  <li>反彈減碼點：反彈至 ___元（前壓力）為減碼良機，非加碼</li>
  <li>第一減碼：跌破 ___元先減 ___成</li>
  <li>全數出場：跌破 ___元（空方結構確認）</li>
</ul>

<h3>▶ ⚠ 禁止加碼（空方結構）</h3>
<p>威科夫派發/下跌相位，攤平加碼為逆勢高風險，現價反彈不視為買點</p>

<h3>▶ 停損（最重要）</h3>
<span class="stop-loss">⚠ 停損位：___元 — 跌破請執行，不要猶豫（距現價約-___% ）</span>
<p>設在支撐位 ___元 下方約2-3%</p>

<h3>▶ 盤面提醒（不構成當日進出依據）</h3>
<p>（結合最後一根K棒型態+量能，一句話說明當下最值得注意的盤面訊號）</p>"""
    elif _direction == 'short':
        action_template = """<h3>▶ 現在適合放空嗎？</h3>
<p>（只選一個）<span class="short-term-title"><strong>可布局放空 / 等跌破確認 / 條件未到不放空</strong></span> — 理由（不超過40字）</p>

<h3>▶ 波段放空框架（2週-1個月+）</h3>
<ul>
  <li>放空觸發：跌破 ___元，且量超過 ___張（5日均量的___倍）</li>
  <li>回測壓力放空區：___元附近（原箱底反轉為壓力）</li>
  <li>下行目標：___元（P&F概念目標，約-___% ）</li>
  <li><span class="stop-loss">⚠ 放空後停損：___元（站回此價立即回補，損失約-___% ）</span></li>
</ul>

<h3>▶ 中線空方布局條件</h3>
<ul>
  <li>等待信號：___（頂部反轉型態 / 放量下跌 / 跌破前低，擇一說明）</li>
  <li>理想放空區：___元 ~ ___元（壓力帶附近）</li>
  <li>中線目標：___元（P&F概念下行目標）</li>
</ul>

<h3>▶ 李佛摩「等待」原則</h3>
<p>目前需要等什麼確認才放空？（跌破前低 / 5日均下彎，達到前不輕易出手）</p>

<h3>▶ 風險提示</h3>
<p>（根據風險係數 {risk_pct}% 說明放空最主要潛在風險，含反彈軋空風險，不超過2句）</p>""".replace('{risk_pct}', str(risk_pct))
    elif status == 'holding':
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

<h3>▶ 盤面提醒（不構成當日進出依據）</h3>
<p>（結合最後一根K棒型態+量能，一句話說明當下最值得注意的盤面訊號）</p>"""
    else:
        action_template = """<h3>▶ 現在適合進場嗎？</h3>
<p>（只選一個）<span class="short-term-title"><strong>可布局 / 等突破確認 / 條件未到不進場</strong></span> — 理由（不超過40字）</p>

<h3>▶ 波段介入框架（2週-1個月+）</h3>
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

    prompt = f"""你是台股操作顧問，提供具體、有數字、可執行的波段操作策略。
每個建議都必須有具體價格數字，絕不說「視情況而定」。
⚠️ 波段紀律：建議為 2 週-1 個月以上定位，不做當沖。所有價位必須引用
market_summary 中【波段錨點】的鎖定值，禁自行估算。失效價未破前論點
不變，禁因單日漲跌翻轉方向或重設價位，禁輸出「今日宜/不宜」當日結論。

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

{_dir_note}{action_template}

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
    _monthly_labels = label_bars(twii_enriched.get('monthly_bars', []), timeframe='monthly')
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
