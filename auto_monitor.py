import yfinance as yf
import pandas as pd
import requests
import os

# --- 設定：LINE Messaging API通知機能 ---
def send_line(message):
    access_token = os.environ.get('LINE_ACCESS_TOKEN')
    user_id = os.environ.get('LINE_USER_ID')
    
    if not access_token or not user_id:
        print("LINEの鍵が見つかりません。")
        return

    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}"
    }
    data = {
        "to": user_id,
        "messages": [{"type": "text", "text": message}]
    }
    response = requests.post(url, headers=headers, json=data)
    print(f"LINE送信結果: {response.status_code}")

# --- スキャンロジック ---
def run_auto_scan():
    try:
        with open('tickers.txt', 'r') as f:
            target_stocks = [line.strip() for line in f if line.strip()]
    except:
        print("tickers.txtが見つかりません。")
        return

    found_stocks = []
    print(f"{len(target_stocks)} 銘銘柄を自動監視中...")

    for ticker in target_stocks:
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="60d")
            if len(df) < 30: continue

            # テクニカル指標の計算
            curr_price = df['Close'].iloc[-1]
            change_pct = ((curr_price - df['Close'].iloc[-2]) / df['Close'].iloc[-2]) * 100
            
            ma5 = df['Close'].rolling(window=5).mean()
            ma25 = df['Close'].rolling(window=25).mean()
            # ゴールデンクロス判定
            is_gc = (ma5.iloc[-2] <= ma25.iloc[-2]) and (ma5.iloc[-1] > ma25.iloc[-1])
            
            # 条件：騰落率3.5%以上 または ゴールデンクロス発生
            if change_pct >= 3.5 or is_gc:
                info = stock.info
                name = info.get('shortName', ticker)
                msg = f"\n【{name} ({ticker})】\n価格: {round(curr_price, 1)}円\n騰落率: {round(change_pct, 1)}%\n{'★GC(ゴールデンクロス)発生！' if is_gc else ''}"
                found_stocks.append(msg)
        except:
            continue

    if found_stocks:
        message = "🔔 本日の自動お宝銘柄通知 🔔\n" + "".join(found_stocks)
        send_line(message)
    else:
        print("条件に合う銘柄はありませんでした。")

if __name__ == "__main__":
    run_auto_scan()