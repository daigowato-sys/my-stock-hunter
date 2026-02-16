import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import numpy as np

# --- 1. ページ基本設定 ---
st.set_page_config(page_title="極・株分析AIシステム", layout="wide")

# --- 2. ニュース感情分析エンジン ---
def analyze_sentiment_free(news_list):
    if not news_list or not isinstance(news_list, list):
        return "【判定：中立 😐】\n\n現在、有効なニュースは見当たりません。"
    pos_words = ["増益", "上方修正", "最高益", "提携", "買収", "拡大", "好調", "反発", "期待", "上昇", "黒字", "配当増", "自社株買い", "buy", "positive", "growth", "surge"]
    neg_words = ["減益", "下方修正", "赤字", "不祥事", "懸念", "失速", "続落", "売り", "下落", "マイナス", "低迷", "急落", "sell", "negative", "loss", "risk"]
    score = 0
    titles = [n.get('title', '') for n in news_list[:5] if isinstance(n, dict)]
    for title in titles:
        t_lower = title.lower()
        for w in pos_words:
            if w in t_lower: score += 1
        for w in neg_words:
            if w in t_lower: score -= 1
    
    news_display = "\n".join([f"・{t}" for t in titles])
    if score > 0: judgment = "【判定：ポジティブ 📈】"
    elif score < 0: judgment = "【判定：ネガティブ 📉】"
    else: judgment = "【判定：中立 😐】"
    return f"{judgment}\n\n--- 解析対象のニュース ---\n{news_display}"

# --- 3. タブ構成 ---
tab1, tab2, tab3 = st.tabs(["🔍 お宝スキャナー & ヒートマップ", "📊 過去検証（バックテスト）", "💰 持ち株ポートフォリオ"])

# --- 4. タブ1: スキャナー & ヒートマップ ---
with tab1:
    st.sidebar.title("🛠️ 分析設定")
    mode = st.sidebar.radio("戦略を選んでください", ["勢い重視（順張り）", "底値狙い（逆張り）"])
    
    if mode == "勢い重視（順張り）":
        min_change = st.sidebar.slider("騰落率のしきい値(%)", 0.0, 10.0, 3.0)
        min_vol = st.sidebar.slider("出来高比のしきい値(倍)", 1.0, 5.0, 1.5)
    else:
        max_rsi = st.sidebar.slider("RSIの上限", 10, 50, 30)
        min_kairi = st.sidebar.slider("25日乖離率(%)", -20, 0, -5)

    try:
        with open('tickers.txt', 'r') as f:
            target_stocks = [line.strip() for line in f if line.strip()]
    except:
        st.error("tickers.txt が見つかりません。")
        target_stocks = []

    if st.button('全銘柄スキャン開始！'):
        with st.spinner(f'{len(target_stocks)} 銘柄をスキャニング中...'):
            all_data = []
            progress_bar = st.progress(0)
            for i, ticker in enumerate(target_stocks):
                try:
                    stock = yf.Ticker(ticker)
                    info = stock.info
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
                    div_yield = info.get('dividendYield', 0)

                    all_data.append({
                        "コード": ticker, "企業名": info.get('shortName', ticker),
                        "業種": info.get('sector', '未分類'), "価格": round(curr_price, 1),
                        "騰落率(%)": round(change_pct, 2), "出来高(倍)": round(vol_ratio, 2),
                        "配当(%)": round(div_yield * 100, 2) if div_yield else 0.0,
                        "RSI": round(rsi, 1), "25日乖離": round(kairi, 2),
                        "GC": "★" if is_gc else "", "概要": info.get('longBusinessSummary', '')[:300], "ニュース": stock.news
                    })
                except: continue
                finally: progress_bar.progress((i + 1) / len(target_stocks))

            df_res = pd.DataFrame(all_data)

            # --- ヒートマップ ---
            st.subheader("🌡️ 市場ヒートマップ（業種別・値動き）")
            fig_hp = px.treemap(df_res, path=['業種', '企業名'], values=np.abs(df_res['騰落率(%)'])+1,
                               color='騰落率(%)', color_continuous_scale='RdYlGn_r',
                               hover_data=['価格', '騰落率(%)'])
            st.plotly_chart(fig_hp, use_container_width=True)

            # --- 結果表示 ---
            if mode == "勢い重視（順張り）":
                results = df_res[(df_res['騰落率(%)'] >= min_change) & (df_res['出来高(倍)'] >= min_vol)]
                sort_col = "騰落率(%)"
            else:
                results = df_res[(df_res['RSI'] <= max_rsi) & (df_res['25日乖離'] <= min_kairi)]
                sort_col = "25日乖離"

            if not results.empty:
                st.success(f"{len(results)} 件の銘柄が合致しました。")
                
                sectors = sorted(results['業種'].unique())
                for s in sectors:
                    with st.expander(f"📁 {s} セクター ({len(results[results['業種']==s)]}銘柄)"):
                        sector_df = results[results['業種']==s].drop(columns=["概要", "ニュース", "業種"])
                        st.dataframe(sector_df.sort_values(by=sort_col, ascending=(mode=="底値狙い（逆張り）")).style.background_gradient(subset=['騰落率(%)', '配当(%)'], cmap='RdYlGn'))
                        
                        for _, row in results[results['業種']==s].iterrows():
                            st.write(f"--- **{row['企業名']} ({row['コード']})** ---")
                            c1, c2 = st.columns(2)
                            with c1: st.write(f"**概要:** {row['概要']}...")
                            with c2: st.info(analyze_sentiment_free(row['ニュース']))
            else:
                st.warning("条件に合う銘柄は見つかりませんでした。")

# --- 5. タブ2: バックテスト (全機能復活) ---
with tab2:
    st.title("📊 「あの時買えばよかった」を検証する")
    selected_ticker = st.text_input("検証したい銘柄コード", value="6758.T")
    if st.button('過去1年の勝率を検証！'):
        with st.spinner('データ解析中...'):
            stock = yf.Ticker(selected_ticker)
            df = stock.history(period="2y")
            if len(df) < 50: st.error("データ不足です。")
            else:
                df['MA5'] = df['Close'].rolling(window=5).mean(); df['MA25'] = df['Close'].rolling(window=25).mean()
                df['GC_Signal'] = (df['MA5'] > df['MA25']) & (df['MA5'].shift(1) <= df['MA25'].shift(1))
                signals = df[df['GC_Signal'] == True].copy(); results = []
                for i in range(len(signals)):
                    buy_date = signals.index[i]; idx = df.index.get_loc(buy_date)
                    if idx + 3 < len(df):
                        results.append(((df['Close'].iloc[idx+3] - df['Close'].iloc[idx]) / df['Close'].iloc[idx]) * 100)
                if results:
                    c1, c2, c3 = st.columns(3)
                    c1.metric("検証期間", "2年間"); c2.metric("★発生回数", f"{len(results)}回")
                    c3.metric("3日後勝率", f"{len([r for r in results if r > 0])/len(results)*100:.1f}%", f"{sum(results)/len(results):.2f}%")
                fig = go.Figure()
                fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='株価'))
                fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], line=dict(color='orange', width=1), name='5日線'))
                fig.add_trace(go.Scatter(x=df.index, y=df['MA25'], line=dict(color='blue', width=1), name='25日線'))
                sig_df = df[df['GC_Signal'] == True]
                fig.add_trace(go.Scatter(x=sig_df.index, y=sig_df['Low']*0.97, mode='markers', marker=dict(symbol='star', size=12, color='gold'), name='GCサイン(★)'))
                fig.update_layout(xaxis_rangeslider_visible=False, height=600); st.plotly_chart(fig, use_container_width=True)

# --- 6. タブ3: ポートフォリオ ---
with tab3:
    st.title("💰 持ち株ポートフォリオ管理")
    portfolio_input = st.text_area("「コード,取得単価,株数」を入力 (例: 7203.T,2500,100)", "7203.T,2500,100")
    if st.button('評価額を更新'):
        pf_list = []
        for line in portfolio_input.split('\n'):
            if ',' in line:
                p = line.split(','); pf_list.append({"コード": p[0].strip(), "単価": float(p[1]), "株数": int(p[2])})
        if pf_list:
            total_pl = 0; pf_rows = []
            for item in pf_list:
                curr = yf.Ticker(item['コード']).history(period="1d")['Close'].iloc[-1]
                pl = (curr - item['単価']) * item['株数']; total_pl += pl
                pf_rows.append({"コード": item['コード'], "現在値": round(curr, 1), "取得単価": item['単価'], "株数": item['株数'], "損益": round(pl, 0), "騰落(%)": round((curr-item['単価'])/item['単価']*100, 2)})
            st.metric("合計含み損益", f"{total_pl:,.0f}円", delta=f"{total_pl:,.0f}")
            st.dataframe(pd.DataFrame(pf_rows).style.background_gradient(subset=['損益'], cmap='RdYlGn'))