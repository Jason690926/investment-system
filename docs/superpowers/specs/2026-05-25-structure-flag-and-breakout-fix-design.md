# 結構閘漏洞 + 強勢突破門檻過嚴：設計

- 日期：2026-05-25
- 觸發：用戶 5/22 持股分析報告 PDF（14 股）+ 5/25 週一收盤截圖 cross-check。14 支 12 漲 2 跌（南亞科 -4.67% / 撼訊 -1.85%）、4 支漲停（合晶 / 東捷 / 瑞軒 / 矽力）。發現 2 個結構性問題。
- 對應 plan：§三十

---

## 一、問題陳述

### Bug A — 結構閘「結構轉折中」漏洞

東捷 8064 月K 序列：12月陽 → 1月陽 → 2月陰 → 3月放量多頭吞噬 → 4月放量大陽 +64% → 5月（進行中）實體 16% 高位震盪。本是強勢上漲剛確立。

`compute_monthly_structure` 排除進行中 5 月後看 2~4 月 3 根：
- highs 嚴格升（57.5 → 77.6 → 104.0）
- lows 不嚴格升（44.80 → **43.30** → 63.80）— 3 月低點略低於 2 月低點
- `_hl_trend` 因 lows 不嚴格升 → 回「**轉折**」
- `_structure_flag` 三層判定「已轉弱 > 未轉弱 > 轉折中」全 fall-through → 「**結構轉折中**」
- gate_hint「可標派發，須附量價證據」允許 AI 標派發

結果：5/22 報表判 short，空停 143.5，5/25 漲停 +9.81% 穿空停（高 145.5）→ 方向反向預測。

### Bug B — 強勢突破狀態被自己拉高的均量打死

5/25 漲停 4 支股票中只有合晶（6182）被認定「強勢突破成立」並解鎖「追進」選項；矽力（6415）/瑞軒（2489）雖突破前高但被打回「不宜追進」。

`_strong_breakout_state` 條件 2 「今日量 ≥ 5 日均量 × 1.5」用的 `volume_5d_avg_zhang` 含今日，又被前一根突破日的爆量拉高均值：

| 股 | 突破日 | 突破日量 | 之後量 | 5 日均 | 門檻 ×1.5 | 結果 |
|----|-------|---------|--------|--------|-----------|------|
| 合晶 | 5/21 (31K) | — | — | ~17.7K（前段縮量壓低）| 26.5K | ✅ 過 |
| 矽力 | 5/4 (?) | 5/19 高位空頭吞噬 16.7K | 5/22 12K | ~10.5K（被 5/19 拉高） | 15.7K | ❌ |
| 瑞軒 | 5/21 (爆量 96K) | 5/22 一字漲停 29K | — | ~49.6K（被 5/21 拉高） | 74.4K | ❌ |

「越強勢的股（突破日越爆量）→ 越容易在第 2 根失格」這個結構性矛盾。

## 二、設計原則

### Bug A：擴充「結構未轉弱」涵蓋「強勢上漲」

不動 `_hl_trend` 原本嚴格的「升 / 跌 / 轉折 / 橫」分類（其他用途仍要嚴）。改動 `_structure_flag` 旗標分支，加「強勢上漲否決」規則：即使 `_hl_trend` 因 lows 沒嚴格升序而回「轉折」，只要 close 嚴格上揚或近 6 月陽月數高，仍視為「結構未轉弱」。

### Bug B：3 條件擇一即可

`_strong_breakout_state` 是純函式，新增兩個獨立的「擇一條件」：
- 條件 B「續強勢」：突破後連續站高（≥5 日 close 都 > range_high）+ 突破超過 5%
- 條件 C「一字漲停型」：今日漲幅 ≥ 9% 且 close 接近 high（一字漲停封死買單）

兩個新條件都不依賴量門檻，避免「越強勢越失格」的結構矛盾。

## 三、影響範圍

- `modules/data_enricher.py`：`compute_monthly_structure` 加 2 欄位、`_structure_flag` 加 2 參數及分支。
- `modules/ai_analyzer_v2.py`：`_strong_breakout_state` 新增條件 B、C；簽名與回傳型別不變。
- 既有 5 個結構閘測試（`test_monthly_structure.py`）+ 5 個強勢突破測試（`test_strong_breakout.py`）：必須零退化。

## 四、修法設計

### 決策 1：`compute_monthly_structure` 新增兩欄位

```python
# completed = monthly_bars[:-1] 排除進行中月
result['monthly_close_strict_up_3'] = (
    len(completed) >= 3
    and float(completed[-3]['close']) < float(completed[-2]['close']) < float(completed[-1]['close'])
)
result['monthly_bull_count_6'] = sum(
    1 for b in completed[-6:]
    if float(b['close']) > float(b['open'])
)
```

### 決策 2：`_structure_flag` 加參數與分支

```python
def _structure_flag(monthly_structure, price_vs_ma60, consecutive_bear,
                    close_strict_up_3: bool = False,
                    bull_count_6: int = 0) -> str:
    if monthly_structure == '資料不足':
        return '資料不足'
    # 1. 結構已轉弱（不變）
    if (price_vs_ma60 == '在下' or monthly_structure == '跌'
            or consecutive_bear >= 2):
        return '結構已轉弱'
    # 2. 結構未轉弱（擴充：含強勢上漲否決）
    if price_vs_ma60 == '在上' and consecutive_bear <= 1 and (
        monthly_structure in ('升', '橫')
        or close_strict_up_3              # 強勢上漲：最近 3 根月 close 嚴格上揚
        or bull_count_6 >= 4               # 強勢上漲：近 6 月有 4 根以上陽月
    ):
        return '結構未轉弱'
    return '結構轉折中'
```

東捷驗算：
- price_vs_ma60='在上'、consecutive_bear=0、close_strict_up_3=True（48.85<63.30<104.0）→ 「結構未轉弱」✅

### 決策 3：`_strong_breakout_state` 3 條件擇一

```python
def _strong_breakout_state(enriched_data: dict, price_f) -> bool:
    """三條件擇一成立即視為強勢突破：
    A. 量價齊揚：現價 > range_high 且 今日量 ≥ 5日均×1.5
    B. 突破後續強勢：現價 > range_high × 1.05 且 近 5 日收盤都 > range_high
    C. 一字漲停型：現價 > range_high 且 漲幅 ≥ 9% 且 close ≥ high × 0.99
    """
    if price_f is None:
        return False
    from modules.candlestick import calc_swing_levels
    sl = calc_swing_levels(enriched_data.get('daily_bars', []), 'long', price_f)
    if not sl or sl.get('range_high') is None:
        return False
    range_high = float(sl['range_high'])
    daily_bars = enriched_data.get('daily_bars', [])
    try:
        price = float(price_f)

        # A. 量價齊揚（現有）
        vt = enriched_data.get('volume_zhang')
        v5 = enriched_data.get('volume_5d_avg_zhang')
        if (price > range_high and vt is not None and v5 not in (None, '--', 0)
                and float(vt) >= float(v5) * 1.5):
            return True

        # B. 突破後續強勢
        if price > range_high * 1.05 and len(daily_bars) >= 5:
            recent_5_closes = [float(b['close']) for b in daily_bars[-5:]]
            if all(c > range_high for c in recent_5_closes):
                return True

        # C. 一字漲停型
        if price > range_high and len(daily_bars) >= 2:
            today_close = float(daily_bars[-1]['close'])
            today_high = float(daily_bars[-1]['high'])
            yest_close = float(daily_bars[-2]['close'])
            if (yest_close > 0
                    and (today_close - yest_close) / yest_close >= 0.09
                    and today_close >= today_high * 0.99):
                return True
        return False
    except (TypeError, ValueError, KeyError, ZeroDivisionError):
        return False
```

驗算：
| 股 | 5/22 | range_high | A | B | C | 結果 |
|----|------|-----------|---|---|---|------|
| 合晶 6182 | 69.9 | 59.3 | ✅ 量過 | — | ✅ 漲幅 9.9% | ✅ |
| 矽力 6415 | 562 | 456 | ❌ 量不足 | ✅ 562>478.8 且近 5 日 close 都 >456 | ❌ 漲幅 0.9% | ✅ |
| 瑞軒 2489 | 51.4 | 48.85 | ❌ 量不足 | ❌ 5/18 39.75<48.85 | ✅ 漲幅 9.83% + close=high | ✅ |
| 東捷 8064 | 132.5 | (走 short 不適用，Bug A 修後改 long 待驗) | — | — | — | — |

### 決策 4：呼叫端不變

`_structure_flag` 加參數有預設值（向後相容）；`compute_monthly_structure` 回傳 dict 加欄位也向後相容。所有呼叫端（`_structure_block` 等）不必動。

## 五、測試計畫

### Bug A 新測試（`tests/test_monthly_structure.py` 追加）
1. `test_structure_flag_close_strict_up_overrides_inflection` — 月K `_hl_trend` 回「轉折」但 close 嚴格上揚 → 結構未轉弱（覆蓋東捷案例）
2. `test_structure_flag_bull_count_6_overrides_inflection` — 月K「轉折」但近 6 月有 ≥4 陽月 → 結構未轉弱
3. `test_structure_flag_below_ma60_not_overridden_by_strong_up` — close 嚴格上揚但價在 MA60 下 → 仍判結構已轉弱（不可越界）
4. `test_compute_monthly_structure_close_strict_up_3_field` — `compute_monthly_structure` 回 dict 含 `monthly_close_strict_up_3` 欄位
5. `test_compute_monthly_structure_bull_count_6_field` — 同上含 `monthly_bull_count_6` 欄位

### Bug B 新測試（`tests/test_strong_breakout.py` 追加）
1. `test_breakout_true_via_condition_b_continuous_high_close` — 條件 B：突破 5% 且近 5 日 close 都站高 → 成立
2. `test_breakout_false_when_recent_close_dips_below_range_high` — 條件 B 失效：近 5 日有任一 close ≤ range_high → 不成立
3. `test_breakout_true_via_condition_c_one_word_limit_up` — 條件 C：今日漲幅 9.8% + close = high → 成立
4. `test_breakout_false_when_limit_up_but_below_range_high` — 漲停但價未過 range_high → 不成立（不誤判反彈）
5. `test_breakout_false_when_close_not_at_high` — 漲幅夠但 close < high × 0.99（有顯著上影） → 不成立

### 回歸測試
- 原 5 個強勢突破測試：全綠
- 原 5 個結構閘測試：全綠（簽名加 default 參數，不破壞舊呼叫）

## 六、風險與回滾

- 純加性：兩個函式新增邏輯分支，不刪除現有條件；
- `compute_monthly_structure` 新增 dict 欄位向後相容（呼叫端只取既有 key）；
- `_structure_flag` 簽名加參數但有預設值；
- 風險點：擴大「結構未轉弱」涵蓋面 → 部分原「結構轉折中」股將改判「結構未轉弱」（如東捷），對應 AI 將被禁標派發。這是修法本意，但需 deploy 後實機驗無誤判其他股。
- 回滾：D1 / D2 各自純加性 + optional 參數，可獨立 `git revert`。

## 七、驗收

1. pytest 全綠：原 239 + 約 10 新 → 250+
2. py_compile（`data_enricher.py` + `ai_analyzer_v2.py`）全綠
3. Deploy 後重跑 5/22 報表（~$0.6）+ 對照 5/25 收盤：
   - 東捷 8064 結構旗標 = 「結構未轉弱」，方向 = long（不再 short）
   - 矽力 6415 = 「強勢突破成立」（條件 B 觸發）
   - 瑞軒 2489 = 「強勢突破成立」（條件 C 觸發）
   - 合晶 6182 = 「強勢突破成立」（條件 A 觸發，不退化）
   - 其他 10 支 long 股無誤判（旗標與方向不變）
