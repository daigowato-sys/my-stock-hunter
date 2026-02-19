import yfinance as yf
import pandas as pd
import requests
import os
import json

def send_line_push(message):
    access_token = os.environ.get('LINE_ACCESS_TOKEN')
    user_id = os.environ.get('LINE_USER_ID')
    if not access_token or not user_id:
        print("エラー: 鍵が見つかりません。GitHub Secretsを確認してください。")
        return

    url = "https://api.line.me/v2/bot/message/push"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {access_token}"}
    data = {"to": user_id, "messages": [{"type": "text", "text": message}]}
    
    response = requests.post(url, headers=headers, data=json.dumps(data))
    if response.status_code == 200:
        print("LINE送信成功")
    else:
        print(f"送信失敗: {response.text}")

def run_auto_scan():
    try:
        with open('tickers.txt', 'r') as f:
            tickers = [l.strip() for l in f if l.strip()]
    except:
        print("tickers.txtが見つかりません。")
        return

    found_strong = [] # 最強サイン用
    found_normal = [] # 通常サイン用

    print(f"{len(tickers)} 銘柄を詳細スキャン中...")

    for t in tickers:
        try:
            s = yf.Ticker(t)
            df = s.history(period="100d") # 指標計算用に100日分取得
            if len(df) < 35: continue
            
            close = df['Close']
            cp = close.iloc[-1]
            prev_cp = close.iloc[-2]
            chg = ((cp - prev_cp) / prev_cp) * 100

            # 1. GC判定 (MA5/MA25)
            ma5 = close.rolling(5).mean()
            ma25 = close.rolling(25).mean()
            is_gc = (ma5.iloc[-2] <= ma25.iloc[-2]) and (ma5.iloc[-1] > ma25.iloc[-1])

            # 2. MACD判定
            ema12 = close.ewm(span=12).mean()
            ema26 = close.ewm(span=26).mean()
            macd_line = ema12 - ema26
            sig_line = macd_line.ewm(span=9).mean()
            is_macd_buy = (macd_line.iloc[-2] <= sig_line.iloc[-2]) and (macd_line.iloc[-1] > sig_line.iloc[-1])

            # 3. ボリンジャーバンド判定 (-2σ以下か)
            bb_mid = close.rolling(20).mean()
            bb_std = close.rolling(20).std()
            is_bb_low = cp <= (bb_mid.iloc[-1] - bb_std.iloc[-1] * 2)

            name = s.info.get('shortName', t)

            # --- 最強の組み合わせ判定 ---
            if is_gc and (is_macd_buy or is_bb_low):
                found_strong.append(f"\n🔥最強買🔥 {name}({t})\n価格:{round(cp,1)} (GC+勢い確認)")
            elif is_gc:
                found_normal.append(f"\n★GC発生 {name}({t})\n価格:{round(cp,1)}")
            elif is_macd_buy and chg > 2.0: # GCはないが勢いがある
                found_normal.append(f"\n📈MACD買 {name}({t})\n価格:{round(cp,1)}")

        except:
            continue

    # メッセージの組み立て
    message = ""
    if found_strong:
        message += "【🚨最重要・最強サイン🚨】" + "".join(found_strong) + "\n"
    
    if found_normal:
        message += "\n【🔔注目サイン】" + "".join(found_normal)

    if message:
        send_line_push("📊 AI自動監視レポート\n" + message)
    else:
        print("本日、特筆すべきサインはありませんでした。")

if __name__ == "__main__":
    run_auto_scan()