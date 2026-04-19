from modules.data_fetcher import get_taiwan_stocks
from modules.technical import analyze_all_stocks

stocks = get_taiwan_stocks()
tech = analyze_all_stocks(stocks)
for name, data in tech.items():
    price = data['price']
    stop = data['stop_loss_price']
    t1 = data['target1']
    t2 = data['target2']
    print(f"{name}: 現價={price} 停損={stop} 目標一={t1} 目標二={t2}")