import yfinance as yf

yf.set_tz_cache_location("/tmp/yfinance_cache")

try:
    from curl_cffi import requests as curl_requests
    curl_session = curl_requests.Session(impersonate="chrome110")
    print("[yf_session] curl_cffi session 初始化成功")
    try:
        t = yf.Ticker("2330.TW", session=curl_session)
        h = t.history(period="2d")
        print(f"[yf_session] 連線測試成功，取得 {len(h)} 筆資料")
    except Exception as e2:
        print(f"[yf_session] 連線測試失敗: {e2}")
except Exception as e:
    print(f"[yf_session] curl_cffi 初始化失敗: {e}")
    curl_session = None
