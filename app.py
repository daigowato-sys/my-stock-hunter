import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import numpy as np

# --- 1. ページ基本設定 ---
st.set_page_config(page_title="極・投資AI司令室", layout="wide")

# --- 2. ニュース感情分析エンジン (無料版) ---
def analyze_sentiment_free(news_list):
    if not news_list or not isinstance(news_list, list):
        return "【判定：中立 😐】"
    pos_words = ["増益", "上方修正", "最高益", "提携", "買収", "拡大", "好調", "反発", "期待", "上昇", "黒字"]
    neg_words = ["減益", "下方修正", "赤字", "不祥事", "懸念", "失速", "続落", "売り", "下落", "リスク"]
    score = 0
    titles = [n.get('title', '') for n in news_list[:5] if isinstance(n, dict)]
    for title in titles:
        t_lower = title.lower()
        for w in pos_words:
            if w in t_lower: score += 1
        for w in neg_words:
            if w in t_lower: score -= 1
    return "【判定：ポジティブ 📈】" if score > 0 else "【判定：ネガティブ 📉】" if score < 0 else "【判定：中立 😐】"

# --- 3. タブ構成 ---
tab1, tab2, tab3 = st.tabs(["🔍 財務診断スキャナー & ヒートマップ", "📊 過去検証（バックテスト）", "💰 持ち株ポートフォリオ"])

# --- 4. タブ1: スキャナー & 健康診断 ---
with tab1:
    st.sidebar.title("🛠️ 分析設定")
    mode = st.sidebar.radio("戦略", ["勢い重視（順張り）", "底値狙い（逆張り）"])
    
    st.sidebar.subheader("🏥 財務フィルター (NISA向)")
    min_safety = st.sidebar.slider("最小安全スコア (0-100)", 0, 100, 30)
    min_dividend = st.sidebar.slider("最小配当利回り(%)", 0.0, 7.0, 2.0)

    try:
        with open('tickers.txt', 'r') as f:
            target_stocks = [line.strip() for line in f if line.strip()]
    except:
        target_stocks = []

    if st.button('全銘柄スキャン開始！'):
        with st.spinner('テクニカル ＆ 財務データを同時解析中...'):
            all_data = []
            progress_bar = st.progress(0)
            for i, ticker in enumerate(target_stocks):
                try:
                    stock = yf.Ticker(ticker)
                    info = stock.info
                    df = stock.history(period="60d")
                    if len(df) < 30: continue

                    # テクニカル指標
                    curr_price = df['Close'].iloc[-1]
                    change_pct = ((curr_price - df['Close'].iloc[-2]) / df['Close'].iloc[-2]) * 100
                    vol_ratio = df['Volume'].iloc[-1] / df['Volume'].iloc[-6:-1].mean()
                    ma5 = df['Close'].rolling(window=5).mean()
                    ma25 = df['Close'].rolling(window=25).mean()
                    is_gc = (ma5.iloc[-2] <= ma25.iloc[-2]) and (ma5.iloc[-1] > ma25.iloc[-1])
                    kairi = ((curr_price - ma25.iloc[-1])/ma25.iloc[-1]*100)
                    
                    delta = df['Close'].diff()
                    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                    rsi = 100 - (100 / (1 + (gain / loss).iloc[-1]))

                    # ファンダメンタル指標 (財務)
                    per = info.get('trailingPE', 999)
                    pbr = info.get('priceToBook', 9)
                    div_yield = info.get('dividendYield', 0) * 100
                    
                    # 自己資本比率の計算 (簡易版)
                    try:
                        balance = stock.balance_sheet
                        equity_ratio = (balance.loc['Stockholders Equity'].iloc[0] / balance.loc['Total Assets'].iloc[0]) * 100
                    except:
                        equity_ratio = 0 

                    # 安全スコア計算
                    safety_score = 0
                    if 0 < per < 15: safety_score += 25
                    if 0 < pbr < 1.2: safety_score += 25
                    if equity_ratio > 40: safety_score += 25
                    if div_yield > 3: safety_score += 25
                    
                    all_data.append({
                        "コード": ticker, "企業名": info.get('shortName', ticker), "業種": info.get('sector', '未分類'),
                        "価格": round(curr_price, 1), "騰落率(%)": round(change_pct, 2), "出来高(倍)": round(vol_ratio, 2),
                        "配当(%)": round(div_yield, 2), "安全スコア": safety_score, "RSI": round(rsi, 1), 
                        "25日乖離": round(kairi, 2), "GC": "★" if is_gc else "", "PER": per, "PBR": pbr, "自己資本比率(%)": equity_ratio,
                        "ニュース": stock.news, "概要": info.get('longBusinessSummary', '')[:200]
                    })
                except: continue
                finally: progress_bar.progress((i + 1) / len(target_stocks))

            df_res = pd.DataFrame(all_data)

            # ヒートマップ表示 (安全スコア可視化)
            st.subheader("🌡️ 財務健全性ヒートマップ（濃い緑ほど安全）")
            fig_hp = px.treemap(df_res, path=['業種', '企業名'], values=np.abs(df_res['騰落率(%)'])+1,
                               color='安全スコア', color_continuous_scale='Greens', hover_data=['価格', '安全スコア'])
            st.plotly_chart(fig_hp, use_container_width=True)

            # フィルタリング
            if mode == "勢い重視（順張り）":
                f_change = (df_res['騰落率(%)'] >= 3.0) # デフォルトフィルタ
                f_vol = (df_res['出来高(倍)'] >= 1.5)
                results = df_res[f_change & f_vol & (df_res['安全スコア'] >= min_safety) & (df_res['配当(%)'] >= min_dividend)]
            else:
                results = df_res[(df_res['RSI'] <= 30) & (df_res['安全スコア'] >= min_safety) & (df_res['配当(%)'] >= min_dividend)]

            if not results.empty:
                st.success(f"{len(results)} 件の銘柄が合致！")
                sectors = sorted(results['業種'].unique())
                for s in sectors:
                    s_df = results[results['業種'] == s]
                    with st.expander(f"📁 {s} ({len(s_df)}銘柄)"):
                        st.dataframe(s_df.drop(columns=["概要", "ニュース", "業種"]).sort_values(by="安全スコア", ascending=False))
                        for _, row in s_df.iterrows():
                            st.write(f"--- **{row['企業名']} ({row['コード']})** ---")
                            c1, c2 = st.columns(2)
                            with c1: st.write(f"**財務詳細:** PER:{row['PER']} / PBR:{row['PBR']} / 自己資本:{row['自己資本比率(%)']}%")
                            with c2: st.info(analyze_sentiment_free(row['ニュース']))
            else:
                st.warning("条件に合う銘柄は見つかりませんでした。")

# --- 5. タブ2: バックテスト ---
with tab2:
    st.title("📊 バックテスト（過去検証）")
    sel_ticker = st.text_input("検証したい銘柄", value="6758.T")
    if st.button('勝率を検証！'):
        df_bt = yf.Ticker(sel_ticker).history(period="2y")
        if len(df_bt) > 50:
            df_bt['MA5'] = df_bt['Close'].rolling(window=5).mean(); df_bt['MA25'] = df_bt['Close'].rolling(window=25).mean()
            df_bt['GC'] = (df_bt['MA5'] > df_bt['MA25']) & (df_bt['MA5'].shift(1) <= df_bt['MA25'].shift(1))
            sigs = df_bt[df_bt['GC'] == True]; rets = []
            for d in sigs.index:
                idx = df_bt.index.get_loc(d)
                if idx + 3 < len(df_bt): rets.append(((df_bt['Close'].iloc[idx+3] - df_bt['Close'].iloc[idx])/df_bt['Close'].iloc[idx])*100)
            if rets:
                st.metric("3日後勝率", f"{len([r for r in rets if r > 0])/len(rets)*100:.1f}%", f"平均利益 {sum(rets)/len(rets):.2f}%")
            fig_bt = go.Figure(data=[go.Candlestick(x=df_bt.index, open=df_bt['Open'], high=df_bt['High'], low=df_bt['Low'], close=df_bt['Close'])])
            fig_bt.add_trace(go.Scatter(x=sigs.index, y=sigs['Low']*0.97, mode='markers', marker=dict(symbol='star', size=12, color='gold')))
            st.plotly_chart(fig_bt, use_container_width=True)

# --- 6. タブ3: ポートフォリオ ---
with tab3:
    st.title("💰 ポートフォリオ管理")
    pt_input = st.text_area("入力形式: コード,単価,株数", "7203.T,2500,100")
    if st.button('更新'):
        pf_data = []
        for line in pt_input.split('\n'):
            if ',' in line:
                c, p, n = line.split(','); pf_data.append({"コード": c.strip(), "現在": yf.Ticker(c.strip()).history(period="1d")['Close'].iloc[-1], "取得": float(p), "株数": int(n)})
        pf_df = pd.DataFrame(pf_data)
        pf_df['損益'] = (pf_df['現在'] - pf_df['取得']) * pf_df['株数']
        st.metric("総損益", f"{pf_df['損益'].sum():,.0f}円")
        st.dataframe(pf_df.style.background_gradient(subset=['損益'], cmap='RdYlGn'))