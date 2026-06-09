# §三十八 設計：強漲回測股誠實揭露 + 看板即時離區標示

日期：2026-06-09
狀態：設計定稿（待用戶 review → writing-plans）

## 緣起

用戶提供 6/9 收盤截圖，對照 6/8 持股分析報告 cross-check，發現兩類「強漲後回測」的觀察股
報表給出**不可操作的進場區 + 無前向目標**，會誤導家人讀者：

| 股 | 6/8 收 | 進場區（6/8 報表） | 寬度÷現價 | P&F 目標 | 現有 pill | 問題 |
|----|--------|------------------|-----------|---------|----------|------|
| 合晶 6182 | 80.0 | 52.1 – 76.8 | 30.9% | 「—」（41.9 已達成）| 🟡 等回測 | 價已**高於**進場區上緣 76.8；下緣 52.1 在現價 −35% 處；無前向目標 |
| 矽力 6415 | 524 | 391 – 542 | 28.8% | 「—」（373 已達成）| 🟢 進場區可佈 | 價**在區內**但區寬 28.8%、停損 391 在 −25% 處；「可佈」叫人現在進場卻無真實停損 |

**根因**：§三十二 `_breakout_overrides` 只在「現價 > range_high 且量過門檻」的**新鮮突破**才縮窄
進場區。對「5 月強漲 → 6 月縮量回測」這種股不觸發 → 沿用 `calc_swing_levels` 的大箱
（停損價 ~ 箱頂），對家人讀者不可操作。

此外有一個**獨立但相關**的看板問題（用戶原列 #1）：
- 微星 6/8 收 132 在進場區 122–137.25 內 → pill `🟢 進場區可佈`（當下正確）
- 6/9 漲到 139.5（+5.68%）已衝出上緣 137.25，但看板 pill/strip 仍是 6/8 的，
  即時價顯示 139.5 卻寫「進 122–137.25 / 進場區可佈」→ 家人讀者誤以為現價仍可進場
- 創惟同理：6/9 收 102.5 已高於上緣 100.9

本 spec 一併處理兩者（用戶定「#1 + #2 一同做」），因兩者共用「價 vs 進場區」比較。

## 設計原則（用戶定案）

走**誠實揭露**，不硬縮區間、不硬湊目標（Q1=選項4）。跟專案一貫「誠實 > 錯誤」哲學一致。
保留唯一客觀有用的數字——**失效價/整波論點作廢價**（合晶 52.1、矽力 391，跌破即整波多頭翻空），
砍掉誤導來源（假進場區上緣、「—」目標）。

## 兩塊分工

| | 觸發時機 | 處理 | 範圍 |
|---|---------|------|------|
| **#2 強漲回測誠實揭露** | 分析時（後端） | 產報表當下價就脫離原箱/區過寬 → pill + strip + PDF 第五節烤入 | WATCH long |
| **#1 看板即時離區** | 看板時（前端） | 分析當下在區內、之後即時價漂出 → 即時灰標 | 看板 long 卡片 |

#2 觸發後 strip 不再顯示區間（只剩失效價）→ #1 無區間可比 → 兩者自然不重疊。

---

## #2 — 強漲回測誠實揭露（後端）

### 觸發 gate（用戶定案：gate=區間過寬，①脫離原箱當標籤）

在 `_decide_action`（`ai_analyzer_v2.py:790`）WATCH long 的 `entry_zone` 區塊插入，順序：

```
WATCH long:
  結構已轉弱            → 🔴 不宜進          （既有，優先）
  breakout             → 🟢 追進 💪         （既有，新鮮突破不適用本 gate）
  price > range_high   → 🟡 突破未驗         （既有）
  entry_zone:
    price < entry_low                    → 🟡 跌穿觀察   （§三十六，優先，最緊急）
    (entry_high − entry_low)/price > 25% → 🟡 強漲回測觀望  ← 新 gate
    entry_low ≤ price ≤ entry_high        → 🟢 進場區可佈  （區窄維持）
    price > entry_high                   → 🟡 等回測      （區窄維持）
```

**為何 gate 用寬度而非「價>上緣」**：分析時「價>上緣」只在股票真強漲、箱沒跟上時發生，
而那必然伴隨寬區間；若單以「價>上緣」觸發會誤殺「窄區間剛站上緣」的正常等回測（微星型）。
故 gate=寬區間，①脫離原箱僅作 strip 子標籤。「價漂出窄區間」交給 #1 前端處理。

**門檻 25%**：合晶 30.9%、矽力 28.8% 都中；微星 11.6%、瑞軒 17% 不誤觸。

### 純函式 `_strong_pullback_state`（新增，可測）

```python
def _strong_pullback_state(price, entry_zone, threshold=0.25):
    """強漲回測誠實揭露狀態判定（純函式）。

    回傳 None（不觸發）或 dict：
      {'symptom': '脫離原箱' | '區間過寬',
       'fail_price': <entry_low>,
       'width_pct': <int, 寬度÷現價的百分比>}

    觸發條件：entry_zone 有效 + price >= entry_low（非跌穿）
              + (entry_high - entry_low)/price > threshold（區間過寬）
    症狀標籤：price > entry_high → '脫離原箱'；否則 '區間過寬'
    """
```

- `_decide_action` 的 gate 直接調用此函式判定（回 dict 即 `🟡 強漲回測觀望`）
- 渲染端（framework/strip）也調用同函式取 symptom + fail_price，DRY

### 第五節操作框架（`_render_operation_framework`，`ai_analyzer_v2.py:950`）

當 pill == `🟡 強漲回測觀望` → 改寫為誠實區塊（不再輸出假進場區/假目標）：

```
─────────────────────
建議動作：🟡 強漲回測觀望
強漲後回測，現價已脫離原箱        ← 症狀「脫離原箱」
（或：進場區過寬 29%，停損距現價過遠）  ← 症狀「區間過寬」
失效（整波論點作廢）：52.10 元 — 跌破即多頭翻空
目標：待新箱形成後估算（先前等幅量度已達成）
─────────────────────
```

### strip（看板 + PDF 同源）

| 症狀 | strip 文字 |
|------|-----------|
| 脫離原箱（合晶）| `失效 52.1 · 脫離原箱待新箱` |
| 區間過寬（矽力）| `失效 391 · 區間過寬待新箱` |

---

## #1 — 看板即時離區標示（前端，Q4=選項A）

`dashboard.js`：即時價載入後（`_loaded_price` 可用時，類比 `adjustPillForDeepLoss` 的重評時機），
對**正常顯示區間**的 long 卡片（即 #2 未觸發、strip 仍有 entry_low/high）比對：

- `price > entry_high` → strip 整條變灰 + 尾端 `↑ 價已離區`
- `price < entry_low`  → strip 整條變灰 + 尾端 `↓ 跌穿`
  - 但 pill 已是 `🟡 跌穿觀察` 則不重複加微標（避免冗餘）
- 區內 → 不變

**僅 long**：short 的 strip（空進/空停/空標）價在區下方是正常「等反彈佈空」等待，非離區，不套用。

實作時機：strip 在 `buildCard` 建立時即時價未必載入；離區判定需在即時價載入後執行
（`updateCardPrice` 或等價的價載入後重評點），與 pill 深虧重評同一時機。

---

## 元件清單

| 檔案 | 改動 |
|------|------|
| `modules/ai_analyzer_v2.py` | 新增 `_strong_pullback_state` 純函式；`_decide_action` WATCH long 插 gate；`_render_operation_framework` 誠實第五節分支 |
| `static/js/dashboard.js` | `renderAnchorStrip` 強漲回測誠實 strip 分支；即時價載入後 long 卡片離區灰標 |
| `app.py` | PDF 報表 strip 同步誠實顯示（與看板同源） |
| `static/css/app.css` | `.card-anchor-strip.drift-out`（灰）+ `.anchor-drift-tag`（↑/↓ 微標）；`🟡 強漲回測觀望` 沿用既有 amber action-pill class |
| `tests/` | `_strong_pullback_state` 純函式 + `_decide_action` 整合 + 渲染 |

## 範圍邊界

- **僅 long**（#2、#1 皆是）。short 維持既有行為。
- 門檻 25%（寬度 ÷ 現價）。
- **零 DB migration**：`entry_low`/`entry_high` 欄位 §三十三 已加；新 pill 只是 `action_pill` 字串值。
- 新 pill `🟡 強漲回測觀望` 沿用既有 🟡 amber class，零新色。
- 不動 §三十六「跌穿觀察」（價<下緣，優先於本 gate）、§三十七「客觀化解耦」（status 恆 watch）。

## 測試計畫

純函式 `_strong_pullback_state`：
- 合晶型（price 80, zone 52.1–76.8）→ symptom='脫離原箱', fail_price=52.1, width_pct≈31
- 矽力型（price 524, zone 391–542）→ symptom='區間過寬', fail_price=391, width_pct≈29
- 微星型（price 132, zone 122–137.25, 窄 11.6%）→ None
- 瑞軒型（price 43.6, zone 37.5–45, 窄 17%）→ None
- 邊界：恰 25%（不觸發）vs 25.1%（觸發）
- 跌穿：price < entry_low → None（讓 _decide_action 走跌穿觀察）

`_decide_action`：
- 合晶/矽力 → `🟡 強漲回測觀望`
- 微星（窄區間價站上緣）→ `🟡 等回測`（不變）
- 瑞軒（窄區間價在內）→ `🟢 進場區可佈`（不變）
- 跌穿觀察優先級保留（價<下緣仍 `🟡 跌穿觀察`）
- breakout 仍 `🟢 追進 💪`（東捷型不誤觸）

`_render_operation_framework`：強漲回測觀望 → 誠實第五節（無假進場區/目標、含失效價）。

前端：`node -c dashboard.js` syntax；離區灰標分支邏輯（價>上緣↑/價<下緣↓/區內不變/short 不套用）。

## 回滾策略

純加性：`_strong_pullback_state` 新函式、`_decide_action` 新分支（不刪既有）、
`_render_operation_framework` 新條件分支、前端新 CSS class + 離區判定、PDF strip 同步。
任一 commit 可獨立 `git revert`：
- 後端 gate revert → 合晶/矽力 回 `等回測`/`進場區可佈`（修法前狀態）
- 前端 #1 revert → 看板回原樣（即時價離區不灰標）
- 無 migration、無既有函式簽名破壞性改動。
