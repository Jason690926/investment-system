# 強勢突破回測區異常 + P&F 目標缺失：設計

- 日期：2026-05-26
- 觸發：用戶 5/25 20:37 持股分析報告 PDF（14 股）+ 5/26 收盤截圖 cross-check。14 檔中 5 檔強勢突破股（東捷 / 矽力 / 合晶 / 瑞軒 / 微星）共同出現：
  - **Bug-1**：「回測進場（保守）」顯示遠低於現價的舊區間（-25% ~ -48%），家人讀者「等回測 75 才進」→ 該檔已起飛到 145.5
  - **Bug-2**：「目標：— 元」缺失，無上漲空間參考
- 對應 plan：§三十二

---

## 一、問題陳述

### Bug-1 — 強勢突破股「回測進場」顯示舊箱型區間

5 檔現價 vs「回測進場」對照：

| 股 | 現價 | 追進停損 (range_high) | 回測進場（報表） | 距現價 |
|----|------|---------------------|----------------|--------|
| 東捷 8064 | 145.5 | 143.5 | **75.00 ~ 109.25** | **-25% ~ -48%** |
| 矽力 6415 | 618 | 456 | **391.00 ~ 423.50** | -32% ~ -37% |
| 合晶 6182 | 76.8 | 59.3 | **52.10 ~ 55.70** | -27% ~ -32% |
| 瑞軒 2489 | 56.5 | 48.85 | **37.50 ~ 43.17** | -23% ~ -34% |
| 微星 2377 | 127 | 124 | **94.50 ~ 109.25** | -14% ~ -25% |

**根因**：`calc_swing_levels` 取 60 日窗口「最近局部峰」（line 76 `swing_high = peaks[-1][1]`），用 `_find_local_peaks(min_gap=3)` 需左右各 3 根確認 → 強勢突破中新峰尚未成形 → `entry_zone = (swing_low, mid)` 仍是更早箱型的範圍。

但 `_strong_breakout_state` 既然已認定「突破成立」，那「回測進場（保守）」概念上的錨點應該是 **被突破的前高**（即 `range_high`），而非更早的舊箱型區間。

### Bug-2 — 強勢突破股 P&F 目標缺失

5 檔報表「目標：— 元」。

**根因**：`calc_pnf_target` Filter A `current_price < base_high × 0.85` → 強勢突破中現價遠超 base_high → 所有候選箱被濾掉 → None。

設計矛盾：強勢突破成立 = 等幅量度條件最齊備的場景（已有確認的 box），這時 target 反而 None。

---

## 二、設計原則

### 原則 1：強勢突破成立 = 既有錨點失效，需用「突破事件」本身作新錨

`calc_swing_levels` 的 `entry_zone` 與 `target` 對「箱型整理 → 等回測」場景設計，但「強勢突破中」是另一個場景：
- 既有箱型已被穿過
- 新箱型尚未形成（需要時間 + 局部峰確認）
- 中間真空期應該用「被突破點」作錨

### 原則 2：retest zone 採「前高反轉為支撐」（Darvas Box / 威科夫 SOT）

突破成立後若回測，會在被突破的 range_high 附近找支撐（前壓力轉支撐原理）。對應數值：`(range_high × 0.97, range_high)` —— 單邊向下 3%，與既有「追進停損 = range_high」邏輯一致（停損 = 進場區下緣）。

不採對稱 ±3%：價格已在 range_high 上方，上限若 > range_high 沒意義。

### 原則 3：target 用「整波起漲點」作 base_low

`calc_swing_levels` 的 `range_low` 是「最近局部谷」，但強勢突破中這個窄箱已被穿過 → 等幅量度目標可能 < 現價（如合晶 range=(37.5, 59.3) → target 81.1，現價 76.8 接近）。

改用「過去 60 日絕對最低」作 base_low，代表「整波起漲點」：
- 合晶 base=28.25（2025/12 月低）→ target = 59.3 + 31.05 = 90.35（vs 現價 76.8 → +18%）✓
- 矽力 base=183.5 → target = 456 + 272.5 = 728.5 ✓

加 cap `min(target, price × 2.0)` 防離譜情況（如極端低基期股算出超大目標）。

---

## 三、影響範圍

- `modules/ai_analyzer_v2.py`：
  - 新增純函式 `_breakout_overrides(swing_levels, daily_bars, price)`
  - `analyze_stock_three_masters` 算完 `_breakout` 後，若 True 則覆寫 `swing_levels['entry_zone']` 與 `['target']`
  - `analyze_market_only` 同步
  - 寫入 `result['target_pnf']` 路徑跟著新值
- `_render_operation_framework` **零改動**（既有邏輯讀 swing_levels）
- dashboard `target` pill 自動同步（讀 `result['target_pnf']`）
- 既有 calc_swing_levels / calc_pnf_target **不動**（其他場景仍用既有邏輯）

---

## 四、修法設計

### 新增 helper：`_breakout_overrides`

```python
def _breakout_overrides(swing_levels: dict, daily_bars: list,
                         price) -> dict:
    """強勢突破成立時，覆寫 entry_zone 與 target（plan §三十二）。

    既有 calc_swing_levels 的 entry_zone / target 對「箱型整理 → 等回測」
    設計，強勢突破中該箱型已失效。本函式以「被突破前高」作 retest 錨點、
    以「過去 60 日絕對最低」作 base_low 重算等幅量度目標。

    輸入：
      - swing_levels: calc_swing_levels 結果（含 range_high）
      - daily_bars: 日 K bars（取最後 60 根）
      - price: 現價

    回傳：{'entry_zone': (rh*0.97, rh), 'target': bounded_etmm}
    任一輸入不足 → 回 {}（呼叫端不覆寫）
    """
    if not swing_levels or not daily_bars or price is None:
        return {}
    rh = swing_levels.get('range_high')
    if rh is None:
        return {}
    try:
        rh_f = float(rh)
        price_f = float(price)
        window = daily_bars[-60:] if len(daily_bars) >= 60 else daily_bars
        deep_low = min(float(b['low']) for b in window)
        if deep_low >= rh_f:  # 邏輯不通，退讓
            return {}
        etmm = rh_f + (rh_f - deep_low)  # 等幅量度
        target = min(etmm, price_f * 2.0)  # ×2 cap 防離譜
        retest_zone = (rh_f * 0.97, rh_f)
        return {'entry_zone': retest_zone, 'target': target}
    except (TypeError, ValueError, KeyError):
        return {}
```

### 呼叫端整合（`analyze_stock_three_masters` / `analyze_market_only`）

```python
# 既有：
_breakout = _strong_breakout_state(enriched_data, _price_f)
_swing_block = _dual_swing_block(enriched_data, _price_f)

# 新增（在 _swing_block 之後、_render_operation_framework 之前）：
if _breakout:
    _overrides = _breakout_overrides(
        _swing_long,  # calc_swing_levels('long') 結果
        enriched_data.get('daily_bars', []),
        _price_f
    )
    if _overrides:
        _swing_long['entry_zone'] = _overrides['entry_zone']
        _swing_long['target'] = _overrides['target']
        # 同步 result['target_pnf']（DIRECTION=long 場景）
        _pnf_long = _overrides['target']
```

`_swing_block` 已用 `_swing_long`/`_swing_short` 渲染（line 383 `_dual_swing_block`），覆寫後既有渲染自動拿新值。

### 邊界處理

| 情境 | 行為 |
|------|------|
| `breakout=False` | 不呼叫 `_breakout_overrides`，沿用 calc_swing_levels 原值 |
| `swing_levels=None` | helper 回 `{}`，不覆寫 |
| `daily_bars` < 1 根 | helper 回 `{}`，不覆寫 |
| `deep_low >= range_high` | 邏輯不通退讓，回 `{}` |
| short / neutral | helper 不呼叫（spec 只處理 long strong_breakout） |

---

## 五、驗證計畫（TDD）

### 新增測試 `tests/test_breakout_overrides.py`（≥7 case）

1. **happy path（東捷 case）**：rh=143.5, deep_low=43.25, price=145.5 → target=243.75, retest_zone=(139.20, 143.50)
2. **cap 觸發**：rh=10, deep_low=0.5, price=12 → etmm=19.5, cap=24 → target=19.5（cap 不踩）
3. **cap 觸發**：rh=100, deep_low=1, price=110 → etmm=199, cap=220 → target=199
4. **cap 觸發實際**：rh=100, deep_low=1, price=50 → etmm=199, cap=100 → **target=100**（cap 生效）
5. **deep_low >= rh 退讓**：rh=50, deep_low=60, price=55 → 回 `{}`
6. **swing_levels=None**：回 `{}`
7. **daily_bars 為空**：回 `{}`
8. **5 檔真實值對照**：套各檔 rh / deep_low / price 應算出設計表中的數字

### 整合測試 `tests/test_strong_breakout.py` 補測

- breakout=True 情境下，`_swing_long['entry_zone']` 被覆寫為 retest zone（單邊向下 3%）
- breakout=True 情境下，`_swing_long['target']` 為新計算值
- breakout=False 情境下，零退化（既有測試應全綠）

### 退化檢查

- 既有 `tests/test_strong_breakout.py` 5 case 全綠
- 既有 `tests/test_operation_framework.py` 6 case 全綠
- `tests/test_decide_action.py` 14 case 全綠（_decide_action 不動）

---

## 六、Deploy 驗收

燒 ~$0.6 重跑一鍵分析，5 檔強勢突破股應顯示：

| 股 | 期望 retest zone | 期望 target |
|----|-----------------|------------|
| 東捷 | 139.20 ~ 143.50 | 243.75 |
| 矽力 | 442.32 ~ 456.00 | 728.50 |
| 合晶 | 57.52 ~ 59.30 | 90.35（或 cap=153.6 → 90.35）|
| 瑞軒 | 47.38 ~ 48.85 | 67.70 |
| 微星 | 120.28 ~ 124.00 | 163.00 |

非強勢突破股（晶心科 / 創惟 / 華星光等）應**零變動**。

---

## 七、回滾策略

純加性 helper + 單一覆寫點，無 DB migration、無既有函式簽名改動。問題 `git revert` 即可。

最壞情況：覆寫邏輯有 bug → 回 `{}` 退讓 → 沿用原 calc_swing_levels 值（即 bug 修法前狀態），不會 crash。
