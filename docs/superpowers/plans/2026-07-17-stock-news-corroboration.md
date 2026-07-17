# §四十二 個股當日新聞佐證量價異動 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 注入個股近 24h 新聞標題供 AI 歸因當日量價異動（含三條鐵律隔離 + 無新聞主動訊號化），零 migration。

**Architecture:** 資料層新純函式 `get_stock_news_rss`（Google News 搜尋 RSS，鏡像 `get_tw_news_rss`，過濾邏輯抽 `_filter_stock_news` 可測）→ prompt 層新純函式 `_stock_news_block`（兩個 analyze 函式共用，取代裸 news_text）→ 兩個 call site 接線（`app.py` 一鍵分析 + `run_daily_report.py` 手動批次）。失敗一律誠實降級回 `[]` 走無新聞分支。

**Tech Stack:** Python（urllib + xml.etree，無新依賴）、pytest。

**Spec:** `docs/superpowers/specs/2026-07-17-stock-news-corroboration-design.md`

**基線:** pytest 439/439 全綠（§四十一 後）。

---

### Task 1: 資料層 — `_filter_stock_news` + `get_stock_news_rss`

**Files:**
- Modify: `modules/data_fetcher.py`（`get_tw_news_rss` 之後，約 :303）
- Test: `tests/test_stock_news.py`（新檔）

- [ ] **Step 1: Write the failing tests**

建 `tests/test_stock_news.py`：

```python
"""
§四十二（2026-07-17）— 個股當日新聞佐證量價異動

Task 1：_filter_stock_news 純過濾邏輯 + get_stock_news_rss fail-open
Task 2：_stock_news_block prompt 注入塊（見同檔下方 class）
spec: docs/superpowers/specs/2026-07-17-stock-news-corroboration-design.md
"""
import sys, os
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from modules.data_fetcher import _filter_stock_news, get_stock_news_rss

UTC = timezone.utc
NOW = datetime(2026, 7, 17, 12, 0, 0, tzinfo=UTC)
CUTOFF = NOW - timedelta(hours=24)


def _item(title, hours_ago=1.0, source='工商時報', pub_dt='auto'):
    if pub_dt == 'auto':
        pub_dt = NOW - timedelta(hours=hours_ago)
    return {'title': title, 'source': source, 'pub_dt': pub_dt}


class TestFilterStockNews:
    def test_title_must_contain_name(self):
        """標題不含股名 → 剔除（搜尋引擎模糊匹配不可信）。"""
        items = [_item('晶心科接單暢旺'), _item('台股大盤震盪整理')]
        out = _filter_stock_news(items, '晶心科', CUTOFF)
        assert len(out) == 1
        assert out[0]['title'] == '晶心科接單暢旺'

    def test_24h_cutoff_boundary(self):
        """23.5h 保留 / 24.5h 剔除。"""
        items = [_item('晶心科 A', hours_ago=23.5), _item('晶心科 B', hours_ago=24.5)]
        out = _filter_stock_news(items, '晶心科', CUTOFF)
        assert [o['title'] for o in out] == ['晶心科 A']

    def test_pub_dt_none_kept_with_empty_label(self):
        """pubDate 解析失敗（pub_dt=None）→ 保留、pub_label=''（沿用寬容邏輯）。"""
        items = [_item('晶心科 C', pub_dt=None)]
        out = _filter_stock_news(items, '晶心科', CUTOFF)
        assert len(out) == 1
        assert out[0]['pub_label'] == ''

    def test_naive_pub_dt_no_crash(self):
        """naive datetime（無 tzinfo）與 aware cutoff 比較會 TypeError → 須保留不 crash。"""
        items = [_item('晶心科 D', pub_dt=datetime(2026, 7, 17, 10, 0, 0))]
        out = _filter_stock_news(items, '晶心科', CUTOFF)
        assert len(out) == 1

    def test_n_limit_5(self):
        """超過 n 則 → 只取前 5。"""
        items = [_item(f'晶心科 {i}') for i in range(8)]
        out = _filter_stock_news(items, '晶心科', CUTOFF, n=5)
        assert len(out) == 5

    def test_pub_label_is_tw_time(self):
        """pub_label = 台灣時間 MM/DD HH:MM（UTC 12:00 → TW 20:00）。"""
        items = [_item('晶心科 E', pub_dt=NOW)]
        out = _filter_stock_news(items, '晶心科', CUTOFF)
        assert out[0]['pub_label'] == '07/17 20:00'

    def test_output_shape(self):
        """回傳 keys = title/source/pub_label（無 pub_dt 內部欄位外洩）。"""
        out = _filter_stock_news([_item('晶心科 F')], '晶心科', CUTOFF)
        assert set(out[0].keys()) == {'title', 'source', 'pub_label'}


class TestGetStockNewsFailOpen:
    def test_network_failure_returns_empty(self, monkeypatch):
        """urllib 失敗 → 回 []（誠實降級，不 raise 不 retry）。"""
        import urllib.request

        def _boom(*a, **kw):
            raise OSError('simulated network failure')

        monkeypatch.setattr(urllib.request, 'urlopen', _boom)
        assert get_stock_news_rss('晶心科', '6533') == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_stock_news.py -v`
Expected: 全部 FAIL/ERROR，`ImportError: cannot import name '_filter_stock_news'`

- [ ] **Step 3: Implement in `modules/data_fetcher.py`**

插在 `get_tw_news_rss` 函式結束之後（`get_financial_news` 之前）：

```python
def _filter_stock_news(items: list, name: str, cutoff, n: int = 5) -> list:
    """§四十二 個股新聞純過濾邏輯（可測試）。

    items: [{'title', 'source', 'pub_dt'(aware datetime | None)}]
    規則：
      - 標題必須含股名（Google News 搜尋模糊匹配不可信，標題含股名才算相關）
      - pub_dt < cutoff → 剔除；pub_dt=None（解析失敗）→ 保留（沿用
        get_tw_news_rss 寬容邏輯）；naive datetime 比較 TypeError → 保留
      - 最多 n 則
    回傳: [{'title', 'source', 'pub_label'}]，pub_label = 台灣時間
    'MM/DD HH:MM'（供 AI 分辨盤前/盤後消息；無 pub_dt → ''）
    """
    from datetime import timezone, timedelta
    TW = timezone(timedelta(hours=8))
    out = []
    for it in items:
        if len(out) >= n:
            break
        title = it.get('title') or ''
        if not title or name not in title:
            continue
        pub_dt = it.get('pub_dt')
        if pub_dt is not None:
            try:
                if pub_dt < cutoff:
                    continue
            except TypeError:
                pass  # naive datetime 無法與 aware cutoff 比較 → 保留
        label = ''
        if pub_dt is not None:
            try:
                label = pub_dt.astimezone(TW).strftime('%m/%d %H:%M')
            except Exception:
                label = ''
        out.append({'title': title, 'source': it.get('source') or '',
                    'pub_label': label})
    return out


def get_stock_news_rss(name: str, symbol: str = '', n: int = 5,
                       hours: int = 24) -> list:
    """§四十二：個股近 24h 新聞（Google News 搜尋 RSS，query=股名）。

    時窗 24h（涵蓋昨盤後重訊公告 + 今日盤中新聞 — 今日漲幅的催化劑常在
    昨盤後發布）。失敗模式：timeout 5s、任何 exception → 回 []（誠實降級，
    caller 走「暫無相關新聞」分支；絕不阻塞分析、不 retry）。
    限流：靠一鍵分析逐股天然間隔（每股間隔 AI 呼叫 20-60s），不加快取。
    symbol 僅供 log 標識，不參與查詢。
    """
    import urllib.request
    import urllib.parse
    import xml.etree.ElementTree as ET
    from email.utils import parsedate_to_datetime
    from datetime import datetime, timezone, timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    query = urllib.parse.quote(name)
    url = (f'https://news.google.com/rss/search?q={query}'
           f'&hl=zh-TW&gl=TW&ceid=TW:zh-TW')
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as r:
            xml_data = r.read()
        root = ET.fromstring(xml_data)
        items = []
        for item in root.findall('.//item'):
            title_el  = item.find('title')
            source_el = item.find('source')
            pub_el    = item.find('pubDate')
            pub_dt = None
            if pub_el is not None and pub_el.text:
                try:
                    pub_dt = parsedate_to_datetime(pub_el.text)
                except Exception:
                    pub_dt = None
            items.append({
                'title':  title_el.text  if title_el  is not None else '',
                'source': source_el.text if source_el is not None else '',
                'pub_dt': pub_dt,
            })
        return _filter_stock_news(items, name, cutoff, n)
    except Exception as e:
        print(f'[stock_news] {symbol or name} 抓取失敗（誠實降級，'
              f'走無新聞分支）: {e}')
        return []
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_stock_news.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add modules/data_fetcher.py tests/test_stock_news.py
git commit -m "feat(news): §四十二 get_stock_news_rss 個股近24h新聞（fail-open + 標題含股名過濾）"
```

---

### Task 2: Prompt 層 — `_stock_news_block` 純函式

**Files:**
- Modify: `modules/ai_analyzer_v2.py`（放在 `_structure_block` 之後、`analyze_stock_three_masters` 之前，約 :1213）
- Test: `tests/test_stock_news.py`（追加 class）

- [ ] **Step 1: Write the failing tests**

追加到 `tests/test_stock_news.py` 末尾：

```python
# ── Task 2：_stock_news_block prompt 注入塊 ──────────────────────
from modules.ai_analyzer_v2 import _stock_news_block


class TestStockNewsBlock:
    def test_empty_list_gives_no_news_ban(self):
        """無新聞 → 主動訊號化：暫無字樣 + 禁止臆測消息面禁令。"""
        block = _stock_news_block([])
        assert '暫無相關新聞（近 24h）' in block
        assert '禁止臆測消息面' in block
        assert '市場傳聞' in block, '禁令應列舉禁用字眼'
        assert '資金面' in block, '應給唯一合法歸因寫法'

    def test_none_input_same_as_empty(self):
        """None 輸入（legacy caller 未傳）→ 同無新聞分支，不 crash。"""
        assert _stock_news_block(None) == _stock_news_block([])

    def test_news_lines_with_label_and_source(self):
        """有新聞 → 每則一行 '- MM/DD HH:MM 標題（來源）'。"""
        block = _stock_news_block([
            {'title': '晶心科接單暢旺', 'source': '工商時報',
             'pub_label': '07/16 18:30'},
        ])
        assert '- 07/16 18:30 晶心科接單暢旺（工商時報）' in block

    def test_three_iron_rules_present(self):
        """有新聞 → 三條鐵律齊全（推翻禁令 / 矛盾程式為準 / 禁引數字）。"""
        block = _stock_news_block([{'title': '晶心科 A', 'source': '',
                                    'pub_label': ''}])
        assert '禁止作為推翻結構旗標' in block
        assert '以程式數據為準' in block
        assert '新聞面與量價數據不一致' in block
        assert '禁止引用新聞中的價位' in block

    def test_max_5_items(self):
        """超過 5 則只列前 5。"""
        news = [{'title': f'晶心科 {i}', 'source': '', 'pub_label': ''}
                for i in range(7)]
        block = _stock_news_block(news)
        assert block.count('- ') == 5

    def test_legacy_format_without_pub_label(self):
        """legacy 格式（無 pub_label/source key，parallel 路徑舊資料）→ 不 crash、無多餘空白。"""
        block = _stock_news_block([{'title': '晶心科 B'}])
        assert '- 晶心科 B' in block
        assert '- 晶心科 B（' not in block, 'source 缺時不應有空括號'
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_stock_news.py::TestStockNewsBlock -v`
Expected: ERROR — `ImportError: cannot import name '_stock_news_block'`

- [ ] **Step 3: Implement in `modules/ai_analyzer_v2.py`**

放在 `_structure_block` 函式結束之後：

```python
def _stock_news_block(news_list: list) -> str:
    """§四十二：個股新聞注入塊（純函式，兩 analyze 函式共用）。

    定位：新聞僅是「當日量價異動的歸因佐證」，不是趨勢引擎輸入 —
    結構旗標 / DIRECTION / 程式錨點全部不受新聞影響（鐵律 1）。
    無新聞 = 主動訊號（無消息拉抬屬主力/資金行為，威科夫框架下
    與利多見報上漲是不同品質的訊號），非缺值。
    向後相容：news_list 舊格式（僅 title/source，無 pub_label）可用。
    """
    items = news_list or []
    if not items:
        return (
            "【個股相關新聞（近 24h，程式抓取）】暫無相關新聞（近 24h）。\n"
            "⚠️ 無新聞禁令：禁止臆測消息面（不得寫「市場傳聞」「消息面利多」"
            "等無依據字眼）；當日量價異動只能歸因為「無公開新聞佐證，"
            "屬資金面/技術面行為」。"
        )
    lines = []
    for n in items[:5]:
        title = n.get('title', '')
        src   = n.get('source', '')
        lbl   = n.get('pub_label', '')
        prefix = f"{lbl} " if lbl else ""
        suffix = f"（{src}）" if src else ""
        lines.append(f"- {prefix}{title}{suffix}")
    return (
        "【個股相關新聞（近 24h，程式抓取）】\n"
        + '\n'.join(lines) + "\n"
        "⚠️ 新聞鐵律：\n"
        "(1) 新聞僅供歸因當日量價異動與敘事佐證，禁止作為推翻結構旗標、"
        "DIRECTION 判定、程式錨點（進場/停損/目標）的依據 — "
        "結構閘禁令優先於任何新聞內容。\n"
        "(2) 標題未經核實（可能為舊聞/內容農場）；若與程式注入的量價特徵"
        "矛盾（如新聞喊爆量但程式特徵=均量），以程式數據為準，可寫"
        "「新聞面與量價數據不一致」。\n"
        "(3) 禁止引用新聞中的價位/漲跌幅/目標價數字 — "
        "所有數字一律用程式注入值。"
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_stock_news.py -v`
Expected: 14 passed

- [ ] **Step 5: Commit**

```bash
git add modules/ai_analyzer_v2.py tests/test_stock_news.py
git commit -m "feat(news): §四十二 _stock_news_block 注入塊（三鐵律 + 無新聞主動訊號化）"
```

---

### Task 3: 兩個 analyze 函式 prompt 換用 block

**Files:**
- Modify: `modules/ai_analyzer_v2.py`（兩處 news_text 定義 + 兩處 prompt 模板）

- [ ] **Step 1: 替換 `analyze_stock_three_masters` 的 news_text（約 :1293）**

原：

```python
    news_text = (
        '\n'.join([f"- {n['title']}" for n in (news_list or [])[:5]])
        or '暫無相關新聞'
    )
```

改為：

```python
    # §四十二：個股新聞注入塊（含鐵律/無新聞禁令），取代裸標題列表
    news_text = _stock_news_block(news_list)
```

- [ ] **Step 2: 替換該函式 prompt 模板的新聞段（約 :1436）**

原（在 `{daily_text}` 之後）：

```
【近期相關新聞】
{news_text}
```

改為（block 自帶標題）：

```
{news_text}
```

- [ ] **Step 3: 對 `analyze_market_only` 做同樣兩處替換（約 :1713 與 :1887）**

news_text 定義替換與 Step 1 完全相同；prompt 模板段原文為：

```
【近期相關新聞】
{news_text}"""
```

改為：

```
{news_text}"""
```

- [ ] **Step 4: 驗證與回歸**

Run: `python -m py_compile modules/ai_analyzer_v2.py && python -m pytest tests/ -q`
Expected: COMPILE OK；453 passed（439 基線 + 14 新）

Run: `grep -n "近期相關新聞" modules/ai_analyzer_v2.py`
Expected: 無輸出（兩處舊標題都已移除；`analyze_daily_news`/weekly 的
news_text 是大盤用，不含此標題、不受影響）

- [ ] **Step 5: Commit**

```bash
git add modules/ai_analyzer_v2.py
git commit -m "feat(news): §四十二 兩 analyze 函式 prompt 換 _stock_news_block（兩函式同步慣例）"
```

---

### Task 4: Call site 接線（app.py + run_daily_report.py）

**Files:**
- Modify: `app.py:732-735`
- Modify: `run_daily_report.py:25`（import）+ `:119-121`

- [ ] **Step 1: app.py 一鍵分析路徑**

原（app.py:732-735）：

```python
        result = analyze_market_only(
            name=stock.name, symbol=stock.symbol,
            enriched_data=enriched, news_list=[], is_holding=_is_holding,
        )
```

改為：

```python
        # §四十二：個股近 24h 新聞（fail-open：失敗回 [] 走無新聞分支）
        from modules.data_fetcher import get_stock_news_rss
        _stock_news = get_stock_news_rss(stock.name, stock.symbol)

        result = analyze_market_only(
            name=stock.name, symbol=stock.symbol,
            enriched_data=enriched, news_list=_stock_news,
            is_holding=_is_holding,
        )
```

- [ ] **Step 2: run_daily_report.py 手動批次路徑**

import 行（:25）原：

```python
from modules.data_fetcher import get_tw_news_rss, get_global_markets
```

改為：

```python
from modules.data_fetcher import get_tw_news_rss, get_global_markets, get_stock_news_rss
```

呼叫處（:119-121）原：

```python
    result = analyze_market_only(name=name, symbol=symbol,
                                 enriched_data=enriched, is_holding=is_holding)
```

改為：

```python
    # §四十二：個股近 24h 新聞（fail-open）
    stock_news = get_stock_news_rss(name, symbol)
    result = analyze_market_only(name=name, symbol=symbol,
                                 enriched_data=enriched, news_list=stock_news,
                                 is_holding=is_holding)
```

- [ ] **Step 3: 驗證**

Run: `python -m py_compile app.py run_daily_report.py && python -m pytest tests/ -q`
Expected: COMPILE OK；453 passed

Run（本機真連線 smoke，零 AI token）:
`python -c "from modules.data_fetcher import get_stock_news_rss; import json; print(json.dumps(get_stock_news_rss('台積電','2330'), ensure_ascii=False))"`
Expected: 台積電新聞多，應回 1-5 筆含 pub_label 的 dict；或（網路異常時）
`[]` + log warning — 兩者皆為合法結果，不得 crash

- [ ] **Step 4: Commit**

```bash
git add app.py run_daily_report.py
git commit -m "feat(news): §四十二 兩 call site 接線（一鍵分析 + 手動批次傳個股新聞）"
```

---

### Task 5: 文件 + push

**Files:**
- Modify: `plan.md`（追加 §四十二 節：緣起 / 五設計點表 / 修法 / 驗收 / 回滾，內容依 spec 濃縮）
- Modify: `CLAUDE.md`（當前進度快照：§四十二 已實作、pytest 453/453、待燒 ~$0.6 驗收三項 prompt 行為）

- [ ] **Step 1: 更新兩份文件**（內容照 spec §2/§4/§5 濃縮，驗收列：有新聞日敘事引用+標時間、無新聞日不腦補題材、撼訊型矛盾寫「新聞面與量價數據不一致」）

- [ ] **Step 2: Commit + push**

```bash
git add plan.md CLAUDE.md
git commit -m "docs: plan.md §四十二 + CLAUDE.md 進度快照（個股新聞佐證已實作、待驗收）"
git push origin main
```

---

## 驗收（用戶執行，燒 ~$0.6 重跑後）

1. 有新聞的股：分析敘事引用新聞歸因當日異動（含發布時間），數字仍全用程式注入值
2. 無新聞的小型股：敘事不出現「市場傳聞」「消息面利多」等腦補字眼，異動歸因「無公開新聞佐證」
3. 新聞與量價矛盾場景（撼訊型）：AI 寫「新聞面與量價數據不一致」而非順著新聞編
4. Render log 觀察 `[stock_news]` 失敗率（若大量失敗 → 評估升級 TTL 快取）

## 回滾

Task 1/2/3/4 各自獨立 revert；`news_list=[]` 改回即回現狀。零 migration、零 DB 寫入。
