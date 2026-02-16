import yfinance as yf
import pandas as pd
import requests
import os
import json

# --- 設定：LINE Messaging API通知機能 ---
def send_line_push(message):
    # GitHubの秘密の保管庫から2つの鍵を読み込む
    access_token = os.environ.get('LINE_ACCESS_TOKEN')
    user_id = os.environ.get('LINE_USER_ID')
    
    if not access_token or not user_id:
        print("エラー: LINE_ACCESS_TOKEN または LINE_USER_ID が見つかりません。")
        return

    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}"
    }
    # Messaging API専用のデータ形式
    data = {
        "to": user_id,
        "messages": [
            {
                "type": "text",
                "text": message
            }
        ]
    }
    
    response = requests.post(url, headers=headers, data=json.dumps(data))
    if response.status_status == 200:
        print("LINE Messaging APIで通知を送りました。")
    else:
        print(f"送信失敗: {response.text}")

# --- スキャンロジック (以前と同じ) ---
def run_auto_scan():
    try:
        with open('tickers.txt', 'r') as f:
            target_stocks = [line.strip() for line in f if line.strip()]
    except:
        print("tickers.txtが見つかりません。")
        return

    found_stocks = []
    print(f"{len(target_stocks)} 銘柄をスキャン中...")

    for ticker in target_stocks:
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="60d")
            if len(df) < 30: continue

            curr_price = df['Close'].iloc[-1]
            change_pct = ((curr_price - df['Close'].iloc[-2]) / df['Close'].iloc[-2]) * 100
            
            ma5 = df['Close'].rolling(window=5).mean()
            ma25 = df['Close'].rolling(window=25).mean()
            is_gc = (ma5.iloc[-2] <= ma25.iloc[-2]) and (ma5.iloc[-1] > ma25.iloc[-1])
            
            if change_pct >= 3.0 or is_gc:
                info = stock.info
                name = info.get('short_name', ticker)
                msg = f"\n【{name} ({ticker})】\n価格: {round(curr_price, 1)}\n騰落率: {round(change_pct, 1)}%\n{'★GC発生！' if is_gc else ''}"
                found_stocks.append(msg)
        except:
            continue

    if found_stocks:
        message = "🔔 本日のお宝銘柄通知 🔔" + "".join(found_stocks)
        send_line_push(message)
    else:
        print("条件に合う銘柄はありませんでした。")

if __name__ == "__main__":
    run_auto_scan()