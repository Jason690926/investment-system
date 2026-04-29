import yfinance as yf

yf.set_tz_cache_location("/tmp/yfinance_cache")

try:
    from curl_cffi import requests as curl_requests
    curl_session = curl_requests.Session(impersonate="chrome110")
    print("[yf_session] curl_cffi session 初始化成功")
except Exception as e:
    print(f"[yf_session] curl_cffi 初始化失敗: {e}")
    curl_session = None
