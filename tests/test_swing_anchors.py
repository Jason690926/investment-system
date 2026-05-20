"""
B 組（2026-05-20）— DB swing anchor 注入 + pill mapping
用戶 2026-05-19 報表 short 股 pill「空進/空停/空標」價位邏輯錯位
（pill 把支撐當空進、目標 = 進場 = 同價位）。
本檔驗證 _resolve_swing_anchors 給出的價位語意正確。
"""
import sys, os, pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from modules.ai_analyzer_v2 import _resolve_swing_anchors


def _bar(date_str, h, l, c=None):
    c = c if c is not None else (h + l) / 2
    return {'date': date_str, 'open': c, 'high': h, 'low': l,
            'close': c, 'volume_zhang': 1000}


def _make_bars(highs_lows, start_date='2026-01-01'):
    from datetime import date as dt_date, timedelta
    d = dt_date.fromisoformat(start_date)
    bars = []
    for h, l in highs_lows:
        bars.append(_bar(d.isoformat(), h, l))
        d += timedelta(days=1)
    return bars


class TestResolveSwingAnchors:
    """_resolve_swing_anchors 依方向回傳 DB 寫入用 anchor dict。"""

    def _enriched(self, daily_bars):
        return {'daily_bars': daily_bars}

    def test_neutral_returns_none_anchors(self):
        """neutral 方向 → 全部 None（neutral 不寫入 anchor）。"""
        bars = _make_bars([(100, 90)] * 30)
        result = _resolve_swing_anchors(self._enriched(bars), 95.0, 'neutral')
        assert result == {
            'support_anchor':    None,
            'resistance_anchor': None,
            'target_anchor':     None,
            'stop_loss_anchor':  None,
        }

    def test_short_anchors_have_correct_semantic(self):
        """short：support=range_low（下方目標）、resistance=range_high（回測壓力）、
        stop_loss=range_high × 1.03（前高失效）。"""
        # 構造明確的 swing high/low：起伏夾雜
        bars = _make_bars([
            (100, 95), (102, 96), (105, 98), (108, 100),  # 上行段
            (110, 105), (112, 106), (115, 108),           # 創高 115（swing_high）
            (113, 109), (110, 105), (108, 102),           # 拉回
            (106, 100), (104, 98), (102, 95),             # 下行
            (100, 92), (98,  90),                          # 創低 90（swing_low）
            (102, 95), (105, 98), (108, 100),             # 反彈
            (110, 104), (112, 106), (115, 108),           # 再上
            (113, 109), (110, 105),                       # 再拉回
        ])
        result = _resolve_swing_anchors(self._enriched(bars), 108.0, 'short')

        # range_low/range_high 取窗口內最近的局部峰谷
        assert result['support_anchor']    is not None, '應有 swing_low'
        assert result['resistance_anchor'] is not None, '應有 swing_high'
        assert result['stop_loss_anchor']  is not None, 'short 必有 stop_loss'

        # 核心語意：空停（前高 ×1.03）必須 > 空進（回測壓力）
        assert result['stop_loss_anchor'] > result['resistance_anchor'], (
            f'空停 {result["stop_loss_anchor"]} 必須 > 空進 {result["resistance_anchor"]}'
        )
        # 空進（壓力）必須 > 空標（支撐 = 下方目標）
        assert result['resistance_anchor'] > result['support_anchor'], (
            f'空進 {result["resistance_anchor"]} 必須 > 空標 {result["support_anchor"]}'
        )

    def test_long_no_stop_loss(self):
        """long：stop_loss = None（long 用 support 當失效已足夠）。"""
        bars = _make_bars([
            (100, 95), (102, 96), (105, 98), (108, 100),
            (110, 105), (112, 106), (115, 108),
            (113, 109), (110, 105), (108, 102),
            (106, 100), (104, 98), (102, 95),
            (100, 92), (98,  90),
            (102, 95), (105, 98), (108, 100),
            (110, 104), (112, 106), (115, 108),
            (113, 109), (110, 105),
        ])
        result = _resolve_swing_anchors(self._enriched(bars), 108.0, 'long')
        assert result['stop_loss_anchor'] is None, 'long 不該有 stop_loss'

    def test_insufficient_bars_all_none(self):
        """資料不足 → 全 None（fallback 至 AI tag 上）。"""
        bars = _make_bars([(100, 95)] * 5)
        result = _resolve_swing_anchors(self._enriched(bars), 97.0, 'short')
        assert all(v is None for v in result.values()), (
            f'資料不足應全 None，實際：{result}'
        )

    def test_stop_loss_rounding(self):
        """stop_loss 數值依股價區間 round：< 100 → 1dp、≥ 100 → 0dp。"""
        # 高價股測試（≥ 100）
        bars_hi = _make_bars([
            (200, 190), (210, 195), (220, 200),
            (215, 205), (210, 200), (205, 195),
            (200, 188), (195, 185), (190, 180),
            (188, 178), (192, 180), (200, 188),
            (210, 195), (220, 205),
        ])
        result = _resolve_swing_anchors({'daily_bars': bars_hi}, 200.0, 'short')
        if result['stop_loss_anchor'] is not None:
            # ≥ 100 應為整數
            assert result['stop_loss_anchor'] == round(result['stop_loss_anchor'], 0)


# ────────────────────────────────────────
# E 組（2026-05-20）— 進場區距現價過近警示
# 華星光 5/19 收 523 / short 進場區上緣 551 只差 5.4%、臻鼎差 1.6%
# → 反彈一日就觸發停損的真實案例
# ────────────────────────────────────────

from modules.ai_analyzer_v2 import _dual_swing_block


class TestEntryProximityWarning:
    """進場區距現價 < 3% 時 swing block 應加警示語。"""

    def _bars_short_near_entry(self):
        """構造 short 情境：cur ~= entry_high，進場區極近。"""
        # 高位震盪後拉回，現價在 swing_high 附近
        return [
            _bar(f'2026-04-{i:02d}', 100, 95) for i in range(1, 26)
        ] + [
            _bar('2026-04-26', 110, 105),
            _bar('2026-04-27', 112, 106),
            _bar('2026-04-28', 115, 108),  # swing_high = 115
            _bar('2026-04-29', 113, 109),
            _bar('2026-04-30', 110, 105),
            _bar('2026-05-01', 108, 102),
            _bar('2026-05-02', 105, 100),
            _bar('2026-05-03', 102, 95),
            _bar('2026-05-04', 100, 92),
            _bar('2026-05-05', 98, 90),    # swing_low = 90
            _bar('2026-05-06', 102, 95),
            _bar('2026-05-07', 108, 102),
            _bar('2026-05-08', 112, 106, c=112),  # cur=112 vs entry_high=115 差 2.6%
        ]

    def test_short_entry_proximity_warning_appears(self):
        """short 進場區上緣距現價 < 3% → 出現警示語。"""
        bars = self._bars_short_near_entry()
        # cur=112，swing_high=115，差 2.6% < 3% → 觸發警示
        result = _dual_swing_block({'daily_bars': bars}, 112.0)
        # 警示語含「過近」字眼
        assert '過近' in result, f'cur 距 entry_high 過近時應有警示，實際：\n{result}'
        assert 'neutral' in result, '警示應建議標 neutral 觀望'

    def test_short_entry_far_no_warning(self):
        """short 進場區距現價 > 3% → 不出警示。"""
        bars = self._bars_short_near_entry()
        # cur=100，swing_high=115，差 15% > 3% → 不觸發
        result = _dual_swing_block({'daily_bars': bars}, 100.0)
        assert '過近' not in result, f'距離足夠時不應出警示，實際：\n{result}'

    def test_warning_only_when_data_complete(self):
        """資料不足時不會 crash，靜默回傳基本 block。"""
        result = _dual_swing_block({'daily_bars': []}, 100.0)
        # 資料不足 → 「本期資料不足」訊息
        assert '資料不足' in result or '波段操作錨點' in result
