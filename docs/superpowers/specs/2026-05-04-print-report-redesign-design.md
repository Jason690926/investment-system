# 持股 PDF 報表改版設計

**日期**：2026-05-04
**範圍**：`templates/print_report.html` + `app.py` 的 `/print-report` route
**目標**：把現行 Material Indigo 範本感的 PDF 改成具識別度的「終端機印刷」風格，順帶修排序 bug、補當日收盤、拆持股/觀察兩節。

---

## 1. 動機

現行 `print_report.html` 有四個問題：

1. **視覺範本感**：用 `#1a237e`（Material Indigo 900）+ Microsoft JhengHei，看起來像隨手生的後台。
2. **排版不精緻**：所有區塊 padding/字級層級很均，沒節奏；資訊密度偏低。
3. **缺當日收盤**：`stock-block-header` 只有名稱與代號，看 PDF 的人要回頭查股價。
4. **排序 bug**：`app.py:605` 用 `order_by(Stock.created_at)`，沒走 dashboard 的 `display_order`，使用者拖拉的順位不會反映在 PDF。

## 2. 設計方向：「終端機印刷」

像 Bloomberg 終端機印在象牙色紙上的氣質。

- **字體**：IBM Plex Mono（數字/標籤）+ IBM Plex Sans（顯示/標題）+ Noto Sans TC（CJK）。Google Fonts 提供，SIL OFL 授權，瀏覽器列印能嵌入 PDF。
- **底色**：象牙紙 `#fbf8f1`（不是純白；省墨且有質感）。
- **強調色**：琥珀 `#b8860b` 為主強調，台股漲紅 `#c0392b` / 跌綠 `#2e7d32`，撐位藍 `#1565c0`。
- **線條**：1px 實心墨黑外框、1px dashed 內分隔、1px 柔灰細分。

## 3. 頁面結構

| # | 章節 | 來源 | 變更 |
|---|------|------|------|
| 1 | Cover（標題 + 週次 + 日期 + 持有/觀察數） | server | 重做 |
| 2 | 大盤週報 | `WeeklyReport.html_market` | 改 wrapper 樣式 |
| 3 | 產業指標股 | `WeeklyReport.html_industry` | 改 wrapper 樣式 |
| 4 | **§ HOLDINGS · 持股** | `Stock.status='holding'` | 新章節標 + 拆出 |
| 5 | **§ WATCHLIST · 觀察** | `Stock.status='watching'` | 新章節標 + 拆出 |
| 6 | 免責聲明 | 模板硬編 | 改色塊樣式 |

不加「投組總覽」頁（已與使用者確認，控制範圍）。

## 4. 持股 / 觀察 區塊版面

兩種共用同一個 wrapper（`.stock-block`），差別在「數據列」與「pills 內容」。

### 4.1 標頭（共用）

```
┌────────────────────────────────────────────────────────┐
│ 台積電    2330                            [01 · HOLD]   │
│ 1,085  ▲ +15 / +1.4%                  close 2026-05-03 │
└────────────────────────────────────────────────────────┘
```

- 名稱與股價**垂直堆疊在左側**（眼動軌跡：名稱 → 馬上看到股價）
- 股價字級 24px、`tracking: -1px`，IBM Plex Mono 700
- 漲跌色用台股慣例（紅漲綠跌）
- 右側上方放 `[編號 · 狀態]` 標籤，下方放收盤日期

### 4.2 持股版（多一條數據列）

```
COST 1,012.50 │ QTY 3.0 張 │ P/L +21.6% │ RISK 2.4%
```

- 4 欄等寬 grid，標籤用 `--font-label`（letter-spacing 2px、9px 全大寫）
- P/L 顏色跟漲跌一致（紅漲綠跌）
- RISK 用 amber

### 4.3 Pills 列（兩版差異）

持股版：`撐 · 壓 · 目標 · 威科夫`
觀察版：`撐 · 壓 · 目標 · 威科夫 · 風險%`（觀察版省略上面數據列，所以風險合進 pills）

每個 pill 用 `border-left: 3px solid` 配對應主色 + 同色低飽和填底（amber-soft / bull-soft / support-soft）。威科夫狀態用反白（黑底白字）。

### 4.4 AI 分析區塊

`.analysis-wrap` 包住 `{{ a.html_content }}`。CSS 接管 AI 吐出來的：

- `h3 / h4` → 統一改成 14px Plex Sans 700 + 3px border-left + soft 填底
- `ul / li / p` → body 11px Plex Sans + Noto Sans TC，line-height 1.75
- 既有 class（`key-point / support-level / resistance-level / target-price / stop-loss / short-term-title / mid-term-title / bull / bear`）映射到新色票

## 5. 後端改動（`app.py:/print-report`）

### 5.1 排序修法

`stocks = db.query(Stock)...order_by(Stock.created_at).all()`
→ `stocks = get_user_stocks(db, current_user.id)`（複用 `modules/stock_service.py:8` 的 helper，已正確處理 `display_order` + NULL fallback）

### 5.2 當日收盤資料

新增一段批次查詢：

```python
from modules.models import QuoteCache
from datetime import date
quotes = {
    q.symbol: q for q in
    db.query(QuoteCache)
      .filter(QuoteCache.symbol.in_(symbols),
              QuoteCache.cache_date == date.today())
      .all()
}
```

每支股取 `quotes.get(s.symbol)`：

- 命中 → 顯示 `close`、計算 `(close - prev_close) / prev_close * 100`
- 沒命中 → 顯示 `—`，不打 Yahoo（避免 N 支股同時打外網慢/失敗）
- `cache_date` 用 today；當日 dashboard 沒看過的股可能沒命中，這是已知降級行為

### 5.3 拆 holdings vs watchlist

```python
holdings = [s for s in stocks if s.status == 'holding']
watching = [s for s in stocks if s.status == 'watching']
holdings_html = _render_stock_blocks(holdings, analyses, quotes, mode='holding')
watching_html = _render_stock_blocks(watching, analyses, quotes, mode='watching')
```

`_render_stock_blocks(list, analyses, quotes, mode)` 接收一個 list，回傳已串接的 HTML 字串；內部迴圈呼叫 `_render_one_block(s, a, q, mode)`。模板換成接收 `holdings_html` 與 `watching_html` 兩個變數。

## 6. 模板改動（`templates/print_report.html`）

- 整支 `<style>` 重寫（保留 print-toolbar 結構不變）
- 在 `<head>` 加 Google Fonts link：

  ```html
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;700&family=IBM+Plex+Sans:wght@400;700&family=Noto+Sans+TC:wght@400;700&display=swap" rel="stylesheet">
  ```

- 所有顏色/字體/間距用 `:root` CSS 變數（見第 7 節 token）
- 兩個新章節標：`<div class="section-divider">§ HOLDINGS · 持股</div>` / `§ WATCHLIST · 觀察`（`.section-divider` 樣式：14px Plex Sans 700、letter-spacing 1px、上下 24px margin、底部 1px solid var(--ink)）
- 加 `@page { size: A4; margin: 18mm 14mm; @bottom-right { content: counter(page) " / " counter(pages); } }`

## 7. 設計 Token

```css
:root {
  /* 字體 */
  --font-sans: "IBM Plex Sans", "Noto Sans TC", sans-serif;
  --font-mono: "IBM Plex Mono", monospace;

  /* 色彩 */
  --paper:        #fbf8f1;
  --ink:          #1a1a1a;
  --amber:        #b8860b;
  --bull:         #c0392b;  /* 台股紅=漲 */
  --bear:         #2e7d32;  /* 台股綠=跌 */
  --support:      #1565c0;
  --amber-soft:   #fff8dc;
  --bull-soft:    #fef0f0;
  --support-soft: #e8f4ff;
  --rule-soft:    #e5e0d0;

  /* 間距 */
  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 12px;
  --space-lg: 20px;
  --space-xl: 32px;

  /* 字級 */
  --fs-display:    24px;  /* 封面標題、股價 */
  --fs-section:    14px;  /* §HOLDINGS 章節標 */
  --fs-stock-name: 16px;
  --fs-body:       11px;
  --fs-label:      9px;   /* 全大寫 letter-spacing 2px */
  --fs-mini:       8px;
}
```

## 8. 風險與緩解

| 風險 | 緩解 |
|---|---|
| AI 既有 `html_content` 帶 `style="..."` inline 樣式蓋過 token | cleanup 加一道 `style=` 屬性整體剝除（雙保險） |
| `QuoteCache` 沒當日資料 → 收盤顯示 `—` | 接受降級；不打 Yahoo 避免 N 支股同時超時 |
| Google Fonts 載入失敗（網路問題） | font-stack 有 system fallback（serif 走 Noto Sans TC，否則 sans-serif） |
| Chrome 列印頁碼語法瀏覽器差異 | 預設 Chrome；其他瀏覽器頁碼可能不顯示，但不影響內容 |

## 9. 不做的事（YAGNI）

- 不加投組總覽頁
- 不改 AI prompt（避免燒 token）
- 不換 PDF 引擎（仍用瀏覽器列印；分享 PDF email 的修法是另一個 task）
- 不加封面圖 / Logo（保持極簡）
- 不做交易記錄表（PDF 只談分析，不重述明細）

## 10. 測試計畫

1. 本機跑 Flask dev server，登入後開 `/print-report`，視覺檢查
2. 抓 DB 既有 5 支有 `html_content` 的股，確認 cleanup + CSS 渲染：標題層級、列表、表格、強調 class
3. Chrome 列印預覽：確認字體嵌入、頁碼、章節 page-break、A4 邊距
4. 蓋多種 AI 輸出情境：完整、截斷、含 markdown 殘留、含 inline style 殘留
5. 排序驗證：拖拉 dashboard 順序後重開 PDF，確認順序一致

## 11. 變更清單（給 plan 階段參考）

- `app.py:595-685` `/print-report` route 重構（用 `get_user_stocks`、加 quote 查詢、拆 holding/watching）
- `app.py` 新增 `_render_stock_blocks(stocks, analyses, quotes, mode)` 與 `_render_one_block(s, a, q, mode)` helpers
- `templates/print_report.html` `<style>` 與 `<body>` 大改
- `modules/ai_analyzer*` 的 cleanup 加一道 `style="..."` 剝除（防禦既有 DB 殘留）
- 不需要新 migration（`QuoteCache` 與 `display_order` 都已存在）

---

**前置條件**：本機要能跑 dev server、能連到 Supabase DB（讀 stocks/quote_cache/stock_analyses/weekly_reports）。
**完成定義**：使用者本機 Chrome 列印 `/print-report` 為 PDF，三組資料（持有 ≥3、觀察 ≥3、含週報）都看起來符合上述設計，且排序與 dashboard 一致、收盤價正確。
