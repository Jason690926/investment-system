# Bug A — 週/月 K 棒退化單日棒 + 日期時區位移：根因與修法設計

- 日期：2026-05-22
- 觸發：用戶以 5/22 dashboard 股價交叉核對 5/21 晚上報表（27 頁、15 股）
- 方法：systematic-debugging（已完成 Phase 1 根因調查 + Phase 2 模式分析）
- 對應 plan：§二十八（待寫）

---

## 一、問題陳述（症狀）

5/21 報表第二節「本間宗久 K 線確認」，**15/15 股**出現：

> 日K 最後一根 == 週K 最後一根 == 月K 最後一根，OHLCV 五欄逐字相同。

例（晶心科 6533，三張表 2026-05-21 列）：開 222 / 高 235 / 低 220.5 / 收 230 / 量 1101.7 —— 三表完全一致。

連帶現象：月K 日期標籤全部顯示「上月最後一日」（`2025-12-31` / `2026-04-30` …），而非月份起始。

**後果：**
1. 「本月月K / 本週週K」不是期間聚合，而是當日單一交易日 → AI 把 1 天的量拿去跟整月量比，系統性誤判「5月縮量 / 本週縮量」。
2. 月K 日期標籤位移一個月 → AI 月份歸屬錯亂（把 5 月的棒當 4 月讀）。

---

## 二、根因調查（Phase 1，含實測證據）

直接打 Yahoo v8 chart API（`query1.finance.yahoo.com/v8/finance/chart/{symbol}`）核對原始回傳。

### 根因 A1 — Yahoo 對 `1wk`/`1mo` 附加一根 spurious 即時棒

6533.TW `interval=1wk`（2026-05-22 實測，n=10，最後兩根）：

| idx | timestamp | OHLCV | 說明 |
|-----|-----------|-------|------|
| [8] | 1779033600（週起始） | O224 H235 L213 C230 **V3,460,999** | ✅ 正確的「本週聚合」 |
| [9] | **1779427816** | O234 H246 L230.5 C240 **V1,027,625** | ❌ spurious，= 當日 5/22 日K |

`interval=1mo` 同樣型態：[5] 為正確「本月聚合」，[6] 為 spurious 單日棒。

**關鍵簽章：spurious 棒的 `timestamp[-1]` 精確等於 `meta.regularMarketTime`**（`1779427816 == 1779427816`），其 OHLCV = 當前交易日的「日K」蠟燭。

跨股驗證（2026-05-22 實測）：

| symbol | `1d` ts[-1]==RMT | `1wk` ts[-1]==RMT | `1mo` ts[-1]==RMT |
|--------|------------------|-------------------|-------------------|
| 6533.TW | False | **True** | **True** |
| 6104.TWO | False | **True** | **True** |
| 2408.TW | False | **True** | **True** |

結論：Yahoo 對**聚合週期（`1wk`/`1mo`）**會在序列尾端多塞一根「即時快照棒」，timestamp = `regularMarketTime`、值 = 當日日K。`1d` 不會（日K 尾端那根本來就是進行中的當日，正確）。Yahoo **同時已提供正確的進行中期間聚合**，就在 spurious 棒的前一根（`[-2]`）。

`modules/data_enricher.py::_yahoo_ohlcv`（line 19–41）原封不動 ingest 全部元素 → `weekly_bars[-1]` / `monthly_bars[-1]` = 單日棒。

### 根因 A2 — `datetime.fromtimestamp()` 用伺服器本地時區

`_yahoo_ohlcv` line 36：
```python
index=pd.to_datetime([datetime.fromtimestamp(t) for t in d['timestamp']])
```
`datetime.fromtimestamp(t)`（無 tz 參數）以**執行環境本地時區**換算。生產在 Render = **UTC**。

Yahoo 的 `1wk`/`1mo` 棒 timestamp = 期間起始的「交易所時區 00:00」。月K 例：`2026-05-01 00:00 TW` = `2026-04-30 16:00 UTC`。在 UTC 伺服器上 `datetime.fromtimestamp` 算回 `2026-04-30` → **月K 標籤位移成上月最後一日**。

- 月K：每根都顯示上月底（`2026-05-01` 月棒 → 顯示 `2026-04-30`）→ 看起來像 4 月的棒。
- 週K：週起始 `週一 00:00 TW` → 顯示前一日（週日）。
- 日K：日K timestamp = `09:00 TW`（開盤）= `01:00 UTC`，−8h 後仍同一 UTC 日 → **日K 不受影響**（巧合安全）。

Yahoo 回傳的 `meta.gmtoffset = 28800`（台股 +8h）目前完全沒被使用。

### 根因確認小結

| | A1 spurious 棒 | A2 時區位移 |
|---|---|---|
| 位置 | `_yahoo_ohlcv`，未過濾 Yahoo 多塞的棒 | `_yahoo_ohlcv` line 36，`fromtimestamp` 未帶 tz |
| 影響週期 | `1wk` / `1mo` | `1wk` / `1mo`（日K 巧合不受影響） |
| 偵測簽章 | `interval∈{1wk,1mo}` 且 `ts[-1]==meta.regularMarketTime` | `meta.gmtoffset` 未套用 |

兩者都在同一函式 `_yahoo_ohlcv`，必須一併修。

---

## 三、影響範圍

`_yahoo_ohlcv` 的 `1wk`/`1mo` 呼叫只有一個來源：`get_full_stock_data()`（line 313–314），產出 `weekly_bars` / `monthly_bars`。下游消費者：

1. **`_render_ktables_html`（ai_analyzer_v2.py:122）** — 第二節 3 張 K 表用 `bars[-n:]`，含 spurious 棒 → AI 本間分析誤判（主症狀）。
2. **`compute_monthly_structure`（data_enricher.py:119）** — ⚠️ **重要**：docstring 明言「最後一根視為進行中，用其前 3 根**已收盤** bar」，程式做 `monthly_bars[:-1]`。
   - 現況（有 spurious 棒）：`[:-1]` 丟掉的是 spurious 垃圾棒，`completed[-1]` 落在「進行中的當月聚合」→ `completed[-3:]` 實際是 `[完成月, 完成月, 進行中月]`，**違反 docstring 本意**。週K 同理。
   - 修好 A1 後：`[:-1]` 丟掉的才是進行中那根，`completed[-3:]` = 3 根真正已收盤月 → **自動回到 docstring 本意**。
   - ⚠️ 這代表修 A1 會**改變威科夫結構閘的輸入視窗** → 部分股票的 `結構旗標` 輸出可能變動。這是**修正**（對齊本意），但屬行為變更，須 deploy 後重驗。
   - （先前對用戶說「結構閘 safe」需更正：閘的 `[:-1]` 在髒資料下並未真正排除進行中月。）
3. **日期標籤** — `_ohlcv_to_list` 的 `dt.strftime('%Y-%m-%d')` 直接吐錯位移日期。

不受影響：`get_stock_quote`（`1d`）、`_resolve_tw_symbol`（`1d`）、所有 MA/MACD/現價（全由 `daily` 計算）。`data_fetcher.py`（舊模組）自有抓取邏輯，不在範圍。

---

## 四、修法設計

### 決策 1：在資料源頭 `_yahoo_ohlcv` 修，不在 render 端

A1/A2 都是資料層缺陷。在源頭修，所有下游（K 表、結構閘）一次乾淨。在 `_render_ktables_html` 補丁屬症狀修，且漏掉結構閘。

### 決策 2：抽純函式 `_chart_json_to_df(result: dict, interval: str)` 便於測試

`_yahoo_ohlcv` 目前內含 `requests.get`，無法單測。比照既有 pattern（`app.py` 的 `_resolve_quote` 抽純函式）抽出：

```
_yahoo_ohlcv(symbol, interval, range_):
    r = requests.get(...)
    d = r.json()['chart']['result'][0]
    return _patch_missing_close(_chart_json_to_df(d, interval))
```

`_chart_json_to_df` 收已解析的 `d`（= `chart.result[0]`），做：時區校正建 index → 偵測並丟 spurious 棒 → 回 DataFrame。測試餵合成 `d` dict，零網路。

### 決策 3：spurious 偵測用 `ts[-1] == meta.regularMarketTime`

精確簽章（實測 3 股 100% 命中）。邏輯：

```
if interval in ('1wk', '1mo') and len(ts) >= 2:
    rmt = meta.get('regularMarketTime')
    if rmt is not None and ts[-1] == rmt:
        # 丟掉最後一根 spurious；ts 與 5 個 quote 陣列同步切片
        ts = ts[:-1]; (open/high/low/close/volume 全 [:-1])
```

- `interval='1d'` 永不進此分支 → 日K 全保留（回歸保護）。
- Yahoo 某日不再附 spurious 棒 → `ts[-1]` = 期間邊界 ≠ `rmt` → 不丟（正確保留進行中聚合）。
- `meta`/`regularMarketTime` 缺 → `rmt=None` → 不丟（退化但不崩，等同現況）。

### 決策 4：時區用 `meta.gmtoffset` 校正日期

```
gmtoffset = meta.get('gmtoffset', 0)   # 台股 = 28800
index = [datetime.fromtimestamp(t, tz=timezone.utc) + timedelta(seconds=gmtoffset)
         for t in ts]
# 轉 naive（去 tzinfo）後給 pandas，維持既有 strftime('%Y-%m-%d') 行為
```

校正後：月K 標籤 = 月份起始（`2026-05-01`），週K = 週一，日K 不變。對所有週期一致套用、對日K 無害。

### 決策 5：不改 `compute_monthly_structure`

源頭修好後它的 `[:-1]` 自動正確。但 spec 須明列「結構閘輸入視窗變動 → deploy 後重驗 `結構旗標`」（見驗收 §七）。

### 決策 6（防禦層）：標示「進行中」期間棒

即使修好 A1，進行中月/週本就是**部分期間**（如報表在週二產出，本週僅 2 天）→ 其累計量天然小於完整期間，AI 仍可能誤稱「縮量」。加兩層防禦：

- (a) `_render_ktables_html`：週K/月K 的最後一根（進行中那根），日期標籤加後綴「（進行中）」。
- (b) `analyze_stock_three_masters` / `analyze_market_only` prompt 第二節加一條鐵律：「週K/月K 標『（進行中）』者為未收盤期間，量能尚未累計完整，**禁**與完整期間直接比較放/縮量」。

判定「進行中」：最後一根的期間是否涵蓋最新日K 日期（或：最後一根 date 落在當前自然週/月）。實作細節留 plan。

---

## 五、測試計畫（TDD，先寫失敗測試）

新增 `tests/test_kbar_spurious.py`，全部餵合成 `d` dict（零網路）：

| # | 測試 | 斷言 |
|---|------|------|
| 1 | `1wk` 含 spurious 棒（`ts[-1]==rmt`） | 末棒被丟，df 末列 = 前一根「正確週聚合」 |
| 2 | `1mo` 含 spurious 棒 | 同上（月） |
| 3 | `1d`（`ts[-1]!=rmt`） | 一根都不丟（**回歸保護**：日K 不可被誤砍） |
| 4 | `1wk` 無 spurious 棒（`ts[-1]` 為期間邊界） | 不丟（不可過砍進行中聚合棒） |
| 5 | 時區：月棒 ts = `2026-05-01 00:00 TW`，`gmtoffset=28800` | 日期標籤 = `2026-05-01`（非 `2026-04-30`） |
| 6 | `meta` 無 `regularMarketTime` | 不崩、不丟 |
| 7 | `compute_monthly_structure` 餵修法後形狀的 monthly_bars | `completed[-3:]` 排除進行中月（驗證閘視窗本意；多半既有 `test_monthly_structure.py` 已涵蓋，補一條對齊即可） |

既有 `tests/test_report_bugfixes.py` / `test_monthly_structure.py` / `test_candlestick.py` 全綠不可退化。

---

## 六、風險與回滾

- **純資料層修正 + 加性純函式**，無 DB / migration / schema 改動。
- 主要風險 = 決策 5 的結構閘視窗變動：修法後 `結構旗標` 可能對少數股翻動（屬對齊 docstring 本意的修正，非退化）。→ 驗收 §七 第 3 點專門重驗。
- 回滾：單一 commit `git revert` 即還原；無資料污染。

---

## 七、驗收

### 程式驗收（不燒 token）
1. pytest 全綠（新 7 案 + 既有全數）；`py_compile data_enricher.py / ai_analyzer_v2.py`。
2. 本機跑 `get_full_stock_data('6533.TW')`：`weekly_bars[-1] != daily_bars[-1]`、`monthly_bars[-1] != daily_bars[-1]`；月K 日期為月份起始。

### Deploy 後驗收（用戶執行，~$0.6 重跑一鍵分析 + 出 PDF）
3. ⚠️ **結構閘重驗**：比對本次與 5/21 報表的 15 股 `結構旗標` / 方向；若有翻動，逐股確認新值（用真正已收盤 3 月）合理、非退化。
4. 第二節 K 表：日K[-1] ≠ 週K[-1] ≠ 月K[-1]；月K 顯示完整月份聚合量（如晶心科 5 月 ≈ 1,500 萬張級，非 1,101 張）。
5. 月K 日期標籤為月份起始（`2026-05-01`），AI 月份歸屬正確。
6. 進行中週/月棒顯示「（進行中）」；AI 不再對該棒稱「縮量」。
