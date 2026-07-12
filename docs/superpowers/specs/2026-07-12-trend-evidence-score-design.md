# 趨勢判斷收斂為加權證據評分 — 設計文件

> 日期：2026-07-12｜方案：兩階段（否決層不變 + 證據層 OR→加權評分）

## 一、問題陳述

`modules/data_enricher.py` 的 `_structure_flag()`（威科夫結構閘，§二十六起沿用至今）決定 `structure_flag` 三態（結構已轉弱 / 結構未轉弱 / 結構轉折中），是全系統唯一的方向第一層閘門——往下接 `_apply_structure_safety_net`、`_decide_action`、P&F 方向選取、pill 顯示，即 CLAUDE.md 記載的「威科夫定方向（第一層，不可被推翻）」架構原則。

自 §三十（2026-05-25）起，每次使用者拿實際收盤結果 cross-check 報表、抓到一個結構誤判案例（東捷型「轉折中卡住強勢起漲股」、技嘉型「進行中月V型反轉」等），修法方式都是在 `_structure_flag` 的證據判斷裡加一個新的布林 override（`close_strict_up_3` / `bull_count_6` / `inprogress_strong_up`，目前已有 3 個），彼此用 `or` 串接。這個模式有兩個問題：

1. **維護成本遞增**：每加一個新訊號都要開一個新的 if 分支，且該分支只解決當初觸發它的那個具體案例，無法表達「多個弱訊號疊加也算數」。
2. **已算出卻未使用的訊號被浪費**：`get_full_stock_data()` 已計算 `ma5`/`ma20`/`ma60`，`compute_monthly_structure()` 內部也已算出 `weekly_momentum`（週K動能），但目前 `weekly_momentum` 只當唯讀文字塞進 prompt 給 AI 參考，均線排列完全沒被使用於任何判斷。

**驗收基準（使用者拍板，2026-07-12）**：這次重構的優先順序是「操作建議/方向判斷要更準確」，其次才是維護成本；新模型在既有歷史 cross-check 案例上必須不遜於現行版本，理想上能新解出目前 4 個布林 override 都接不住的邊界案例。

## 二、設計目標

把「證據層」（未轉弱 vs 轉折中的判斷）從 OR 串接布林值，改成加權證據評分 + 門檻。**否決層（結構已轉弱的判定）完全不動**——這是最高風險的部分，任何訊號都不該有機會稀釋掉「現價跌破季線 / 月K下跌 / 連續兩月收陰」這三個否決條件，繼續維持絕對優先、不可被其他訊號抵銷。

### 非目標

- 不改否決層判定邏輯（`price_vs_ma60=='在下'` / `monthly_structure=='跌'` / `consecutive_bear>=2` → 結構已轉弱，逐字保留）。
- 不對外新增欄位、不改 `structure_flag` 的三態字串值域。`_decide_action`、`_apply_structure_safety_net`、prompt 樣板、其餘 8+ 個測試檔對 `structure_flag` 字串比對的呼叫點全部不用修改。
- 不新增資料來源：`ma5`/`ma20` 已在 `enriched_data` 內，`weekly_momentum` 已在 `compute_monthly_structure` 內部算出。
- 不允許新訊號（均線排列、週K動能）把已經被舊觸發條件判定「未轉弱」的案例往回拉成「轉折中」（見下方權重設計，新訊號單獨權重恆低於門檻）。

## 三、加權證據評分設計

### Stage 1（否決層，逐字不動）

```
if monthly_structure == '資料不足':
    return '資料不足'
if price_vs_ma60 == '在下' or monthly_structure == '跌' or consecutive_bear_months >= 2:
    return '結構已轉弱'
```

### Stage 2（前提不變，OR 改加權評分）

前提沿用現行 `and` 條件：`price_vs_ma60 == '在上' and consecutive_bear_months <= 1`（未達此前提直接落入「結構轉折中」，不進入評分）。

新增 `_trend_evidence_score(...)` 純函式，回傳分數：

| 訊號 | 條件 | 權重 |
|------|------|------|
| 月K結構 | `monthly_structure in ('升', '橫')` | +1.5 |
| close 嚴格上揚 | `close_strict_up_3` | +1.5 |
| 近6月陽月數 | `bull_count_6 >= 4` | +1.5 |
| 進行中月強漲 | `inprogress_strong_up` | +1.5 |
| **新增** 均線多頭排列 | `ma5 > ma20 > ma60`（皆非 None）| +1.0 |
| **新增** 週K動能=升 | `weekly_momentum == '升'` | +0.5 |
| **新增** 週K動能=橫 | `weekly_momentum == '橫'` | +0.2 |

**門檻 = 1.5**：`score >= 1.5` → `結構未轉弱`，否則 `結構轉折中`。

**權重設計理由**：
1. 四個既有觸發條件的權重都剛好等於門檻（1.5=1.5），保證「無新訊號介入時，輸出與現行版本逐位元組相容」——這是零退化的數學保證，不是靠測試碰運氣。
2. 兩個新訊號權重（1.0 / 0.5 / 0.2）均個別低於門檻，無法單獨觸發「結構未轉弱」，只能在**其他證據不足時聯手**把原本卡在「轉折中」的邊界案例拉過門檻（例：均線多頭排列 1.0 + 週K動能升 0.5 = 1.5，剛好過關）。這保證新訊號只會把「轉折中」案例往「未轉弱」推，不會動到任何現行已判定「未轉弱」的案例——即使全部既有布林值都不成立，加總新訊號的最高分（1.0+0.5=1.5）也只是「剛好」達標，不會無故大幅改變分類邊界。

### 簽章變更

`compute_monthly_structure(monthly_bars, weekly_bars, price, ma60, ma5=None, ma20=None)` 新增兩個可選參數（預設 `None`，未提供時均線排列訊號恆為 False，行為等同現行版本）。

`_structure_flag()` 新增對應參數 `ma_alignment: bool = False`，由呼叫端算好傳入（沿用既有函式傳「已算好的布林值」風格，例如 `close_strict_up_3` 就是外部算好傳入，非在 `_structure_flag` 內部重算）。

### 呼叫端變更

`modules/ai_analyzer_v2.py:_structure_block()`（全系統唯一呼叫點）：

```python
ms = compute_monthly_structure(
    enriched_data.get('monthly_bars', []),
    enriched_data.get('weekly_bars', []),
    price_f,
    enriched_data.get('ma60'),
    enriched_data.get('ma5'),
    enriched_data.get('ma20'),
)
```

## 四、附帶修法：short 方向結構安全網對稱

`_apply_structure_safety_net()`（`ai_analyzer_v2.py:734`）目前只單向保護 long：

```python
if structure_flag == '結構已轉弱' and direction == 'long':
    return 'neutral'
return direction
```

`結構未轉弱` 時 prompt 明文禁止 AI 標 short（見 `_structure_block` 的 gate_hint），但完全沒有 post-process 防護網——若 AI 違規輸出 `DIRECTION=short`，`result['direction']` 會持續污染下游（dashboard 方向 badge、`_dual_pnf` 選邊、`_resolve_swing_anchors` 選錨點），且沒有任何字面文字砍除。目前無實際案例證實已發生，但這是與本次改動同一批消費端、同一批測試檔的邏輯漏洞，一併補上鏡像分支：

```python
if structure_flag == '結構已轉弱' and direction == 'long':
    return 'neutral'
if structure_flag == '結構未轉弱' and direction == 'short':
    return 'neutral'
return direction
```

## 五、實作位置

| 檔案 | 變更 |
|------|------|
| `modules/data_enricher.py` | `_structure_flag()` 改為呼叫新 `_trend_evidence_score()` 計算證據層分數；`compute_monthly_structure()` 加 `ma5`/`ma20` 參數並算出 `ma_alignment` 傳入 `_structure_flag` |
| `modules/ai_analyzer_v2.py` | `_structure_block()` 呼叫端補傳 `ma5`/`ma20`；`_apply_structure_safety_net()` 加 short 鏡像分支 |

## 六、測試

- `tests/test_monthly_structure.py` 既有 21 個測試（含東捷型/技嘉型/晶心科型/臻鼎型等真實案例還原 fixture）**全數維持逐字通過**，作為零退化的主要證據。
- 新增 `_trend_evidence_score()` 單元測試：四個既有觸發條件各自單獨達門檻（1.5）、任一新訊號單獨不達門檻、均線排列+週K動能升聯手達門檻、均線排列+週K動能橫聯手不達門檻（1.0+0.2=1.2<1.5）。
- 新增 1 個示範性 `compute_monthly_structure` 整合案例：monthly_structure=轉折、四個舊觸發全部不成立、但均線多頭排列+週K動能升 → 結構未轉弱（標註為示範案例，非真實歷史 cross-check 還原；真實精準度提升待下次使用者重跑報表後的 cross-check 確認，與過去 38 輪驗證模式一致）。
- `_apply_structure_safety_net` 新增 short 鏡像測試：`('結構未轉弱', 'short')` → `'neutral'`；`('結構未轉弱', 'long')` → `'long'`（不誤殺）；`('結構已轉弱', 'short')` → `'short'`（不誤殺，沿用既有測試不變）。

## 七、驗收標準

1. pytest 全綠（現行 375 + 新增，`test_monthly_structure.py` 既有 21 個逐字不變）。
2. py_compile `data_enricher.py` / `ai_analyzer_v2.py` 全綠。
3. 燒 ~$0.6 重跑一鍵分析後（用戶執行）：既有結構旗標判斷不應出現任何案例翻轉（與修法前同一批股票同一天 cross-check，方向判斷應完全一致）。
4. 下次真實 cross-check（用戶下一輪收盤後對照）：觀察是否有先前卡在「轉折中」的股票因均線+週K聯手證據被正確拉入「未轉弱」而避免誤判——此為精準度提升的實際驗收，非本次可靜態證明。

## 八、回滾策略

純加性變更 + 既有函式新增可選參數（預設值維持原行為）：
- `_structure_flag` 加權重構：`data_enricher.py` 單一 commit，可獨立 `git revert`，revert 後即完全恢復現行 OR 邏輯。
- short 安全網鏡像修法：`ai_analyzer_v2.py` 單一函式加一個 if 分支，可獨立 revert，不影響上述證據評分改動。
- 無 DB / migration 改動。
