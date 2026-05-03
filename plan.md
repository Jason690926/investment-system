# 投資建議書系統 — 重構計畫
> 建立日期：2026-04-30｜更新日期：2026-05-02 20:30｜基於兩次訪談決策 + 實作後討論補充

---

## 一、核心決策

**不是「修」也不是「全部重寫」，而是分兩階段：**
- 第一階段：本週修好 GitHub Actions，讓系統今天起能自動跑
- 第二階段：3-5 週重寫架構骨幹，保留已除錯完成的模組

---

## 二、系統定位

| 項目 | 決定 |
|------|------|
| 使用者 | 1-5 人（自己 + 家人朋友），各自獨立帳號與持股清單 |
| 存取方式 | 瀏覽器（電腦 / 手機皆可），無需安裝 |
| 多地點支援 | ✅ 雲端部署，A點B點兩台電腦用同一個網址登入即可 |
| 報表交付 | 網頁直接看（主）、Email 通知就緒（可關掉）、PDF 匯出（次）|
| 線圖 | TradingView 嵌入（網頁互動）+ Matplotlib 靜態圖（PDF 用）|
| AI 分析模式 | 文字餵數值（不用視覺/圖片），效果好且費用低 |
| 登入方式 | Google OAuth（家人朋友免記帳密，安全性由 Google 負責）|

---

## 三、月費估算（4人）

| 項目 | 費用 |
|------|------|
| 伺服器（Render Starter） | US$7/月 |
| 資料庫（Supabase 免費 PostgreSQL） | US$0 |
| GitHub Actions（定時報表） | US$0 |
| Claude API（~20支獨立股 × 22天，含 Prompt Cache） | US$4-5/月 |
| 財經新聞（Google News RSS） | 免費 |
| Email（Gmail SMTP） | 免費 |
| **合計** | **約 US$11-12/月** |

### 擴充門檻
| 用戶數 | 建議動作 | 月費變化 |
|--------|---------|---------|
| 1-10人 | 不動 | US$11-12 |
| 10-20人 | 升級 Supabase Pro（US$25/月） | ~US$40 |
| 20-50人 | 升級 Render Standard（US$25/月） | ~US$60 |
| 50人以上 | 架構重新設計 | 另計 |

---

## 四、第一階段：GitHub Actions（本週，半天）

### 目標
讓現有系統在 Render 之外自動執行，每天台灣時間 14:30 自動產生報表並寄 Email。

### 工作清單
- [ ] 建立 `.github/workflows/daily_report.yml`
- [ ] 在 GitHub Secrets 設定所有環境變數（Claude API Key、Email 設定等）
- [ ] 測試手動觸發（workflow_dispatch）
- [ ] 確認 Email 正常寄出
- [ ] 設定每日 14:30（UTC 06:30）自動執行

### workflow 草稿
```yaml
name: 每日投資報表
on:
  schedule:
    - cron: '30 6 * * 1-5'  # UTC 06:30 = 台灣 14:30，週一到週五
  workflow_dispatch:
jobs:
  run-report:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt
      - run: python main.py
        env:
          CLAUDE_API_KEY: ${{ secrets.CLAUDE_API_KEY }}
          # 其他 secrets 待補齊
```

---

## 五、第二階段：重構架構（3-5 週）

### 模組決策

| 模組 | 決策 | 原因 |
|------|------|------|
| `yf_session.py` | 保留 | 已除錯完成，穩定 |
| `data_fetcher.py` | 保留 + 擴充 | 加入週K、月K、成交量、MACD、MA5/20/60 |
| `watchlist.py` | 改寫 | 分 已持有/觀察中，支援多筆買入記錄 |
| `stock_names.py` | 保留 | 本地對照表穩定 |
| `threading.Thread` 架構 | 丟掉重寫 | 換成非同步任務佇列 |
| `report_scheduler.py` | 重寫 | 整合進新架構 |
| AI Prompt | 完整重寫 | 見第六節 |
| 前端介面 | 重寫 | 多用戶 + 手機 + TradingView + 逐支即時顯示 |
| Email 寄送 | 變可選通知 | 報表就緒時寄通知，用戶可在設定關掉 |

### 技術選型

| 項目 | 選擇 | 原因 |
|------|------|------|
| 資料庫 | PostgreSQL（Supabase 免費）| 持久性、擴充性，SQLite 在 Render 會被清空 |
| ORM | SQLAlchemy | 抽象層，未來換資料庫只改連線設定 |
| 後端框架 | Flask（沿用）| 現有程式碼基礎 |
| 前端 | Jinja2 + Bootstrap（RWD）| 手機/電腦皆可 |
| 線圖（網頁）| TradingView Widget | 免費、互動式、專業 |
| 線圖（PDF）| Matplotlib / mplfinance | 靜態圖嵌入 PDF |
| PDF 產生 | WeasyPrint | 現有套件 |
| 部署（網頁）| Render Starter（US$7/月）| 常駐服務，處理網頁請求與手動觸發 |
| 定時報表 | GitHub Actions | 免費，已驗證可用，不佔 Render 資源 |
| 登入 | Google OAuth（Flask-Dance 或 Authlib）| 用戶免記帳密，半天可完成 |

---

## 六、AI 分析框架（三大宗師架構）

### 主從結構（C方案）

```
威科夫（量價關係）→ 主骨幹，判斷市場結構
本間宗久（K線型態）→ 確認信號層
李佛摩（動能時機）→ 出手時機與資金管理層
```

### 時間框架分配

| 宗師 | 負責時間框架 | 任務 |
|------|------------|------|
| 威科夫 | 月線 + 5日 + 日線 | 判斷四個階段（吸籌/上漲/派發/下跌）+ 量價關係（均量單位：張）|
| 李佛摩 | 月線 + 5日均 | 判斷大趨勢方向與近期動能強弱 |
| 本間宗久 | 日K + 週K | 給出進出場觸發信號與型態確認 |

### 量的單位

- 所有成交量、均量顯示一律用**張**（÷ 1000 轉換，整數省略小數，有 .5 才顯示）
- 持倉數量輸入與顯示也用張，資料庫存 `NUMERIC(10,1)`

### 資料回溯長度

| 資料 | 回溯長度 | 說明 |
|------|---------|------|
| 日K | 60個交易日 | 計算 MA60 需要 |
| 週K | 26根（6個月）| 本間型態 + 李佛摩動能轉折 |
| 月K | 12根（1年）| 威科夫階段判斷 |

### 上位否決規則（B方案）

**降權但不否決**：月線看空時，日K買進信號仍呈現，但明確標示：
- 風險係數（0-100%，0%=完全順勢，100%=完全逆勢，不用文字標籤）
- 「逆大結構，適合短線操作，不建議重倉」

### 威科夫目標價

- 使用 P&F 概念估算（AI 概念推算，不建實際 P&F 圖）
- 同時給出壓力點與支撐點
- **一般用戶不能修改估算值**
- 管理者（你）可在後台覆寫

---

## 七、新報表結構

### 股票卡片頂部佈局

```
┌─────────────────────────────────────┐
│ 台積電 2330          ▲ $985  +1.2% │
│ 風險係數 23%  ████░░░░░░            │
└─────────────────────────────────────┘
```

- 左側：股票名稱（大字）+ 代號
- 右側：現價（大字）+ 漲跌幅（紅漲綠跌）
- 第二行：風險係數百分比 + 視覺進度條

### 大盤分析深度（日報 vs 週報）

| 項目 | 每日報表 | 每週報表 |
|------|---------|---------|
| 大盤走勢 | ✅ 簡化 | ✅ 完整 |
| K線型態分析 | ✅ | ❌ |
| 成交量分析（張）| ✅ | ❌ |
| 全球情勢對台股影響 | ❌ | ✅ |
| 台股技術面展望 | ❌ | ✅ |
| 大盤操作策略 | ❌ | ❌ |

### 三種操作模式

| 模式 | 觸發 | AI | Token |
|------|------|----|-------|
| **看圖模式** | 隨時自由點 | ✗ | 0 |
| **逐股分析** | 每日收盤後 14:30，有防重複快取 | ✓ | 中 |
| **產業週報** | 每週固定一次（週六）| ✓ | 低 |

### 防重複快取規則

- 快取在**每支股票**層級，跨用戶共用（客觀市場面）
- 14:30 收盤後產生的分析才算有效；14:30 前的舊快取允許重跑
- **整體持倉建議**：各用戶獨立產生（因持股組合不同）

### 威科夫快取策略（混合C方案）

- **每日**：帶入前次威科夫結論 + 新日K/週K，輕量分析（省 token）
- **每週一次**：完整送所有時間框架，重新判斷威科夫階段，更新基準

### 報表顯示方式

- 逐支即時顯示：每分析完一支立刻更新頁面，不等全部完成

### 每股報表內容

**客觀市場面（跨用戶共用）：**
1. 威科夫階段判斷（月線結構）
2. 多時間框架走勢（月/週/5日/日）
3. K線型態（日K + 週K）
4. 技術指標融合（RSI + MACD + MA5/20/60 + 成交量）
5. 壓力點 / 支撐點
6. 威科夫 P&F 概念目標價區間
7. 風險係數（0-100%，量化各時間框架衝突程度，不顯示文字標籤）
8. 推理過程（不只給結論）

**個人化操作建議（各用戶獨立）：**
- **已持有**：持有 / 加碼 / 減碼 / 出場建議（含成本考量，若有填入）
- **觀察中**：現在可入場嗎 / 等什麼條件再進

### 產業週報內容（每週一次）

1. **大盤回顧**（走勢回顧、全球情勢對台股影響、台股技術面展望）— 不給操作策略
2. 財經新聞亮點（重要新聞 + 受惠/受害產業）
3. 產業輪動方向
4. 看好產業的指標股參考（AI 從新聞正面提及中萃取，每產業 3-5 支，僅列出不做 AI 分析）
5. 下週投資標的方向建議

---

## 八、多用戶功能需求

### 帳號系統

| 項目 | 設計 |
|------|------|
| 登入 | Google OAuth |
| 角色 | 管理者（你）/ 一般用戶 |
| 管理者權限 | 看所有人狀態、覆寫 AI 估算值、調整用戶股票配額 |

### 持股清單設計

| 身份 | 資料 |
|------|------|
| **已持有** | 股票代號、多筆買入記錄（價格/數量/日期）、系統算加權平均成本；成本資料**可選填** |
| **觀察中** | 只有股票代號，無成本資料 |

### 股票追蹤上限

- 管理者：無限制
- 一般用戶：預設 10 支，管理者可調整（存在 `users.max_stocks` 欄位）

### 通知機制

- GitHub Actions 跑完後寄 Email「今日報表已就緒」+ 網頁連結
- 用戶可在個人設定關掉 Email 通知

---

## 九、存取需求

| 情境 | 解法 |
|------|------|
| A點電腦 | 瀏覽器開網址登入 |
| B點電腦 | 同一網址登入，資料完全同步 |
| 手機 | RWD 響應式設計，手機瀏覽器可用 |
| 資料同步 | PostgreSQL 存在 Supabase，所有裝置共享同一份資料 |

---

## 十、開發優先順序

```
週1 ✅：GitHub Actions（撐住日常需求）
週2 ✅：Google OAuth + PostgreSQL/SQLAlchemy + 持股管理重構（已持有/觀察中）
週3 ✅：新 data_enricher（週K/月K/成交量/MACD/MA）+ AI 三宗師框架
週4 ✅：深色主題前端（RWD + lightweight-charts + 逐股分析 + 看圖模式）
週5（進行中）：產業週報 + PDF 匯出 + Render Starter 部署（+ 以下補充決策）
```

**部署前修復（2026-05-02 已完成）：**
1. ✅ 修 `Procfile`：`web: python app.py`
2. ✅ 新增 `run_daily_report.py`：批次入口（重疊排序 + 快取優先）
3. ✅ 修 `daily_report.yml`：改用新腳本 + Supabase secrets
4. ✅ `ai_analyzer_v2.py`：加入兩段式函式（`analyze_market_only` + `generate_personal_recommendation`）
5. ✅ `app.py`：`/analyze` 存市場快取，新增 `/recommend` 個人建議端點
6. ✅ `database.py`：連線驅動從 `psycopg` 改為 `psycopg2`（已在 requirements.txt）
7. ✅ `app.py`：Flask 綁定 `0.0.0.0` + 讀取 `PORT` 環境變數（Render 部署必要）
8. ✅ GitHub Secrets 設定完成（Supabase 五個 + 既有 Claude/Email）
9. ✅ Render 環境變數設定完成（Supabase + OAuth + Flask）
10. ✅ `plan.md` 移入 `investment-system` repo（GitHub 同步，跨電腦可用）
11. ✅ `CLAUDE.md` 建立（自動讀 plan.md + 前端美學指引）
12. ✅ Render 部署成功（`Your service is live 🎉`）
13. ✅ Google OAuth redirect URI 修正（ProxyFix，http → https）
14. ✅ `init_db()` 加入啟動流程（非 fatal）
15. ✅ Supabase Session Pooler 連線（IPv4，解決 Render 免費版 IPv6 問題）

**Supabase 連線問題紀錄：**
- Render 免費版不支援 IPv6，Supabase Direct 連線 `db.cctvzvyfvbwrbcfgidnn.supabase.co` 解析到 IPv6 → 連線失敗
- 解法：改用 Supabase Session Pooler（IPv4）
  - `SUPABASE_DB_HOST` → `aws-1-ap-northeast-1.pooler.supabase.com`
  - `SUPABASE_DB_USER` → `postgres.cctvzvyfvbwrbcfgidnn`
- 上述兩個 Render 環境變數更新中，更新後需手動重新部署

**部署完成後待做：**
- ✅ 確認網站可正常登入（Google OAuth）
- ✅ 加入 GitHub Secret `APP_URL`（Render 網址）
- ✅ 手動觸發 GitHub Actions 測試批次分析（成功，Email 收到）

**週5 Bug 修復與功能補強（2026-05-02）：**
- ✅ Bug：改股票代號後名稱不更新（移除 `!nameEl.value` 條件）
- ✅ Bug：K 線 crosshair 移動時成交量數字不更新（加 `subscribeCrosshairMove`）
- ✅ Bug：週K / 月K 成交量與 K 線重疊（動態調整 `scaleMargins.top`：日0.80/週0.85/月0.88）
- ✅ 功能：Dashboard 一鍵分析按鈕（⚡ 逐支分析，完成的卡片亮藍色頂邊 + ✦ 已分析標記）
- ✅ Bug：股票名稱顯示英文（`stock_names.py` 從 76 支擴充為 39,255 支，涵蓋全台股上市+上櫃）
  - 查詢優先順序：本地字典 → TWSE/TPEX API → Yahoo 英文名（最後手段）
- ✅ Bug：登出按鈕無效 → 改導向 `/`（顯示 login.html 登入按鈕頁）
- ✅ Bug：Dashboard 看板未顯示「已分析」/風險係數 → `stock_service.py` 合入 `StockAnalysis` 查詢結果
- ✅ Bug：分析報表文字不可見 → `#analysis-content *` 用 `!important` 強制深色主題；剝除所有 inline `style=""`
- ✅ Bug：分析報表 metadata 行洩露（`RISK_PCT: 35...`）→ 補 `TARGET_PRICE:` + 通用 TAG regex；API 端也套 `_clean_html_output`（含舊快取）
- ✅ Bug：Dashboard 風險係數數字有色塊 → `.risk-low/mid/high` 改為 `color`，補 `.risk-fill.*` 的 `background`
- ✅ UI：分析報表護眼優化（`--text-dim: #b0bec8`，`line-height:1.9`，`font-size:15px`，統一 CSS 覆蓋）
- ✅ UI：看板卡片放大（`minmax(360px)` / `min-height:200px` / padding 放大 / 字體 card-name 20px bold）
- ✅ UI：看板卡片依股票數動態調整大小（`adjustGridLayout(count)`：1-2支→520px/300px，3-4→420px/260px，5-6→360px/220px，7-9→300px/195px，10+→260px/175px）
- ✅ 功能：看板卡片顯示當日 OHLC + 收盤價 + 漲跌幅（非同步並行抓取）
- ✅ 功能：Wyckoff 相位 badge 大型化（14px bold，多頭綠/空頭紅/中性橘，分析後即時更新）
- ✅ Bug：AI 分析白背景污染整頁（`<style>body{background:white}</style>` 被注入 innerHTML）
  - 修法：`_clean_html_output` 加第一步驟：剝除 `<style>`、`<head>`、`<html>`、`<body>` 標籤
- ✅ Bug：看板股價未顯示（原因：用 `/data` 端點抓 4 月資料，6 支股並行 = 18 次 Yahoo API，超時失敗）
  - 修法：新增輕量 `/api/market/<symbol>/quote` 端點（只抓 10 日），看板改用此端點
- ✅ 功能：市場資料雙層快取（加 `MarketDataCache` DB 表）
  - `/quote`：伺服器記憶體快取，當日有效，跨 user 共用
  - `/data`：Supabase DB 快取，當日有效，跨 user 共用，Render 重啟不失效
  - 效果：首次訪問股票詳情頁約 3 秒；同日第 2 位 user 訪問同一股票 → 瞬間回傳

**效能與 Bug 修復（2026-05-03）：**
- ✅ Perf：一鍵分析改為 3 並行 worker pool（10 支：~250s → ~90s）；進度條同時顯示 3 支名稱 + 快取命中數
- ✅ Bug：分析中點擊卡片導航 → 剩餘股票全部停止分析
  - 修法：新增 `isAnalyzing` 旗標；`openStockPage()` 在分析期間改為 `window.open(_blank)`，分析繼續在原分頁跑
- ✅ Bug：一鍵分析後部分股票無股價（如 2891）
  - 根因：分析完大量 Yahoo Finance 請求後速率受限，後續 `/quote` 獨立呼叫失敗
  - 修法：`/quote` 端點優先從 `MarketDataCache`（分析時已存 DB）推導 OHLC，完全不再打 Yahoo Finance；僅冷啟動時才 fallback
- ✅ Bug：個股分析中途離開再回來，顯示「點按鈕」而非等待狀態
  - 根因：Flask Gunicorn 繼續執行分析寫 DB，但前端 JS context 已銷毀，回頁後 `loadCachedAnalysis` 在完成前回傳 `{cached:false}`
  - 修法：`runAnalysis()` 啟動時寫 `localStorage`；回頁後偵測到記錄 < 2 分鐘則顯示「分析進行中」+ 每 5 秒輪詢，完成自動顯示；3 分鐘逾時顯示重試按鈕
- ✅ Bug：看板顯示「已分析」藍框，進入個股卻無分析內容
  - 根因：看板用「最新一筆（不限日期）」，詳情頁只查「今日」，日期不一致
  - 修法：`api_get_analysis` 先查今日，找不到 fallback 最新一筆；回傳 `is_today` + `analysis_date`；非今日顯示橘色警示「⚠ 分析日期：YYYY-MM-DD（非今日，建議重新分析）」
- ✅ UI：分析報表分節排版優化（`h3` 加藍色左邊框區塊 + 淡藍底色，margin-top 32px；`li` 行距 6→10px；`p` 間距 10→14px）
- ✅ UI：個人建議區塊 `h3` 改為橘色左邊框區塊（與市場分析藍色區別）
- ✅ UI：分析頁數字方塊放大（label 12→13px，value 22→28px，padding 加大）
- ✅ UI：個股資訊列放大（MA5/MACD/量能 label 11→13px，value 15→17px）

**AI 分析品質優化（2026-05-02）：**
- ✅ 功能：K線型態強化 — `analyze_market_only()` 第二節強制要求逐根說出中文型態名稱（錘子/吞噬/早晨之星等），日K由15根增至20根，max_tokens 2800→3500
- ✅ 功能：李佛摩「等待」原則補強 — 加入轉折點確認（Pivot Point，前高突破/前低跌破）、明確等待條件、三選一行動判斷（立刻可行動/等待確認/不宜行動）
- ✅ Bug：個人操作建議從未顯示 — `stock.js` 僅呼叫市場分析，從未觸發 `/recommend` 端點
  - 修法：`showAnalysis()` 結尾自動掛入 `.recommend-section` 骨架並呼叫 `loadRecommendation()`
  - 市場分析（藍色標題）與個人建議（橘色標題）分兩區塊顯示
- ✅ 功能：個人建議大幅強化（max_tokens 500→1200）
  - 已持有：整體判斷（續抱/加碼/減碼/出場）+ 加碼觸發條件含量能 + 分階段停利 + 具體停損價格
  - 觀察中：進場判斷（立刻可入/等待/不建議）+ 短線介入含量能門檻 + 中線布局條件 + 李佛摩「等什麼確認」
  - `app.py /recommend`：從 `MarketDataCache` 取近5根日K傳給 AI，讓建議更貼近當前盤面
- ✅ UI：`key-point` 重要結論標記（金黃色粗體 + 左側實線條 + 淡金底色）
  - 顏色語意分工：🟡金黃=本節最重要結論（每節限1-2句）/ 🔴紅色=危險停損壓力 / 🟢綠色=支撐多頭 / 🟣紫色=目標價 / 🔵藍色=標題
  - AI prompt 明確限制：每節最多標記1-2句，禁止濫用

---

## 十一、AI 分析架構補充決定（2026-05-02）

### AI Prompt 拆兩段（跨用戶快取的關鍵）

原設計把客觀市場分析和個人建議混在同一個 prompt，無法做到真正的跨用戶快取。
**決定：拆成兩段分開呼叫：**

```
第一段：客觀市場分析（跨用戶完全共用，存 StockAnalysis.market_analysis）
  威科夫骨幹 + 本間宗久K線確認 + 李佛摩時機
  + 風險係數(0-100) + 支撐/壓力 + P&F概念目標價 + 威科夫階段

第二段：個人化建議（各用戶獨立，prompt 短，token 少）
  輸入：第一段結論摘要 + 此用戶的持倉狀態/平均成本/損益
  輸出：
    - 已持有 → 持有/加碼/減碼/出場建議（含停損價）
    - 觀察中 → 現在可入場嗎 / 等什麼條件進場
```

**快取共用規則：**
| 情境 | 第一段 | 第二段 |
|------|--------|--------|
| 觀察中（無個人資料）| 跨用戶共用 | 跨用戶共用 |
| 已持有 | 跨用戶共用 | 各用戶獨立 |

---

### GitHub Actions 批次分析順序（Token 最佳化）

每日 14:30 GitHub Actions 觸發時，**不是按用戶順序，而是按股票重疊性排序**：

```sql
SELECT symbol, COUNT(*) AS user_count
FROM stocks
GROUP BY symbol
ORDER BY user_count DESC
```

重疊最多的股票先分析 → 後面的用戶進來直接吃快取 → 整體 token 最省。

分析完成後寄 Email 通知各用戶（依 `users.email_notify` 決定是否寄）。

---

### Dashboard「一鍵分析全部」

- Dashboard 有「分析全部」按鈕
- 後端先查快取，今日已分析過的股票直接跳過（不重複呼叫 AI）
- 分析進度用 SSE 逐支即時顯示：`分析中 2/10：台積電 ✅ 聯發科 ✅ 旺宏 ⟳...`
- SSE 架構參考舊系統 `web_dashboard/app.py`

---

### 手動觸發兜底

若 GitHub Actions 未自動跑（假日/失敗），用戶可從 Dashboard 手動一鍵觸發，邏輯相同（快取優先，重疊性排序）。

---

## 十二、待確認事項

- [x] GitHub Repo 網址：`https://github.com/Jason690926/investment-system`（私人）
- [ ] 財經新聞來源（計畫用 Google News RSS，待確認）
- [ ] 週報固定跑哪天？（建議週六上午）
- [ ] Render Starter 升級時機（目前仍用 Free 方案）
