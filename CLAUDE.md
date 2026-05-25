# Investment System — Claude 指引

## 工作流程
- **開工指令**：「繼續 investment-system 工作」→ 讀本檔「當前進度」區塊，給一段摘要，然後繼續
- **收工指令**：「先停這裡」→ 更新下方「當前進度」快照，再結束
- **架構決策**：討論完方案後，先更新 `plan.md`，再開始寫程式
- `plan.md` 只在需要查架構細節時才讀（節省 token）

## 當前進度（2026-05-25 — §三十 + §三十一 已 deploy 驗收完成 ✅）

**所在週次：週8（AI 偏空校正 + 報表品質）**

**狀態：HEAD = `d8bf2a2`；§三十 5 commit + §三十一 6 commit 全部已 push origin/main + Render deploy + Supabase migration 完成 + 實機驗收通過**

### 驗收依據
用戶 5/25 20:37 重跑 14 支分析（migration 已先跑 `ALTER TABLE stock_analyses ADD COLUMN IF NOT EXISTS action_pill VARCHAR(32)` via Supabase SQL Editor）。PDF + dashboard 截圖 cross-check 確認修法生效。

### ✅ 驗收結果（PDF 5/25 20:37 + dashboard）

| 股票 | 5/22 原判斷 | 5/25 實際 | 5/25 報表方向 / pill | 驗收項目 |
|------|------------|-----------|---------------------|---------|
| **東捷 8064** | **short 派發** 空停 143.5 | 漲停 +9.81% 高 145.5 穿停損 | **多 / 上漲 / 🟢 追進 💪** | §三十 Bug A 結構閘漏洞（強勢上漲否決分支） |
| **矽力 6415** | long「不宜追進」（量未到）| 漲停 +9.96% 618 | **多 / 上漲 / 🟢 追進 💪** | §三十 Bug B-B（條件 B 突破後續強勢）|
| **瑞軒 2489** | long「不宜追進」（量未到）| 一字漲停 +9.92% 56.5 | **多 / 上漲 / 🟢 追進 💪** | §三十 Bug B-C（條件 C 一字漲停封死）|
| **合晶 6182** | 強勢突破成立（條件 A）| 漲停 +9.87% | 強勢突破不退化 | §三十 條件 A 量價齊揚仍維持 |
| **晶心科 6533**（HOLD）| 觀望持有 | +1.88% | **🟢 續抱** | §三十一 HOLD 決定樹 |
| **大聯大 3702**（WATCH）| 等回測 | +4.66% | **🟡 等突破** | §三十一 WATCH long 過 entry_zone 但未強勢突破 |

dashboard 4 chip 並排正常顯示：**方向 → 威科夫 → 風險 → 建議**（用戶 strong refresh 後確認）

### ✅ 第五節「操作框架」程式渲染生效（C2）

PDF 第五節改為結構化區塊：
```
五、操作框架
─── 建議動作：🟢 續抱  進場區：224.50 ~ 242.25 元（觸發須量 ≥ 1,529 張）
   停損：224.50 元 — 跌破即論點作廢  目標：266.00 元 ───
```
不再是 AI 自由發揮的「▸【強勢突破狀態】未成立 → 標準回測進場版」長文字。

### Deploy 過程中踩到的坑（紀錄供後續經驗）
1. **Migration 必須先跑**：第一次重 deploy 後直接按 PDF 出現 500（`UndefinedColumn: action_pill` SQLAlchemy ProgrammingError f405）— 因為 SQLAlchemy model 已含 action_pill 但 DB 沒，所有 SELECT 都失敗。
2. **Render Free 沒 Shell**：用戶 Free 方案無法用 Render shell 跑 migration，改用 **Supabase Web SQL Editor** 直接 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS ...`。
3. **解決路徑**：之後若有 DB schema 變動，建議用 Supabase SQL Editor 為主路徑（Render Free user 通用）。

### 沿用未驗 / 持續觀察
- §二十九 10 bug 修法（5/24 push 17 commit `517d0e4..83e3e99`）在此次重跑也一併驗（沒退化）
- §二十八 4 bug + 優化 1/2 仍未獨立驗（但都隨此次 deploy 上線）
- Dashboard 迷你 K 線快取漏洞（§二十七，5/22 用戶「又好了」，暫不修）
- Bug D 大盤對比 TWII rate limit（`memory/bug-d-twii-rs-rate-limit.md`）

### 已知小瑕疵（不阻塞，未修）
- 第五節結構化區塊的 `\n` 分行在 markdown→HTML 渲染後可能擠成一行（PDF 抽文字看到，視覺待 PDF 列印實際確認）— 若視覺不夠分明，下次優化 _render_operation_framework 改用 `<br>` 或 `<ul><li>`。

### 回滾策略
§三十 5 commit + §三十一 6 commit 全部純加性：
- 結構閘 / 強勢突破純函式修法 → 邏輯增強，不破壞既有判斷
- _decide_action / _render_operation_framework 純函式 + 整合層雙層防護
- DB action_pill 欄位允許 NULL，向後相容
- UI 新增 chip，原 chip 不動

任一有問題 `git revert <commit>` 獨立回滾。

---

## 過往進度（2026-05-25 — 報表「建議動作」明確化：pill + 第五節結構化 6 commit）

**所在週次：週8（AI 偏空校正 + 報表品質）**

**狀態：HEAD = `6e4b31f`；6 commits 已 push origin/main (`23198fd..6e4b31f`)，Render auto-deploy 觸發中**

### 緣起
§三十 修法完成後用戶指出「報表的建議字（動作）夠用比較明確方式標記出來嗎？」目前散落在第五節長段落、第六節（HOLD only）裡，沒有單一字眼可瞄一眼。決議 A+B+C 一起做。

### A. 修法總覽（6 commit，TDD 流程，pytest 249→269 全綠）

| Commit | 內容 | 檔案 |
|--------|------|------|
| `23198fd` test(action) | _decide_action 14 TDD 決定樹（WATCH long 5 + WATCH short 3 + HOLD 4 + 邊界 2）| tests/test_decide_action.py |
| `e22f079` test(framework) | _render_operation_framework 6 TDD + test_strong_breakout 修正 | tests/test_operation_framework.py + test_strong_breakout.py |
| `584270c` feat(action+framework) | **核心**：_decide_action + _render_operation_framework 純函式 + analyze_market_only / three_masters 整合 [[OPERATION_FRAMEWORK]] placeholder + post-process（雙層防護）| modules/ai_analyzer_v2.py |
| `b19b3a8` feat(db) | StockAnalysis 加 action_pill String(32) + migration（IF NOT EXISTS）+ app.py/run_daily_report.py 寫入端 + stock_service.py 讀取端 + app.py PDF pill | modules/models.py + migrate_add_action_pill.py + app.py + run_daily_report.py + modules/stock_service.py |
| `079fa91` feat(ui) | dashboard.js buildCard 加 actionChip（方向→威科夫→風險→建議 4 chip 並排）+ actionClass helper + app.css 5 色 .action-pill 樣式 | static/js/dashboard.js + static/css/app.css |
| `6e4b31f` docs | plan.md §三十一 + spec + impl plan | plan.md + docs/superpowers/{specs,plans}/ |

### B. 建議動作 pill 字典（12 種 + 邊界）

| 情境 | pill 字 |
|------|---------|
| WATCH long: 結構已轉弱 | 🔴 不宜進 |
| WATCH long: 強勢突破成立 | 🟢 追進 💪 |
| WATCH long: 過 range_high 但量未到 | 🟡 等突破 |
| WATCH long: 在 entry_zone 內 | 🟢 進場區可佈 |
| WATCH long: 在 entry_zone 上方 | 🟡 等回測 |
| WATCH short: 結構未轉弱 | ⚪ 觀望（不宜空）|
| WATCH short: 過空停 | 🔴 論點作廢 |
| WATCH short: 在空進區 | 🔴 分批佈空 |
| WATCH short: 空進區下方 | 🟡 等反彈佈空 |
| HOLD: 跌破成本停損 | 🔴 出場 |
| HOLD: 結構已轉弱 | 🟠 減碼 |
| HOLD: 強勢突破成立 | 🟢 加碼 💪 |
| HOLD: 一般多頭持倉 | 🟢 續抱 |

### 驗證狀況
- pytest **269/269 全綠**（249 原 + 14 decide_action + 6 framework；含 1 test 修正避免假退化）
- py_compile（ai_analyzer_v2 / models / stock_service / app.py / run_daily_report / migrate）+ `node -c dashboard.js` 全綠
- 純函式設計 → testable，整合層有雙層防護（placeholder 不存在時 append fallback）
- 純加性：新 DB 欄位 IF NOT EXISTS，向後相容；既有報表生成流程不退化

### ⚠️ Deploy 驗收（需手動跑 migration + ~$0.6 重跑報表）
1. **Render shell 跑 migration**：`python migrate_add_action_pill.py`
2. **Dashboard 燒 ~$0.6 一鍵分析**，對照 5/25 收盤：
   - 14 支股每張卡片 status row 出現 4 chip（方向/威科夫/風險/建議）
   - 漲停 4 支：合晶 / 瑞軒 / 矽力 pill = `🟢 追進 💪`、東捷（修 §三十 後）方向應改 long
   - 南亞科 pill = `🟡 等回測`（現價遠超 entry_zone 上緣）
   - 撼訊 pill = `🟢 進場區可佈`（在 entry_zone 內）
   - 第五節格式統一結構化（不再各股長度/欄位差異）
   - PDF 列印 pill 與 dashboard 一致

### 沿用未驗（持續）
- §三十 5 commit（5/25 push）也在這次 deploy 一併驗
- §二十九 10 bug + §二十八 4 bug + 優化 1/2 仍待 deploy 驗
- Dashboard 迷你 K 線快取漏洞（§二十七，暫不修）
- Bug D 大盤對比 TWII rate limit

### 回滾策略
6 commit 純加性：
- test commit 純加 test file
- feat(action+framework) 新函式 + 整合，雙層防護
- feat(db) IF NOT EXISTS 安全，欄位允許 NULL
- feat(ui) 新增 chip，原 chip 不動
- docs 純加文件

任一有問題 `git revert <commit>` 獨立回滾。最危險的是 `584270c`（prompt 行為改變），revert 會讓第五節回 AI 寫長文字，但 dashboard pill 仍會運作（讀 DB NULL 不顯示）。

---

## 過往進度（2026-05-25 — 5/22 報表 vs 5/25 收盤 cross-check：結構閘漏洞 + 強勢突破門檻 5 commit）

**所在週次：週8（AI 偏空校正 + 報表品質）**

**狀態：HEAD = `48b9d2f`；5 commits 已 push origin/main (`be1c6c9..48b9d2f`)，Render auto-deploy 觸發中**

### 緣起
用戶提供 5/22 20:35 持股分析報告 PDF（14 股）+ 5/25 週一收盤截圖。14 支 12 漲 2 跌（南亞科 -4.67% / 撼訊 -1.85%）、**4 支漲停（合晶 +9.87% / 東捷 +9.81% / 瑞軒 +9.92% / 矽力 +9.96%）**。Cross-check 抓出 2 個結構性問題（§二十九 10 bug 沿用未驗，故先濾掉同類議題）。

### A. 已完成 2 bug 修法（spec + plan + 5 commit，pytest 239→249 全綠）

| Bug | 嚴重度 | 修法 | commit |
|-----|--------|------|--------|
| **A 結構閘「結構轉折中」漏洞** | 🔴 | 東捷 8064 強勢上漲剛確立（4 月放量大陽 +64%）卻被誤判 short 派發、5/25 漲停 +9.81% 穿空停 143.5。根因：`_structure_flag` 三層 fall-through 未涵蓋強勢上漲。修法：`compute_monthly_structure` 加 `monthly_close_strict_up_3` + `monthly_bull_count_6` 兩欄位；`_structure_flag` 加 default 參數，「結構未轉弱」條件擴充為原 (升/橫+在上+連續陰≤1) **或** 強勢上漲否決 (在上+連續陰≤1+(close 嚴格上揚 ≥3 根 或 近 6 月陽月數 ≥4)) | `00c25db` |
| **B 強勢突破門檻被自己拉高的均量打死** | 🟡 | 5/25 漲停 4 支只有合晶被認定強勢突破，矽力/瑞軒突破前高卻被打回「不宜追進」。根因：`volume_5d_avg_zhang` 含今日 → 前一根爆量拉高均值 → 越強勢越易在第 2 根失格（瑞軒 5/21 96K → 5/22 門檻 74.4K → 量 29K 不足）。修法：`_strong_breakout_state` 改 3 條件擇一即可：A 原量價齊揚 / B 突破後續強勢（>range_high×1.05 且 近 5 日 close 都站高，涵蓋矽力）/ C 一字漲停型（漲幅≥9% 且 close=high，涵蓋瑞軒 5/22 一字漲停封死） | `7e9aa7b` |

spec：`docs/superpowers/specs/2026-05-25-structure-flag-and-breakout-fix-design.md`
plan：`docs/superpowers/plans/2026-05-25-structure-flag-and-breakout-fix.md` + plan.md §三十

### 驗證狀況
- pytest **249/249 全綠**（239 原 + 10 新：Bug A 5 + Bug B 5）
- py_compile（data_enricher + ai_analyzer_v2）全綠
- 兩個函式都是純函式 + 新增邏輯分支（不刪原條件），向後相容
- D1 / D2 各自純加性 + optional 參數，可獨立 `git revert`

### ⚠️ Deploy 驗收（用戶可執行，~$0.6 重跑驗全部）
已 push → Render auto-deploy。燒 ~$0.6 跑一鍵分析 + 出 PDF 驗：
1. **Bug A**：東捷 8064 結構旗標 = 「結構未轉弱」（close 嚴格上揚 48.85→63.30→104.0），方向應改 long 而非 short
2. **Bug B-B**：矽力 6415 = 「強勢突破成立」（562 > 456×1.05=478.8 且 5/18~5/22 5 日 close 都 > 456）
3. **Bug B-C**：瑞軒 2489 = 「強勢突破成立」（51.4 > 48.85，漲幅 9.83%，close=high=51.4 一字漲停封死）
4. **回歸不退化**：合晶 6182 仍維持「強勢突破成立」（量價齊揚 A 條件）
5. **其他 10 支 long 股無誤判**（旗標與方向不變）

### ⏭ 待做（§三十一，§三十驗收後再進）
報表「建議動作」明確化（A+B+C 三項已對齊決定樹）：
- A 頂部加「建議動作 pill」：追進/等回測/等突破/續抱/減碼/出場 等動作字
- B 強勢突破狀態 emoji 💪 合進 A（不獨立 pill）
- C 第五節「操作框架」改程式渲染（C2，類 K 表 `[[OPERATION_FRAMEWORK]]` placeholder 注入）
- 預估 ~6 commit、改動 ~3 倍於 §三十（涉及 prompt + templates + CSS）

### 沿用未驗（持續）
- §二十九 10 bug 修法（5/24 push 過 17 commit `517d0e4..83e3e99`）+ §三十 5 commit 一併在這次 deploy 驗
- 5/22 §二十八 4 bug + 優化 1/2 仍待驗
- Dashboard 迷你 K 線快取漏洞（§二十七，5/22 用戶「又好了」，暫不修）
- Bug D 大盤對比 TWII rate limit（`memory/bug-d-twii-rs-rate-limit.md`）

### 回滾策略
5 commit 純加性 + optional 參數，無 DB/migration；D1（結構閘）與 D2（強勢突破）各自獨立 `git revert`。若部分股因「結構轉折中」改判「結構未轉弱」造成 prompt 行為變動 → 先 revert D1，D2 仍生效。

---

## 過往進度（2026-05-24 — 5/22 週報 cross-check：10 bug 修法 6 commit）

**所在週次：週8（AI 偏空校正 + 報表品質）**

**狀態：HEAD = `83e3e99`（本快照 commit）；14 commits 已 push origin/main (`517d0e4..83e3e99`)，Render auto-deploy 觸發中**

### 緣起
用戶提供 5/22 20:35（週五晚週末視窗）持股分析報告 PDF（27頁、14股 = 2 hold + 12 watch）完整核對。

### A. 已完成 10 bug 修法（spec + plan + 6 TDD commits，pytest 208→239 全綠）

| Bug | 嚴重度 | 修法 | commit |
|-----|--------|------|--------|
| **S1** 進行中週/月K close 滯後一天 | 🔴 | data_enricher 用當日 daily roll-up 合成進行中週/月棒（high=max, low=min, close=最新日 close, volume=sum），S1 修好 W1 也自動對齊 | `1518663` |
| **W1** 大盤雙重收盤值 (42267 vs 41368) | 🔴 | 同 C1（weekly_bars[-1].close 自動 = price） | `1518663` |
| **S2** 撼訊 pill 73.7 vs 內文 74 | 🟡 | _quantize_price (<100→1dp, ≥100→0dp) 統一寫進 block + result['target_pnf'] | `d65a813` |
| **S4** P&F 重複/巢狀 (矽力/南亞科/華星光) | 🟡 | _dual_pnf placeholder 改注入完整成品句「P&F概念目標：73.7元（等幅量度）」AI verbatim 引用；prompt 鐵律改「禁加 P&F概念目標：前綴造成巢狀」 | `d65a813` |
| **W2** 量能描述邏輯反 | 🟢 | analyze_weekly_taiwan_v2 從 weekly_bars 算 week_vol_zhang + 近 5 週均量，label 改「本週週量」/「近 5 週均量」 | `18a20fb` |
| **W3** 收盤區間描述錯 | 🟢 | 加注入「近 3 週收盤區間」「近 3 週高低區間」+ 鐵律「不可混用」 | `18a20fb` |
| **I2** INDUSTRY 句尾截斷 | 🟡 | get_industry_indicator_stocks max_tokens 800→1500 | `18a20fb` |
| **S5** 結構已轉弱 + 再積累 UX 衝突 | 🟢 | gate_hint「結構已轉弱」加「相位限定派發/再派發/下跌/不明，禁標 積累/上漲/再積累」對稱規則 | `a02c563` |
| **S3** 觀察股第六節洩漏 (12 檔 3 違規) | 🟡 | **雙層防護**：prompt 改「禁止輸出『六、』標題」+ 新 helper _strip_section_six post-process regex 砍 ### 六、至下一節/disclaimer/結尾 | `e0ab0a5` |
| **I1** 週末 NEWS 缺失 | 🔴 | dashboard.js 週末分支加 /api/news/regenerate（與日報對稱）+ run_weekly_report 新 _resolve_industry_news：RSS 空降級 DB 近 7 天 DailyMarketSummary fallback + note 標明來源 | `f7653c5` |

spec：`docs/superpowers/specs/2026-05-24-weekly-report-bugs-design.md`
plan：`docs/superpowers/plans/2026-05-24-weekly-report-bugs.md` + plan.md §二十九

### 驗證狀況
- pytest **239/239 全綠**（原 208 + 31 新：S1+W1 7 + S2+S4 8 + W2+W3+I2 4 + S5 2 + S3 5 + I1 5）
- py_compile（data_enricher / ai_analyzer_v2 / run_weekly_report）+ `node -c dashboard.js` 全綠
- C1（資料層）影響面最大但純加性 + 邊界 case 涵蓋完整
- C2-C5 純 prompt 改寫 / 加性 helper，無 DB migration
- C6 跨檔（dashboard.js + run_weekly_report.py + ai_analyzer_v2.py）

### ⚠️ Deploy 驗收（用戶可執行，一次重跑驗全部）
已 push → Render auto-deploy。燒 ~$0.6 跑一鍵分析 + 出 PDF 驗：
1. **S1+W1**：每股進行中週/月 close = 當日日 close（晶心科週/月 close 240，非 230）；大盤週報「本週收盤」與週 OHLC 一致
2. **W2+W3**：大盤週報量能 label「本週週量」非「本週末量」；出現「近 3 週收盤區間 / 近 3 週高低區間」分明
3. **I2**：INDUSTRY 區無句尾截斷
4. **S2+S4**：撼訊 pill 與內文 P&F 同源；矽力/南亞科/華星光 P&F 段無重複/巢狀
5. **S3**：觀察股全部零洩漏第六節（12 檔），若 AI 違規 server log 出現「[_strip_section_six] AI 違規輸出第六節...」warning
6. **S5**：撼訊結構旗標「結構已轉弱」時 phase 不會標「再積累」（應改標 派發/不明）
7. **I1**：INDUSTRY 區出現真實新聞或 fallback 標示「（新聞來源：YYYY-MM-DD DB 快取）」，無「本次無新聞資料」全推斷分支

### 沿用未驗（持續，待用戶 deploy 後實機）
- 5/22 §二十八 4 bug + 優化 1/2 仍待驗（CLAUDE.md 上次快照清單）
- Dashboard 迷你 K 線快取漏洞（§二十七，5/22 用戶「又好了」，暫不修）
- Bug D 大盤對比 TWII rate limit（`memory/bug-d-twii-rs-rate-limit.md`）

### 回滾策略
6 commits 純加性 + prompt 改寫，無 DB/migration；任一有問題 `git revert` 對應 commit。C1 對全 14 檔報表所有 K 表影響最大，若新合成棒導致 yfinance 數值不對 → 先 revert C1，下游修法仍生效。

---

## 過往進度（2026-05-22 — 報表 cross-check：4 bug 修復 + 2 優化 spec）

**所在週次：週8（AI 偏空校正 + 報表品質）**

**狀態：HEAD = `665f691`（優化1）後接本 CLAUDE.md 快照 commit；全部已 push origin/main**

### 緣起
用戶 5/22 dashboard K 線恢復後，提供 5/22 股價截圖 + 5/21 晚上報表 PDF（27頁15股）交叉核對。
**結論：威科夫結構閘大成功** — 5/20 報表 15股判10空 → 5/21 報表 12 long / 3 neutral / 0 short，
5/22 實際 14/15 上漲（6 檔漲停），偏空校正方向完全正確；唯一下跌的大聯大報表早警示「現價偏高、
等回測」。同時揪出 4 個 bug + 3 項優化。

### A. 已完成 4 bug（3 commits 已 push `4052618..dc4d434`）
| Bug | 嚴重度 | 修法 | commit |
|-----|--------|------|--------|
| A 週/月K退化單日棒 + 日期位移 | 🔴 | `_chart_json_to_df` 剔除 Yahoo `1wk/1mo` spurious 即時棒（`ts==regularMarketTime`）+ `gmtoffset` 校正日期；進行中棒標「（進行中）」+ 第二節 prompt 鐵律 | `4052618` |
| B pill 撐/壓 與內文支撐壓力撞名 | 🟡 | long pill 撐/壓→箱底/箱頂（程式 swing 錨點）；目標 pill 改用 `target_pnf` 與內文同源 | `e80799e` |
| C 型態標籤日期 vs AI 文字不符 | 🟡 | 第二節 prompt 鐵律：多根組合型態以標注日期為準 | `dc4d434` |
| D 距峰值回落數字打架 | 🟡 | `_structure_block` 鐵律：內文須引用程式注入值 | `dc4d434` |

優化3（週/月K日期標籤位移）= Bug A2，已隨 A 修好。
spec：`docs/superpowers/specs/2026-05-22-kbar-spurious-bar-fix-design.md`

### 驗證狀況
- pytest **201/201 全綠**（190 + 11 新 `tests/test_kbar_spurious.py`）、py_compile 全綠
- Bug A 真資料驗證：6533 月K `1027張`(退化) → `15929張`(真聚合)、月K 日期校正 `2026-05-01`
- ⚠️ 結構閘 `compute_monthly_structure` 的 `[:-1]` 在修 A 後自動對齊「排除進行中月」docstring
  本意 → 結構旗標可能對少數股翻動（屬修正非退化），deploy 後須重驗
- ⚠️ Bug C/D 屬 prompt 行為改動，需燒 ~$0.6 重跑才驗得到

### B. 已完成 優化1/2（plan.md §二十八，commits `6ee6a68` `665f691`）
| 優化 | 修法 | commit |
|------|------|--------|
| 優化2 強勢突破追蹤 | 純函式 `_strong_breakout_state`（現價>swing range_high 且量≥突破門檻）；long 操作框架條件分支：強勢突破成立→「追進」+「回測進場（保守）」並陳 | `6ee6a68` |
| 優化1 持倉部位建議 | `analyze_market_only` 加 `is_holding` 旗標；持股時 static_block 輸出「六、持倉部位建議」（續抱/減碼判斷+錨點觸發價+持倉停損）；neutral 持股也給具體價位 | `665f691` |

spec：`docs/.../2026-05-22-holding-position-advice-design.md`（§七 記實作修正）、
`...-strong-breakout-tracking-design.md`。plan：`docs/.../2026-05-22-holding-advice-breakout-tracking.md`。

⚠️ **優化1 實作修正**：spec 原設計 `holding_ctx` 帶個人成本/損益注入 prompt，實作時發現
`StockAnalysis` 跨用戶共用 → 會洩漏給其他看同股的用戶。已改 `is_holding` 純旗標，
第六節為 user-agnostic 結構建議（不含個人損益數字）。

### 驗證狀況（A+B 合計）
- pytest **208/208 全綠**（190 + 11 kbar + 5 breakout + 2 holding）、py_compile 全綠
- ⚠️ 結構閘 `compute_monthly_structure` 的 `[:-1]` 修 A 後自動對齊「排除進行中月」本意 → 結構旗標可能對少數股翻動（修正非退化）
- ⚠️ C/D + 優化1/2 屬 prompt 行為改動，需燒 ~$0.6 重跑才驗得到

### ⚠️ Deploy 驗收（用戶可執行，一次重跑驗全部）
已 push → Render 自動部署。燒 ~$0.6 跑一鍵分析 + 出 PDF 驗：
1. 結構閘旗標未退化（修 A 後視窗變動）
2. 第二節 K 表：日K[-1] ≠ 週K[-1] ≠ 月K[-1]；月K 完整月聚合量、日期為月份起始；進行中週/月棒標「（進行中）」
3. pill：long 股顯示「箱底/箱頂/目標」，目標 pill = 內文 P&F 同值
4. Bug C：多根型態 AI 敘述日期不再與標籤打架；Bug D：內文回落%=程式注入值
5. 優化1：持股（晶心科/創惟）報表出現「六、持倉部位建議」3 bullet；neutral 持股也有續抱/減碼價位；觀察股無此節
6. 優化2：強勢突破股 long 操作框架出現「強勢突破追蹤（追進）」+「回測進場（保守）」並陳

### Dashboard 迷你K（plan §二十七）
用戶回報 5/22 dashboard K 線「又好了」→ 該快取漏洞暫無急迫性，仍列觀察。

### 回滾策略
全部純資料層/前端/prompt 加性修改 + optional 參數，無 DB/migration；任一有問題 `git revert` 對應 commit。

---

## 過往進度（2026-05-21 — 威科夫結構閘 + 報表 6 bug 修法）

**所在週次：週8（AI 偏空校正 + 報表品質）**

**狀態：HEAD = `9c51600`（已 push origin/main，本地與遠端同步）**

### 緣起
用戶 5/20 報表 PDF（22 頁、15 股）對照 5/21 股價 — 15 股判 10 空，5/21 卻 14 股漲。發現兩件事：AI 系統性偏空（多月大漲股只因單月收陰就被打成派發）+ 6 個殘留 bug。

### A. 威科夫結構閘（修系統性偏空）
spec `docs/superpowers/specs/2026-05-21-wyckoff-phase-gate-design.md`、plan §二十六。
方案 B：程式算【月線結構客觀事實】+ prompt 雙閘，`結構未轉弱` 硬禁 AI 標派發/再派發/下跌。
- `data_enricher.compute_monthly_structure()`：月K結構（近3根升/跌/轉折/橫）+ 連續月陰線 + 距峰值回落 + 現價vsMA60 + 結構旗標 + 週K動能（唯讀）
- `結構未轉弱` = 現價在MA60上 且 月K結構∈{升,橫} 且 連續月陰線≤1（≥2 黑或跌破MA60 或 月K跌 → 結構已轉弱）
- `ai_analyzer_v2._structure_block()` 注入 analyze_stock_three_masters / analyze_market_only 兩函式

### B. 報表 6 bug 修法
plan `docs/superpowers/plans/2026-05-21-report-6-bug-fixes.md`。
| Bug | 修法 |
|-----|------|
| 1+2 HTML外洩 / 第四節截斷 | analyze_market_only max_tokens 2000→3000 + _clean_html_output 清殘破標籤 |
| 3+6b K表欄序錯亂 / 型態欄錯位 | 第二節 K 表改程式產生（_render_ktables_html/_inject_ktables），prompt 用 `[[K_TABLES]]` 佔位 |
| 4 缺空停 | _resolve_swing_anchors：swing 失敗時用近20日高×1.03 補空停 |
| 5 日K缺根 | _yahoo_ohlcv 補 null 收盤價（(H+L)/2，不再整列 dropna）|
| 6a 多根型態標單根 | label_bars 多根組合型態加「（N根組合）」後綴 |

### C. Supabase migration 確認
連 information_schema 查證：`stock_analyses.stop_loss` 欄位、`personal_recommendations` 表（含唯一索引）皆已執行，不需補跑。

### 本次 commits（14 個，已 push）
- 結構閘：`10f577f`(spec+plan) `61d7ddc` `8016d54` `203aca1` `38f0a82` `4659f76` `2bb76f0`
- 6 bug：`08f7978`(plan) `510ce1b` `f7e26c3` `2ae224a` `36b0937` `b67e026` `9c51600`

### 驗證狀況
- pytest **190/190 全綠**（結構閘 +17、6 bug 修法 +約 15）
- py_compile 全綠
- ⚠️ 結構閘 + Bug1/2/3/6b 屬 prompt 行為改動，需 deploy + 燒 ~$0.6 重跑才驗得到

### ⚠️ Deploy 驗收（用戶必執行）
已 push → Render 自動部署。燒 ~$0.6 跑一鍵分析 + 出 PDF 對照：
1. 結構閘：臻鼎/合晶/瑞軒（月K升）不再標派發；晶心科/創惟（真下跌）仍可標空
2. Bug1/2：無 `<span` 殘字外洩、每股第四節「三宗師融合結論」完整
3. Bug3/6b：K 表每列高≥低、型態欄=型態名、特徵欄=量能
4. Bug4：撼訊/合晶/大聯大 short 股都有空停
5. Bug5：日K 根數一致；Bug6a：多根型態顯示「三白兵（3根組合）」後綴

### 回滾策略
純加性 + prompt 改寫，無 DB/migration 改動。任一修法有問題 `git revert` 對應 commit。

### 下次待辦（已記錄 plan.md §二十七）
**Dashboard 迷你 K 線圖快取漏洞** — 用戶 5/21 發現 9 支觀察股「近20日K」迷你圖空白。根因：迷你圖資料只來自 `MarketDataCache`，而該表只在使用者點進個股詳情頁時才寫入；今日 14:30 批次完全沒刷新它（連「正常」6 支都是 2-3 週前舊圖）。**非當日 deploy 造成**（`get_full_stock_data` live 測正常）。修法方向 A+B：A=每日批次刷新所有股 `MarketDataCache`；B=dashboard miss 時即時補抓。下次走 spec→plan→subagent。

---

## 過往進度（2026-05-20 — 投資建議書 15 Bug 全面修法）

**所在週次：週7（UI 重整 + 設計層 bug 修復）**

**狀態：HEAD = `cad66f3`（已 push）**

### 本次 — 用戶 5/19 22:09 報表 PDF（22 頁、15 支股）審視找 15 Bug，全做

走完整 spec → plan.md → 7-commit TDD 執行 → 驗證流程。spec 見
`docs/superpowers/specs/2026-05-20-report-quality-fixes-design.md`、plan §二十四。

**致命三件（會直接誤導決策）：**
- #1 持股部位處理建議缺位（晶心科 -39.6% / 創惟 -18.6% 多單虧損，分析給「建新空單」）
- #2 Pill 價位 ↔ 內文錯位（short 股「空進=支撐線、空標=目標」，家人讀 pill 進場=目標）
- #3 K 棒重複/缺漏（5 支股同日列兩次「(補充)/(最新)」、技嘉日 K 只 3 根）

**用戶 5/20 拍板：** B1c（加 stop_loss 欄位，schema 永遠中性語意，1 migration）+ Personal 全部包含（持股+觀察）。

### 本次 commits（9 個：spec + plan + 7 fix + 驗證）

| commit | 內容 |
|--------|------|
| `1d8aecf` | spec + plan.md §二十四 |
| `fc04aa3` | Task1 D 組型態誤判（D1 多根去重 + D2 tick 容差 + D3 月 K skip） |
| `58be033` | Task2 C 組 K 棒去重（_fmt_bars dedup + prompt 行數鐵律） |
| `a999bf5` | Task3 H 組字型 fallback（mono 加 Noto Sans TC 修半形 glyph） |
| `5dcb80f` | Task4 G 組 PnF Filter C + 月 K 表注入 |
| `31c70d5` | Task5 B 組 stop_loss 欄位 + swing 注入 + pill mapping（**需 Supabase migration**） |
| `089484f` | Task6 A 組 print PDF 含 Personal + 持倉診斷段（**需 Supabase migration**） |
| `0de57dc` | Task7 E+F 組 操作框架強制 schema + 量價術語方向 qualify |
| `cad66f3` | Task8 驗證測試（short pill 順序 + personal_html render，6 case） |

### 驗證狀況
- pytest **158/158 全綠**（原 127 + 新 31：D 12 + C 7 + G 3 + B 5 + B/A 整合 6 + 既有 print_report 一致）
- py_compile（app.py / ai_analyzer_v2 / candlestick / models / data_enricher / run_daily_report）全綠
- B 組核心斷言：short pill 順序「空標 < 空進 < 空停」價位邏輯通（防「進場=目標」誤導）
- E+F 組純 prompt，需 AI 重跑驗

### ⚠️ Deploy 步驟（用戶必執行）

**Step 1：跑 Supabase migration（兩個 SQL，零 downtime）**
1. `migrations/2026-05-20-add-stop-loss-column.sql` — `ALTER TABLE stock_analyses ADD COLUMN stop_loss`
2. `migrations/2026-05-20-add-personal-recommendations-table.sql` — `CREATE TABLE personal_recommendations`

**Step 2：deploy（Render auto-deploy on push）**

**Step 3：燒 ~$0.6 跑一鍵分析驗 commit 5/6/7 AI 行為（共 6 點）：**
1. short 股 pill 順序「空進 > 空停 > 空標」三價位邏輯通（空進在上、空停最高、空標最低）
2. long 股 pill「撐 < 壓 ≤ 目標」與改前一致，neutral 不顯示 stop_loss
3. 三宗師結論第五段「操作框架」三模板擇一輸出 + 3 結構化 bullets 都有
4. short 股「等待條件」用「跌破量/賣壓確認量」字眼，非「突破量門檻」
5. 無「放量失敗」字面、無「努力大結果差」誤套到下跌量大場景、無「月 K 早晨之星」幻覺
6. PDF：持股段（晶心科/創惟）有「持倉診斷（方向衝突警示）」三 bullets；按過「個人建議」按鈕的觀察股 PDF 含 personal 章節

**Step 4：刷 PDF 視覺驗（不燒 token）：**
- 字型：「⼗字星/⼤陰線/⽇期」改為正常「十/大/日」（H 組修法）
- 第二節 K 線 table：月 K 6 + 週 K 3 + 日 K 5 共 3 張表（G2 修法）
- 日 K 表無「(補充)/(最新)」補充行（C 組修法）
- 撼訊三川底非連 3 天觸發（D1 修法）；華星光 5/19 不誤判平頭頂（D2 修法）

### 回滾策略
純 prompt 改動 + 加性欄位 + 加性 helper → AI 不遵守則 revert 對應 commit；stop_loss 欄位保留為 NULL 向後相容；PersonalRecommendation 表獨立，不影響既有功能。

### 沿用未驗（持續，待用戶實機）
- 中長期波段框架 Task 6（spec 2026-05-19）：6 點 AI 行為驗證（連兩日重跑同股方向不變等）—— 已大部分被本次 commit 5/6/7 覆蓋
- Bug F NEWS chip：當日、近 12h、regen 失敗 toast
- persona 併入：long/neutral 個人建議向後相容、Darvas Box 語意
- Bug D 大盤對比仍少數股出現（memory/bug-d-twii-rs-rate-limit.md）

---

## 過往進度（2026-05-19 收工 — 中長期波段框架：穩定論點 + 程式鎖定錨點）

**所在週次：週7（UI 重整 + 設計層 bug 修復）**

**狀態：HEAD = `b710dac`（未 push → 本次一併 push；前一 HEAD `2fb5c7c`）**

### 本次 — 用戶 5/18 報表回饋三項：缺雙向支撐壓力、太短期翻來覆去、要中長期

走完整 brainstorming → spec → writing-plans → subagent 逐 Task 執行流程。

**三骨架決策（用戶 2026-05-19 拍板，plan.md §二十三 / spec 2026-05-19）：**
- D1 穩定論點 + 失效價位（失效未破論點不變，每日重跑只更新「距失效距離」）
- D2 程式鎖定錨點（復用 candlestick.py，非 AI 每日推斷 → 根治漂移）
- D3 neutral → 誠實不操作 + 雙向條件觸發（根除「都是買多」偏見）

**根因：** `ai_analyzer_v2.py:359/365/720` prompt 寫死短線(1-5日)/今日時機；支撐壓力 AI 每日推斷 → 漂移 → 論點漂移。

### 本次 commits（7 個，spec→plan→Task1-5）

| commit | 內容 |
|--------|------|
| `73229f4` | spec 設計文件 |
| `410b144` | 6-task TDD 實作計畫 |
| `88b332f` | Task1：`calc_swing_levels()`（復用 `_find_local_peaks/_troughs`+`calc_pnf_target`，long/short 鏡像、neutral 區間+雙向 flip）+ 8 測試（含穩定性回歸：尾端加未觸及失效 bar 後錨點不變）|
| `7675261` | Task2：`_dual_swing_block`（鏡像 `_dual_pnf`）+ `analyze_stock_three_masters` action_section 移除▶短期(1-5日)換波段框架 + 波段穩定鐵律 |
| `2dade2c` | Task3：`analyze_market_only` 對齊（注入錨點 + `今日時機`→波段定位 + 穩定鐵律；守「不含操作建議」邊界不加 entry/add 段）|
| `291df02` | Task4：`generate_personal_recommendation` 注入錨點到 market_summary + 5 模板去當沖化 + prompt 波段紀律（short 禁加碼/neutral 模板結構未動）|
| `b710dac` | Task5：DB raw 推演 + 靜態證明 + plan.md §二十三 |

### 驗證狀況
- pytest **127/127 全綠**（119 既有 + 8 新 `test_swing_levels.py`，零退化）
- py_compile（ai_analyzer_v2 / candlestick）OK
- DB 8 筆真實 `StockAnalysis` raw 跑 `_clean_html_output`/`_parse_tagged` 無 crash；git diff 靜態證明標記定義/解析/清理函式體零改動 → 解析端零退化
- 每 Task 全新 subagent 執行、Task 間審查（commit 範圍 + 全測試 + 關鍵 grep）

### 留給下次 — ⚠️ Task 6 只能用戶做（AI 行為無法靜態證明）
deploy 後燒 ~$0.6 重跑一鍵分析，驗收 6 點：
1. 出現「波段操作框架（2週-1個月+）」，無「短期(1-5日)」/「今日時機」
2. long/short 各有明確失效(停損)+加碼觸發價，與 dynamic_block【波段操作錨點】鎖定值一致
3. neutral 寫「無方向+區間+雙向 flip」，非「等回檔買進」
4. 個人建議去當沖化、價位與分析錨點一致
5. **連兩日重跑同股（失效未破）→ 方向與價位不變**（翻來覆去根治實證）
6. 第一行結構化標記/pill/方向 badge 全正常

回滾：純 prompt + 加性 helper，無 migration → AI 不遵守則 revert 對應 commit，無資料污染。

**沿用未驗（持續待用戶 deploy / AI 重跑）：**
- Bug F：一鍵分析後 NEWS chip = 當日、近 12h；regen 失敗 toast（spec/plan §二十二）
- persona 併入：long/neutral 個人建議向後相容、Darvas Box 語意
- Bug D 大盤對比仍少數股出現（`memory/bug-d-twii-rs-rate-limit.md`）

---

## 過往進度（2026-05-19 收工 — Bug F：NEWS 自 5/12 凍結修復 + 12h 新聞窗口）

**所在週次：週7（UI 重整 + 設計層 bug 修復）**

**狀態：HEAD = `79cca6a`（已 push origin/main；前一 HEAD `90338c5`）**

### 本次 — 用戶提供 5/18 20:35 報表，NEWS chip 顯示 5/12（6 天前）

**根本診斷（systematic-debugging）— 非 AI 幻覺/freshness，是架構操作斷層：**
- `DailyMarketSummary`（NEWS 來源）全系統只有兩條產生路徑：① `run_daily_report.py` 14:30 批次（cron 自 2026-05-03 停用，`.github/workflows/daily_report.yml:5-6` 註解，1 人手動模式）② `/api/news/regenerate`（只有「🗑 清快取」按鈕觸發）
- 用戶日常「一鍵分析 → 開報表」中 `analyzeAll()` **完全不碰 NEWS** → 從最後一次清快取（5/12）凍結 6 天；`print-report` 誠實取最新一筆 = 5/12
- 設計原假設「14:30 批次每天跑」，cron 停用後該假設破裂、`analyzeAll` 未補

**用戶決策（plan.md §二十二）：選項 1 + 12h 窗口；不做過期警示、不重啟 cron（違背手動省成本初衷）**

### 本次改動（commit `79cca6a`，3 檔 +65/-2）

| 檔案 | 修改點 |
|------|--------|
| `modules/data_fetcher.py` | F-1：`get_tw_news_rss` cutoff `hours=48`→`12` + docstring（用戶要求「報表產生時間前 12h 新聞才列入」） |
| `static/js/dashboard.js` | F-2/F-3：`analyzeAll()` 非週末視窗→背景並行射 `/api/news/regenerate`（比照週末→週報 pattern），個股完成後 await NEWS 就緒才宣告完成（避免太早開報表又拿舊摘要）；**每次**一鍵分析都重生（單次 ~$0.01，唯有每次重生保證前 12h） |
| `plan.md` | §二十二 記架構決策（含殘留風險 + 12h 副作用取捨） |

`/api/news/regenerate` 端點本身不動（已冪等 delete+insert(today)）。

### 驗證狀況
- pytest **119/119 全綠**、`node -c dashboard.js` OK、`py_compile data_fetcher.py` OK
- 12h cutoff 邊界本機實測：11.5h 保留 / 12.5h 剔除 / pubDate 解析失敗保留（沿用既有 except→pass）

### 留給下次 — ⚠️ 待用戶 deploy 後實機驗證
1. 一鍵分析跑完 → 開報表，NEWS chip 顯示**當天日期**、內容為近 12 小時新聞
2. regen 失敗時出現 toast「財經新聞更新失敗，報表將顯示前次摘要」
3. 12h 窗口副作用觀察：盤前/隔夜/連假新聞是否過少導致摘要偏薄（屬已知取捨，太誇張再議）
4. **殘留風險（用戶已知）：** 未做選項 2 過期警示，regen 失敗時 print-report 仍 fallback 最新一筆（可能舊），僅靠 toast 提示

**沿用未驗（持續待用戶 AI 重跑 / deploy 實機）：**
- persona 併入：long/neutral 個人建議向後相容、派發股出現空方框架、第一行 `RISK_PCT/DIRECTION` 標記未受 static_block 加長影響、Darvas Box 箱頂/箱底語意
- Bug D 大盤對比仍只少數股出現（觀察是否偏離真實過大需啟動 TTL 快取修法，見 `memory/bug-d-twii-rs-rate-limit.md`）
- 生產：6104 收 100.5 / 6415 收 467.5 印表正確；盤前清快取 server log「TWII 非今日」警告

---

## 過往進度（2026-05-18 收工 — persona 選擇性併入 + 個人建議空方化 + Bug D 觀察）

**所在週次：週7（UI 重整 + 設計層 bug 修復）**

**狀態：HEAD = `90338c5`（已 push origin/main；前一 HEAD `b4654bf`）**

### 本次重點 — 用戶提供報表實機驗證 + persona 討論 + 兩項實作

**E-2 / E-3 實機驗證通過（2026-05-17 報表，15 支）：**
- E-2 方向判定：派發/再派發股全 `DIRECTION=short`，三宗師雙向招式正確（空方進場/回補/下行目標），neutral/long 無退化
- E-2 風險評分：6789「個股強於大盤，放空需留意反彈風險」— direction-aware 生效
- E-3 前端：持股/觀察 pill 全翻 空進/空停/空標 + 方向 badge「空」，相位反推方向正確

**Bug D 部分失效 — 已定位、用戶決定先不修（memory 記錄）：**
- 15 支只有 3 支出現【大盤對比】（6789、3515/6150、2489 區；含「非 beta 連動」鐵律遵守）
- 根因：`_market_rs_block` 每股各自呼叫 `get_index_daily_closes('^TWII')`，15 支報表=15 次相同 Yahoo 請求，Render IP 限流 ~12/15 回 `{}`（誠實>錯誤如實觸發）。本機實測 code 正確，純架構缺陷
- 用戶決定列觀察，「以後偏離真實太多再修」。最小修法（module-level TTL 快取）記於 `memory/bug-d-twii-rs-rate-limit.md`

**架構決策（plan.md §二十一）— AI persona 選擇性併入：**
- 用戶草擬完整「股票分析師」persona，評估後**不當全系統 persona、不取代現有 block**（會破壞 news/產業/個人建議多任務、回退 Bug E 雙向、缺程式計算鐵律、「主動要求數據」對批次有害）
- 只把 3 個加分元素併入 `analyze_stock_three_masters` + `analyze_market_only` 兩 static_block
- 核心調和：**威科夫定方向（第一層，不可被推翻）/ 李佛摩階梯定時機（第二層，趨勢>結構>訊號>確認）** — 兩者不同層非競爭，補上現有 block 缺的進場時機仲裁

### 本次改動（未 commit → 本次一併）

| 檔案 | 修改點 | 退化驗證 |
|------|--------|----------|
| `modules/ai_analyzer_v2.py` | 兩 static_block 併入 Darvas Box 雙向框架 + 兩層決策分工 + 交易原則（純 +18 行 0 刪除對稱）；`generate_personal_recommendation` 空方化（`phase_to_direction` 反推，short 加 holding/watching 空方模板 + `_dir_note`，零退化巢狀法 `if`→`elif` 既有模板 byte-identical）| diff 僅刪 2 行（控制流），long/neutral 輸出 byte-identical |
| `plan.md` | §二十一 記架構決策 | — |
| `CLAUDE.md` | 本快照 | — |
| `memory/` | Bug D 觀察 + MEMORY.md 索引（新增 memory 機制首次使用）| — |

### 驗證狀況
- pytest **119/119 全綠**、py_compile OK
- 消費/解析端零退化由 git diff 靜態證明（結構化標記/`_clean_html_output`/風險評分/DIRECTION 判定全未動）
- **AI 輸出端為 prompt 改動，需真實重跑驗證**（風險低：純加性、不矛盾既有鐵律、第一行標記指令未動）

### 留給下次 — ⚠️ 待用戶 AI 重跑實機驗證
1. long/neutral 股個人建議與改前一致（向後相容）
2. 派發/下跌股個人建議出現空方框架（放空/回補/減碼/出場、禁加碼），非「加碼買入」
3. 個股/大盤分析仍正確輸出第一行 `RISK_PCT/DIRECTION...` 標記（static_block 加長未影響）
4. 報表出現 Darvas Box 箱頂/箱底語意，空方股寫「跌破箱底=空方進場」非「轉弱」
5. （沿用）Bug D 大盤對比仍只少數股出現 — 觀察是否偏離真實過大需啟動 TTL 快取修法

**待生產驗證（沿用，用戶 deploy 後實機）：** 6104 收 100.5 / 6415 收 467.5 印表正確；NEWS chip 顯示實際 `summary_date`；盤前清快取 server log「TWII 非今日」警告

---

## 過往進度（2026-05-17 收工 — Bug D + Bug E(空方) 全實作）

**所在週次：週7（UI 重整 + 設計層 bug 修復）**

**狀態：HEAD = `95260e5`（已 push origin/main）**

本次自上次同步落後 22 commit 已快轉，並完成 Bug D + Bug E 三 commit：

| 項目 | Commit | 內容 |
|------|--------|------|
| E-1 | `6c5afa5` | `calc_pnf_target` 加 `direction='long'|'short'`（預設 long 逐字保留零退化；short 幾何鏡像 target=box_bottom−(box_top−box_bottom)，Filter A/B 鏡像）+ 8 short 測試 |
| E-2 | `86c10f4` | `analyze_market_only`/`analyze_stock_three_masters` prompt 加結構方向判定（威科夫相位→方向，禁預設多頭，派發/下跌須給空方框架）+ 三宗師雙向招式 + direction-aware 風險評分（風險=逆勢程度，順勢放空低分）+ `DIRECTION: long|short|neutral` tag + 雙向 P&F 注入；`_clean_html_output` 剝除 DIRECTION |
| E-3 | `8f4f943` | `_render_one_block` pill 由相位反推方向翻轉（撐→空進/壓→空停/目標→空標）+ 方向 badge；`dashboard.js` 看板方向 chip（復用 wyckoff 色系，零新 CSS） |
| Bug D | `095ea7a` | `data_fetcher.get_index_daily_closes('^TWII')` + `_market_rs_block`/`_twii_close_on_or_before`：個股 vs TWII 5/20日相對強度(pp)鎖定值 + beta≠alpha 鐵律注入 dynamic_block；TWII 失敗/bar 不足不注入 |

### 關鍵設計決策
- **零-migration**：`StockAnalysis` 無 direction 欄位。新增 `phase_to_direction(威科夫相位)` 反推方向（AI 的 DIRECTION 本質即相位之函數），DIRECTION tag 仍驅動 AI 內部推理 + 雙 P&F 選取，僅持久化/渲染走相位反推，免動線上 Supabase schema。
- **單一框架識別方向**（決策2），非拆 long/short 兩套 prompt（省成本、框架本就鏡像）。
- **plan §20 E-3 映射更正**：原文「壓力→空方目標」方向相反，已更正為財務正確「壓力在上=空方停損、向下 target=空方目標」，plan.md 同步註記。

### 驗證狀況
- pytest **119/119 全綠**（37 candlestick + 8 E-1 short + 既有 TWII/quote/format + 10 新 Bug D）
- py_compile（candlestick/ai_analyzer_v2/data_fetcher/app）+ `node -c dashboard.js` 全綠
- E-2 成本紀律前置完成：合成 short 輸出 + **真實 DB 派發股 6743/4958/6415 dry-run**，`_clean_html_output` 零退化、DIRECTION 不外漏

### 留給下次

**⚠️ 待用戶決策（不在 plan §20 議定範圍，未擅自擴大）：** `generate_personal_recommendation` 仍純多方框架（加碼/進場買入）。市場分析轉空方時個人建議會不一致。它已收 `wyckoff_phase` 參數，可比照 `phase_to_direction` 加空方 action_template；但屬 per-user 高頻呼叫、有 AI 成本，需用戶拍板是否補。

**⚠️ 待用戶 AI 重跑實機驗證（E-2 / Bug D，本次用戶將跑一次報表）：**
1. 派發/下跌股輸出有 `DIRECTION: short` + 空方操作框架（賣空進場/回補停損/下行目標），非「不宜行動」
2. 看板/印表 short 股 pill 顯示 空進/空停/空標 + 方向 badge「空」
3. dynamic_block 出現【大盤對比】區塊且 AI 遵守 beta≠alpha 鐵律
4. neutral/long 股維持原行為（向後相容）；DIRECTION 缺漏時由相位正確 fallback

**待生產驗證（沿用，用戶 deploy 後實機操作）：**
1. 印表報表 6104 收盤 100.5 顯示 100.5、6415 收盤 467.5 顯示 467.5
2. 印表報表 6150 撼訊 P&F 目標欄位（合理 > 73.1 或「—」）
3. NEWS chip 顯示實際 `summary_date`
4. 盤前清快取時 server log「TWII 資料非今日」警告，AI 輸出不含大盤點位

---

## 過往進度（2026-05-13 收工 — 三 bug 徹底解決：股價格式 / NEWS 大盤 / P&F 目標）

**所在週次：週7（UI 重整 + 設計層 bug 修復）**

**狀態：HEAD = `00f5159`（已 push origin/main）**

**本次（2026-05-13 第三輪）進度 — 用戶系統性除錯三個 bug：**

### Commit `e601d3e` — fix(format): _format_price 依 TWSE tick 規則

**用戶回報：** 創惟（6104）收盤 100.5 顯示 100、矽力-KY（6415）收盤 467.5 顯示 468

**根本診斷：** `app.py:_format_price` line 73-78 對 ≥100 用 `f"{v:,.0f}"`，Python `:.0f` 採 IEEE 754 round-half-to-even（banker's rounding）：
- `f"{100.5:,.0f}"` = `"100"`（100 偶數）→ 創惟案例
- `f"{467.5:,.0f}"` = `"468"`（468 偶數）→ 矽力案例

設計缺陷：TWSE tick 規則 100–500 元區間 tick=0.5，必然產生 .5 價位，整數格式必丟資訊。dashboard.js 用 `${q.close}` 顯示完整精度不受影響，僅 print_report.html 4 處（價格 + 撐/壓/目標 pill）受害。

**修法（依 TWSE 申報價格升降單位）：**
- `<50` 元（tick 0.01–0.05）→ 2 dp
- `50–500` 元（tick 0.10–0.50）→ 1 dp
- `≥500` 元（tick 1.00–5.00）→ 0 dp 千分位

**驗證：** `tests/test_format_price.py` 新增 15 case（user bug case + tick 邊界 + Decimal/int 輸入）。

### Commit `7ee7950` — fix(twii): NEWS 大盤數字昨日復發徹底解決

**用戶回報：** 今日財經新聞的大盤數字是昨日的，前次 `fde93e5` / `f800c7f` 修法已做過卻又發生。

**根本診斷：前次修法盲區**
- `fde93e5` 只擋 AI 從訓練資料引用歷史數字（"1778點" / "破3萬點"）
- 但若 `modules/data_fetcher.py:_fetch_ticker` 對 `^TWII` 回傳「昨日 bar」（盤前 / Render IP 限流 / Yahoo 1d chart 邊界），caller 盲拿 `iloc[-1]` 餵給 `analyze_daily_news` → AI 忠實複述「今日大盤 X 點」實際是昨日的 X
- 這不是 AI 幻覺，是資料層說謊
- 個股已透過 `32bf6af` 的 `_resolve_quote` 加 stale 偵測，TWII 卻無對等防護

用戶 pushback「股價都可以抓取了，為何大盤指數不能抓?」一針見血 — 答案：個股有 freshness check、TWII 沒有。

**修法（比照個股 stale 偵測 pattern，三件事）：**
1. `modules/data_fetcher.py:_fetch_ticker` 回傳 dict 加 `last_date` 欄位（success / fallback 兩 path 都有）
2. `run_daily_report.py` + `app.py:/api/news/regenerate` 取 `twii_data` 後檢查 `last_date == today_tw`：
   - 一致 → 注入 `twii_price` 給 `analyze_daily_news`
   - 不一致 → 不注入 + log 警告，AI prompt 無 `twii_block`，誠實 > 錯誤
3. `templates/print_report.html` 範圍 chip 改顯示 `daily_news.summary_date` 而非 `date_str[:10]`，header 文案「今日財經新聞」改「財經新聞」配合 — 同時修了 Bug 6 (2026-05-08) 「fallback yesterday 但 UI 顯示今天」的雙重誤導

**驗證：** `tests/test_twii_freshness.py` 新增 7 case（_fetch_ticker source 含 last_date / freshness logic 五情境 / analyze_daily_news 在 twii_price=None 時不注入 twii_block）。

### Commit `00f5159` — fix(pnf): 目標價邏輯不通（target<現價）

**用戶回報：** 6150 撼訊現價 73.1 但 P&F 概念目標 62（目標低於現價無意義）。質疑「其他沒有目標 = 尚未突破前高」邏輯：「照理說應該是往歷史回朔去找出現在的目標價才對」。

**根本診斷：`modules/candlestick.py:512-575 calc_pnf_target` 兩面盲區**
- 找到舊期窄箱後檢查 `cur > box_top × 1.02` 即過關
- 但 target = box_top + (box_top - box_bottom) 可能已被 cur 遠超，**code 未檢查就 return**
- 另一面：line 566-567 寫死「最近箱體未突破 → 直接 None，不往舊箱找」，違反用戶「回溯找歷史」期待

**修法（Filter A + Filter B）：**
- Filter A（既有調整）：`cur ≤ box_top × 1.02` → `continue` 往更早找（舊邏輯 `return None` 不再硬死）
- Filter B（新增）：`target ≤ cur × 1.02` → `continue` 往更早找
- 全歷史掃完都無有效箱才回 None

**設計選擇：** 保留 Darvas 等幅量度（破鄉理論）而非重寫為 P&F 3-box reversal counting — 對 AI 報表觀感無實質差異、維護成本低、與既有 commit / CLAUDE.md 語意一致。若日後 None 頻繁出現再評估升級為 P&F counting，進 `plan.md`。

**驗證：**
- 既有 7 個 calc_pnf_target test 仍綠（`test_basic_breakout` / `test_stable_target_after_new_bar` 兩個 cur 微調以滿足 Filter B）
- 新增 2 個 regression：`test_bug_c_target_below_current_rejected`（6150 風格）、`test_bug_c_unbroken_recent_falls_back_to_older_box`（用戶回溯期待）

### 本輪共同 sanity 信號
- pytest 46/46 全綠（37 candlestick + 7 TWII + 2 Bug C 新增）
- 本機因 Flask 依賴未裝，`tests/test_format_price.py` 15 case 與 `tests/test_print_report.py` 在本機無法 collect；邏輯已 inline 驗證 13/13；CI / 主開發機可正常跑
- py_compile candlestick / app / data_fetcher / run_daily_report / ai_analyzer_v2 全綠
- 三 commit 已 push（`84d1e95..00f5159`），Render auto-deploy 觸發中

### 留給下次

**Bug D（✅ 2026-05-17 已完成，commit `095ea7a`，方案見 `plan.md §十九`）：** 個股 vs 大盤同期對比，避免 AI 把 beta 當 alpha。
- 採最小版：`data_fetcher.get_index_daily_closes('^TWII')` + `ai_analyzer_v2._market_rs_block`（5/20日相對強度 pp 鎖定值 + 大盤對比鐵律）注入 dynamic_block；零新 DB/回填/經常成本
- TWII 取得失敗/個股 bar 不足 → 不注入（誠實 > 錯誤）；測試 `tests/test_market_rs.py` 10 case
- 中等版（產業分類）/ 廣版（RS Rating）暫不做，未來規模擴大再評估
- ⚠️ 待用戶 AI 重跑實機驗證大盤對比區塊有出現且 AI 有遵守鐵律

**E（下輪討論）— 空方/賣空進場點與下行目標：** 目前系統只實作上漲方向（突破箱頂 → 等幅量度向上 target）。用戶需要反向思考：
- 跌破箱底後的賣空進場點
- 跌破後回檔測試「壓力線」（原箱底反轉為壓力）的進場時機
- 等幅量度向下的下行目標空間：`box_bottom - (box_top - box_bottom)`
- AI 三宗師框架的空方對應：威科夫派發/下跌/再派發 phase 該給賣空建議而非僅「不宜行動」；本間頂部反轉型態（黃昏之星/吊人/空頭吞噬）應觸發空方時機；李佛摩跌破前低 + 5日均下彎為空方 pivot

**✅ 2026-05-17 兩項優先決策已定（方案見 `plan.md §二十`）：**
- **決策 1：`calc_pnf_target` 加 `direction='long'|'short'` 參數（預設 long）**，不做鏡像函式 — 等幅量度與 Filter A/B 掃描邏輯對稱共用，鏡像會雙倍維護剛修好的 `00f5159` 邏輯
- **決策 2：維持單一三宗師框架**，prompt 內先判結構方向再套對應招式，不拆 long/short 兩套（拆者更貴、框架本就對稱）

**實作三 commit 全完成（2026-05-17）：**
- **E-1 ✅**（commit `6c5afa5`）：`calc_pnf_target` 加 `direction` 參數（預設 long、long 分支逐字保留零退化）+ short 幾何鏡像 + 8 測試
- **E-2 ✅**（commit `86c10f4`）：`ai_analyzer_v2` 兩分析函式 prompt 加結構方向判定 + 三宗師雙向招式 + direction-aware 風險評分 + `DIRECTION` tag + 雙向 P&F；`_clean_html_output` 剝除 DIRECTION。**零-migration 設計**：DIRECTION 持久化/渲染改由 `phase_to_direction(威科夫相位)` 反推（AI 的 DIRECTION 本質即相位之函數），不新增 StockAnalysis 欄位。成本紀律前置已完成（合成 + 真實 DB 6743/4958/6415 派發股 dry-run 零退化）
- **E-3 ✅**（commit `8f4f943`）：`_render_one_block` pill 依相位反推方向翻轉（撐→空進/壓→空停/目標→空標）+ 方向 badge；`dashboard.js` 看板方向 chip（復用 wyckoff 色系，零新 CSS）。**plan §20 E-3 原文「壓力→空方目標」方向相反，已更正為財務正確映射**（壓力在上=空方停損、目標在下=空方目標），plan.md 同步更正
- 風險係數 direction-aware 由 E-2 prompt 重構達成（後端僅存 AI int，無需另改評分）

**⚠️ 待用戶決策（不在 plan §20 議定範圍，未擅自擴大）：** `generate_personal_recommendation` 仍純多方框架（加碼/進場買入），市場分析轉空方時個人建議會不一致。需決定是否補 direction-aware（它收 `wyckoff_phase` 參數，可比照 phase_to_direction 加空方 action_template；但屬 per-user 高頻呼叫、有成本）。

**⚠️ 待用戶 AI 重跑實機驗證（E-2/Bug D）：**
1. 派發/下跌股分析輸出有 `DIRECTION: short`、空方操作框架（賣空進場/回補/下行目標），非「不宜行動」
2. 印表報表/看板 short 股 pill 顯示空進/空停/空標 + 方向 badge「空」
3. dynamic_block 出現【大盤對比】區塊且 AI 遵守 beta≠alpha 鐵律
4. neutral/long 股維持原行為（向後相容）

**待生產驗證（用戶 deploy 後實機操作）：**
1. 印表報表 6104 收盤 100.5 顯示 100.5、6415 收盤 467.5 顯示 467.5
2. 印表報表 6150 撼訊 P&F 目標欄位（看是顯示「—（尚未接近突破點）」還是合理的 > 73.1 數字）
3. NEWS chip 顯示實際 `summary_date`（若昨日 fallback 則顯示昨日日期）
4. 盤前清快取時 server log 出現「TWII 資料非今日」警告，AI 輸出不含大盤點位

---

## 過往進度（2026-05-13 收工 — 修 QuoteCache 鎖死 bug）

**所在週次：週7（UI 重整 + 設計層 bug 修復）**

**狀態：HEAD = `32bf6af`（已 push origin/main）**

**本次（2026-05-13 第二輪）進度 — 修「儀表板股價不是當日收盤」設計層 bug：**

**Commit `32bf6af` — fix(quote): 修 QuoteCache 鎖死壞資料整天 — post-close 優先 MarketDataCache + stale 偵測**

**根本診斷：systematic-debugging 四階段定位根因**
- `QuoteCache` 註解明文寫死「寫滿即固化（盤中自動更新由前端 retry/refresh 控制）」，但 `dashboard.js` 沒有 setInterval / retry / refresh 機制
- 失效條件只看 `cache_date == today_tw`，不分「盤前/盤中/盤後」身份；任何盤前/盤中 cache miss 觸發 yfinance → 寫入「未 settle 的 OHLC」→ 整天黏住
- DB 證據：5/13 全 18 支於 TPE 00:36 凌晨被某觸發源寫入（GitHub Actions 已停用、`run_daily_report.py` 不寫 quote_cache、dashboard.js 無 setInterval — 觸發源未確認），盤後查仍是凌晨那份；`prev_close` 連 5/12 真實收盤都對不上

**修法（B+C 融合，純後端一檔改動）：**
- 抽 `_resolve_quote(db, symbol, today_tw, now_utc, get_yahoo_quote=None)` 純函式 + 6 helpers（`_post_close_tw` / `_today_close_threshold_utc` / `_upsert_quote_cache` / `_bars_to_spark` / `_strip_internal` / `_try_market_data_cache` / `_try_quote_cache_db`）
- `api_market_quote` view function 簡化為 dispatch
- 讀取優先序變更：

| 時段 | 順序 |
|------|------|
| post-close（TW ≥ 14:30）| ① **MarketDataCache(today)**（命中即 upsert QuoteCache）→ ② mem stale check → ③ QuoteCache stale check → ④ Yahoo（upsert QuoteCache）|
| pre-close | ① mem → ② QuoteCache → ③ MarketDataCache → ④ Yahoo（保留原行為）|

- stale 判定：`cached_at < 今日 14:30 TW threshold` → 視為盤前/盤中寫入、不可信、繞過
- `_quote_cache` value 加 `_cached_at_utc` 內部欄位，回傳前以 `_strip_internal` 剝除底線開頭欄位
- 自動修復：post-close 第一個 request 進來後既有壞 QuoteCache 會被自動覆寫

**驗證：**
- 新增 `tests/test_market_quote.py`：11 case（4 helper + 5 核心優先序 / stale 偵測 + 1 pre-close 不退化 + 1 mem invalidation + 1 Yahoo 失敗）全綠
- 既有 65 case 全綠（pytest 76/76）
- `py_compile app.py` OK
- 用 DB 既有 MarketDataCache 拆 `daily_bars[-1]` 驗證 close 對得上 QuoteCache（6921.TW 5/12 → MATCH ✓）
- **生產驗證**：commit push → Render auto-deploy → user refresh dashboard → 5/13 quote_cache **18/18 從凌晨 00:36 → 20:51 TPE**；`prev_close` 全部對得上 5/12 MDC 真實收盤 ✅

**還沒解（不影響功能）：**
- 凌晨 00:36 觸發源仍未確認（剩可能：Render warm-up / 外部 monitor / 手機分頁喚醒）
- 但無論誰觸發，新邏輯都會在 post-close 第一次 request 自動修復，所以列為 nice-to-have

**留給下次：**
- 想根除凌晨觸發：查 Render 後台 cron / health-check 設定
- 想 post-close 也走 ③ MDC 而非 fall through 到 Yahoo：跑一次「一鍵分析」讓今日 MDC populate（GitHub Actions 已停用，需手動觸發）

---

## 過往進度（2026-05-13 dashboard 卡片改版 + 工具鏈擴充）

**狀態：HEAD = `37cc3e6`**

**本次（2026-05-13）進度 — dashboard 卡片重新設計（5 輪 mockup → 正式上線）：**

**Commit `37cc3e6` — feat(ui): dashboard 卡片改版 — slate-900 + 台股紅綠 + 20日K + IBM Plex Sans**

設計流程（用 ui-ux-pro-max skill 查設計庫 + mockup 迭代）：
- v1：slate-900 + IBM Plex Sans + tabular-nums（基礎方案）
- v2：加 7 日 sparkline + RISK 改 inline chip + 移除 risk-bar
- v3：翻轉漲跌色為**台股紅綠慣例**（用戶提醒既有 app.css 用美股慣例是 bug）
- v4：badge 從 absolute 改 inline（解決「觀察中」3 字壓到 price）+ sparkline 改 mini K 棒
- v5：對齊修正（wyckoff/risk chip） + K 棒擴增 7 → 20 根（覆蓋 1 個月交易日）

**主要技術變動：**
1. **CSS token 重定義** `static/css/app.css`：
   - 主題：slate-950/900 系列（bg `#020617` / card `#0F172A` / border `#334155`）
   - 漲跌：`--up: #EF4444` / `--down: #22C55E`（台股慣例）
   - 風險：`--risk-low: cyan` / `--risk-mid: amber` / `--risk-high: fuchsia`（獨立 token 避開紅綠）
   - 強調：`--accent: #38BDF8`（已分析、tab active）
2. **全檔色彩翻轉**：`.up/.down/.bull/.bear/.support-level/.resistance-level/.wyckoff-*/.qs-*` 從美股慣例改為台股
3. **字體**：IBM Plex Sans Google Font + `font-feature-settings: 'tnum' on` 全域
4. **卡片 layout**：
   - badge `absolute` → inline 放 card-name 上方
   - 新增 `.card-status-row`（wyckoff + RISK chip 並排）
   - 新增 `.card-spark-wrap`（20 日迷你 K 線 SVG）
   - 移除 `.risk-bar/.risk-fill`（長條圖換 inline chip）
   - `.analyzed-badge` display:none（漸層 bar 已足夠）
5. **Sparkline 後端**：
   - `get_stock_quote` 抓 30 天 → 回傳 `spark_bars: [{o,h,l,c}] × 20`
   - `api_market_quote` 三條讀取路徑（QuoteCache / MarketDataCache / Yahoo）均回 spark_bars
6. **Sparkline 前端**：
   - `renderSparkline(bars)`：動態生成 SVG 20 根 K 棒（紅實體 = 漲 / 綠實體 = 跌）
   - `sparkPctLabel(bars)`：算 20D 整體漲跌幅 + 染色
   - `buildCard / updateCardPrice / markCardAnalyzed` 全部適配新結構

**Memory 紀錄：**
- 新增 `feedback_taiwan_stock_color_convention.md`：台股漲跌色慣例規則，未來會話開工自動載入提醒

**Claude Code 工具鏈擴充（user scope 全域）：**
- 安裝 `ui-ux-pro-max` skill（67 風格 / 161 配色 / 99 UX 準則，本次主要用它跑 fintech dashboard design system）
- 安裝 `context7` MCP server（即時抓 Flask/SQLAlchemy/Anthropic SDK 等套件文件）
- CLAUDE.md「Claude Code 工具鏈」區塊新增說明

**驗證：**
- pytest 37/37 通過
- py_compile 全綠
- dashboard.js / app.js syntax OK
- Render 自動 deploy 中（webhook 觸發）

---

## 過往進度（2026-05-12 收工 — 6項邏輯Bug全修）

**狀態：HEAD = `fb58e39`**

**本次（2026-05-12 第二輪）進度 — 系統性審視週7程式碼，找出並修正 6 項邏輯 Bug：**

**Commit `fb58e39` — fix(audit): 修6項邏輯Bug — HTML清理/AI幻覺/權限/時間鎖/週末視窗/快取TW date**

| # | 嚴重度 | 檔案:行 | Bug | 修法 |
|---|--------|---------|-----|------|
| 1 | 🔴 | `ai_analyzer_v2.py:875` | `analyze_taiwan_market_v2` 末尾無 `_clean_html_output`，AI 若回傳 `<head>/<style>` 會污染頁面（與其他三個 AI 函式不一致）| 末尾加 `_clean_html_output(...)` 包裝 |
| 2 | 🔴 | `ai_analyzer_v2.py:973-977` | `analyze_weekly_taiwan_v2` 沒加歷史幻覺鐵律（commit `fde93e5` 只強化了 daily_news + taiwan_market_v2，週報函式遺漏）| prompt 加【數據鐵律】區塊（與 taiwan_market_v2 同模板）|
| 3 | 🟡 | `app.py:738-739` | `api_clear_today_cache` 缺 admin 檢查，任何登入用戶可清光所有共用快取 | 加 `if current_user.role != 'admin': return 403` |
| 4 | 🟡 | `app.py:505,509` | 時間鎖與冷卻硬編碼為 `< 0`（永遠停用），CLAUDE.md 標註的「測試模式遺留」 | 還原 `< 15` 與 `< 4 * 3600`，移除測試模式註解 |
| 5 | 🟡 | `app.py:822-827` + `dashboard.js:208-214` | 週末視窗只判 `h >= 14`，週五 14:00–14:29 報表已切到「週末視窗」但週報未跑 → daily_news=None、weekly=None 頂部空缺 | 兩端都改為 `h > 14 or (h == 14 and m >= 30)` 精確到分鐘 |
| 6 | 🟢 | `app.py:304, 382` | `api_market_quote` / `api_market_data` 用 UTC `dt_date.today()`，與其他端點用的 TW date 不一致，08:00 TW 翻日後 cache key 失準 | 改用 `(utcnow + 8h).date()` |

**未修 — 微小 7：`_fmt_bars` 特徵基準退化**
- 重新審視後判斷不算 bug：現有 fallback 已處理 `range_high == range_low → 中段` / `vol_avg == 0 → 均量`；生產 daily_bars ≥ 60 根不會踩到。

**驗證：**
- `pytest tests/test_candlestick.py` → 37/37 通過
- `py_compile`：app.py / ai_analyzer_v2.py / run_daily_report / run_weekly_report / stock_service 全綠
- `dashboard.js` JS SYNTAX OK
- 變更：3 檔、+23/-14 行

**注意：修 2 改了 `analyze_weekly_taiwan_v2` 的 prompt，下次週報跑（最近的週末視窗）才會看到效果。模板已被 `taiwan_market_v2` 同步驗證，不需特別重跑。**

---

**本次（2026-05-12 第一輪）進度 — K線多空欄位誤判修正：**

**Commit `e4bec98` — fix(kline): 修正K線多空欄位誤判邏輯 + 加入程式化特徵標注**

**根本診斷：AI 看紅K就說看漲、綠K就說看跌**
- `_fmt_bars()` 只輸出 OHLCV，AI 靠單根顏色+「陽線（收>開）看漲/陰線（收<開）看跌」速查推斷
- `analyze_market_only` prompt table 有「多空」欄，AI 填的是主觀判斷，非程式計算
- 違背本間宗久原則：十字星含意取決於高位/低位，非固定看法

**修法：**
- `_fmt_bars()`：每根K棒加入程式計算 `【特徵=量能·位置[·跳空]】`
  - 量能：放量(>1.5x)/縮量(<0.7x)/均量，基準 bars[-20:] 平均
  - 位置：極高位/高位/中段/低位/極低位，基準 bars[-20:] 高低範圍
  - 跳空：open vs prev_close ±1% 判定
- `analyze_market_only()` prompt：table 「多空」欄改「特徵」，移除「陽線/陰線」速查，加特徵欄鐵律，加K線序列bullet
- `analyze_stock_three_masters()` prompt：「說明多空含意」改「結合特徵量能·位置解讀」，加禁止只看紅/綠鐵律

**本次（2026-05-11）進度 — NEWS 區塊無法即時重生：**

**Commit `f800c7f` — fix(news): 清快取一併刪 DailyMarketSummary + 新增 /api/news/regenerate**

**根本診斷：清快取後 NEWS 仍顯示舊資料**
- `api_clear_today_cache` 只刪 `StockAnalysis`，完全不動 `DailyMarketSummary`
- NEWS 區塊讀最近一筆 `DailyMarketSummary`，只有 14:30 batch 才會更新
- 清快取→重跑一鍵分析：個股重新產生，NEWS 永遠是舊的

**修法：**
- `api_clear_today_cache`：一起刪 `DailyMarketSummary` 所有記錄
- 新增 `/api/news/regenerate` POST：重抓 RSS + 取 TWII 即時行情 + 呼叫 AI（含新鐵律 prompt）+ 覆寫今日 `DailyMarketSummary`
- `dashboard.js clearTodayCache`：清完後自動串呼 `/api/news/regenerate`，按鈕顯示「重生新聞…」進度

**本次（2026-05-11）進度 — AI 歷史幻覺封鎖 + K線 30 項測試：**

**Commit `fde93e5` — fix(ai): 封鎖AI引用歷史幻覺數字 + 新增K線30項測試**

**根本診斷：「1778點/突破3萬點」重複出現的根因**
- 前次修法（pubDate 48h + TWII注入）只保護 `analyze_daily_news()`
- `analyze_taiwan_market_v2()` 完全無防護 → AI 從訓練資料注入歷史事件
- 修法：兩個函式均加入明確禁令，列舉具體禁止數字（「1778點」「突破3萬點」「史高」等）

**修法細節：**
- `analyze_daily_news()`：補 2 條鐵律（禁歷史事件數字 + 新聞含此類描述需核實才引用）
- `analyze_taiwan_market_v2()`：新增【數據鐵律】區塊，注入當前收盤點位 `{price}` 並禁止引用訓練資料歷史數字；提供替代寫法（「創近N日高」）

**K線型態測試套件：**
- 新增 `tests/test_candlestick.py`，30 項測試，全部通過
- 覆蓋：Bug1三山頂freshness / Bug2嚴格峰谷 / Bug3大陽線gap_down / Bug4/5三白兵三黑鴉首根影線 / Bug6/7星形型態體型要求 + 回歸測試（正常形態不誤觸）

**本次（2026-05-11）進度 — K線型態全面 Bug 修正（7項）：**

**Commit `5b0fd26` — fix(candlestick): 7項K線型態Bug修正**

| # | 型態 | Bug | 修法 |
|---|------|-----|------|
| 1 | 三山頂/三川底 | 型態成立後每日重複觸發（舊高低點持續在40根窗口內）| 加入 `bars_since_peak/trough <= 15`，第三峰/谷超過15根前不觸發 |
| 2 | 峰谷偵測函數 | `>=` / `<=` 導致平台頂底（多根同高）每根都算峰值，製造假三山 | 改為嚴格 `>` / `<` |
| 3 | 大陽線 | 只排除 `gap_up`，跳空低開強力收復仍顯示「無跳空缺口」，描述矛盾 | 補上 `not gap_down` |
| 4 | 三白兵 | 第一根K棒（i-2）上影線未驗證 | 補 `(h[i-2]-c[i-2]) <= 30% 實體` |
| 5 | 三黑鴉 | 第一根K棒（i-2）下影線未驗證 | 補 `(c[i-2]-l[i-2]) <= 30% 實體` |
| 6 | 早晨之星 | 第一根任意陰線即觸發、第三根小陽線也觸發 | 要求第一根實體 > 50% 振幅、第三根同樣 > 50% |
| 7 | 黃昏之星 | 同上，第一根/第三根大小無限制 | 要求第一根大陽線（>50%）、第三根大陰線（>50%）|

**根本診斷：三山頂「一直顯示」的根因**
- Bug 2（`>=`偵測假峰）× Bug 1（無時效性）= 平台震盪股每天觸發
- 修後：第三峰必須是近15根內的真實局部高點，超過後自動靜音

---

**本次（2026-05-08）進度 — 分析日 14:30 邊界修正：**

**Bug E（分析日用 UTC 凌晨 00:00 翻日，08:00~14:30 灰色地帶）**
- ✅ 根因：`date.today()` 在 UTC+0 伺服器上，台灣 08:00 就翻日 → 08:00~14:30 快取失效但收盤資料還不在，跑出來是昨日資料且擋住下午正確分析
- ✅ 修法：新增 `_analysis_day_tw()`（三個檔案共用邏輯）
  - 平日 14:30 後 → 今日；其他（含週末/假日）→ 往前找最近工作日
- ✅ `app.py`：三個分析端點（`api_get_analysis` / `api_analyze_stock` / `api_recommend_stock`）改用此 helper
- ✅ `stock_service.py` `get_user_stocks()`：改由 `analysis_day` 精確篩選（非 `max(date)` 不限日期）
  - 效果：14:30 後看板卡片全部回到「尚未分析」→ 視覺提示可以分析了
- ✅ `run_daily_report.py`：`is_cached_today` / `cache_market_analysis` 改用 TW date 保持一致

**本次（2026-05-08）進度 — 週報觸發邏輯重整：**

**週末視窗 + 一鍵分析合併週報**
- ✅ 設計：週五 14:00 ~ 週一 09:00 = 週末視窗，一個入口
- ✅ `dashboard.js`：`isWeeklyWindow()` 判斷（UTC+8 換算）；`analyzeAll()` 在週末視窗先射 `/api/weekly-report/generate` 背景並行；`updateAnalyzeBtn()` 動態標示「含週報」
- ✅ `dashboard.html`：移除獨立「📊 週報」按鈕
- ✅ `app.py` `show_weekly`：補上週一 09:00 前條件 `(wd==0 and h<9)`
- ✅ `run_weekly_report.py`：`week_end` 改用 `(weekday-4)%7` 永遠指向本週五（修前週六跑 → 日期顯示 Mon~Sat）
- ✅ `run_daily_report.py`：移除 Friday auto-trigger（改為 button-driven）

**本次（2026-05-08）進度 — K線型態酒田五法強化 + 四項修復：**

**Bug 7（三山頂/三川底 偽陽性，9根就觸發）**
- ✅ 根因：用固定 bar index (`highs[2]`, `highs[6]`) 而非真實局部高低點；窗口只有 9 根，遠不足
- ✅ 修法：新增 `_find_local_peaks()` / `_find_local_troughs()`（左右各 min_gap=3 根確認真實峰谷）；lookback 改為 40 根；要求3個高/低點彼此間距 ≥ 5 根且高度在均值 ±3% 以內
- ✅ `_MULTI_CANDLE` 三山/三川 candle_count 從 10 → 40（與 lookback 一致）

**三白兵/三黑鴉條件補齊（酒田正規）**
- ✅ 舊：只要連三陽/陰線收盤遞增/減
- ✅ 新：加入「每根開盤必須在前根實體內（不跳空進入）」+ 上/下影線短（≤ 實體的 30%）
- 效果：連三跳空大漲現在只觸發三空上升，不再誤觸三白兵

**新增三空（酒田五法）**
- ✅ 三空上升（酒田）：連三根跳空上漲 → bearish（追漲已竭）
- ✅ 三空下降（酒田）：連三根跳空下跌 → bullish（恐慌已竭）

**新增三法（酒田五法）**
- ✅ 上升三法（酒田）：大陽線 → 3根在範圍內整理 → 大陽線突破 → bullish（多頭趨勢確認）
- ✅ 下降三法（酒田）：大陰線 → 3根在範圍內整理 → 大陰線跌破 → bearish（空頭趨勢確認）

**K線型態補全（酒田單根）**
- ✅ 新增蜻蜓十字（長下影無上影，強烈底部訊號 bullish/strong）
- ✅ 新增長腳十字（上下影線均長，強烈不確定 neutral/medium）
- ✅ 新增平頭頂（兩根高點相同，bearish/medium）、平頭底（兩根低點相同，bullish/medium）
- ✅ 十字星加互斥條件，避免與蜻蜓十字/長腳十字重複觸發

**Bug A（股票名稱旁股價消失）**
- ✅ 根因：`app.py /print-report` 用 `cache_date == today_tw` 查 QuoteCache → 14:30 前批次未跑，回傳空
- ✅ 修法：改用 max(cache_date) subquery 取最近一筆（與 Bug6 DailyMarketSummary 同模式）

**Bug B（報表未提示量需突破多少張）**
- ✅ 根因：突破/Spring 量能門檻完全依賴 AI 自行發揮，無程式計算數值
- ✅ 修法：`ai_analyzer_v2.py` 兩個函式新增 `_vol_breakout = vol_5avg × 1.5`、`_vol_spring = vol_5avg × 1.2`
  - dynamic_block 注入【突破最低量能門檻】欄位（程式計算，禁止更改）
  - `analyze_stock_three_masters` action_section 直接嵌入具體張數
  - `analyze_market_only` static_block 等待條件指示 AI 引用欄位數值

**Bug C（P&F 目標價偏高 — 破鄉理論驗證）**
- ✅ 破鄉理論公式正確：`target = base_high + (base_high - base_low)` = 等幅量度 Measured Move
- ✅ 問題是基底定義不嚴謹：用趨勢段（波動率>35%）當基底 → 目標必然偏高
- ✅ 修法 `calc_pnf_target`：
  1. 波動率 > 35% → 縮至 4 根找更緊箱體
  2. `current_price < base_high × 0.85` → 回 None（尚未接近突破點，不顯示目標）
- ✅ 兩個 analyze 函式均傳入 `current_price` 參數；None 時顯示「—（尚未接近突破點）」

**本次（2026-05-08）進度 — 財經新聞區塊修復：**

**Bug 6（每日財經新聞區塊完全不出現）**
- ✅ 根因 A：`app.py /print-report` 用 `filter_by(summary_date=今天)` 查 DB，但批次 14:30 才跑 → 早上開報表回傳 None → 整個 `§ NEWS` 區塊消失
  - 修法：改為 `.order_by(summary_date.desc()).first()` 取最近一筆（昨天資料含「隔日方向注意」早上看最有用）
- ✅ 根因 B：`analyze_daily_news()` prompt 從未設計「建議」section → 三個預期區塊只有兩個
  - 修法：加第三個 `<h3>操作建議（依新聞評估）</h3>` section，max_tokens 600 → 800
  - 生效時機：今天 14:30 批次重跑後，新摘要才含第三個區塊

**2026-05-07 累積修復（昨日）：**
- Bug 1 & 2：財經新聞引用錯誤大盤數值（pubDate 48h 過濾 + TWII 注入）
- Bug 3：K線型態 AI 自行命名（`label_bars()` 程式標注 + 鐵律）
- Bug 4：列印 PDF 大量空白（移除 `.stock-block` page-break-inside: avoid）
- Bug 5：P&F 目標 AI 自行估算（`calc_pnf_target()` 等幅量度程式計算）

**本次（2026-05-07）進度 — 報表三大 Bug 修復 + PDF 空白 Bug 修復 + P&F 計算修正：**

**Bug 1 & 2（財經新聞引用錯誤大盤數值）**
- ✅ `data_fetcher.py`：`get_tw_news_rss()` 加 pubDate 48 小時過濾，排除舊文章混入（根因：無日期篩選導致 Google News 回傳歷史舊文，如「台股破3萬點」「大漲1778點」）
- ✅ `ai_analyzer_v2.py`：`analyze_daily_news()` 新增 `twii_price` / `twii_change_pct` 參數，注入 prompt 並加鐵律「若提及大盤點位必須使用此數值，嚴禁訓練資料歷史數值」
- ✅ `run_daily_report.py`：呼叫 `get_global_markets()` 取 TWII 今日收盤與漲跌幅，傳入 `analyze_daily_news()`

**Bug 3（K線型態 AI 自行命名錯誤）**
- ✅ `candlestick.py`：新增 `label_bars(bars) -> dict`，對每根 K 棒以數學公式計算型態標籤（`{date: 型態名稱}`），日K/週K/月K 三個時間框架均適用
- ✅ `ai_analyzer_v2.py`：`_fmt_bars()` 加 `pattern_labels` 參數，每根K棒後附加 `▶大陰線` 等程式計算標籤；`analyze_market_only()`、`analyze_stock_three_masters()`、`analyze_taiwan_market_v2()`、`analyze_weekly_taiwan_v2()` 全部套用
- ✅ 所有分析 prompt 加鐵律：「▶型態名稱 為程式精確計算，禁止更改，只解讀含意」
- ✅ 驗證：晶心科 2026/05/06 → `▶大陰線`（正確）、2026/05/07 → `▶陽線(11%)`（正確）

**Bug 4（列印 PDF 持股與分析之間大量空白）**
- ✅ `templates/print_report.html`：移除 `.stock-block` 的 `page-break-inside: avoid`
  - 根因：analysis-wrap 超過一頁時 Chrome 仍分頁，但先把整塊推到下一頁，前頁留下大整頁空白
  - 修法：對各子區塊個別控制 — `.stock-block-header` / `.data-row` / `.pills` 加 `break-inside: avoid` + `break-after: avoid`，讓 analysis 緊接 pills 自然展開；`.analysis-wrap table` 加 `break-inside: avoid` 防 K棒表格被切斷

**Bug 5（P&F 概念目標 AI 自行估算，無固定公式）**
- ✅ 根因：`TARGET_PNF:` 完全由 AI 自由輸出，每次結果不同，HTML span 與結構化標記可能不一致
- ✅ `candlestick.py`：新增 `calc_pnf_target(bars, lookback=12) -> float | None`，公式 = `base_high + (base_high - base_low)`（等幅量度），優先用週K（12根≈3個月），備援日K（20根）
- ✅ `ai_analyzer_v2.py`（`analyze_market_only` + `analyze_stock_three_masters`）：
  - 移除 `TARGET_PNF:` 結構化標記（不再需要 AI 輸出）
  - dynamic_block 注入程式計算值 + 鐵律「禁止更改」
  - result dict 直接用 `_pnf`，不再解析 AI 輸出
- ✅ 驗證：base_high=250, base_low=175 → 目標 325（與手算一致）
- 注意：**支撐壓力維持 AI 推斷**（從真實 OHLCV 推斷，非純幻想；支撐壓力本身主觀，AI 推斷可接受）

**先前未解（仍待）：**
- ⏳ 分享 PDF 寄送 timeout：`SSL/465: timed out`（Render → Gmail SMTP 不穩）
  - 決策：暫緩，改手動存 PDF 轉傳給親友
  - 已討論方案供日後參考：A. 換 Resend HTTP API（推薦） / B. Render Starter / C. 加 timeout

**下一步（按優先順序）：**
1. **驗證 K線特徵標注**：下次個股分析後，確認第二節 table「特徵」欄顯示程式計算值（如「放量·高位」），不再出現「看漲/看跌」；十字星解讀有帶位置語境
2. **驗證 AI 幻覺封鎖**：Render 部署 `e4bec98` 後，按「🗑 清快取」→ 等新聞重生 → 確認 NEWS 不再出現「1778點」「突破3萬點」
3. **驗證三山頂修正**：觀察原本天天顯示三山頂的個股，確認 15 根靜音機制生效
4. **驗證早晨之星/黃昏之星**：確認小陰+小實體+小陽不再誤觸發（需 3 根實體均 > 50% 振幅才觸發）
5. **驗證週末視窗**：週五 14:00 後按一鍵分析，確認按鈕顯示「含週報」、週報背景產生、PDF 顯示 §MARKET
6. **驗證量能門檻出現**：下次個股分析確認報表「等待條件」有具體張數（如「突破需 1,800 張」）
7. **驗證 P&F 目標合理性**：若顯示「—（尚未接近突破點）」代表修法生效
8. **K線型態歷史累積**：目前第一批資料已入 DB，待 1-2 個月後查看 return_3/5/10d 回填結果
9. 清理遺留
   - 還原時間鎖 `< 0` → `< 15`、冷卻 `< 0` → `< 4 * 3600`（`app.py`）
   - 移除「🗑 清快取」按鈕（`dashboard.html`、`dashboard.js`、`app.py`）
10. 重新跑一次週報驗證 commit `c95d0dd` 修法（會燒 ~$0.20）
11. （未做）「移除聯絡人」UI — v1 沒做，要刪要進 DB

## 費用速查

| 情境 | 月費 |
|------|------|
| 個人使用（1人 × 18支）| 約 US$15（NT$480）|
| 對外收費建議 | NT$300/人/月 |
| 打平門檻 | 5-6人（5人接近打平，6人開始盈餘）|

詳細估算見 `plan.md` 第零節（每日 ~$0.64、每週含週報 ~$3.40）。

## 專案基本資訊
- GitHub：`https://github.com/Jason690926/investment-system`（私人）
- 部署：Render `https://investment-system-lxq5.onrender.com`
- 資料庫：PostgreSQL via Supabase
- 本機路徑：`C:\Users\frodo.MSI\OneDrive\Desktop\investment-system`

---

## Claude Code 工具鏈（user scope，全域）

裝於 2026-05-12，跨專案可用：

- **ui-ux-pro-max** (skill)：UI/UX 設計庫查詢，50+ 風格、161 配色、57 字體配對、99 UX 準則、25 圖表類型，含 dark mode 獨立規則與對比度檢查。
  - **何時觸發**：改 `templates/*.html`、`static/css/*`、`static/js/dashboard.js` 視覺面 / 配色 / 字體 / 排版 / chart 時自動觸發
  - **成本**：核心是 local Python 查詢，0 token；後續套規格走我一般 token
  - **指令**：`python3 ~/.claude/skills/ui-ux-pro-max/scripts/search.py "<query>" --design-system`
- **context7** (MCP server)：即時抓套件官方文件，補我訓練 cutoff (2025-08) 後的 API 變動。
  - **何時觸發**：問 Flask / SQLAlchemy / yfinance / anthropic SDK / mistune / SortableJS / html2pdf.js 等套件文件時自動觸發
  - **成本**：MCP call，0 token（不打 LLM）
  - **工具**：`mcp__plugin_context7_context7__resolve-library-id` + `query-docs`

**注意：**
- ui-ux-pro-max **不適用** AI prompt 調整、DB schema、K 線演算法、cache 邏輯這類非前端工作
- context7 **不適用** 重構、寫腳本、debug 業務邏輯、code review，僅限「套件文件查詢」
- 兩者互不衝突，可同時觸發（例：改前端時若用到新版 Tailwind class，先 context7 確認語法，再 ui-ux-pro-max 給設計建議）

---

## 修改 AI 功能的紀律（避免燒 token）

修改會呼叫 Claude API 的程式碼前（週報產生、個股分析、產業指標股、市場分析等），必須在本機**用 DB 既有的真實 raw 輸出**完整推演 cleanup / prompt / 渲染管道，確認修法在實際資料上會 work，再讓使用者重跑。

**Why：** 每次週報重跑燒 ~$0.20、每次個股全分析燒 ~$0.6+。一輪「推測 → push → 使用者重跑 → 還是壞 → 再推測」就燒掉 $0.40+。1 人月預算才 $15，反覆燒會明顯吃掉預算且使用者體驗差。

**How to apply（修 AI 相關 bug 必做）：**
1. **先撈 DB 既有壞掉的 raw 輸出**（如 `WeeklyReport.html_market`、`StockAnalysis.html_content`）看實際內容，**不要憑想像**
2. **本機跑 cleanup / 渲染 pipeline 在那份真實壞資料上**驗證，確認修法 work
3. **覆蓋多種失敗情境**：完整輸出、截斷輸出、未閉合標籤、markdown 包裝等都要測
4. 如果只能用 AI 重跑才能驗證（如 prompt 改動），明確告知使用者「這次修法是基於分析、不確定 AI 會否規矩遵守，請評估是否值得花 ~$X 重跑」
5. 不確定就用「prompt + cleanup 雙保險」（prompt 約束根本面、cleanup 防禦邊界）— 不要只改其中一個就 push

---

## 前端設計原則

<frontend_aesthetics>
You tend to converge toward generic, "on distribution" outputs. In frontend design, this creates what users call the "AI slop" aesthetic. Avoid this: make creative, distinctive frontends that surprise and delight. Focus on:

Typography: Choose fonts that are beautiful, unique, and interesting. Avoid generic fonts like Arial and Inter; opt instead for distinctive choices that elevate the frontend's aesthetics.

Color & Theme: Commit to a cohesive aesthetic. Use CSS variables for consistency. Dominant colors with sharp accents outperform timid, evenly-distributed palettes. Draw from IDE themes and cultural aesthetics for inspiration. This project uses a dark theme — keep it dark and extend it with character.

Motion: Use animations for effects and micro-interactions. Focus on high-impact moments: one well-orchestrated page load with staggered reveals (animation-delay) creates more delight than scattered micro-interactions.

Backgrounds: Create atmosphere and depth rather than defaulting to solid colors. Layer CSS gradients, use geometric patterns, or add contextual effects that match the overall aesthetic.

Avoid generic AI-generated aesthetics:
- Overused font families (Inter, Roboto, Arial, system fonts)
- Clichéd color schemes (particularly purple gradients on white backgrounds)
- Predictable layouts and component patterns
- Cookie-cutter design that lacks context-specific character

Interpret creatively and make unexpected choices that feel genuinely designed for the context.
</frontend_aesthetics>
