from modules.portfolio import load_portfolio, save_portfolio, buy_stock, sell_stock, get_portfolio_summary
from modules.livermore import check_entry_signal, check_exit_signal, check_pyramid
import config

def run_simulation(technical_results, current_prices):
    portfolio = load_portfolio()
    actions_taken = []

    # 第一步：檢查現有持倉是否需要停損或停利
    holdings_copy = dict(portfolio['holdings'])
    for name, holding in holdings_copy.items():
        curr_price = current_prices.get(name)
        if curr_price is None:
            continue

        exit_signal = check_exit_signal(holding, curr_price)

        if exit_signal['action'] == 'SELL':
            portfolio, msg = sell_stock(portfolio, name, curr_price, exit_signal['reason'])
            actions_taken.append({
                'action': 'SELL',
                'name': name,
                'price': curr_price,
                'reason': exit_signal['reason'],
                'message': msg
            })
        else:
            # 檢查是否可以金字塔加碼
            pyramid = check_pyramid(holding, curr_price)
            if pyramid['action'] == 'ADD':
                actions_taken.append({
                    'action': 'PYRAMID',
                    'name': name,
                    'price': curr_price,
                    'reason': pyramid['reason'],
                    'message': f'💡 {name} {pyramid["reason"]}'
                })

    # 第二步：尋找新的買進機會
    for name, tech_data in technical_results.items():
        if name in portfolio['holdings']:
            continue

        signal = check_entry_signal(name, tech_data)
        curr_price = current_prices.get(name)

        if signal['action'] == 'BUY' and curr_price:
            symbol = tech_data.get('symbol', '')
            reason = f'李佛摩買進訊號 分數:{signal["score"]} ' + ', '.join(signal['passed'])
            portfolio, msg = buy_stock(portfolio, name, symbol, curr_price, reason)
            actions_taken.append({
                'action': 'BUY',
                'name': name,
                'price': curr_price,
                'score': signal['score'],
                'reason': reason,
                'message': msg
            })

    # 第三步：產生投資組合摘要
    summary = get_portfolio_summary(portfolio, current_prices)

    return {
        'portfolio': portfolio,
        'summary': summary,
        'actions': actions_taken
    }

def get_current_prices(taiwan_stocks):
    prices = {}
    for name, data in taiwan_stocks.items():
        prices[name] = data.get('price', 0)
    return prices