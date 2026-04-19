import os
from dotenv import load_dotenv

load_dotenv()

# Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
# NewsAPI
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

# Gmail
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")

# 模擬投資設定
INITIAL_CAPITAL = 500000        # 初始資金 50萬台幣
MAX_SINGLE_STOCK = 0.20         # 單一標的上限 20%
MAX_HOLDINGS = 5                # 最多同時持有 5 檔
MIN_CASH_RATIO = 0.20           # 保留現金下限 20%
STOP_LOSS = -0.10               # 停損 -10%
PYRAMID_PROFIT = 0.10           # 金字塔加碼門檻 +10%

# 技術分析設定
MA_SHORT = 5                    # 短期均線
MA_MID = 20                     # 中期均線
MA_LONG = 60                    # 長期均線
RSI_PERIOD = 14                 # RSI 週期
RSI_OVERBOUGHT = 75             # RSI 超買
RSI_OVERSOLD = 30               # RSI 超賣
VOLUME_RATIO = 1.5              # 成交量倍數門檻

# 報表設定
REPORTS_DIR = "reports"
DATA_DIR = "data"