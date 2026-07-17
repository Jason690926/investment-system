# §四十二 個股當日新聞佐證量價異動 — 設計文件

日期：2026-07-17
狀態：已與用戶定案（brainstorming 五題全數拍板）

## 1. 緣起與目標

7/16 報告 cross-check 發現「AI 敘事 vs 程式量價數據脫鉤」個案（撼訊：AI 寫
「放量 250 張」但程式特徵=均量）。同時，系統對「今日漲停/急漲的性質」缺乏
消息面佐證 — 無消息拉抬（主力/資金行為）與利多見報上漲（大眾行為）在威科夫
框架下是不同品質的訊號，目前 AI 只能瞎猜。

**目標**：注入個股近 24h 新聞標題供 AI 歸因當日量價異動，提升敘事品質；
同時以鐵律嚴格隔離，**不允許新聞影響趨勢判斷**（結構旗標 / DIRECTION /
程式錨點全部不動）。

**定位（用戶拍板）**：新聞是「當日量價異動的歸因佐證」，不是趨勢引擎的輸入。

## 2. 用戶已拍板的五個設計點

| # | 設計點 | 決定 |
|---|--------|------|
| 1 | 角色範圍 | **A：只餵 AI 當佐證** — 只注入 prompt，報表不新增新聞區塊、不持久化，零 migration |
| 2 | 新聞時窗 | **24h** — 涵蓋昨盤後重訊公告（今日漲幅常見催化劑）+ 今日盤中新聞；每則附發布時間 |
| 3 | 限流對策 | **誠實降級，不加快取** — timeout 5s、失敗/0 則 → 「暫無相關新聞」分支，不阻塞不 retry；靠逐股分析天然間隔（每股間隔 20-60s AI 呼叫） |
| 4 | 鐵律 | **三條全上**（見 §4.2） |
| 5 | 無新聞日 | **主動訊號化** — 「暫無相關新聞（近 24h）」+ 禁止臆測消息面禁令 |

## 3. 現狀（已查證）

- `analyze_market_only` / `analyze_stock_three_masters` prompt 已有「相關新聞」
  欄位（前 5 則標題，缺則「暫無相關新聞」）— 接線半埋好
- 生產路徑 `app.py:732`（一鍵分析）寫死 `news_list=[]`，個股新聞欄位一直空轉
- `run_daily_report.py:120` 亦未傳 news_list（cron 停用，手動批次仍可走）
- `analyze_stock_three_masters` 僅 legacy `analyze_stocks_parallel_v2` 呼叫
  （非生產路徑），其株連過濾（大盤 15 則裡標題含股名）小型股命中率趨近零
- `get_tw_news_rss`（data_fetcher.py:257）：urllib + ElementTree 解析
  Google News RSS、pubDate cutoff、fail-open 回 `[]` — 結構可直接鏡像

## 4. 設計

### 4.1 資料層 — `data_fetcher.get_stock_news_rss(name, symbol, n=5, hours=24)`

新純函式，鏡像 `get_tw_news_rss`（同一套 urllib + ET，無新依賴）：

- **查詢**：Google News 搜尋 RSS（`hl=zh-TW&gl=TW&ceid=TW:zh-TW`），
  query = 股名（如「晶心科」）
- **相關性過濾**：抓回後**要求股名出現在標題**才保留（搜尋引擎模糊匹配
  不可信；標題含股名才算相關）
- **時窗**：pubDate 距今 ≤ `hours`（預設 24h）；pubDate 解析失敗保留該筆
  （沿用既有寬容邏輯）
- **回傳**：`[{'title': str, 'source': str, 'pub_label': str}]`，
  `pub_label` = 台灣時間 `MM/DD HH:MM`（讓 AI 分辨盤前/盤後消息）；
  pubDate 缺失/解析失敗 → `pub_label=''`
- **失敗模式**：timeout 5 秒；任何 exception → 回 `[]` + `print` warning
  （誠實降級；`[]` 自然落入無新聞分支）
- 最多回傳 `n` 則（預設 5）

**symbol 參數用途**：僅供 log 標識（`[stock_news] 6533 抓取失敗: ...`），
不參與查詢（股名查詢 + 標題含股名過濾已足夠）。

### 4.2 Prompt 層 — `ai_analyzer_v2._stock_news_block(news_list)` 純函式

抽出獨立注入塊（純函式 → 可靜態測試；兩個 analyze 函式共用，消掉現有
news_text 重複段）。

**有新聞（≥1 則）**：

```
【個股相關新聞（近 24h，程式抓取）】
- MM/DD HH:MM 標題（來源）
- ...（最多 5 則）
⚠️ 新聞鐵律：
(1) 新聞僅供歸因當日量價異動與敘事佐證，禁止作為推翻結構旗標、
    DIRECTION 判定、程式錨點（進場/停損/目標）的依據 —
    結構閘禁令優先於任何新聞內容。
(2) 標題未經核實（可能為舊聞/內容農場）；若與程式注入的量價特徵矛盾
    （如新聞喊爆量但程式特徵=均量），以程式數據為準，可寫
    「新聞面與量價數據不一致」。
(3) 禁止引用新聞中的價位/漲跌幅/目標價數字 — 所有數字一律用程式注入值。
```

**無新聞（空列表 / None）**：

```
【個股相關新聞（近 24h，程式抓取）】暫無相關新聞（近 24h）。
⚠️ 無新聞禁令：禁止臆測消息面（不得寫「市場傳聞」「消息面利多」等
無依據字眼）；當日量價異動只能歸因為「無公開新聞佐證，屬資金面/
技術面行為」。
```

設計意涵：「無消息放量拉抬」（主力行為）vs「利多見報上漲」（大眾行為）
是威科夫框架下不同品質的訊號 — 無新聞本身是可解讀證據，非缺值。

**兩函式同步改**：`analyze_market_only` 與 `analyze_stock_three_masters`
的 news_text 段都換成 `_stock_news_block(news_list)`（沿用歷來兩函式
同步慣例，避免 legacy 路徑行為分裂）。

### 4.3 接線 — 兩個 call site

| 位置 | 改動 |
|------|------|
| `app.py:732`（一鍵分析） | 呼叫前 `news_list=get_stock_news_rss(name, symbol)` 取代 `news_list=[]` |
| `run_daily_report.py:120`（手動批次） | 同樣補傳 |

限流靠天然間隔（逐股分析、每股間隔 AI 呼叫）+ Google News RSS 容忍度；
不加快取（一天跑一輪，TTL 快取幾乎永遠 miss，YAGNI）。若日後觀察到
限流（log 大量抓取失敗），再升級 module-level TTL 快取。

## 5. 測試策略

**可靜態測（TDD）**：
- `_stock_news_block`：有新聞（鐵律三條字樣、5 則上限、pub_label 呈現）、
  無新聞（禁令字樣）、None 輸入
- `get_stock_news_rss` 過濾邏輯：標題含股名過濾、24h cutoff（邊界：23.5h
  保留 / 24.5h 剔除）、pubDate 解析失敗保留、fail-open 空列表 —
  比照既有 12h cutoff 測試手法（mock feed / 抽內部過濾 helper）

**需燒 token 驗（純 prompt 行為，無 post-process 安全網可做）**：
- AI 在敘事中正確歸因（有新聞日引用、標時間）
- 無新聞日不再腦補題材（不出現「市場傳聞」等字眼）
- 撼訊型矛盾場景寫「新聞面與量價數據不一致」而非順著新聞編

## 6. 範圍邊界

- 零 migration、零 DB 寫入、零前端改動、報表不新增新聞區塊
- 結構旗標 / §三十九加權評分 / DIRECTION gate / 程式錨點完全不動
- 成本：每股 prompt +約 200-300 token；RSS 免費
- 個人建議（`generate_personal_recommendation`）不注入新聞（不在本次範圍）

## 7. 回滾

- 資料層新函式：獨立，revert 無副作用
- prompt block：revert 回原 news_text 裸列表
- call site：`news_list=[]` 改回即回到現狀
- 三者各自獨立 revert，無資料污染

## 8. 已知風險（誠實揭露）

1. **純 prompt 約束**：敘事文字無法 regex 驗證，鐵律遵守度只能靠重跑
   cross-check 驗收（與歷來 prompt 類修法同級風險）
2. **Google News 搜尋品質**：股名過短或同名詞（如「合晶」）可能混入
   非個股新聞；標題含股名過濾可擋大半，殘餘雜訊由鐵律 (2) 兜底
3. **24h 時窗副作用**：連假後第一個交易日可能漏掉假期中的公告（屬已知
   取捨，與大盤 NEWS 12h 同哲學：誠實精簡 > 補舊聞）
