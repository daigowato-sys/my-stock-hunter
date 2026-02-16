import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np

# --- 1. ページ設定 ---
st.set_page_config(page_title="最強・株分析システム", layout="wide")

# --- 2. 無料版：ニュース感情分析エンジン（エラー対策済み） ---
def analyze_sentiment_free(news_list):
    if not news_list or not isinstance(news_list, list):
        return "【判定：中立 😐】\n\n現在、この銘柄に関する有効なニュースは見当たりません。"
    
    pos_words = ["増益", "上方修正", "最高益", "提携", "買収", "拡大", "好調", "反発", "割安", "買い推奨", "追い風", "期待"]
    neg_words = ["減益", "下方修正", "赤字", "不祥事", "懸念", "失速", "続落", "売り", "向かい風", "訴訟", "慎重", "下落"]
    
    score = 0
    detected_pos = []
    detected_neg = []
    
    # 安全にタイトルを取得
    titles = [n.get('title', '') for n in news_list[:5] if isinstance(n, dict)]
    
    for title in titles:
        for w in pos_words:
            if w in title:
                score += 1
                detected_pos.append(w)
        for w in neg_words:
            if w in title:
                score -= 1
                detected_neg.append(w)
    
    if score > 0:
        judgment = "【判定：ポジティブ 📈】"
        reason = f"ポジティブなキーワード（{', '.join(list(set(detected_pos)))}）が検出されました。"
    elif score < 0:
        judgment = "【判定：ネガティブ 📉】"
        reason = f"ネガティブなキーワード（{', '.join(list(set(detected_neg)))}）が検出されました。"
    else:
        judgment = "【判定：中立 😐】"
        reason = "直近のニュースには目立ったキーワードが見当たりません。"
    
    return f"{judgment}\n\n{reason}"

# --- 3. サイドバー：分析設定 ---
st.sidebar.title("🛠️ 分析設定")
mode = st.sidebar.radio("戦略を選んでください", ["勢い重視（順張り）", "底値狙い（逆張り）"])

if mode == "勢い重視（順張り）":
    st.sidebar.subheader("🚀 順張り設定")
    min_change = st.sidebar.slider("騰落率のしきい値(%)", 0.0, 10.0, 3.0)
    min_vol = st.sidebar.slider("出来高比のしきい値(倍)", 1.0, 5.0, 1.5)
else:
    st.sidebar.subheader("📉 底値・NISA設定")
    max_rsi = st.sidebar.slider("RSIの上限（低いほど売られすぎ）", 10, 50, 30)
    min_kairi = st.sidebar.slider("25日乖離率(%)（マイナスに大きいほど底値）", -20, 0, -5)

# --- 4. タブ構成 ---
tab1, tab2 = st.tabs(["🔍 リアルタイム・スキャナー", "📊 過去検証（バックテスト）"])

# --- 5. タブ1: スキャナー機能 ---
with tab1:
    st.title(f"💎 お宝銘柄発見スキャナー - {mode}")

    try:
        with open('tickers.txt', 'r') as f:
            target_stocks = [line.strip() for line in f if line.strip()]
    except:
        st.error("tickers.txt が見つかりません。")
        target_stocks = []

    if st.button('全銘柄スキャン開始！'):
        if not target_stocks:
            st.warning("銘柄リストが空です。")
        else:
            with st.spinner(f'{len(target_stocks)} 銘柄をスキャン中...'):
                all_data = []
                progress_bar = st.progress(0)
                
                for i, ticker in enumerate(target_stocks):
                    try:
                        stock = yf.Ticker(ticker)
                        info = stock.info
                        company_name = info.get('shortName') or info.get('longName') or ticker
                        summary = info.get('longBusinessSummary', '特徴データなし')[:300] + "..."
                        div_yield = info.get('dividendYield', 0)
                        div_yield_pct = round(div_yield * 100, 2) if div_yield else 0.0

                        df = stock.history(period="60d")
                        if len(df) < 30: continue

                        curr_price = df['Close'].iloc[-1]
                        change_pct = ((curr_price - df['Close'].iloc[-2]) / df['Close'].iloc[-2]) * 100
                        vol_ratio = df['Volume'].iloc[-1] / df['Volume'].iloc[-6:-1].mean()
                        
                        ma5 = df['Close'].rolling(window=5).mean()
                        ma25 = df['Close'].rolling(window=25).mean()
                        is_gc = (ma5.iloc[-2] <= ma25.iloc[-2]) and (ma5.iloc[-1] > ma25.iloc[-1])
                        kairi = ((curr_price - ma25.iloc[-1]) / ma25.iloc[-1]) * 100
                        
                        delta = df['Close'].diff()
                        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                        rsi = 100 - (100 / (1 + (gain / loss).iloc[-1]))

                        all_data.append({
                            "コード": ticker, "企業名": company_name, "価格": round(curr_price, 1),
                            "騰落率(%)": round(change_pct, 2), "出来高(倍)": round(vol_ratio, 2),
                            "配当(%)": div_yield_pct, "RSI": round(rsi, 1), "25日乖離": round(kairi, 2),
                            "GC": "★" if is_gc else "", "概要": summary, "ニュース": stock.news
                        })
                    except: continue
                    finally: progress_bar.progress((i + 1) / len(target_stocks))

                if all_data:
                    df_res = pd.DataFrame(all_data)
                    if mode == "勢い重視（順張り）":
                        results = df_res[(df_res['騰落率(%)'] >= min_change) & (df_res['出来高(倍)'] >= min_vol)]
                        sort_col = "騰落率(%)"
                    else:
                        results = df_res[(df_res['RSI'] <= max_rsi) & (df_res['25日乖離'] <= min_kairi)]
                        sort_col = "25日乖離"

                    if not results.empty:
                        st.success(f"{len(results)} 件の銘柄が見つかりました！")
                        display_df = results.drop(columns=["概要", "ニュース"])
                        st.dataframe(display_df.sort_values(by=["GC", sort_col], ascending=[False, (mode == "底値狙い（逆張り）")]).style.background_gradient(subset=['騰落率(%)', '配当(%)'], cmap='RdYlGn'))
                        
                        st.subheader("📋 個別銘柄詳細レポート")
                        for _, row in results.iterrows():
                            with st.expander(f"{row['コード']} {row['企業名']} {'★GC発生中' if row['GC']=='★' else ''}"):
                                col_left, col_right = st.columns(2)
                                with col_left:
                                    st.write("**【企業概要】**")
                                    st.write(row['概要'])
                                with col_right:
                                    st.write("**【簡易ニュース診断】**")
                                    st.info(analyze_sentiment_free(row['ニュース']))
                    else:
                        st.warning("条件に合う銘柄はありませんでした。")

# --- 6. タブ2: バックテスト機能 ---
with tab2:
    st.title("📊 「あの時買えばよかった」を検証する")
    selected_ticker = st.text_input("検証したい銘柄コードを入力", value="6758.T")
    
    if st.button('過去の勝率を検証！'):
        with st.spinner('過去のデータを解析中...'):
            stock = yf.Ticker(selected_ticker)
            df = stock.history(period="2y")
            if len(df) < 50:
                st.error("データが不足しています。")
            else:
                df['MA5'] = df['Close'].rolling(window=5).mean()
                df['MA25'] = df['Close'].rolling(window=25).mean()
                df['GC_Signal'] = (df['MA5'] > df['MA25']) & (df['MA5'].shift(1) <= df['MA25'].shift(1))
                
                signals = df[df['GC_Signal'] == True].copy()
                results = []
                for i in range(len(signals)):
                    buy_date = signals.index[i]
                    idx = df.index.get_loc(buy_date)
                    if idx + 3 < len(df):
                        buy_price = df['Close'].iloc[idx]
                        sell_price = df['Close'].iloc[idx + 3]
                        results.append(((sell_price - buy_price) / buy_price) * 100)
                
                col1, col2, col3 = st.columns(3)
                if results:
                    win_rate = len([r for r in results if r > 0]) / len(results) * 100
                    col1.metric("検証期間", "過去1〜2年")
                    col2.metric("★発生回数", f"{len(results)}回")
                    col3.metric("3日後の勝率", f"{win_rate:.1f}%", f"{sum(results)/len(results):.2f}% (平均利益)")
                
                fig = go.Figure()
                fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='株価'))
                fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], line=dict(color='orange', width=1), name='5日線'))
                fig.add_trace(go.Scatter(x=df.index, y=df['MA25'], line=dict(color='blue', width=1), name='25日線'))
                
                sig_df = df[df['GC_Signal'] == True]
                fig.add_trace(go.Scatter(x=sig_df.index, y=sig_df['Low'] * 0.97, mode='markers', marker=dict(symbol='star', size=12, color='gold'), name='GCサイン(★)'))
                fig.update_layout(title=f"{selected_ticker} のサイン検証チャート", xaxis_rangeslider_visible=False, height=600)
                st.plotly_chart(fig, use_container_width=True)