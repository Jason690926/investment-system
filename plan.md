# 投資建議書系統 — 重構計畫
> 建立日期：2026-04-30｜更新日期：2026-05-17（週7持續；新增 Bug D / Bug E 架構決策）｜基於兩次訪談決策 + 實作後討論補充

---

## 零、費用與收費規劃（2026-05-03 更新；基準改 18 支）

### 個人使用成本（1人 × 18支股票）

**單日報表（每交易日）**

| 項目 | 用量 | 成本 (USD) |
|------|------|-----------|
| `analyze_market_only` | 18 支 | $0.39 |
| `generate_personal_recommendation` | 18 支 | $0.23 |
| `analyze_taiwan_market_v2` | 1 次 | $0.02 |
| **每日合計** | — | **~$0.64（NT$20.5）** |

**每週費用（5 個交易日）**

| 情境 | 每週 USD | 每週 NT$ |
|------|---------|---------|
| 個股每日分析 × 5 天 | $3.20 | NT$103 |
| ＋ 週報（每週六大盤週報 + 產業指標股） | +$0.20 | +NT$6 |
| ＋ PDF 匯出（已改瀏覽器列印，無 API 成本）| +$0 | +NT$0 |
| **總週費（含週報＋PDF）** | **~$3.40** | **~NT$109** |

**月費（4.4 週）**

| 項目 | 費用/月 |
|------|---------|
| API（含週報、含 PDF） | ~US$15 |
| Render Free 方案 | US$0 |
| **個人合計** | **約 US$15/月（NT$480）** |

> 已套用 2026-05-03 的優化：Prompt Caching + max_tokens 調降（analyze_market_only 3500→2000、analyze_stock_three_masters 3500→2500），預估費用較優化前降低 40-45%。
>
> PDF 匯出在 commit `6a20805` 改為瀏覽器列印方案，零 API 成本。
>
> 假設每交易日都跑分析；若某天沒打開 dashboard 也沒手動觸發，當日 $0。

### 擴大成本結構（N 人使用，每人 18 支）

`analyze_market_only` 跨用戶共用快取，市場面成本不線性；個人化建議仍按 N×18 線性成長：

| 人數 | 預估不重複股票 | API/月 | Render/月 | **總成本** | **每人均攤** |
|------|--------------|--------|-----------|------------|------------|
| 1人 | 18支 | $15 | $0 | **$15** | $15 |
| 3人 | ~36支 | $30 | $7（Starter）| **$37** | $12.3 |
| 5人 | ~54支 | $42 | $7 | **$49** | $9.8 |
| 10人 | ~78支 | $65 | $25（Standard）| **$90** | $9 |

### 收費建議（打平費用）

**建議定價：NT$300/人/月**（不變）

| 人數 | 月收入 | 月成本 | 結餘 |
|------|--------|--------|------|
| 1-2人 | NT$300-600 | NT$480-768 | ❌ 略虧（自補） |
| 3-4人 | NT$900-1,200 | NT$1,184-1,408 | ❌ 略虧（接近打平）|
| 5人+ | NT$1,500+ | NT$1,568 | ±0 打平 |
| 6人+ | NT$1,800+ | ~NT$1,750 | ✅ 開始盈餘 |

- 1-4 人期間（初期測試）自己補貼，差額 NT$100-300/月在可接受範圍
- 5 人起接近打平、6 人正式盈餘
- 若改收 NT$400/人：3 人即打平、4 人盈餘，門檻較友善
- 18 支基準若提高到 25 支，每人月成本 +$3-4；建議自己控管在 20 支內以維持成本可預測

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
週5 ✅：產業週報 + PDF 匯出 + Render Starter 部署
週6 ✅：Bug 1-7 修復 + 酒田五法強化 + 四項分析品質修復（2026-05-07~08）
週7 ✅：K線7項Bug修正 + AI幻覺封鎖 + NEWS即時重生機制（2026-05-11）
週7 ✅：K線特徵程式化標注 + 多空欄位修正（_fmt_bars量能·位置·跳空 + prompt鐵律）（2026-05-12）
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

**Plan A + Plan B + Bug 修復（2026-05-03）：**
- ✅ Plan A：快速結論卡（Quick Summary Card）— 分析報告頂部新增 pill badge 列
  - 方向判斷（▲偏多 / ▼偏空 / —觀望）、風險等級（低/中/高 + 百分比）、撐/壓/目標價
  - `buildQuickSummary()` 函式於 `stock.js`，顯示於 risk-summary 與分析內容之間
  - CSS：`.quick-summary`、`.qs-pill`、`.qs-bull/bear/neutral`、`.qs-risk-low/mid/high`、`.qs-num`
- ✅ Plan B：AI 分析 prompt 格式鐵律
  - 嚴禁散文段落，所有分析以 `- ` bullet 輸出；每條 bullet ≤ 20 中文字
  - 禁用詞：「然而/因此/綜合以上/由此可見/值得注意的是」
  - 每 `###` 小節 3~5 條 bullet + 結尾 1 條 `<span class="key-point">` 結論（全文上限 4 個）
  - 第二節（本間宗久 K 線）必須輸出 HTML table（週K 3根 + 日K 5根各一張）
  - CSS：`#analysis-content table/th/td` 深色主題樣式
- ✅ Bug：6741（上櫃股票）載入失敗
  - 根因：系統一律補 `.TW`，但上櫃股 Yahoo Finance 代號為 `.TWO`
  - 修法：`_resolve_tw_symbol()` — 先試 `.TW`，失敗自動換 `.TWO`；結果 cache 避免重複探測
  - 套用範圍：`get_full_stock_data()`、`get_stock_quote()`、`get_stock_info()`
- ✅ 功能：強制重新分析（`?force=1`）
  - `POST /api/stocks/<id>/analyze?force=1` 跳過今日快取，強制重跑 AI
  - 個股頁「重新分析」按鈕改傳 `force=1`（`runAnalysis(true)`）
- ✅ 功能：重新分析費用保護機制
  - 時間鎖：台灣時間 < 15:00，force 重新分析回傳 429 `CUTOFF|15:00`（盤後資料才有意義）
  - 冷卻期：上次分析距今 < 4 小時，回傳 429 `COOLDOWN|HH:MM`
  - 無今日快取（新股票）：不受時間鎖限制，隨時可分析
  - UI：15:00 前「重新分析」按鈕 disabled 顯示「15:00 後可重新分析」；觸發限制時 toast 提示並恢復現有報告
  - ⚠️ **測試模式中**：時間鎖 `< 0`、冷卻 `< 0`（測試完需還原 `< 15` 和 `< 4 * 3600`）
- ✅ Fix：派發等威科夫階段字體過小
  - 改用 `.risk-box-phase` CSS class（`flex:0 0 auto`、`font-size:22px`），不與數字 box 競爭寬度
- ✅ Fix：操作建議顯示原始 Markdown 符號（`**`、`###`、`---`）
  - 根因：`action_template` 用 Markdown 語法，AI 跟著輸出，CSS 無法渲染
  - 修法：`action_template` 全改純 HTML（`<h3>`、`<ul><li>`、`<p>`、`<strong>`）
  - prompt 明確禁止：`** / ### / ---` 等 Markdown，違者輸出無效
- ✅ 測試工具：Dashboard 新增「🗑 清快取」按鈕（橘色，測試用）
  - `POST /api/admin/clear-today-cache`：刪除**所有日期**的 `StockAnalysis` 記錄（含歷史）
  - Bug fix：原本只刪今日 → 有歷史分析的股票因 fallback 仍顯示舊資料，看起來沒清乾淨
  - 根因：`get_user_stocks()` 用 `func.max(analysis_date)` 不限日期；`api_get_analysis` 也有 fallback，清今日後舊資料自動補上
  - 按後自動重整看板，再按一鍵分析才是真正從零開始
  - ⚠️ **測試完需移除**：`dashboard.html` 按鈕、`dashboard.js` 函式、`app.py` 端點

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

## 十二、Dashboard 自訂排序（2026-05-03）

### 需求
新加入的股票預設追加在最後，用戶想自訂順位（例如把新股拉到第 3 位置）。

### 互動方式：拖拉
- 卡片直接拖到想要的位置，一次到位（5-15 支特別順手）
- 桌面：mouse drag
- 手機：long-press 觸發 drag
- 引入 SortableJS（CDN，~12KB gzipped）

### 資料模型
- `stocks` 表新增 `display_order INTEGER`（NULL = 用 created_at 排序）
- 預設值 NULL；只有用戶手動重排後才寫入
- 撈單 ORDER BY：`COALESCE(display_order, 999999), created_at`
  - 沒設過順位的維持原本「按建立時間」行為
  - 設過順位的排在最前，按 display_order 數字小到大

### API
- `PATCH /api/stocks/reorder`（body: `{order: [stock_id, stock_id, ...]}`）
- Server 收完整新順序的 id list，依序寫 display_order = 0, 1, 2, ...
- 只允許重排自己的股票（user_id 匹配）

### 前端
- `dashboard.html`：grid 引入 SortableJS init（CDN）
- 拖拉結束（onEnd）→ 收集 DOM 順序的 stock_id → `PATCH /api/stocks/reorder`
- 樂觀更新：先動 UI，失敗才 toast 提示（不 reload）
- chip 過濾（holding/watching）切換時，順序仍按 display_order

### 邊界情況
- 跨類拖拉：同一 grid 內可任意排，分類過濾不影響底層順序（過濾只影響顯示）
- 重整：依 display_order 持久化、F5 順序保留
- 新增股票：display_order 不主動寫入，靠 COALESCE fallback 排在最後
- 刪除股票：不重整其他人的 display_order（因為 ORDER BY 用的是相對大小，缺 id 無妨）

### 測試重點
- 桌面拖拉到不同位置 → 重整後順序保留
- 手機 long-press → 拖到新位置 → 順序保留
- 過濾 chip 切換不影響相對順序
- 新加入股票排在最後

---

## 十三、Email 分享 PDF 報表（2026-05-03）

### 需求
1 人使用情境，產出報表後可手動把 dashboard 報表寄給朋友（PDF 附檔）。
收件人需可被記憶，下次寄不用重打 email。

### 設計：客戶端產 PDF
- 為何不用 server 端 WeasyPrint：commit `6a20805` 已移除（Render 中文字體/啟動慢）
- 改用 `html2pdf.js`（CDN ~100KB）在前端用既有 `/print-report` 頁面渲染 PDF
- PDF Blob 上傳到 server，server 用既有 `EMAIL_SENDER` SMTP 寄出

### 資料模型
新表 `email_contacts`：
| 欄位 | 型別 | 說明 |
|------|------|------|
| id | INT PK | |
| user_id | INT FK users | 屬於誰的通訊錄 |
| email | VARCHAR(256) | 收件人 |
| name | VARCHAR(64) nullable | 顯示名（選填）|
| last_used_at | DATETIME | 排序：最近用過的優先顯示 |
| created_at | DATETIME | |

UNIQUE (user_id, email) 防止同一 email 重複入庫。

### API
- `GET /api/contacts` → 列出我的聯絡人（按 last_used_at DESC）
- `POST /api/share/dashboard-pdf`（multipart）
  - `pdf`: PDF 檔案
  - `emails`: JSON list `["a@x.com", "b@y.com"]`
  - server 把 PDF 當附檔寄給每個 email（BCC 隱藏其他收件人）
  - 寄完後新 email 自動入 `email_contacts`、舊 email 更新 last_used_at

### UI
- Dashboard 標頭加「📧 分享」按鈕（在「⚡ 一鍵分析」旁）
- 按下→ Modal：
  - 已記憶聯絡人：chip 列表（點擊加入收件人）
  - 收件人輸入框：可手打新 email，逗號分隔多人
  - 已選收件人：以 chip 顯示（可移除）
  - 「確認寄送」→ 顯示「產生 PDF 中…」→「寄送中…」→「✓ 已寄出」

### 信件內容
- Subject: `【{你的名字}】{YYYY/MM/DD} 投資建議書`
- Body（純文字）：
  ```
  您好，
  這是 {你的名字} 的本日投資建議書 PDF，請見附件。
  本報表為自動化系統產出，僅供參考，不構成投資建議。
  ```
- Attachment: `投資建議書_{YYYYMMDD}.pdf`

### 邊界情況
- PDF 太大（>10MB）：先 client-side 限制每次最多 20 支股票（dashboard 本來就 1-15 支左右，極端情況才會超）
- SMTP 失敗：toast 顯示失敗的收件人 email
- 朋友未回信：通訊錄保留無妨，使用者自己手動移除（v1 不做「移除聯絡人」UI，下版加）

---

## 十五、K線型態識別 + 平日新聞報表（2026-05-07~08）

### 功能概述

**K線型態 Rule-based 偵測（`candlestick.py`）**

- `detect_from_bars(daily_bars)` 將 enriched data 格式轉 DataFrame 後呼叫 `detect_patterns()`
- 偵測型態清單（截至 2026-05-08）：

| 類型 | 型態 |
|------|------|
| 單K（跳空優先）| 跳空上漲/下跌 |
| 單K（特殊十字）| 蜻蜓十字（強底部）/墓碑十字（強頂部）/長腳十字（強不確定）/十字星 |
| 單K（實體）| 錘子/吊人/射擊之星/倒錘子/大陽線/大陰線 |
| 雙K | 多頭吞噬/空頭吞噬/烏雲蓋頂/曙光初現/平頭頂/平頭底 |
| 三K | 早晨之星/黃昏之星 |
| 三K（酒田正規）| 三白兵（開盤在前根實體內+影線≤30%）/三黑鴉 |
| 三K（酒田五法）| 三空上升/三空下降（連三跳空）|
| 五K（酒田五法）| 上升三法/下降三法（大實體→整理→突破）|
| 多K（酒田五法）| 三山頂/三川底（`_find_local_peaks/troughs`，lookback=40，間距≥5根，高度±3%，最後峰/谷需在近15根內）|

- 跳空（gap_up/gap_down）優先判斷
- 每個 pattern 含 `name`, `type`, `desc`, `strength`, `candle_count`
- `_MULTI_CANDLE` 為模組層級常數（不在函式內重建）

**2026-05-11 Bug 修正（7項，commit `5b0fd26`）：**

| # | 型態 | 修正內容 |
|---|------|---------|
| 1 | 三山頂/三川底 | 加 `bars_since_peak/trough <= 15` 時效性檢查，舊高低點型態15根後自動靜音 |
| 2 | `_find_local_peaks/troughs` | `>=` / `<=` 改嚴格 `>` / `<`，排除平台頂底假峰 |
| 3 | 大陽線 | 加 `not gap_down`，與 desc「無跳空缺口」一致 |
| 4 | 三白兵 | 補第一根（i-2）上影線 ≤ 30% 實體（原只查後兩根）|
| 5 | 三黑鴉 | 補第一根（i-2）下影線 ≤ 30% 實體（原只查後兩根）|
| 6 | 早晨之星 | 第一根需實體 > 50% 振幅（大陰線）+ 第三根需實體 > 50%（大陽線）|
| 7 | 黃昏之星 | 同上，第一根需大陽線，第三根需大陰線 |

**`label_bars(bars) -> dict`** — 對每根 K 棒輸出 `{date: 型態名稱}`，供 `_fmt_bars()` 在 K 棒文字後附加 `▶型態` 標注，AI prompt 鐵律禁止更改。

**`calc_pnf_target(bars, lookback, current_price) -> float | None`** — 等幅量度（Measured Move）：
- `target = base_high + (base_high - base_low)`
- 波動率 > 35%（趨勢段）→ 縮至 4 根找緊箱體
- `current_price < base_high × 0.85` → 回 None（尚未接近突破點）

**量能門檻程式計算（`ai_analyzer_v2.py`）**
- `_vol_breakout = vol_5avg × 1.5`（突破確認門檻）
- `_vol_spring = vol_5avg × 1.2`（Spring/測試縮量門檻）
- 兩個值注入 dynamic_block 為鎖定數值，AI 禁止更改

**批次儲存型態歷史（`run_daily_report.py`）**

- `_save_patterns(db, symbol, detected_patterns, close_price, today)`
  - 預取既有 pattern_name 為 set，避免 N+1，使用 UniqueConstraint 防重複
- `_backfill_patterns(db, symbol, daily_bars, today)`
  - 回填 return_3d/5d/10d（bisect.bisect_right，O(log N)）
  - 條件：detected_date <= today - 3天 且 return_10d IS NULL

**DB 新資料表**

| 表名 | 用途 |
|------|------|
| `daily_market_summary` | 每日財經新聞摘要 + 明日方向 HTML，PK = summary_date（TW 時區）|
| `pattern_history` | K線型態偵測歷史，含 return_3/5/10d 事後回填，UQ (symbol, detected_date, pattern_name) |

**平日/週末報表切換（`app.py` + `print_report.html`）**

見第十六節週末視窗設計。

**QuoteCache 股價查詢（`app.py`）**

- `/print-report` 查 QuoteCache 改用 `max(cache_date)` subquery 取最近一筆
- 修前：`filter cache_date == today` → 14:30 前批次未跑 → 股價欄空白
- 修後：永遠有資料（與 DailyMarketSummary 同模式）

### 成本影響

- 每日批次多1次 `analyze_daily_news()` 呼叫（max_tokens=800）≈ +$0.01/日
- `analyze_market_only()` 日K從20→30根，token 略增，估計 +5-8%
- `/api/news/regenerate` 手動觸發 ≈ +$0.01/次（只在測試/清快取時用）

---

## 十七、AI 幻覺封鎖 + NEWS 即時重生（2026-05-11）

### 問題：「1778點/突破3萬點」持續出現

根因分層：

| 層 | 問題 | 修法 |
|----|------|------|
| 第一層 | `analyze_taiwan_market_v2()` 無任何歷史數字禁令 | 新增【數據鐵律】，列舉「1778點」「突破3萬點」「史高」為禁止用詞 |
| 第二層 | `analyze_daily_news()` 鐵律不夠明確 | 補「嚴禁引用歷史特定漲跌事件數字」+ 新聞含此類描述需核實才引用 |
| 第三層 | 清快取不清 `DailyMarketSummary`，NEWS 永遠顯示舊 batch 結果 | `api_clear_today_cache` 一併刪 `DailyMarketSummary`；新增 `/api/news/regenerate` 即時重呼叫 AI |

### /api/news/regenerate 端點設計

```python
# app.py
@app.route('/api/news/regenerate', methods=['POST'])
@login_required
def api_regenerate_news():
    # 1. 呼叫 get_tw_news_rss(15)
    # 2. 呼叫 get_global_markets() 取 TWII 即時行情
    # 3. 呼叫 analyze_daily_news(news, twii_price, twii_change_pct)
    # 4. 刪今日 DailyMarketSummary，寫入新結果
```

### dashboard.js 清快取流程（更新後）

```
clearTodayCache()
  → POST /api/admin/clear-today-cache  （刪 StockAnalysis + DailyMarketSummary）
  → POST /api/news/regenerate           （重抓 RSS + AI 重生成，5-15秒）
  → loadStocks()                        （重整看板）
```

### K線 30 項測試套件（`tests/test_candlestick.py`）

| 測試類別 | 項目 | 驗證內容 |
|---------|------|---------|
| `TestBug2PeakDetection` | 4項 | 嚴格 `>` 偵測峰谷，平台頂不算峰 |
| `TestBug1SanshanFreshness` | 4項 | `bars_since_peak <= 15` 時效性 |
| `TestBug3DaYangGapDown` | 3項 | 大陽線需排除 gap_down |
| `TestBug45ThreeSoldiersCrowsFirstCandle` | 4項 | 三白兵/三黑鴉首根影線 ≤ 30% 實體 |
| `TestBug67StarPatterns` | 7項 | 早晨/黃昏之星體型要求 > 50% 振幅 |
| `TestRegressionNormalPatterns` | 8項 | 錘子/射擊之星/十字星/吞噬正常觸發不誤觸 |

---

## 十六、週報觸發邏輯 + 週末視窗（2026-05-08）

### 核心設計：週末視窗 = 週五 14:00 ~ 週一 09:00（台灣時間）

不自動排程，一鍵分析按鈕是唯一入口。

### 週末視窗判斷（`isWeeklyWindow()` in `dashboard.js`）

```js
const tw = new Date(Date.now() + 8 * 60 * 60 * 1000); // UTC+8
const wd = tw.getUTCDay();   // 0=Sun 1=Mon ... 5=Fri 6=Sat
const h  = tw.getUTCHours();
return (wd === 5 && h >= 14) || wd === 6 || wd === 0 || (wd === 1 && h < 9);
```

### 一鍵分析行為

| 時間 | 行為 | 按鈕文字 |
|------|------|---------|
| 週一 09:00 ~ 週五 14:00 | 只跑個股分析 | ⚡ 一鍵分析 |
| 週五 14:00 ~ 週一 09:00 | 個股 + 週報並行 | ⚡ 一鍵分析（含週報） |

週報：`POST /api/weekly-report/generate` 先射出（背景 threading），個股同時 3-worker 跑，~90s 後均完成。

### PDF 顯示切換（`app.py show_weekly`）

```python
show_weekly = (
    (wd == 4 and h >= 14) or   # 週五 14:00+
    wd in (5, 6) or            # 週六、週日
    (wd == 0 and h < 9)        # 週一 09:00 前
)
```

- `show_weekly=True`：§MARKET 大盤週報 + §INDUSTRY 產業指標 + 各股分析
- `show_weekly=False`：§NEWS 每日財經新聞 + 各股分析

### `week_end` 修正（`run_weekly_report.py`）

```python
days_to_friday = (today.weekday() - 4) % 7
week_end = today - timedelta(days=days_to_friday)
```

任何執行日均算出本週五（Friday=0天, Saturday=1天, Sunday=2天, Monday=3天偏移）。

### 分析日邊界統一（`_analysis_day_tw()`）

三個檔案共用同一邏輯（平日 14:30 後 → 今日；其他 → 往前找最近工作日）：

```python
def _analysis_day_tw():
    TW = timezone(timedelta(hours=8))
    now_tw = datetime.now(TW)
    wd = now_tw.weekday()
    after_close = now_tw.hour > 14 or (now_tw.hour == 14 and now_tw.minute >= 30)
    if wd < 5 and after_close:
        return now_tw.date()
    day = now_tw.date() - timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day
```

| 檔案 | 修改點 |
|------|--------|
| `app.py` | 三個分析端點（`api_get_analysis`/`api_analyze_stock`/`api_recommend_stock`）改用 helper；原 `dt_date.today()` 在 UTC 伺服器台灣 08:00 就翻日 → 08:00~14:30 快取失效 |
| `modules/stock_service.py` | `get_user_stocks()` 改由精確日期篩選（`analysis_date == analysis_day`），取代原本 `func.max(analysis_date)` 不限日期 |
| `run_daily_report.py` | `is_cached_today` / `cache_market_analysis` 改用 TW date 保持一致 |

**看板卡片狀態效果：**

| 時間 | `analysis_day` | 快取存在？ | 看板卡片 |
|------|---------------|----------|---------|
| 14:30 前 | 昨日 | ✅（昨天已分析）| 顯示昨日風險係數 |
| 14:30 後 | 今日 | ❌（今天尚未跑）| 全部「尚未分析」灰框 |
| 14:30 後分析完 | 今日 | ✅ | 顯示今日風險係數 |

視覺提示：14:30 後看板自動出現空白卡，使用者按一鍵分析即可。

### GitHub Actions 狀態

- `daily_report.yml`：schedule 已停用，保留 `workflow_dispatch`（可手動觸發）
- `weekly_report.yml`：schedule 已停用，保留 `workflow_dispatch`（備用）
- 主要入口：Dashboard 一鍵分析按鈕

---

## 十四、待確認事項

- [x] GitHub Repo 網址：`https://github.com/Jason690926/investment-system`（私人）
- [x] 財經新聞來源：Google News RSS（已實作）
- [x] 週報觸發時機：週五 14:00 一鍵分析自動含週報（已實作）
- [ ] Render Starter 升級時機（目前仍用 Free 方案）

---

## 十八、K線特徵程式化標注（2026-05-12）

### 根本問題

AI 看到 `▶大陽線` → 填「看漲」；看到 `▶大陰線` → 填「看跌」；看到 `▶十字星` → 填「觀望」。  
prompt 有「陽線（收>開）、陰線（收<開）」速查表，直接給了 AI 機械式的紅→漲/綠→跌映射。  
違背本間宗久原則：單根顏色不等於方向，十字星的含意取決於它在高位還是低位。

### 修法核心：特徵 = 量能 · 位置 [· 跳空]（程式計算，AI 只能抄）

**`_fmt_bars(bars, label, n, pattern_labels)` — commit `e4bec98`**

每根K棒輸出新增 `【特徵=X·Y[·Z]】`：

| 維度 | 計算方式 | 分類值 |
|------|---------|--------|
| 量能 | vol / bars[-20:] 平均量 | 放量(>1.5x) / 縮量(<0.7x) / 均量 |
| 位置 | (close - range_low) / (range_high - range_low)，range 取 bars[-20:] | 極高位(≥0.85) / 高位(≥0.65) / 中段(≥0.35) / 低位(≥0.15) / 極低位 |
| 跳空 | open vs prev_close ±1% | ·跳空高開 / ·跳空低開 / （空字串，不顯示）|

輸出範例：
```
2026-05-12  O=320 H=325 L=315 C=322  量=2150張  【特徵=放量·高位·跳空高開】  ▶大陽線
2026-05-11  O=310 H=312 L=308 C=309  量=450張   【特徵=縮量·中段】            ▶十字星
```

### Prompt 修正

| 位置 | 舊 | 新 |
|------|----|----|
| `analyze_market_only` table 表頭 | `<th>多空</th>` | `<th>特徵</th>` |
| table 範例值 | `<td class="bull">看漲</td>` | `<td>放量·高位</td>` |
| K棒速查表 | `陽線（收>開）、陰線（收<開）` | 移除（根本錯誤來源）|
| 十字星速查 | `十字星（開收相等/猶豫）` | `十字星（開收相等/高位→頂部訊號·低位→底部訊號·中段→觀望）` |
| 第二節 bullet | — | 新增「K線序列：依特徵欄量能·位置變化說明動能」|
| `analyze_stock_three_masters` | `說明多空含意` | `結合【特徵=...】量能·位置解讀含意（禁止只看紅/綠）` |

**特徵欄鐵律（加入 prompt）：**
> `⚠️ 【特徵欄鐵律】table 的「特徵」欄必須直接抄 K棒資料中 【特徵=...】 的值，禁止自行判斷，禁止只因陽線/陰線填寫看漲/看跌。`

### 測試

37 項全過（含 7 項 P&F 穩定性測試），`_fmt_bars` smoke test 驗證輸出正確。

---

## 十九、Bug D — 個股 vs 大盤同期表現對比

> ✅ **2026-05-17 已實作**（commit `095ea7a`，採最小版）：`data_fetcher.get_index_daily_closes` + `ai_analyzer_v2._market_rs_block`/`_twii_close_on_or_before`，注入兩分析函式 dynamic_block；TWII 失敗/bar 不足不注入；`tests/test_market_rs.py` 10 case 全綠。待用戶 AI 重跑實機驗證。下為原始決策記錄。

### 問題本質

AI 看個股 K 棒/量能時，無法區分「個股獨立訊號（alpha）」與「大盤連動（beta）」。
範例：大盤 TWII 五日 −2.0%，個股五日 −2.4% → AI 寫「個股破位走弱、空方訊號」，
實際只是貼著大盤走的 beta 連動，扣掉大盤後個股相對只弱 0.4pp，並非獨立利空。
反向亦然：大盤大漲帶動個股跟漲，AI 誤判為個股突破強勢。

### 方案評估（三選一）

| 方案 | 內容 | 資料需求 | 維護成本 | AI 驗證成本 | 結論 |
|------|------|---------|---------|------------|------|
| **最小版** | dynamic_block 注入 TWII 同期 change% + 相對強度 + 1 行鐵律 | TWII 日 K（news pipeline 已抓 `^TWII`，commit `7ee7950` 已有 `last_date`/freshness）| **0**（無新 DB、無回填、無排程）| ~$1.2（一次市場面重跑驗證）| ✅ **採用** |
| 中等版 | 加產業同期表現對比 | 需 industry classification（TWSE 產業別映射表 + 逐股分類 + 自建產業指數）| 中（映射表需維護、新上市股漏分類）| ~$1.2 | ⏸ 暫不做 |
| 廣版 | RS Rating（IBD 式相對強弱評級）| 需全追蹤股 1 年歷史回填 + 每日持續維護排程 | 高 | ~$1.2 | ⏸ 暫不做 |

### 決策：採最小版

**理由：**
1. **80/20**：核心痛點是「AI 把 beta 當 alpha」。最小版用「個股同期 change% vs 大盤同期 change% → 相對強度（pp）」直接解掉，捕捉約 80% 分析價值，成本/複雜度約 5%。
2. **資料零增量**：TWII 已在 news pipeline 抓取且有 freshness check；只需取同 lookback 窗口（5/20 日）對齊個股日期，無新 DB 表、無回填作業、無排程。
3. **與個人系統規模相稱**：1–18 支個人系統，RS Rating 的 1 年回填 + 每日維護不成比例；產業分類缺可靠免費資料源且需長期維護映射表。
4. **成本紀律**：月預算 $15。最小版除一次性 ~$1.2 驗證外無經常性成本，符合「修改 AI 程式碼前先用 DB 既有 raw 輸出本機推演」紀律。

### 修法設計（最小版）

- **資料層**：新增 helper 取 `^TWII` 日 K（複用 `modules/data_fetcher.py` `^TWII` path），與個股 `daily_bars` 依日期對齊，算 5 日 / 20 日窗口 Δ%。窗口取個股 bars 同期間，避免交易日不齊。
- **計算層**：相對強度 `rs = stock_chg_pct − twii_chg_pct`（單位 pp），分 5 日 / 20 日兩組。作為**鎖定數值**注入 dynamic_block，比照 `_vol_breakout`/`_vol_spring` pattern（AI 禁止更改）。
- **Prompt 鐵律（新增 1 行）**：
  > `⚠️【大盤對比鐵律】判斷個股強弱前先扣除大盤同期漲跌幅；個股與大盤同向且幅度相近時，不得歸因為個股獨立訊號（beta 連動非 alpha）。相對強度欄為程式精確計算，禁止自行推估。`
- **dynamic_block 輸出範例**：
  ```
  【大盤對比】個股5日 +3.2% vs TWII5日 +1.1% → 相對強度 +2.1pp（跑贏大盤）
            個股20日 −4.0% vs TWII20日 −5.5% → 相對強度 +1.5pp（抗跌）
  ```

### 涉及範圍

| 檔案 | 修改點 |
|------|--------|
| `modules/data_fetcher.py` | 視需要補一個 TWII 日 K 取得 helper（若現有 `^TWII` 取法只回單根，需擴成可取 lookback bars）|
| `modules/ai_analyzer_v2.py` | dynamic_block builder 注入相對強度鎖定值 + 大盤對比鐵律 |
| `tests/` | 新增測試：日期對齊、窗口 Δ% 計算、TWII bars 不足/缺漏的 fallback、相對強度正負號 |

### 測試重點

- 個股與 TWII 交易日不齊（個股停牌/新上市）時對齊邏輯不爆 index
- TWII fetch 失敗 → dynamic_block 不注入大盤對比區塊（誠實 > 錯誤，比照 `7ee7950` twii freshness pattern）
- 相對強度正負號與「跑贏/抗跌/落後」文字對應正確

### 未來升級路徑

若日後規模擴大或用戶要求產業輪動視角，再評估中等版（產業分類）；RS Rating 僅在多用戶/多股且願負擔回填維護時才考慮。屆時回此節更新。

---

## 二十、Bug E — 空方/賣空進場點與下行目標

> ✅ **2026-05-17 三 commit 全實作**：E-1 `6c5afa5`（calc_pnf_target direction 參數）、E-2 `86c10f4`（prompt 方向判斷 + DIRECTION tag + 雙向 P&F）、E-3 `8f4f943`（pill/badge direction-aware）。**零-migration 設計**：DIRECTION 持久化/渲染改由 `phase_to_direction(威科夫相位)` 反推，不新增 StockAnalysis 欄位（AI 的 DIRECTION 本質即相位之函數）。**待用戶決策**：`generate_personal_recommendation` 仍純多方、不在本節議定範圍，未擅自擴大。待用戶 AI 重跑實機驗證。下為原始決策記錄。

### 問題本質

系統目前只實作上漲方向：突破箱頂 → 等幅量度向上 target。
威科夫派發/下跌相位、本間頂部反轉型態、李佛摩跌破前低時，AI 只能說「不宜行動」，
無法給「跌破箱底放空進場 / 回測壓力線 / 向下等幅目標」的空方建議。

### 開工優先討論題（CLAUDE.md 指定）→ 兩項決策

#### 決策 1：`calc_pnf_target` 雙方向參數 vs 鏡像函式

**決定：同一函式加 `direction='long'|'short'` 參數（預設 `'long'`）。**

理由：
- 等幅量度邏輯本質對稱：
  - long target = `box_top + (box_top − box_bottom)`
  - short target = `box_bottom − (box_top − box_bottom)`
- Filter A / Filter B（commit `00f5159` 剛精修完）的「全歷史回溯找有效箱」掃描迴圈兩方向共用，僅比較運算子與 target 公式正負號翻轉。
- 鏡像函式 `calc_pnf_target_short` 會**整段複製**剛修好的掃描/過濾邏輯 → 雙倍維護、兩份易 drift（這函式才剛謹慎修過，最忌再複製）。
- 預設 `direction='long'` → 既有所有 caller 與 9 個既有測試零改動，向後相容。

參數化點：
| 邏輯 | long | short |
|------|------|-------|
| 突破/跌破檢查（Filter A）| `cur > box_top × 1.02` | `cur < box_bottom × 0.98` |
| target 公式 | `box_top + (box_top − box_bottom)` | `box_bottom − (box_top − box_bottom)` |
| 目標有效性（Filter B）| `target > cur × 1.02` | `target < cur × 0.98` |
| 全歷史掃完無有效箱 | 回 None | 回 None（對稱）|

#### 決策 2：AI prompt 單一框架識別方向 vs 拆 long/short 兩套

**決定：維持單一三宗師框架，prompt 內先判結構方向再套對應招式（不拆兩套 prompt）。**

理由：
- **成本**：CLAUDE.md 明示「拆兩套後者更貴」，月預算 $15 緊。拆 prompt = 近乎雙倍呼叫或大幅加長 prompt。
- **框架本就對稱**：三宗師空方招式是既有多方招式的鏡像，分析素材已存在於同一心智模型：
  - 威科夫：已有派發/下跌相位定義，只需在這些相位**給空方建議**而非「不宜行動」
  - 本間：`candlestick.py` 已偵測黃昏之星/吊人/空頭吞噬等頂部反轉型態
  - 李佛摩：已有 pivot 概念，跌破前低 + 5 日均下彎即空方 pivot
- 現行 prompt 缺陷是**預設多頭**（突破箱頂→等幅向上）。修法：prompt 先以威科夫相位判結構方向（吸籌/上漲→多方招式；派發/下跌→空方招式；中性→觀望），輸出方向標籤 + 對應 target/停損語意。單次市場面呼叫，僅空方分支規則使 prompt 略長，token 大致持平。

### 修法設計（拆三 commit，依成本由低到高排序）

**Commit E-1（純邏輯，零 AI 成本，先做）**
- `modules/candlestick.py:calc_pnf_target` 加 `direction` 參數，參數化上表四點
- 新增 short 方向 regression 測試（鏡像既有 long 9 case 的關鍵情境）
- 既有 long 測試須全綠（向後相容驗證）

**Commit E-2（AI prompt，~$0.6–1.2 一次重跑驗證）**
- `modules/ai_analyzer_v2.py`：
  - prompt 補「先判結構方向」段，移除多頭預設假設
  - 三宗師各補空方對應招式說明（威科夫派發給空方時機、本間頂部型態觸發、李佛摩跌破前低 pivot）
  - 標準化輸出 `DIRECTION: long|short|neutral` tag（比照既有 `RISK_PCT:`/`TARGET_PRICE:` tag 機制，供前端解析、`_clean_html_output` 一併處理）
- **成本紀律前置（必做）**：撈 DB 既有「派發/下跌相位」股票的 `StockAnalysis` raw 輸出，本機跑 cleanup/render pipeline，驗證新 prompt 的空方輸出（`DIRECTION:short` tag、空方目標 pill）能正確被既有清洗+渲染管道處理，再讓用戶 AI 重跑

**Commit E-3（前端，零 AI 成本）**
- `app.py:_render_one_block` pill 區依方向動態切換：
  - short：撐位 → 「空進」（跌破箱底放空進場）、**壓力 → 「空停」（上方=回補停損）**、目標 → 「空標」（下行目標）
  - long / neutral：維持現狀（撐/壓/目標）
  - ⚠️ **更正**：本節原文「壓力→空方目標、撐位→空方停損」方向相反；財務正確為「壓力在上=空方停損、向下 target=空方目標」，實作以更正版為準
- dashboard 卡片加方向標籤（多/空/觀望）；漲跌色維持台股慣例（紅漲綠跌），空方分析無需翻色（下跌股顯綠本就正確）
- 風險係數 direction-aware 重構（**關鍵 nuance**）：現行風險係數 = 逆勢程度（0=順勢/100=逆勢）。順勢放空（下跌段做空）應為**低風險**而非高風險。故評分須改為「建議動作對抗主結構的程度」而與 long/short 無關 — 空頭排列 +20 僅適用於「在空頭排列中做多」；「在空頭排列中放空」反而應低分。與既有「多頭排列 −20」對稱對齊。

### 涉及範圍總表

| 檔案 | Commit | 修改點 |
|------|--------|--------|
| `modules/candlestick.py` | E-1 | `calc_pnf_target` 加 `direction` 參數 |
| `tests/test_candlestick.py` | E-1 | short 方向 regression + long 向後相容 |
| `modules/ai_analyzer_v2.py` | E-2 | prompt 方向判斷 + 三宗師空方招式 + `DIRECTION` tag |
| `app.py` | E-3 | `_render_one_block` pill 動態標籤、`_clean_html_output` 處理 `DIRECTION` tag |
| `static/js/dashboard.js` + CSS | E-3 | 方向標籤 badge |
| 風險係數計算（`ai_analyzer_v2.py` 或 scoring 處）| E-3 | direction-aware 評分表 |

### 測試重點

- E-1：short target 公式正負號；跌破箱底回溯找有效箱；既有 long 9 case 零退化
- E-2：派發相位股 raw 輸出本機 pipeline 驗證；`DIRECTION` tag 被 `_clean_html_output` 正確剝除/解析；neutral 時不誤觸空方語意
- E-3：pill 標籤隨 `DIRECTION` 切換；風險係數「順勢放空=低分、逆勢放空=高分」對稱性

### 排序理由

E-1 純確定性邏輯先行、可單測、零成本；E-2 才花 AI 預算且前置本機推演；E-3 前端零成本收尾。把便宜可驗證的工作做完再花 AI budget。

---

## 二十一、AI 角色 / 鐵律架構 — persona 選擇性併入（2026-05-18）

### 緣起

用戶提出「系統好像沒設角色」，並草擬一份完整「專業股票分析師」persona（四理論整合 + 固定五步驟 + 強制六項輸出 + 交易原則 + 決策優先順序）。

### 評估結論：不當全系統 persona、不取代現有 block

現況分兩層：
- **AI 端角色已存在**：7 個 AI 函式各有任務角色（三宗師分析師 / 操作顧問 / 財經新聞分析師 / 產業分析師 / 週報分析師）。刻意分工，非冗餘。
- **真實 bug 類別**是「全域鐵律散落且 drift」（CLAUDE.md 史例：2026-05-12 Bug 2 週報函式漏歷史幻覺鐵律），非 persona 散落。

用戶草稿三個問題（不可當全系統 persona / 取代現有 block 的理由）：
1. **多任務破壞**：強制五步驟+六項輸出套到 `analyze_daily_news`/`analyze_industry`/`generate_personal_recommendation` 會壞（逼新聞畫箱體等）。
2. **回退 Bug E 雙向**：草稿「跌破箱底=轉弱訊號」是隱性偏多，現有 `static_block:380-385` 已是「派發/下跌→DIRECTION=short 完整空方框架」的進階版，取代 = 把 E-2/E-3 打回原形。
3. **缺程式計算鐵律 + 一條對自動化有害**：草稿無第一行結構化標記、無 ▶型態/P&F/量能門檻禁改鐵律、無數據鐵律；且「若資訊不足主動要求數據」在批次自動跑會印出「請提供更多K線資料」。

### 決定：選擇性併入技術 static_block（用戶 2026-05-18 拍板）

只把草稿**三個真正加分、現有 block 沒明寫**的元素，併入**僅** `analyze_stock_three_masters` + `analyze_market_only` 的 `static_block`。**不動** news / 產業 / 週報 / 個人建議函式。

| 加分元素 | 併入方式 |
|----------|----------|
| 箱型理論（Darvas Box）顯式 | 列為第四框架，箱頂/箱底**雙向**描述（long 突破箱頂進場 / short 跌破箱底進場），**禁寫「轉弱」**以保留 Bug E 雙向 |
| 決策優先順序階梯 | 定位為**進場時機仲裁**（趨勢李佛摩 > 結構箱型 > 訊號K線 > 確認量價），**不奪威科夫的方向裁決權** |
| 交易原則 | 沒突破不追價／沒止損不進場／風險優先於報酬 — 加入輸出紀律要求 |

### 核心調和：威科夫定方向 / 李佛摩階梯定時機（用戶接受）

衝突：現有 `static_block:392`「威科夫月K相位為最高骨幹」 vs 草稿「趨勢（李佛摩）第一」。風險評分整套（`static_block:394-405`）建立在威科夫定 DIRECTION 上，直接併入會給 AI 對立指令。

調和（兩者在不同層，非競爭）：
1. **威科夫月K相位 → 決定「做哪邊」**（long/short/neutral）：保留為結構方向裁決者，`DIRECTION` 與風險評分**不動**。
2. **李佛摩階梯 → 決定「何時動手」**：方向定後，趨勢 > 結構 > 訊號 > 確認 排序**進場時機**衝突仲裁。

白話：威科夫說往哪打，李佛摩階梯說何時扣扳機。補上現有 block 缺的「進場時機衝突仲裁」，零回退。

### 涉及範圍

| 檔案 | 修改點 |
|------|--------|
| `modules/ai_analyzer_v2.py` | `analyze_stock_three_masters` static_block(~370)、`analyze_market_only` static_block(~625) 併入三元素 + 調和段 |

`DIRECTION` 結構化標記、風險評分原則、▶型態/P&F/量能門檻程式計算鐵律、結構方向判定段 — **全保留逐字不動**。

### 驗證（依 CLAUDE.md AI 修改紀律）

撈 DB 既有 `StockAnalysis` raw（含 short/派發股），本機跑 `_clean_html_output`/render pipeline，確認新 static_block 不破壞第一行結構化標記解析、DIRECTION/pill 零退化，再請用戶 AI 重跑。鐵律性質為「約束」非「創意重寫」，驗證 = 確認該禁的沒出現、該有的標記都在。

---

## 二十二、Bug F — NEWS 自 5/12 凍結 + 12h 新聞窗口（2026-05-19）

### 緣起 / 根本診斷（systematic-debugging）

用戶 5/18 20:35 產生報表，NEWS chip 顯示 `2026-05-12`（6 天前）。非 AI 幻覺/freshness（前修過），是**架構操作斷層**：

`DailyMarketSummary`（NEWS 來源）全系統只有兩個產生路徑：
1. `run_daily_report.py` 14:30 批次 — **cron 已停用**（`.github/workflows/daily_report.yml:5-6` 自 2026-05-03 註解，1 人手動模式）
2. `/api/news/regenerate` — **只有「🗑 清快取」按鈕觸發**（`dashboard.js:698`）

用戶日常習慣「一鍵分析 → 開報表」中 `analyzeAll()`（`dashboard.js:300`）**完全不碰 `DailyMarketSummary`**。最後一次清快取在 5/12 → NEWS 從此凍結。`print-report` 誠實取最新一筆（`app.py:983-985`）= 5/12。設計原假設「14:30 批次每天跑」，cron 停用後該假設破裂、`analyzeAll` 未補。

### 決定（用戶 2026-05-19 拍板）

**選項 1（一鍵分析併入刷新 NEWS）+ 新增 12h 新聞窗口要求。** 不做選項 2（print-report 過期警示）、不做選項 3（重啟 cron，違背手動省成本初衷）。

| # | 決定 | 理由 |
|---|------|------|
| F-1 | `get_tw_news_rss` pubDate 窗口 **48h → 12h** | 用戶要求「財經分析必須是報表產生時間前 12 小時新聞才列入」。窗口相對於 regen 呼叫時刻，因「一鍵分析→立即開報表」習慣，regen 時刻 ≈ 報表時刻 |
| F-2 | `analyzeAll()` 非週末視窗 → **背景並行**射 `/api/news/regenerate` | 比照既有週末視窗自動射週報 pattern（`dashboard.js:312-319`）。維持用戶單按鈕習慣不變 |
| F-3 | **每次一鍵分析都重生 NEWS**（不加 skip-if-exists 守衛） | 唯有每次重生才能保證「報表產生時間前 12h」。`analyze_daily_news` 為單次 ~800 token 呼叫（~$0.01），相對 18 股 ~$0.6 微不足道；`/api/news/regenerate` 既有 delete+insert(today) 本就冪等覆寫，無 DB 膨脹 |
| F-4 | regen 失敗 → toast 告警 + analyzeAll 續跑（不阻斷個股） | 比照週報 pattern 容錯 |

**殘留風險（用戶已知、未選選項 2）：** regen 失敗時 print-report 仍 fallback 最新一筆（可能舊）、無過期警示。常態（regen 成功）正確；僅 RSS/AI 故障時退化，靠 toast 提示。

**12h 窗口副作用：** 盤前/隔夜/連假新聞可能很少甚至 0 筆 → 摘要偏薄。屬用戶明示取捨（誠實精簡 > 補舊文）；`analyze_daily_news` 既有空 news 容錯不變。

### 涉及範圍

| 檔案 | 修改點 |
|------|--------|
| `modules/data_fetcher.py` | `get_tw_news_rss` cutoff `hours=48`→`12` + docstring |
| `static/js/dashboard.js` | `analyzeAll()` 非週末分支射 `/api/news/regenerate`（背景並行，結束前 await）+ 進度文案 |

`/api/news/regenerate` 端點本身**不動**（已冪等 + 已有 12h 無關的 freshness/TWII 注入邏輯）。

### 驗證

- pytest 全綠 + `node -c dashboard.js`
- `get_tw_news_rss` 12h 邏輯：mock RSS pubDate 邊界（12h 內保留 / 12h 外剔除 / pubDate 解析失敗保留）
- 用戶 AI 重跑：一鍵分析後 NEWS chip = 當日、內容為近 12h；regen 失敗時 toast 出現

---

## 二十三、中長期波段框架 — 穩定論點 + 程式鎖定錨點（2026-05-19）

### 緣起
用戶 5/18 報表回饋：(1) 缺雙向支撐壓力（做多/做空各自停損點/加碼點）(2) 太短期翻來覆去「今天宜/不宜」(3) 不做當沖，要 2週-1個月波段。

### 根因
`ai_analyzer_v2.py:359/365/720` prompt 寫死短線(1-5日)/今日時機；支撐壓力 AI 每日推斷 → 漂移 → 論點漂移。

### 三骨架決策（用戶 2026-05-19 拍板）
| # | 決策 |
|---|------|
| D1 | 穩定論點 + 失效價位（失效未破論點不變）|
| D2 | 程式鎖定錨點（復用 candlestick.py，非 AI 推斷）|
| D3 | neutral → 誠實不操作 + 雙向條件觸發 |

方案 A：新增 `calc_swing_levels()`（純加性，復用 `_find_local_peaks/_troughs`+`calc_pnf_target`）+ 三函式注入錨點+波段框架取代短線段+穩定鐵律。零 DB schema、零經常性 AI 成本。

### 涉及
`candlestick.py`(+calc_swing_levels)、`ai_analyzer_v2.py`(+_dual_swing_block，analyze_stock_three_masters/analyze_market_only/generate_personal_recommendation)、`tests/test_swing_levels.py`。`analyze_market_only` 守「不含操作建議」邊界只做語言+錨點+鐵律。

### 驗證
pytest 127 全綠；DB raw 推演證標記/解析端零退化；⚠️ AI 行為須用戶重跑(~$0.6)驗 6 點（見 spec §4c）。

---

## 二十四、投資建議書 15 Bug 修法（2026-05-20）

### 緣起
用戶提供 2026-05-19 22:09 報表 PDF（22 頁、15 支股），審視後找出 15 個不符常理 / 市場建議書規範的 bug。spec 見 `docs/superpowers/specs/2026-05-20-report-quality-fixes-design.md`。

### 致命三件（會直接誤導決策）
- **#1 持股部位處理建議缺位**：持股多單虧損中、分析給「建新空單」、無「停損出場/減碼/續抱」
- **#2 Pill ↔ 內文價位錯位**：short 股 pill「空進=支撐線、空標=目標」邏輯互換，家人照 pill 行動會「進場=目標」
- **#3 K 棒重複/缺漏**：5 支同日重複列、技嘉日 K 只 3 根

### 用戶拍板架構決策
| # | 決策 | 否決的替代 |
|---|------|-----------|
| B1c | DB 加 `stop_loss` 欄位（1 migration），support/resistance/target 永遠中性語意 | B1a 同欄位語意隨方向變（schema 髒）、B1b 加 3 欄位（migration 多） |
| Personal | print PDF 全部包含（持股 + 觀察）| 只 holding 加 personal |

### 修法分組
| Commit | 組 | 內容 | 需 AI 重跑 |
|--------|----|------|-----------|
| 1 | D | 型態誤判（label_bars 多根組合型態去重 + 平頭頂改絕對 tick + 月 K skip 3+ 根型態）| ❌ |
| 2 | C | data_enricher daily_bars dedup + _fmt_bars 缺漏 fallback | ❌ |
| 3 | H | print_report.html `--font-mono` 加 Noto Sans TC fallback | ❌ |
| 4 | G | calc_pnf_target Filter C + 月 K 表注入 | ❌ |
| 5 | B | StockAnalysis 加 `stop_loss` 欄位、DB 寫入改用 swing_levels 鎖定值、pill mapping 對齊（撐/壓/目標/空停）| ✅ |
| 6 | A | print_report.html 加 personal 區塊 + generate_personal_recommendation 加「方向衝突診斷」holding 模板 | ✅ |
| 7 | E+F | NEWS 末段觀察池總覽 + 三宗師結論強制 schema + 量能門檻方向感知 + 量價術語 qualify + 禁「放量失敗」 | ✅ |

### 涉及
`modules/candlestick.py`（D + G）、`modules/data_enricher.py`（C）、`modules/ai_analyzer_v2.py`（C + G + B + A + E + F）、`modules/models.py`（B：stop_loss 欄位）、`app.py`（B：pill mapping）、`templates/print_report.html`（A + H）、`tests/`（多 case 新增）。

### 驗證
- pytest 既有 127 + 新增（D 9+、C 4+、G 3+）全綠
- DB 8 筆既有 raw 推演零退化（commit 1-4 + commit 5 long 部分）
- ⚠️ commit 5/6/7 需用戶 AI 重跑(~$0.6)驗：
  1. short 股 pill「空進在上、空停最高、空標最低」邏輯通
  2. 多單持有 + 派發分析的「方向衝突警示 + 出場條件 + 續抱條件」三 bullets 都有
  3. NEWS 末段出現觀察池方向總覽
  4. 三宗師結論強制有「## 操作框架」段 + 進場/停損/目標 bullets
  5. short 「等待條件」用「跌破量門檻」非「突破量門檻」字眼
  6. 無「放量失敗」、「月 K 早晨之星」等矛盾表述


---

## 二十五、反指標觀察 + 方向/時機分離（2026-05-20）

### 緣起
用戶 5/19 22:09 報表 12 支股 short、5/20 開盤 8 支大反彈（華星光 +7.46%、矽力 +5.19%、臻鼎 +7.47%、合晶 +4.32%、大聯大 +9.68%）。用戶問是否反指標 / 系統 bug。

### 重新判讀（嚴格波段紀律）
不是「方向錯」，是「進場條件未達 vs 已觸發」混淆：
- 進場觸發 + 方向對：1 支（東捷 -9.85%）
- 進場觸發 + 停損觸發：2 支（華星光過 551、臻鼎過 415-420）
- 進場條件未達：9 支（紀律下根本不該進場）
- 多方：瑞軒 對、撼訊 錯、微星 未到位

**真風險 = 用戶誤把「等回測壓力放空」讀成「現在可以放空」**，急著進場踩雷。

### 根因
1. **「不預設多頭」rule 無對稱「不預設空頭」**（`ai_analyzer_v2.py:474`）
2. **派發/下跌相位「必須給空方框架」義務化**（Bug E 2026-05-17 加），AI 無餘裕標 neutral
3. **缺「結構方向 vs 短期時機」分離教育**，AI 把「波段空方」說成「明日可放空」
4. **缺「進場區距現價過近」程式警示**，華星光 5/19 收 523 / 進場區 551 只差 5.4%、臻鼎差 1.6% → 反彈一日就觸發停損

### 4 條修法（A+B+D+E，C 列下次）
| # | 修法 | 涉及 |
|---|------|------|
| A | dynamic_block 注入「大盤前日漲跌」+「個股 5 日累跌」+ prompt 超賣警示鐵律 | ai_analyzer_v2._dynamic_block / static_block |
| B | 派發/下跌段改寫「結構為空方但 1-3 週內可能反彈」，分離方向 vs 時機 | static_block |
| D | 加「不預設空頭」對稱條款 + 允許 neutral 餘裕 | static_block（移除「派發必須給空方框架」義務） |
| E | 程式計算「進場區距現價%」< 3% 標警示 | _dual_swing_block + prompt 引用 |

C（分批進場提示）列下次考慮（屬風控教育，非根本邏輯）。

### 驗證
- pytest 全綠 + py_compile
- 純 prompt + 加性 helper，無 DB schema 變動
- ⚠️ 需用戶 deploy + AI 重跑驗（~$0.6）：
  1. 報表派發/下跌相位 prompt 明確「結構空方 + 1-3 週可能反彈」分離
  2. 大盤前日跌 >1.5% 個股出現「短期超賣」警示
  3. AI 在派發+超賣場景敢標 neutral（非機械 short）
  4. 進場區距現價 < 3% 出現「進場區極接近現價」警示

---

## 二十六、威科夫派發判定門檻 — 結構閘（2026-05-21）

### 緣起
5/20 報表 15 支判 10 支放空，5/21 隔日 14 支上漲。根因：`ai_analyzer_v2.py` 的威科夫月K相位**完全由 AI 自由判斷**，無量化錨點，AI 系統性偏空——多月大漲股只因「最近一個月收陰 + 量縮」就被打成派發 / 假突破 / 頂部結構。

### 用戶校準基準
多月大漲後**單月收陰且量縮，相位仍是「上漲」（上漲中的回測），方向 long**。臻鼎（去年12月 142 → 5月 439，+200%，僅 4 月收一根陰線）= 上漲中回測，非派發。

### 方案 B（已定案）：程式算結構事實 + prompt 雙閘
- **結構閘（硬護欄）**：程式從 12 月K + 日線 MA60 算出【月線結構客觀事實】，`結構未轉弱` 時硬禁止 AI 標派發 / 再派發 / 下跌。
- **量價證據閘（AI 判）**：即使結構閘允許，AI 仍須列具體派發訊號，不得僅憑「單月收陰+量縮」。

### 已定案參數
- 月K結構：最近 **3 根已收盤**月K（`bars[-4:-1]`），高低點序列 → 升 / 跌 / 轉折 / 橫
- 連續月陰線 **≥2** → 結構轉弱
- 季線用**日線 MA60**（現價在上/在下）
- `結構未轉弱` = 現價在 MA60 上 且 月K結構∈{升,橫} 且 連續月陰線≤1
- `結構已轉弱` = 現價跌破 MA60 或 月K結構=跌 或 連續月陰線≥2
- 不對稱：本案只收緊空方誤判，不阻擋多方相位（積累/再積累/上漲）

### 週K 動能（唯讀欄位，不參與閘門）
- 週K 負責確認層 / 時機層（本間+李佛摩），不裁相位 → 結構閘維持月K
- 加唯讀欄位「週K近期動能（升/跌/橫）」+「守穩支撐（是/否）」，供李佛摩時機層用
- `守穩支撐` = 最近 3 根週K收盤離散 <3% 且 收盤墊高（收盤基準，非最低點）
- 量價證據閘新增正向型態：連續週K守支撐 + 回測量縮 + 反彈量增 = 吸籌/再積累 SOT，偏多

### 實作位置
- `data_enricher.py`：新增 `compute_monthly_structure()` helper
- `ai_analyzer_v2.py`：兩個市場分析函式各注入 `structure_block`；`static_block` 結構方向判定段加結構閘規則

### spec
`docs/superpowers/specs/2026-05-21-wyckoff-phase-gate-design.md`

### 驗收（需 deploy + 重跑 ~$0.6）
- pytest 全綠
- 臻鼎/合晶/瑞軒/南亞科（月K升、現價在 MA60 上）不再標派發
- 晶心科/創惟（真下跌）仍可標空方 → 驗證閘門不對稱、未誤殺真派發

---

## 二十七、待辦：Dashboard 迷你 K 線圖快取漏洞（2026-05-21 發現，下次修）

### 現象
用戶 5/21 進 dashboard，15 支觀察股中 9 支「近20日K」迷你圖空白（采鈺/南亞科/微星/華擎/撼訊/東捷/合晶/大聯大/瑞軒），重整無效。即時報價 OHLC 數字正常顯示，只有迷你圖空白。

### 根因（已查證，非當日 deploy 造成）
- 迷你圖資料只來自 DB `MarketDataCache.daily_bars`。
- `MarketDataCache` **只在使用者點進個股詳情頁**（`app.py:570` `/api/market/<symbol>/data` cache miss）時才寫入，且 key 為 `cache_date=today`。
- 9 支空白股 = 從未被點進詳情頁 → 無 `MarketDataCache` → spark 空。
- 6 支「正常」股 = 早在 5/03~5/17 被點過 → 有舊 `MarketDataCache` → 畫得出來但是 2-3 週前舊 K 線。
- `_resolve_quote`（`app.py:419`）post-close 先查當日 `MarketDataCache`，全 15 支皆 miss（無今日資料）→ spark 一律退回「最近一筆 `MarketDataCache`」→ 有舊的才畫得出。
- 驗證：live 測 `get_full_stock_data('6789.TW')` 回 daily_bars 60 根正常 → 抓取程式沒問題，純粹是快取從未寫入。

### 更大的問題
今日（5/21）14:30 批次，15 支**沒有一支**更新到 `MarketDataCache` → 連「正常」6 支看到的都是舊圖。整個 dashboard 迷你圖機制等於沒在維護。

### 修法方向（下次走 spec→plan→subagent 流程）
- **A.** 每日 14:30 批次跑完後，順便刷新所有持股/觀察股的 `MarketDataCache`（每天自動新）
- **B.** dashboard 載入時某股無當日 `MarketDataCache` → 即時抓一次並寫入（新加的股也立刻有圖）
- 建議 A+B 都做。

---

## 二十八、報表 cross-check 後續：4 bug 修復 + 優化1/2（2026-05-22）

用戶以 5/22 股價交叉核對 5/21 報表，揪出 4 bug + 3 優化。

### 已完成（4 bug，commits `4052618..dc4d434`）
Bug A 週/月K退化單日棒+日期位移、B pill 撐壓撞名、C 型態標籤日期、D 距峰值回落數字打架。
spec `docs/superpowers/specs/2026-05-22-kbar-spurious-bar-fix-design.md`。優化3=Bug A2 已含。

### 優化1/2（用戶拍板「走 spec」）
- **優化1 持倉部位建議**：虧損持股判 neutral 時報表只說「區間不操作」，缺部位指引。
  `analyze_market_only` 加 `holding_ctx` 參數，holding 時 static_block 加「六、持倉部位建議」
  段（neutral 持股也給續抱/減碼價位），零額外 AI 呼叫。
  spec `docs/superpowers/specs/2026-05-22-holding-position-advice-design.md`。
- **優化2 強勢突破追蹤**：波段框架對放量突破前高的強勢股（東捷漲停那種）只會說「等回測」。
  新增程式純函式 `_strong_breakout_state`（現價 > swing range_high 且量 ≥ 突破門檻），
  long 操作框架加條件式「追進」分支（並陳「回測進場（保守）」）。
  spec `docs/superpowers/specs/2026-05-22-strong-breakout-tracking-design.md`。

實作計畫：`docs/superpowers/plans/2026-05-22-holding-advice-breakout-tracking.md`（5 Task TDD）。
兩者皆 prompt 行為改動，需 deploy 後燒 ~$0.6 重跑驗證。

---

## 二十九、5/22 週報 cross-check 後續：10 bug 修法（2026-05-24）

用戶提供 5/22 20:35（週五晚週末視窗）持股分析報告 PDF（27頁、14股），完整核對抓出 10 bug。

### Bug 清單（嚴重度排序）

#### P0
- **S1 進行中週/月 K 棒 close 滯後一天** — 全 14 檔 K 表：日K 5/22 close ≠ 進行中週/月 close，後者均 = 前一交易日（5/21）日 close。
  根因：`data_enricher._chart_json_to_df` Bug A 只剔除 Yahoo spurious 即時棒，沒把當日 daily K roll-up 進進行中週/月棒。
- **W1 大盤週報雙重收盤值** — Page 1 第一段「收報 42267.97」VS 週 OHLC「收 41368.21」同頁打架。
  根因：`twii_enriched.price` = daily close 末根 = 42267，weekly_bars 末根 close 受 S1 影響 = 41368，prompt 兩源並陳。
- **I1 週末視窗 NEWS 缺失** — Page 2 INDUSTRY「⚠️ 本次無新聞資料，改依市場背景推斷」。
  根因：`dashboard.js:315` 週末視窗分支只觸發 `/api/weekly-report/generate`，沒呼叫 `/api/news/regenerate`（daily 路徑有，週路徑漏）+ `run_weekly_report.py` RSS 抓空時無 DB fallback。

#### P1
- **S2 撼訊 pill 內文 0.3 元差距** — 內文「P&F 概念目標：74 元」、pill「目標 73.7」。
  根因：`_dual_pnf` 用 `:.0f` 給 AI，DB 存 float 73.7；兩條路徑量化粒度不同。
- **S3 觀察股第六節洩漏** — 12 檔觀察股中技嘉/南亞科/瑞軒 3 檔錯誤輸出「六、持倉部位建議」（25% 違規率）。技嘉/南亞科給完整觀望持有；瑞軒輸出「dynamic_block 未出現【持倉提示】，本節跳過」洩漏內部欄位名。
  根因：純 prompt gate 無 post-process safety net；瑞軒洩漏屬 instruction-following failure。
- **S4 P&F 概念目標重複/巢狀** — 矽力/南亞科/華星光 3 檔出現「P&F概念目標：P&F概念目標：—（...）元（等幅量度）」三層巢狀。
  根因：`_dual_pnf` 注入含 label 字串，prompt 模板又強制「P&F概念目標：[數值]元」，AI 把 label 整段當 [數值] 代入。
- **I2 INDUSTRY 句尾截斷** — Page 2「⚠️ 這些股票」沒寫完。
  根因：`get_industry_indicator_stocks` `max_tokens=800` 過小。

#### P2
- **W2 大盤週量能描述語意反** — 「本週成交量 25621.8 張，明顯低於 5 日均量 5124.4 張」，25621/5≈5124 是同件事。
  根因：注入欄位 `vol`/`vol5` 是日量/日均量，週報函式沿用，label 卻叫「本週末量」。
- **W3 三週累計收盤區間描述錯** — 「三週累計收盤區間 41000~42400」，42400 是 5/11 週高不是收盤。
  根因：prompt 沒分離「收盤區間」vs「高低區間」欄位，AI 自由命名。
- **S5 「結構已轉弱 + 再積累」UX 衝突** — 撼訊結構閘旗標「結構已轉弱」但 phase 標「再積累」。
  根因：gate_hint 只禁「結構未轉弱」標派發/再派發/下跌，反向「結構已轉弱」沒禁標 積累/上漲/再積累。

### 修法總覽（6 commits，TDD 流程）

| Commit | Bugs | 檔案 | 修法核心 |
|--------|------|------|---------|
| C1 | S1+W1 | `modules/data_enricher.py` | 剔除 Yahoo spurious 後，用當日 daily K roll-up 合成進行中週/月棒（high=max, low=min, close=最新日 close, volume=sum, ts=本週/本月起始日）。S1 修好後 W1 自動對齊。 |
| C2 | S2+S4 | `modules/ai_analyzer_v2.py` `_dual_pnf` | (a) 統一 rounding：<100 取 1dp、≥100 取 0dp；(b) round 後同步寫回 `result['target_pnf']`（單一 SoT）；(c) prompt placeholder 改注入完整成品句「P&F概念目標：73.7元（等幅量度）」/「P&F概念目標：—（尚未接近突破點）」，AI verbatim 引用。 |
| C3 | W2+W3+I2 | `modules/ai_analyzer_v2.py` 週報 | (a) `analyze_weekly_taiwan_v2` 從 weekly_bars 算「本週週量」+「近 5 週均量」relabel；(b) 加「最近 3 週收盤區間/高低區間」兩欄；(c) `get_industry_indicator_stocks` max_tokens 800→1500。 |
| C4 | S5 | `modules/ai_analyzer_v2.py` `_structure_block` | gate_hint「結構已轉弱」加「相位限定派發/再派發/下跌/不明，禁標 積累/上漲/再積累」。 |
| C5 | S3 | `modules/ai_analyzer_v2.py` + `run_daily_report.py` | **雙層防護**：(a) prompt 改「禁止輸出『六、』標題」；(b) 新增 `_strip_section_six` post-process，對 `is_holding=False` 強制 regex 砍 `### 六、` 後整段。 |
| C6 | I1 | `static/js/dashboard.js` + `run_weekly_report.py` | (a) dashboard.js 週末視窗分支也呼叫 `/api/news/regenerate`（與日報對稱）；(b) `run_weekly_report.py` 在 RSS 抓空時降級到 DB 最近 NEWS（避免 RSS 故障害全 fallback）。 |

### 設計決策（已拍板 2026-05-24）

1. **S1 採合成進行中棒**，不採「只警示不合成」：用戶看週/月 close 必須包含當日，否則 5/22 週五尾盤產的週報毫無意義。
2. **S3 採雙層防護**（prompt + post-process）：5/22 12 檔觀察股有 3 檔違規（25% 失效率），純 prompt 信不過。
3. **I1 走 regen + DB fallback**：regen 是主路徑，RSS 偶發故障時 DB 最近 NEWS 兜底，避免整份 INDUSTRY 全推斷。

### 驗收（需 deploy + 重跑 ~$0.6）
- pytest 全綠（預計 208 + 約 25 新 test → 230+）
- 重跑 5/22 報表：
  1. 每股進行中週/月 close = 當日日 close（晶心科週/月 close 240，非 230）
  2. 大盤週報「本週收盤」與週 OHLC 一致、量能 label 寫「週量」非「日均」
  3. INDUSTRY 區出現真實新聞或 DB fallback 標示，無「本次無新聞」全推斷分支
  4. 觀察股零洩漏第六節
  5. 撼訊 pill「目標 73.7」與內文「73.7 元」一致；矽力/南亞科/華星光無 P&F 重複/巢狀
  6. 撼訊結構旗標「結構已轉弱」時 phase 不會標「再積累」

spec：`docs/superpowers/specs/2026-05-24-weekly-report-bugs-design.md`
plan：`docs/superpowers/plans/2026-05-24-weekly-report-bugs.md`

---

## 三十、5/25 cross-check：結構閘漏洞 + 強勢突破門檻過嚴（2026-05-25）

用戶提供 5/22 20:35 持股分析報告 PDF（14 股）+ 5/25 週一收盤截圖（14支12漲2跌、4支漲停），cross-check 找到 2 個結構性問題（§二十九 10 bug 沿用未驗，故先濾掉同類議題）。

### Bug 清單

#### P0
- **A 結構閘「結構轉折中」漏洞 — 東捷 8064 short 誤判** — 報表判 short「派發訊號初現」、空停 143.5，5/25 漲停穿空停（高 145.5）。
  月K 序列（完整）：12月陽→1月陽→2月陰→3月放量多頭吞噬→4月放量大陽 +64%→5月實體 16% 高位震盪，本是強勢上漲剛確立。
  根因：`_structure_flag` 三層判定「已轉弱 > 未轉弱 > 轉折中」是 fall-through，未涵蓋「強勢上漲」。`_hl_trend(2~4 月)` 因 3 月低點 43.30 < 2 月低點 44.80 → 不嚴格升序 → 「轉折」 → fall through「結構轉折中」，gate_hint「可標派發，須附量價證據」允許 AI 標派發。

#### P1
- **B 強勢突破狀態被自己拉高的均量打死** — 5/25 漲停 4 支股票中只有合晶（6182）被認定「強勢突破成立」並標「追進+回測並陳」；矽力（6415，續強勢）/瑞軒（2489，一字漲停封死）雖突破前高但被打回「不宜追進」。
  根因：`_strong_breakout_state` 條件 2 用 `volume_5d_avg_zhang`（含今日的 5 日均量），剛突破爆量那一根被計入均值，造成第 2 根強勢延伸時量自然回落就被自己上一根拉高的均值打死。瑞軒 5/21 爆量 96K → 5 日均飆到 ~49.6K → 突破門檻 74.4K → 5/22 量 29K 不足；矽力 5/19 高位空頭吞噬 16.7K 拖高 5 日均，5/22 12K 也不足。

### 修法總覽（2 commits，TDD 流程）

| Commit | Bug | 檔案 | 修法核心 |
|--------|-----|------|---------|
| D1 | A | `modules/data_enricher.py` `_structure_flag` + `compute_monthly_structure` | `compute_monthly_structure` 新增兩欄位：`monthly_close_strict_up_3`（最近 3 根月 close 嚴格上揚）、`monthly_bull_count_6`（近 6 根月陽月數）。`_structure_flag` 加新參數，「結構未轉弱」條件擴充：原 (升/橫 + 在上 + 連續陰≤1) **或** 強勢上漲否決 (在上 + 連續陰≤1 + (close 嚴格上揚 ≥3 根 或 近6月陽月數≥4))。 |
| D2 | B | `modules/ai_analyzer_v2.py` `_strong_breakout_state` | 改為 3 條件擇一即可：(A 現有) 現價 > range_high 且 今日量 ≥ 5日均×1.5（量價齊揚）；(B 新增) 現價 > range_high × 1.05 且 近 5 日收盤都 > range_high（突破後續強勢）；(C 新增) 現價 > range_high 且 今日漲幅 ≥ 9% 且 close ≥ high × 0.99（一字漲停封死型突破）。 |

### 設計決策

1. **Bug A 採方案 b（旗標分支）**，不採方案 a（鬆綁 `_hl_trend`）：旗標分支影響面可控、`_hl_trend` 其他用途不受波及；不採方案 c（只動 prompt）：軟約束 AI 不一定照辦；不採方案 d（資料層+prompt 雙管齊下）：改動過多超出此次必要。
2. **Bug B 採方案 C+（3 條件擇一）**，不採方案 a（量基準改不含今日）：a 線性修法但仍會被 4 日窗口內歷史爆量打死；不採方案 b（純放寬倍數）：可能讓平常小量推升也標突破。
3. **C+ 中的條件 C（一字漲停封死）是討論加進來的**：原 C 方案兩條件無法涵蓋瑞軒 5/22 一字漲停（開=低=50.7、高=收=51.4、漲幅 9.83%）。台股實務中一字漲停的縮量是「買單封死無法成交」而非動能不足，威科夫框架下屬「籌碼鎖定後續攻」訊號，應該被認定強勢突破。

### 驗收（需 deploy + 重跑 ~$0.6）

- pytest 全綠（預計 239 + 約 10 新 test → 250+）
- 重跑 5/22 報表 + 對照 5/25 收盤實機驗：
  1. **Bug A**：東捷 8064 結構旗標應為「結構未轉弱」（close 嚴格上揚 48.85→63.30→104.0），方向應標 long 而非 short
  2. **Bug B-B**：矽力 6415 應被認定強勢突破狀態（562 > 456×1.05=478.8 且 5/18~5/22 5 日 close 都 > 456）
  3. **Bug B-C**：瑞軒 2489 應被認定強勢突破狀態（51.4 > 48.85 且 漲幅 9.83%≥9% 且 close=high=51.4）
  4. **回歸不退化**：合晶 6182 仍維持強勢突破成立（量價齊揚 A 條件）

spec：`docs/superpowers/specs/2026-05-25-structure-flag-and-breakout-fix-design.md`
plan：`docs/superpowers/plans/2026-05-25-structure-flag-and-breakout-fix.md`

---

## 三十一、報表「建議動作」明確化：pill + 第五節結構化（2026-05-25）

§三十 cross-check 過程中，用戶指出「報表的建議字（動作）夠用比較明確方式標記出來嗎？」— 目前散落在第五節長段落、第六節（HOLD only）裡，沒有單一字眼可瞄一眼。決議 A+B+C 一起做。

### 問題陳述

當前報表上「建議性質的字」分散在 3 個層級：
1. **頂部 Pill**（已視覺化）：方向 / 威科夫 / 風險 — 是「看法」/「階段」/「衝突量化」，**不是動作**
2. **第五節「操作框架」**（純 AI 寫長文字）：「進場價 X~Y」「停損」「目標」「不宜追進」「等回測」「強勢突破追蹤」等
3. **第六節「持倉部位建議」**（只 HOLD 股）：「整體判斷：續抱 / 觀望持有 / 減碼 / 出場」

問題：對 WATCH 股，動作建議藏在第五節長文字裡，用戶要往下讀完才知道「該等回測 vs 該追進」；對 HOLD 股則要讀到第六節；對「強勢突破成立」狀態完全沒視覺化（只在第五節文字裡）。

### 修法總覽（A+B+C 整合）

#### A. 頂部加「建議動作」pill

新 pill 字典（決定樹已對齊 2026-05-25）：

| status | 條件 | pill 字 |
|--------|------|---------|
| **WATCH long** | 結構閘 = 結構已轉弱 | 🔴 不宜進 |
|  | `_strong_breakout_state` = True | 🟢 追進 💪 |
|  | 現價 > range_high 但未強勢突破（量未到）| 🟡 等突破 |
|  | 現價 在 entry_zone 內 | 🟢 進場區可佈 |
|  | 現價 > entry_zone 上緣（mid 以上）| 🟡 等回測 |
|  | 其他 / neutral | ⚪ 觀望 |
| **WATCH short** | 結構閘 = 結構未轉弱 | ⚪ 觀望（不宜空）|
|  | 現價 > 空停 | 🔴 論點作廢 |
|  | 現價在空進區內 | 🔴 分批佈空 |
|  | 現價 < 空進區下緣 | 🟡 等反彈佈空 |
| **HOLD** | 現價 < 持倉停損 | 🔴 出場 |
|  | 結構閘 = 結構已轉弱 | 🟠 減碼 |
|  | `_strong_breakout_state` = True | 🟢 加碼 💪 |
|  | 現價在 entry_zone 內 + 量增 | 🟢 加碼 |
|  | 結構閘 = 結構轉折中 + 現價 < entry_zone 中點 | 🟡 觀望持有 |
|  | 一般多頭持倉 | 🟢 續抱 |

#### B. 強勢突破標記 💪 emoji 合進 A pill

不另開獨立 pill（避免三個 pill 並排太雜）。當 `_strong_breakout_state=True` 時，A pill 旁邊加 💪 emoji：
- `🟢 追進 💪`（WATCH long）
- `🟢 加碼 💪`（HOLD）

#### C. 第五節「操作框架」改程式渲染（C2，類 K 表注入）

prompt 用 `[[OPERATION_FRAMEWORK]]` placeholder，程式 post-process 替換為結構化區塊：

```
五、操作框架
─────────────────────
建議動作：🟡 等回測 進場
進場區：214.50 ~ 283.75 元（觸發須量 ≥ 157,892 張）
停損：214.50 元 — 跌破即論點作廢
目標：—（待突破 353 元有效突破後重算）
─────────────────────
```

強勢突破成立版（多一段「追進」並陳）：
```
建議動作：🟢 追進 💪
強勢突破追蹤：現價 69.9 > 前高 59.30 元、量達門檻 → 可順勢追進
  追進停損：59.30 元（跌回前高即假突破）
回測進場（保守）：52.10 ~ 55.70 元
停損：52.10 元 — 跌破即論點作廢
目標：— 元
```

short 版 / neutral 版各自獨立模板（spec 詳述）。

### 修法總覽（多 commit，TDD 流程）

| Commit | Bug | 檔案 | 修法核心 |
|--------|-----|------|---------|
| E1 | A | `modules/ai_analyzer_v2.py` + `tests/test_decide_action.py` | 新增 `_decide_action(status, direction, structure_flag, swing_levels, breakout, price, ...)` 純函式 + ~12 TDD case 覆蓋 WATCH long/short + HOLD 完整決定樹 |
| E2 | C | `modules/ai_analyzer_v2.py` + `tests/test_operation_framework.py` | 新增 `_render_operation_framework(action, direction, swing_levels, breakout, vol_threshold, ...)` 純函式 + ~6 TDD case 涵蓋 long/long強勢/short/neutral 4 種模板 |
| E3 | A+C 整合 | `modules/ai_analyzer_v2.py` | analyze_market_only / analyze_stock_three_masters / generate_personal_recommendation prompt 加 `[[OPERATION_FRAMEWORK]]` placeholder；分析完成後 post-process：呼叫 `_decide_action` 得 pill、呼叫 `_render_operation_framework` 替換 placeholder、寫入 result dict + StockAnalysis DB |
| E4 | A DB | `modules/models.py` + `migrate_add_action_pill.py` | StockAnalysis 加 `action_pill = Column(String(32))` + migration 腳本（ALTER TABLE IF NOT EXISTS） |
| E5 | A UI | `static/js/dashboard.js` `buildCard()` + `templates/print_report.html` + `static/css/app.css` | dashboard `card-status-row` 加 actionChip（dirChip → wyckoffChip → riskChip → actionChip 順序）；PDF `stock-block-header` 加 action pill；CSS 樣式（綠/黃/紅/灰/橘 5 色 + 💪 emoji 標記 class）|

### 設計決策

1. **B 不獨立 pill**：三個（方向 / 威科夫 / 風險）已是視覺極限，再加兩個太雜。emoji 💪 合進 A 是視覺平衡的折衷。
2. **C2 程式渲染（非 C1 AI key-value）**：§二十九 S3 證明純 prompt 約束會洩漏 25%（觀察股第六節 12 檔有 3 違規）。第五節改程式生產相同等級的格式穩定性。
3. **action_pill 存 DB 而非每次重算**：dashboard 顯示 14+ 卡片時若每張都即時跑 `_strong_breakout_state` 需要 daily_bars 60 根 + swing_levels 計算，效能差。存字串 1 次寫多次讀。
4. **A pill 在 status row 第 4 位**（最後）：左→右順序為 方向 → 威科夫 → 風險 → 建議動作，視覺由「看法」漸進到「動作」，符合閱讀直覺。

### 驗收（需 deploy + 重跑 ~$0.6）

- pytest 全綠（預計 249 + 約 18 新 → 267+）
- migration `migrate_add_action_pill.py` 跑過 + DB 欄位存在
- 重跑 5/22 報表 + 對照 5/25 收盤實機驗：
  1. 14 支股每張卡片頂部出現 action pill（4 chip 並排）
  2. 漲停 4 支：合晶/瑞軒/矽力 pill = 🟢 追進 💪、東捷（修 §三十 後）pill = 🟢 追進 💪 或 進場區可佈
  3. 南亞科 pill = 🟡 等回測（5/22 現價 310.5 遠超進場區）
  4. 撼訊 pill = 🟢 進場區可佈（現價在 entry_zone 內）
  5. 第五節格式統一結構化（不再每股長度/欄位差異）
  6. PDF 列印 pill 與 dashboard 一致

spec：`docs/superpowers/specs/2026-05-25-action-pill-and-framework-design.md`
plan：`docs/superpowers/plans/2026-05-25-action-pill-and-framework.md`

---

## 三十二、5/26 cross-check：強勢突破 retest 區異常 + P&F 目標缺失（2026-05-26）

用戶提供 5/25 20:37 持股分析報告 PDF（14 股）+ 5/26 收盤截圖（瑞軒 -8.50% / 合晶仍漲停 +9.90% / 矽力 +1.94% / 東捷 +2.41%），cross-check 找到 5 檔強勢突破股共同的兩個 bug，加 4 個次要 bug（紀錄不修）。

### Bug 清單

#### P0
- **Bug-1 強勢突破股「回測進場（保守）」顯示舊箱型區間** — 5 檔受害（東捷 / 矽力 / 合晶 / 瑞軒 / 微星）。家人讀者「等回測 75 才進」→ 東捷已起飛到 145.5（+94%）→ 完全錯過機會。

  | 股 | 現價 | 追進停損 | 回測進場 | 距現價 |
  |----|------|---------|---------|--------|
  | 東捷 8064 | 145.5 | 143.5 | **75.00 ~ 109.25** | -25%~-48% |
  | 矽力 6415 | 618 | 456 | **391.00 ~ 423.50** | -32%~-37% |
  | 合晶 6182 | 76.8 | 59.3 | **52.10 ~ 55.70** | -27%~-32% |
  | 瑞軒 2489 | 56.5 | 48.85 | **37.50 ~ 43.17** | -23%~-34% |
  | 微星 2377 | 127 | 124 | **94.50 ~ 109.25** | -14%~-25% |

  根因：`calc_swing_levels` 取 60 日窗口「最近局部峰」（`peaks[-1][1]`），用 `_find_local_peaks(min_gap=3)` 需左右各 3 根確認 → 強勢突破中新峰尚未成形 → `entry_zone = (swing_low, mid)` 仍是更早箱型範圍。

- **Bug-2 強勢突破股「目標：— 元」缺失** — 同 5 檔。`calc_pnf_target` Filter A `current_price < base_high × 0.85` → 強勢突破中現價遠超 base_high → 候選箱被全濾掉 → None。

  設計矛盾：強勢突破成立 = 等幅量度條件最齊備的場景（已有確認的 box），這時 target 反而 None。

#### 次要 bug（紀錄不修，留下次或不修）

- **Bug-3 撼訊 6150 pill 矛盾** → **本次一併修**（見 F8）：pill 🔴 不宜進（程式判結構已轉弱），AI 內文卻寫「方向一致順勢做多」「現價在進場區內」「威科夫(再積累)」— AI 沒遵守程式注入的 structure_flag。雙層修法：(1) gate_hint 強化「三重禁令」（禁多方相位 + 禁 DIRECTION=long + 禁多頭字眼）；(2) post-process 安全網（結構已轉弱+AI 標 long → 強制覆寫 neutral）。
- **Bug-4 瑞軒 -8.50% 翻車** → **本次一併修**（見 F6）：`_strong_breakout_state` 條件 C「一字漲停封死」雖滿足形式，但實質過熱。加附加條件「近 3 日 ≥2 根漲停」區分結構性連續漲停（合晶 5/22~5/26 連 3+ 根 ✓）vs 單根衝動（瑞軒 5/22 首次 ✗）。條件 A/B 仍能涵蓋真強勢，不需新增 ⚠️ pill 變體。
- **Bug-5 技嘉 short 但月線 5 連陽** → **本次一併修**（見 F7）：§三十 Bug A 看的是 completed = `monthly_bars[:-1]`（排除進行中月），漏掉進行中月強漲案例。加 `monthly_inprogress_strong_up`（進行中月漲幅 ≥7% + 在 MA60 之上）作為強勢上漲否決的 OR 分支。
- **Bug-6 「等突破」vs「等回測」命名混淆** → **本次一併修**（見下方 F4）：`_decide_action` line 726「price > range_high → 🟡 等突破」字面誤導（已突破還等什麼），改為「🟡 突破未驗」（已突破，等量能驗證）。

### 修法總覽（本次修 P0 + Bug-6 命名，TDD 流程）

| Commit | Bug | 檔案 | 修法核心 |
|--------|-----|------|---------|
| F1 | 1+2 test | `tests/test_breakout_overrides.py` | 新增 ≥8 case TDD：happy path（5 檔真實值）+ cap 觸發 + 退讓邊界（None / 空 bars / deep_low≥rh） |
| F2 | 1+2 impl | `modules/ai_analyzer_v2.py` | 新增純函式 `_breakout_overrides(swing_levels, daily_bars, price)`；`analyze_stock_three_masters` / `analyze_market_only` 算完 `_breakout` 後若 True 則覆寫 `_swing_long['entry_zone']` 與 `['target']`，同步 `result['target_pnf']` |
| F3 | docs | `plan.md` + `docs/superpowers/{specs,plans}` | spec + impl plan + plan.md §三十二 |
| F4 | 6 命名 | `modules/ai_analyzer_v2.py` + `tests/test_decide_action.py` | `_decide_action` 「🟡 等突破」→「🟡 突破未驗」（已突破等量能驗證），對應 test 字串同步 |
| F5 | Opt-1 | `modules/ai_analyzer_v2.py` + `tests/test_operation_framework.py` | `_render_operation_framework` 每行包 `<div class="op-row">` 取代 `\n`（mistune→HTML 後吃掉換行造成擠成一行 bug，CLAUDE.md §三十一「已知小瑕疵」）；順手移除冗餘「五、操作框架」前綴（AI prompt 已輸出節標題，避免重複）；HTML escape `>`/`&` 字元 |
| F6 | Bug-4 | `modules/ai_analyzer_v2.py` + `tests/test_strong_breakout.py` | `_strong_breakout_state` 條件 C 加附加條件「近 3 日 ≥2 根漲停（含今日）」避免單根衝動誤判（瑞軒 5/22 首次一字漲停 → 5/26 -8.5% 翻車）。結構性連續漲停（合晶 5/22~5/26 連 3+ 根）仍觸發；單根漲停降為「🟡 突破未驗」或其他依 entry_zone 判 |
| F7 | Bug-5 | `modules/data_enricher.py` + `tests/test_monthly_structure.py` | `compute_monthly_structure` 加 `monthly_inprogress_strong_up` 欄位（進行中月漲幅 ≥7% 且在 MA60 之上）；`_structure_flag` 強勢上漲否決條件加 OR 分支。覆蓋技嘉型 V 反轉（5 月進行中 278→336.5 +21% 但 completed 月線 close 不嚴格上揚 + bull_count<4 → 原本 fall-through 到「結構轉折中」允許 AI 標 short） |
| F8 | Bug-3 | `modules/ai_analyzer_v2.py` + `tests/test_structure_safety_net.py` + `tests/test_structure_gate_short.py` | 雙層修法：(1) `_structure_block` gate_hint「結構已轉弱」強化為「三重禁令」— 禁標 WYCKOFF_PHASE 多方相位 + 禁標 DIRECTION=long + 禁多頭字眼清單（「方向一致」「順勢做多」「進場區內」「再積累」「主升段」）；(2) 新增純函式 `_apply_structure_safety_net(structure_flag, direction)`，post-process 階段（兩處）若 AI 仍標 long → 強制覆寫 neutral 並 log warning。撼訊 5/25 報表案例（pill 🔴 / AI 內文方向一致順勢做多）|

### 設計決策

1. **retest zone 採單邊向下 3%**（`(rh*0.97, rh)`），不採對稱 ±3%：價格已在 range_high 上方，上限若 > rh 沒意義。依據：Darvas Box / 威科夫 SOT — 突破後前壓力反轉為支撐。
2. **target base_low 用「過去 60 日絕對最低」**：代表「整波起漲點」，避免最近 swing_low 已被穿過後等幅量度目標小於現價。
3. **target cap = price × 2.0**：防 base 太低算出離譜目標（如矽力若 base 用 12 月低 191.5 會算出 1044 → 顯然超出實務）。
4. **新 helper 而非改 `calc_swing_levels`**：既有函式對「箱型整理 → 等回測」場景設計仍正確，「強勢突破中」是另一個場景需要不同錨點邏輯。新加 helper 不影響既有測試與非突破場景。
5. **不改 `_render_operation_framework`**：覆寫 swing_levels dict 後既有渲染邏輯自動拿新值 → 整潔。
6. **dashboard target pill 自動同步**：因 `result['target_pnf']` 跟著被覆寫，零前端改動。

### 驗收（需 deploy + 重跑 ~$0.6）

- pytest 全綠（預計 269 + 8 新 → 277+）
- 5 檔強勢突破股 deploy 後預期：

  | 股 | retest zone | target |
  |----|------------|--------|
  | 東捷 | 139.20 ~ 143.50 | 243.75 |
  | 矽力 | 442.32 ~ 456.00 | 728.50 |
  | 合晶 | 57.52 ~ 59.30 | 90.35 |
  | 瑞軒 | 47.38 ~ 48.85 | 67.70 |
  | 微星 | 120.28 ~ 124.00 | 163.00 |

- 非強勢突破股（晶心科 / 創惟 / 華星光 / 南亞科 / 撼訊 / 技嘉 / 華擎 / 大聯大 / 瑞耘）零變動

### 回滾

純加性 helper + 單一覆寫點，無 DB migration、無既有函式簽名改動。問題 `git revert` 即可。
最壞情況：helper 有 bug → 回 `{}` 退讓 → 沿用原 calc_swing_levels 值（= bug 修法前狀態），不會 crash。

spec：`docs/superpowers/specs/2026-05-26-strong-breakout-retest-and-target-design.md`
plan：`docs/superpowers/plans/2026-05-26-strong-breakout-retest-and-target.md`

---

## 三十三、Dashboard 尚未分析顯示上次分析 + 錨點 strip（2026-05-28）

### 緣起

§三十二 8 commit deploy 驗收完成後，用戶提出 Opt-2/3 dashboard UX 兩件事：
- **Opt-2**：新交易日開盤後 14:30 前，14 檔 mini-card 全部回到「尚未分析」灰色狀態，家人讀者失去前一日決策參考
- **Opt-3**：mini-card 缺關鍵價位（進場區/停損/目標），需逐一點進個股詳情才能掃 → 14 檔過慢

### 已決設計（用戶定案）

| 設計問題 | 選擇 | 理由 |
|----------|------|------|
| 顯示時機 | B 都顯示（已分析+尚未分析 UI 結構一致） | 家人讀者一眼掃過所有持股錨點 |
| 資料來源 | C+ 改 `stock_service.get_user_stocks()` 加 fallback | 零新 API、單一資料路徑 |
| 舊資料視覺 | A 4 chip 淺灰 60% + 「上次 MM-DD」tag | 視覺清楚分辨今日 vs 上次 |
| 失效策略 | 14 天 lookback + 超過 → 完全空白 | 涵蓋週末/假日避免極舊資料誤導 |
| 錨點 strip 資料 | 加 entry_low / entry_high migration | 精確進場區間，sup/res 單值對 short 場景不對稱 |
| 方向 awareness | 依方向動態切換 label（long/short/neutral） | 與既有 pill 概念一致 |
| 時間 tag 格式 | 絕對日期「上次 5/25」 | 不會 stale，家人讀者易讀 |

### 影響範圍（6 commit）

| Commit | 類型 | 內容 |
|--------|------|------|
| F1 | feat(db) | `migrations/2026-05-28-add-entry-zone-columns.sql`（IF NOT EXISTS）+ `models.py` 加 `entry_low` / `entry_high` Numeric(10,2) Column |
| F2 | test | `tests/test_stock_service_fallback.py` 5 TDD case（紅燈：主查詢命中 / fallback / 14 天邊界 / 取最近 / 混合）|
| F3 | feat(analyzer) | `ai_analyzer_v2.py` 兩函式寫入 `result['entry_low/high']` 從 `_sl['entry_zone']`；`app.py` / `run_daily_report.py` 寫入端加 column 對應 |
| F4 | feat(stock_service) | `get_user_stocks` 加 14-day fallback 查詢 + item dict 新增欄位（risk_pct/wyckoff_phase/action_pill 沿用 + support/resistance/target_pnf/stop_loss/entry_low/entry_high/is_today_analysis/last_analysis_date） |
| F5 | feat(ui) | `dashboard.js` buildCard 加 `card-stale-data` class、`last-analysis-tag` chip、`renderAnchorStrip` direction-aware；`markCardAnalyzed` 移除 stale；`analyzeAll` 結尾 reload；`app.css` 4 新 class |
| F6 | docs | spec + impl plan + plan.md §三十三 |

### 為什麼這樣設計

1. **加 entry_low / entry_high column 而非沿用 support 單值**：support_price 對 long ≈ entry_zone 下緣，但 short 場景「空進」是 resistance，概念不一致；從 html_content 解析脆弱。1 migration 換取「精確且 direction-aware」strip，成本可控。
2. **14-day fallback 而非無限制**：週末(5) + 連假(6) + 系統暫停(1-2) < 14 天；超過代表停權/新觀察/系統故障，寧可空白避免誤導。
3. **兩階段查詢（主+fallback）而非「一次查 14 天」**：主查詢命中率 ≈100%，fallback 只跑 missing 子集，DB 載入量最小。
4. **正向命名 `is_today_analysis` 而非反向 `is_stale`**：undefined 為「今日已分析」邏輯與既有行為一致，避免新欄位破壞舊測試。
5. **markCardAnalyzed 後 reload 整 grid 而非局部更新 strip**：strip 需要 entry_low/high 等多欄位，API response 不含；14 檔 grid render < 50ms，可接受。
6. **`formatLastDate('2026-05-25') → '5/25'`**：家人讀者熟悉短日期，省 chip 空間。

### 驗證狀況

- pytest **296/296 全綠**（291 原 + 5 fallback）
- py_compile（models / ai_analyzer_v2 / stock_service / app / run_daily_report）+ `node -c dashboard.js` 全綠
- 5 commit 純加性 + 1 migration（IF NOT EXISTS 安全）+ 1 test 檔
- 既有「今日已分析」路徑零退化（fallback 只對 missing symbol 觸發）

### ⚠️ Deploy 順序（用戶必執行）

1. **先跑 migration**（§三十一 踩過 UndefinedColumn 500 坑）：Supabase Web SQL Editor 跑 `migrations/2026-05-28-add-entry-zone-columns.sql`
2. SQL 驗證：`SELECT column_name FROM information_schema.columns WHERE table_name='stock_analyses' AND column_name IN ('entry_low','entry_high');` 預期 2 row
3. `git push origin main` → Render auto-deploy
4. Dashboard hard refresh

### 驗收兩階段

**零 token（migration + deploy 後即可驗）：**
1. 開盤前場景 09:00 TW → 14 檔顯示淺灰 60% + 4 chip + 「上次 5/26」tag + 錨點 strip（沿用昨日資料）
2. 若 tag 顯示但 strip 顯示「—」→ 表示舊資料 entry_low/high 為 NULL（合理；新欄位 5/26 那次分析還沒寫入）→ 需重跑

**燒 ~$0.6 重跑：**
3. 按一鍵分析 → 14 檔 stale 樣式移除（回正常色彩）+ tag 消失
4. 錨點 strip 顯示新分析錨點：
   - long（如矽力突破中）：`進 442.3-456.0 | 停 224.5 | 標 728.5`
   - short（如撼訊）：`空進 73.7 | 空停 76.0 | 空標 62.0`
   - neutral：`區間 X-Y | 雙向`
5. 隔日 09:00 開 dashboard → 14 檔自動回到 stale 視覺（沿用今日分析）→ Opt-2 完整驗收

### 回滾策略

F1-F5 commit 設計可單獨 revert，互不依賴：
- F1 migration nullable 加性 → 留 NULL 不影響讀取（最壞 `DROP COLUMN IF EXISTS` 回退）
- F3 寫入端 revert → DB 兩 column 留 NULL，前端 strip 顯示「—」
- F4 fallback revert → 回到「主查詢 only」舊行為（早上 09:00 全部尚未分析灰色 = 修法前）
- F5 前端 revert → 卡片回原樣（無 stale 視覺、無 strip），後端 fallback 仍工作但前端不消費

spec：`docs/superpowers/specs/2026-05-28-dashboard-stale-anchor-design.md`
plan：`docs/superpowers/plans/2026-05-28-dashboard-stale-anchor.md`

---

## 三十四、5/28 cross-check：6 bug 修法（pill P/L gate / 雙重停損 / boundary buffer / P&F 揭露）（2026-05-28）

### 緣起

用戶 5/26 21:46 跑 14 支報表，5/27 沒重跑、5/28 收盤後做 cross-check。
我手動撈 5/27-5/28 OHLC（9 檔走 yfinance、5 檔走 TPEx 新 endpoint
`https://www.tpex.org.tw/www/zh-tw/afterTrading/tradingStock`）對照 5/26 PDF
14 檔報表預測，發現 5 bug + 1 優化 + 1 文件不一致。

### A. 修法總覽（4 commit + 1 docs）

| Commit | Bug | 修法 |
|--------|-----|------|
| `cec5bff` | Bug-1+3 | _decide_action 加 pl_pct 參數 + HOLD 深虧 ≤ -20% 抑制「加碼」改「觀望持有」；short path 加 zlo×1.005 buffer 讓 boundary case 改判等反彈佈空。adjust_pill_for_deep_loss helper 在 PDF / dashboard 讀取端 post-process（避免 DB cross-user pollution） |
| `3e1cc23` | Bug-2+4 | _render_operation_framework breakout=True 分支加「⚠️ 突破首日反轉風險」watermark + 主停損（追進停損 = rh）/ 次停損（論點作廢 = inv）label hierarchy |
| `51145a9` | Opt-1 | calc_pnf_target_relaxed 新函式：放寬 Filter A/B/C 仍回 (target, gate_price)；_dual_pnf 整合 → strict None 時注入「P&F理論目標：X 元 — 需先突破/跌破 Y 元觸發」整句替代「— 元」 |
| 本 commit | Bug-5 + docs | CLAUDE.md §三十二 驗收表更正：微星實際 4/5 ✅ (非 5/5)；plan.md §三十四（本節）+ spec + impl plan |

### B. cross-check 證據摘要（用戶決策參考）

| 股 | 5/26→5/28 % | 5/26 報表 pill | 結論 |
|---|------------|--------------|------|
| 晶心科 (H) | **-6.40%** | 🟢 加碼（cost=355 虧 -34%）| ❌ Bug-1 主訴求 |
| 東捷 | **-10.74%** | 🟢 追進 💪 | ❌ Bug-2/Bug-4 主訴求 |
| 瑞軒 | -7.16% | 🟢 追進 💪 | ❌ Bug-2/Bug-4 同 |
| 撼訊 (short) | -2.86% | 🔴 分批佈空（70 vs zlo 69.6 邊界）| ❌ Bug-3 主訴求 |

### C. 為什麼這樣設計

1. **Bug-1 用 user 端 post-process 而非分析時 inject pl_pct**：DB StockAnalysis 跨用戶共用 cache，若分析時根據個人 cost 算 pill 會污染 cross-user。讀取端（PDF / dashboard）有用戶 avg_cost + price 才能精確算 pl_pct，post-process 覆寫 base pill 是乾淨的分層設計。
2. **Bug-3 buffer 用 ×1.005（0.5%）**：撼訊 5/26 70.0 vs zlo 69.60 距離 +0.57%，buffer 須 ≥ 此值才生效。再大會誤殺真正在區內的 case。
3. **Bug-4 hierarchy 用 🔴 主 / 🟠 次 emoji**：與 _decide_action pill 配色一致（🔴 退出 / 🟠 警戒），語義延續性高。
4. **Opt-1 用「理論目標 — 需先突破 Y」而非「P&F 概念目標：X」**：揭露「未觸發」狀態，避免家人讀者以為已是確定目標。

### 驗證狀況

- pytest **315/315 全綠**（原 304 + 8 Bug-1/3 + 6 Bug-2/4 + 4 Opt-1 - 部分 test 改寫重複扣除）
- py_compile 全綠
- 4 commit 純加性（helper 新增 + 既有函式新參數 default None）
- 純 docs commit 更正 CLAUDE.md §三十二 微星驗收

### ⚠️ Deploy 驗收（用戶可執行，需重跑 ~$0.6 驗 AI prompt 行為）

**零 token 視覺驗收**（push 後 hard refresh）：
1. 晶心科 print PDF / dashboard：HOLD + cost=355 / price~234 → pill 應顯示「🟡 觀望持有」非「🟢 加碼」（既有 5/26 cache 透過 read-time post-process 覆寫）
2. 撼訊 print PDF：第五節未變（沿用 5/26 cache）但下次重跑生效

**燒 ~$0.6 重跑**（5/27-5/28 走勢已知，驗 prompt + 渲染）：
3. 東捷 / 瑞軒 / 矽力 / 合晶 第五節含「⚠️ 突破首日反轉風險：假突破常於突破後 1-2 日翻盤...」watermark
4. 4 檔強勢突破第五節停損改 hierarchy：「🔴 主停損（觸發即出場）：rh 元」+「🟠 次停損（整波論點作廢）：rl 元」（取代「停損：X 元」單字段）
5. 撼訊重跑後 pill 若仍在區下方 → 「🟡 等反彈佈空」（buffer 0.5% 生效）
6. 11 檔原顯示「P&F 目標：—」者重跑後改顯示「P&F理論目標：X 元 — 需先突破/跌破 Y 元觸發」

### 回滾策略

4 commit 純加性 + helper 新增 + 既有函式新參數 default None：
- C1 (cec5bff)：revert → _decide_action 回 §三十一 簽名 + dashboard 無 deep loss adjust
- C2 (3e1cc23)：revert → 強勢突破第五節回單一「停損」+ 無 watermark
- C3 (51145a9)：revert → calc_pnf_target_relaxed 函式不存在 + _dual_pnf 沿用「—」
- 各自獨立 revert 不依賴

spec：`docs/superpowers/specs/2026-05-28-cross-check-6-fixes-design.md`
plan：`docs/superpowers/plans/2026-05-28-cross-check-6-fixes.md`

---

## 三十五、5/28 cross-check Round 2：5 bug 修法（API error / 深虧續抱 / Filter B / RISK 隔離 / 錨點 fallback）（2026-05-28）

### 緣起

§三十四 修法 deploy 後（push origin/main `e5aed91`），用戶燒 ~$0.6 重跑 14 檔 5/28 報表 + 截圖。Cross-check 發現 5 個追加 bug：

1. **Bug-H**（P0）：個股詳情頁「📌 持股操作建議」直接 leak Anthropic API raw error（credit balance too low）。DB cache 永久污染 — even credit 充值後 existing_rec 命中仍回 error 字串
2. **Bug-A**（P0）：晶心科 5/28 cost=-38% / direction=neutral / entry_zone=None → _decide_action default 走「🟢 續抱」，§三十四 Bug-1 修法只 catch「加碼」字眼故未覆寫 → 家人讀者誤導
3. **Bug-D**（P0）：Opt-1 relaxed sentence 對 Filter B 失敗場景（cur 已遠超 gate）仍寫「需先突破 Y」邏輯不通（矽力/東捷/合晶/瑞軒 4 檔受害）
4. **Bug-G**（P1）：analyze_market_only 對 is_holding=True 注入【持倉提示】可能污染 RISK_PCT 客觀性（晶心科 42% → 62% 升幅可能含「持股人視角」加成）
5. **Bug-B**（P1）：晶心科 dashboard 錨點 strip 完全「— | — | —」— frontend wyckoff='再積累'=long phase 但 AI direction=neutral → calc_swing_levels neutral 不回 entry_zone → DB entry_low/high=None → 全 '—'

### A. 修法總覽（5 commit + 1 docs）

| Commit | Bug | 內容 |
|--------|-----|------|
| `da4e3ac` | Bug-H | `AIGenerationError` 異常類別 + `_detect_error_kind` helper；`generate_personal_recommendation` 失敗 raise；`api_recommend_stock` catch → 503 + 友善訊息 + 不寫 cache；既有 5/28 兩筆 error cache（6533/6104）已 DB cleanup |
| `db29965` | Bug-A | `adjust_pill_for_deep_loss` 擴大 catch：HOLD 深虧 ≤ -20% 時把「續抱」也改「🟡 觀望持有」（不只「加碼」） |
| `8f0e973` | Bug-D | `calc_pnf_target_relaxed` signature 改 (target, gate, status) 三元組；'reached' 狀態下 `_dual_pnf` 寫新句「P&F概念目標：先前等幅量度 X 已達成（突破點 Y），等新箱形成」 |
| `747fbb3` | Bug-G + B | analyze_market_only 兩處 prompt 強化：【持倉提示】明確隔離 + 風險評分加「客觀性鐵律」；dashboard.js renderAnchorStrip：entry_low/high 都 None 時 fallback 走 neutral path |
| 本 commit | docs | plan.md §三十五（本節）+ spec + impl plan + CLAUDE.md 進度更新 |

### B. 5/28 cross-check 證據摘要

| 股 | 5/28 重跑後現象 | 修法結果 |
|---|----------------|---------|
| 晶心科 6533 (H) | pill=🟢 續抱 / cost=-38% / strip=「— \| — \| —」/ 個股詳情 leak error | Bug-A pill 覆寫 / Bug-B strip fallback / Bug-H 不再 leak |
| 矽力/東捷/合晶/瑞軒 | 「需先突破 Y」但現價已遠超 Y | Bug-D 改新句「先前已達成」 |
| 14 檔重跑 RISK 評分 | is_holding 可能暗中污染 | Bug-G prompt 強化客觀性鐵律 |
| 個股詳情頁/PDF 個人建議 | DB 永久存 error 字串 | Bug-H raise + cleanup |

### C. 為什麼這樣設計

1. **Bug-H 採三層防護而非單點修**：
   - `_generate` 保留 return error string（向後相容 analyze_market_only 等大盤 caller，不想牽動範圍）
   - `generate_personal_recommendation` 失敗 raise（精準針對 PersonalRecommendation cache 路徑）
   - `api_recommend_stock` catch + 不寫 cache + 友善訊息（端點級防護）
   - 既有 cache cleanup 一次性 SQL（避免下次 read 再 leak）

2. **Bug-A 擴大 catch 為「加碼/續抱」**：HOLD 深虧 + 結構未轉弱 + entry_zone=None → default 「續抱」是個常見路徑（直接 fall-through），單獨 catch「加碼」漏掉。

3. **Bug-D status 三元組而非新函式**：與 calc_pnf_target_relaxed 共用箱體掃描，差別僅在 caller 看 status 決定 sentence。比拆兩函式 DRY。

4. **Bug-G 純 prompt 而非結構改動**：is_holding 是必要旗標（觸發第六節），無法移除；只能靠 prompt 教 AI 隔離影響範圍。需重跑驗 prompt 行為。

5. **Bug-B frontend 解 backend 限制**：calc_swing_levels neutral 不回 entry_zone 是 API 語意（neutral 無進場/出場觸發），改後端會破壞語意。frontend 偵測「同 phase 但 entry 為 None」即知後端走 neutral path，用 support/resistance 顯示「區間 X-Y | 雙向」對家人讀者更友善。

### 驗證狀況

- pytest **340/340 全綠**（既有 315 + 11 Bug-H + 9 Bug-A + 5 Bug-D）
- py_compile（ai_analyzer_v2 / candlestick / app）+ `node -c dashboard.js` 全綠
- 5 commit 純加性 + prompt 強化 + signature 擴展（既有 4 個 relaxed test 改三元組解構）

### ⚠️ Deploy 驗收

**零 token 立即生效**：
1. **Bug-H**：個股詳情頁「持股操作建議」不再 leak raw API error；若 credit 不足 → 顯示「AI 服務額度不足，請聯絡管理員充值」
2. **Bug-A**：晶心科 cost=-38% 場景，pill 從「🟢 續抱」覆寫為「🟡 觀望持有」
3. **Bug-B**：晶心科 dashboard 卡片錨點 strip 從「— | — | —」改顯「區間 213-249.5 | 雙向」

**燒 ~$0.6 重跑驗 prompt 行為**：
4. **Bug-D**：強勢突破 4 檔（矽力/東捷/合晶/瑞軒）第五節 P&F 句改寫為「先前等幅量度 X 已達成」（不再「需先突破 Y」）
5. **Bug-G**：14 檔重跑 RISK 評分對「持股 vs 觀察」狀態變化更穩定（同股切換 status 不應改 RISK）

### 回滾策略

5 commit 純加性 + 既有函式新參數 default：
- `da4e3ac` revert → AIGenerationError 不存在 + api_recommend_stock 回到舊行為
- `db29965` revert → adjust_pill_for_deep_loss 回到只 catch「加碼」
- `8f0e973` revert → relaxed 回兩元組（既有 4 test 已 unpack 3 個，會 fail，故 revert 須一併改 test）
- `747fbb3` revert → prompt 回舊版 + frontend 回 long-only path

各 commit 獨立 revert（除 `8f0e973` 因 signature 改動需配對 test）。

spec：`docs/superpowers/specs/2026-05-28-cross-check-round2-design.md`
plan：`docs/superpowers/plans/2026-05-28-cross-check-round2.md`

---

## 三十六、5/28 cross-check Round 3：Bug-I 跌穿停損 P&F 矛盾 + Bug-J WATCH long 跌穿 pill（2026-05-28）

### 緣起

§三十五 deploy 後用戶 21:14 重跑（credit 已充）。對照新 PDF 發現兩個新 bug：

1. **Bug-I**（P1）：晶心科 pill=「🔴 出場」（程式偵測跌穿停損 224.5→219.5）+ 同段 P&F 顯示「需先突破 260 元觸發」邏輯矛盾。家人讀者「該出場還是該等突破？」
2. **Bug-J**（P2）：瑞耘 phase=再積累 (long) 但收 96.2 < entry_low 96.8 → _decide_action fall-through 到 default ⚪ 觀望 + 顯示「停損 96.80（已跌穿）」邏輯矛盾

### A. 修法總覽（2 commit + 1 docs）

| Commit | Bug | 修法 |
|--------|-----|------|
| `9611f02` | Bug-I | `_dual_pnf` 加 invalidation gate：long 跌穿 swing_low × 0.985 / short 站回 swing_high × 1.015 → P&F 句改「論點已失效」覆蓋既有 strict / relaxed 句 |
| `8946529` | Bug-J | `_decide_action` WATCH long path 加跌穿 entry_low 判斷 → 新 pill「🟡 跌穿觀察」（取代 fall-through 觀望）|
| 本 commit | docs | plan.md §三十六（本節）+ spec + impl plan |

### B. 為什麼這樣設計

1. **Bug-I 在 _dual_pnf 早期判斷而非 _render_operation_framework 後置**：P&F 句是注入 AI prompt 的 block text，AI verbatim 引用到第四節。後處理無法乾淨覆寫 AI 內文。在 _dual_pnf 階段就把 sentence 改寫，AI 自然會引用新句。

2. **1.5% buffer 避免過度觸發**：晶心科 219.5 / stop 224.5 = -2.2% 跌穿；buffer 0.985 (1.5%) 表示「明確破位」才觸發失效，避免「現價貼著停損晃動」反覆切換語義。

3. **Bug-J pill 字典擴充而非沿用「⚪ 觀望」**：⚪ 觀望語義「無動作」，但跌穿 entry_low 的情境需要「主動觀察止跌訊號」，🟡 跌穿觀察 更符合家人讀者實務行為。

4. **「結構已轉弱」優先級高於跌穿判定**：若結構已轉弱仍走 🔴 不宜進（pill 字典原邏輯）。跌穿觀察只在「結構未轉弱但價跌穿」的灰色地帶觸發。

### 驗證狀況

- pytest **349/349 全綠**（既有 340 + 5 Bug-I + 4 Bug-J）
- py_compile + node -c 全綠
- 2 commit 純加性 helper / 新 pill 字典項 / 不影響其他既有 caller

### ⚠️ Deploy 驗收

**零 token 立即生效**：
- 晶心科 5/28 既有 cache + read-time 不會有效果（cache 已寫入舊 P&F sentence）→ 需重跑

**燒 ~$0.05 重跑單檔驗證**：
- 晶心科 / 瑞耘 重跑後 PDF 該檔第四節 P&F 句應為：
  - 晶心科：「P&F概念目標：論點已失效（跌穿支撐 224.5 元），論點重建前 P&F 不適用」
  - 瑞耘：「🟡 跌穿觀察」pill 取代「⚪ 觀望」

### 回滾策略

2 commit 純加性 + 新 pill 字典項：
- `9611f02` revert → _dual_pnf 回 §三十五 邏輯（晶心科又顯示「需先突破 260」誤導）
- `8946529` revert → WATCH long 跌穿回 default ⚪ 觀望

各 commit 獨立 revert 互不依賴。

spec：`docs/superpowers/specs/2026-05-28-cross-check-round3-design.md`
plan：`docs/superpowers/plans/2026-05-28-cross-check-round3.md`
