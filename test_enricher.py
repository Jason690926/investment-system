from modules.data_enricher import get_full_stock_data
import json

data = get_full_stock_data('2330.TW')
if data:
    print(f"股價: {data['price']}")
    print(f"MA5/20/60: {data['ma5']} / {data['ma20']} / {data['ma60']}")
    print(f"MACD: {data['macd']}")
    print(f"成交量: {data['volume_zhang']}張  5日均量: {data['volume_5d_avg_zhang']}張")
    print(f"日K根數: {len(data['daily_bars'])}")
    print(f"週K根數: {len(data['weekly_bars'])}")
    print(f"月K根數: {len(data['monthly_bars'])}")
    print(f"最新日K: {data['daily_bars'][-1]}")
    print(f"最新週K: {data['weekly_bars'][-1] if data['weekly_bars'] else '無'}")
    print(f"最新月K: {data['monthly_bars'][-1] if data['monthly_bars'] else '無'}")
else:
    print("抓取失敗")
