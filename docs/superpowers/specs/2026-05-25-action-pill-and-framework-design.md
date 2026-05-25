# 報表「建議動作」明確化：pill + 第五節結構化（設計）

- 日期：2026-05-25
- 觸發：用戶 5/25 cross-check 完 §三十 後指出「建議的字夠用比較明確方式標記出來嗎？」
- 對應 plan：§三十一

---

## 一、問題陳述

當前報表上「建議性質的字」分散在 3 個層級：

1. **頂部 Pill 區**（已視覺化）：方向 (多/空/觀望) / 威科夫 (再積累/上漲/派發) / 風險 (35%)
   - 都是「看法 / 階段 / 衝突量化」，**不是動作**
2. **第五節「操作框架」**（純 AI 寫長文字）：散落「進場價」「停損」「目標」「不宜追進」「等回測」「強勢突破追蹤」等
3. **第六節「持倉部位建議」**（只 HOLD 股）：「整體判斷：續抱 / 觀望持有 / 減碼 / 出場」

問題：
- WATCH 股動作建議藏在第五節長文字裡，用戶要往下讀完才知道「該等回測 vs 該追進 vs 不宜進」
- HOLD 股要讀到第六節才看到動作字
- 「強勢突破狀態」程式已算出（`_strong_breakout_state`）但完全沒視覺化
- 第五節格式各股長度/結構不一致，AI 自由發揮

## 二、設計原則

### 「動作」是程式可計算的客觀結論

「動作」由 5 個輸入決定：
- `status`（hold / watch）
- `direction`（long / short / neutral）
- `structure_flag`（結構未轉弱 / 轉折中 / 已轉弱）— §二十六 + §三十 已有
- `swing_levels`（range_high / range_low / entry_zone / invalidation）— §二十三 已有
- `_strong_breakout_state`（True / False）— §三十 已有

所有輸入都已存在 enriched_data 或 analysis_result，計算「動作」是純函式，無需 AI。

### 「建議動作」應該明確、單一、視覺化

每張卡片只有 1 個 pill 字串、用 emoji 色標醒目區分：
- 🟢 = 進取（追進、加碼、續抱）
- 🟡 = 等待（等回測、等突破、等反彈）
- 🟠 = 警戒（減碼）
- 🔴 = 退出 / 不宜（出場、不宜進、論點作廢、分批佈空 — 對 short 是動作）
- ⚪ = 中性（觀望）

額外用 💪 emoji 標記「強勢突破成立」狀態（合進 A pill，不獨立 pill）。

### 第五節改程式渲染（與 A pill 同源）

`_render_operation_framework()` 跟 `_decide_action()` 用同一組輸入算，確保第五節內容與 pill 100% 一致（沒有「pill 寫追進、第五節卻寫不宜追進」這種矛盾）。

## 三、影響範圍

- `modules/ai_analyzer_v2.py`：新增 `_decide_action()` + `_render_operation_framework()` 兩個純函式；3 個分析函式呼叫端整合
- `modules/models.py`：`StockAnalysis` 加 `action_pill` 欄位
- `migrate_add_action_pill.py`：新建 migration 腳本
- `static/js/dashboard.js` `buildCard()`：加 actionChip 顯示
- `templates/print_report.html`：PDF stock-block-header 加 action pill
- `static/css/app.css`：actionChip pill 樣式（5 色 + 💪 標記）
- 既有 249 個測試：必須零退化

## 四、修法設計

### 決策 1：`_decide_action()` 純函式（決定樹）

```python
def _decide_action(status: str, direction: str, structure_flag: str,
                   swing_levels: dict | None, breakout: bool,
                   price: float | None,
                   cost_stop_loss: float | None = None) -> str:
    """根據 5 個輸入決定建議動作 pill 字串。

    回傳格式：'<emoji color> <動作字> [💪]'，例如 '🟢 追進 💪' / '🟡 等回測'

    決定樹見 plan.md §三十一 表格。
    """
    # 邊界：資料不足
    if not direction or price is None:
        return '⚪ 觀望'

    sl = swing_levels or {}
    range_high   = sl.get('range_high')
    entry_zone   = sl.get('entry_zone')
    invalidation = sl.get('invalidation')

    # ---------- HOLD ----------
    if status == 'hold':
        # 持倉停損優先（個人成本層級的停損 > 程式波段停損）
        stop = cost_stop_loss if cost_stop_loss is not None else invalidation
        if stop is not None and price < float(stop):
            return '🔴 出場'
        if structure_flag == '結構已轉弱':
            return '🟠 減碼'
        if breakout:
            return '🟢 加碼 💪'
        if entry_zone:
            zlo, zhi = entry_zone
            if zlo <= price <= zhi:
                return '🟢 加碼'
            if structure_flag == '結構轉折中':
                mid = (zlo + zhi) / 2
                if price < mid:
                    return '🟡 觀望持有'
        return '🟢 續抱'

    # ---------- WATCH ----------
    if status == 'watch':
        if direction == 'long':
            if structure_flag == '結構已轉弱':
                return '🔴 不宜進'
            if breakout:
                return '🟢 追進 💪'
            if range_high is not None and price > float(range_high):
                return '🟡 等突破'
            if entry_zone:
                zlo, zhi = entry_zone
                if zlo <= price <= zhi:
                    return '🟢 進場區可佈'
                if price > zhi:
                    return '🟡 等回測'
            return '⚪ 觀望'

        if direction == 'short':
            if structure_flag == '結構未轉弱':
                return '⚪ 觀望（不宜空）'
            if invalidation is not None and price > float(invalidation):
                return '🔴 論點作廢'
            if entry_zone:
                zlo, zhi = entry_zone
                if zlo <= price <= zhi:
                    return '🔴 分批佈空'
                if price < zlo:
                    return '🟡 等反彈佈空'
            return '⚪ 觀望'

        # WATCH neutral
        return '⚪ 觀望'

    return '⚪ 觀望'
```

### 決策 2：`_render_operation_framework()` 純函式

```python
def _render_operation_framework(action_pill: str, direction: str,
                                swing_levels: dict | None, breakout: bool,
                                vol_threshold_zhang: int | None = None) -> str:
    """渲染第五節「操作框架」結構化區塊。

    回傳 HTML/markdown 段落（具體格式依模板）。
    """
    sl = swing_levels or {}
    rh = sl.get('range_high')
    rl = sl.get('range_low')
    ez = sl.get('entry_zone')
    tg = sl.get('target')
    inv = sl.get('invalidation')

    def _fmt(v):
        return f"{v:.2f}" if v is not None else "—"

    def _fmt_zone(z):
        if not z:
            return "—"
        return f"{_fmt(z[0])} ~ {_fmt(z[1])}"

    if direction == 'long':
        if breakout:
            return (
                "五、操作框架\n"
                "─────────────────────\n"
                f"建議動作：{action_pill}\n"
                f"強勢突破追蹤：現價 > 前高 {_fmt(rh)} 元、量達門檻 → 可順勢追進\n"
                f"  追進停損：{_fmt(rh)} 元（跌回前高即假突破）\n"
                f"回測進場（保守）：{_fmt_zone(ez)} 元\n"
                f"停損：{_fmt(inv)} 元 — 跌破即論點作廢\n"
                f"目標：{_fmt(tg) if tg else '—'} 元\n"
                "─────────────────────"
            )
        else:
            vol_str = f"（觸發須量 ≥ {vol_threshold_zhang:,} 張）" if vol_threshold_zhang else ""
            return (
                "五、操作框架\n"
                "─────────────────────\n"
                f"建議動作：{action_pill}\n"
                f"進場區：{_fmt_zone(ez)} 元{vol_str}\n"
                f"停損：{_fmt(inv)} 元 — 跌破即論點作廢\n"
                f"目標：{_fmt(tg) if tg else '—'} 元\n"
                "─────────────────────"
            )

    if direction == 'short':
        return (
            "五、操作框架\n"
            "─────────────────────\n"
            f"建議動作：{action_pill}\n"
            f"空進：{_fmt_zone(ez)} 元（回測壓力佈空）\n"
            f"空停：{_fmt(inv)} 元 — 站回突破即論點作廢\n"
            f"空標：{_fmt(tg) if tg else '—'} 元（P&F 下行目標）\n"
            "─────────────────────"
        )

    # neutral
    return (
        "五、操作框架\n"
        "─────────────────────\n"
        f"建議動作：{action_pill}\n"
        "（neutral 觀望中，無進場 / 出場觸發價）\n"
        "─────────────────────"
    )
```

### 決策 3：prompt 改 placeholder

3 個分析函式（`analyze_market_only` / `analyze_stock_three_masters` / `generate_personal_recommendation`）的 `action_section` 變數改為 `[[OPERATION_FRAMEWORK]]` placeholder：

```python
# 原本
action_section = """
五、操作框架
▸【強勢突破狀態】{breakout_line}
▶ 進場價：{entry_zone} 元（觸發須量 ≥ {vol_threshold} 張）
▶ 停損：{stop_loss} 元 — 跌破即論點作廢
▶ 目標：{target} 元
"""

# 改為
action_section = "[[OPERATION_FRAMEWORK]]"
```

分析完成後 post-process：
```python
# 在 AI 輸出後、寫入 DB 前
action_pill = _decide_action(status, direction, structure_flag,
                              swing_levels, breakout, price, cost_stop_loss)
op_framework_html = _render_operation_framework(action_pill, direction,
                                                  swing_levels, breakout,
                                                  vol_threshold_zhang)
ai_html = ai_html.replace('[[OPERATION_FRAMEWORK]]', op_framework_html)

result['action_pill'] = action_pill
result['html'] = ai_html
```

### 決策 4：DB 加欄位 `action_pill` String(32)

```python
# modules/models.py StockAnalysis
class StockAnalysis(Base):
    # ... 既有欄位
    action_pill = Column(String(32))  # e.g., '🟢 追進 💪'（plan §三十一）
```

```python
# migrate_add_action_pill.py
with engine.begin() as conn:
    conn.execute(text(
        "ALTER TABLE stock_analyses ADD COLUMN IF NOT EXISTS action_pill VARCHAR(32)"
    ))
```

### 決策 5：Dashboard JS + PDF + CSS

**dashboard.js**：`buildCard()` 加 actionChip：
```javascript
const actionChip = s.action_pill
  ? `<span class="action-pill ${actionClass(s.action_pill)}" title="建議動作">${s.action_pill}</span>`
  : '';
const statusRowHtml = (dirChip || wyckoffChip || riskChip || actionChip)
  ? `<div class="card-status-row">${dirChip}${wyckoffChip}${riskChip}${actionChip}</div>`
  : '';
```

**`actionClass()` helper**：依 emoji 開頭判斷 CSS class：
- `🟢` → `action-bull`
- `🟡` → `action-amber`
- `🟠` → `action-warn`
- `🔴` → `action-bear`
- `⚪` → `action-neutral`

**print_report.html**：PDF stock-block-header 加 pill（與 dashboard 一致）。

**app.css** 加 5 色樣式。

## 五、測試計畫

### `tests/test_decide_action.py` 新建（~12 cases）

WATCH long（5 cases）：
1. 結構已轉弱 → 🔴 不宜進
2. breakout=True → 🟢 追進 💪
3. 現價 > range_high 但 breakout=False → 🟡 等突破
4. 現價在 entry_zone 內 → 🟢 進場區可佈
5. 現價 > entry_zone 上緣 → 🟡 等回測

WATCH short（3 cases）：
6. 結構未轉弱 → ⚪ 觀望（不宜空）
7. 現價 > 空停 → 🔴 論點作廢
8. 現價在空進區 → 🔴 分批佈空

HOLD（4 cases）：
9. 現價 < cost_stop_loss → 🔴 出場
10. 結構已轉弱 → 🟠 減碼
11. breakout=True → 🟢 加碼 💪
12. 一般多頭持倉 → 🟢 續抱

### `tests/test_operation_framework.py` 新建（~6 cases）

1. long 一般版（含 vol_threshold）→ 含「進場區/停損/目標」字串
2. long 強勢突破版 → 含「強勢突破追蹤/回測進場（保守）」字串
3. short 版 → 含「空進/空停/空標」字串
4. neutral 版 → 含「觀望中」字串
5. swing_levels 缺值（target=None）→ 顯示「—」
6. entry_zone 缺值 → 顯示「—」

### 回歸測試

- 既有 249 個測試零退化
- pytest 整體跑通

## 六、風險與回滾

- 純加性：新函式 + 新 DB 欄位（IF NOT EXISTS）+ UI 加 pill；既有功能 byte-identical
- 風險點 1：第五節改程式渲染後，AI 在第五節區的「補充解釋」消失。若用戶需要 AI 對動作的補充解釋，後續可加「五-A 補充」段（spec 未做）
- 風險點 2：prompt 用 `[[OPERATION_FRAMEWORK]]` placeholder，AI 偶爾可能複製這字串失敗（hallucinate 自寫第五節）→ 加 post-process 雙層防護：先 replace placeholder，若 ai_html 中找不到 placeholder，append 框架到 html 結尾
- 回滾：E1（_decide_action）/ E2（_render_operation_framework）/ E3（整合）/ E4（DB）/ E5（UI）各自純加性，獨立 `git revert`。E4 migration 已用 `IF NOT EXISTS`，revert 後欄位仍存在但無寫入。

## 七、驗收

1. pytest 全綠：249 + 約 18 新 → 267+
2. py_compile（ai_analyzer_v2 + models）全綠
3. Migration 跑過 + DB `stock_analyses.action_pill` 欄位存在
4. Deploy 後重跑 5/22 報表（~$0.6）+ 對照 5/25 收盤實機驗：
   - 14 支股每張卡片頂部 status row 出現 actionChip（4 chip 並排：方向/威科夫/風險/建議）
   - 漲停 4 支：合晶/瑞軒/矽力 pill = 🟢 追進 💪
   - 東捷（修 §三十 後）pill = 🟢 追進 💪 或 進場區可佈（依結構閘修正後決定）
   - 南亞科 pill = 🟡 等回測（現價 310.5 遠超 entry_zone 上緣）
   - 撼訊 pill = 🟢 進場區可佈
   - 第五節格式統一結構化（不再各股長度/欄位差異）
   - PDF 列印 pill 與 dashboard 一致
