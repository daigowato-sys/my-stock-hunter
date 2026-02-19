import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import numpy as np

# --- 1. ページ基本設定 ---
st.set_page_config(page_title="極・投資AI司令室(フル機能版)", layout="wide")

# --- 2. ニュース感情分析エンジン ---
def analyze_sentiment_free(news_list):
    if not news_list or not isinstance(news_list, list):
        return "【判定：中立 😐】\n有効なニュースはありません。"
    pos_words = ["増益", "上方修正", "最高益", "提携", "買収", "拡大", "好調", "反発", "期待", "上昇", "buy", "growth"]
    neg_words = ["減益", "下方修正", "赤字", "不祥事", "懸念", "失速", "続落", "売り", "下落", "risk", "sell"]
    score = 0
    titles = [n.get('title', '') for n in news_list[:5] if isinstance(n, dict)]
    for title in titles:
        t_l = title.lower()
        for w in pos_words:
            if w in t_l: score += 1
        for w in neg_words:
            if w in t_l: score -= 1
    judgment = "【判定：ポジティブ 📈】" if score > 0 else "【判定：ネガティブ 📉】" if score < 0 else "【判定：中立 😐】"
    return f"{judgment}\n\n対象ニュース:\n" + "\n".join([f"・{t}" for t in titles if t])

# --- 3. タブ構成 ---
tab1, tab2, tab3 = st.tabs(["🔍 多角スキャナー & ヒートマップ", "📊 過去検証", "💰 ポートフォリオ"])

# --- 4. タブ1: スキャナー & ヒートマップ (最強判定ロジック搭載) ---
with tab1:
    st.sidebar.title("🛠️ 分析設定")
    map_color = st.sidebar.radio("ヒートマップの色分け", ["値動き（騰落率）", "健全性（安全スコア）"])
    mode = st.sidebar.radio("スキャン戦略", ["勢い重視（順張り）", "底値狙い（逆張り）"])
    st.sidebar.subheader("🏥 財務フィルター (NISA向)")
    min_safety = st.sidebar.slider("最小安全スコア", 0, 100, 0)
    min_dividend = st.sidebar.slider("最小配当利回り(%)", 0.0, 7.0, 0.0)

    try:
        with open('tickers.txt', 'r') as f:
            target_stocks = [line.strip() for line in f if line.strip()]
    except:
        st.error("tickers.txt が見つかりません。")
        target_stocks = []

    if st.button('全銘柄・多角スキャン開始！'):
        with st.spinner('テクニカル・モメンタム・財務を同時解析中...'):
            all_data = []
            progress_bar = st.progress(0)
            for i, ticker in enumerate(target_stocks):
                try:
                    stock = yf.Ticker(ticker)
                    info = stock.info
                    df = stock.history(period="100d") # MACD計算用に長めに取得
                    if len(df) < 35: continue
                    
                    close = df['Close']
                    # ① テクニカル指標計算
                    ma5, ma25 = close.rolling(5).mean(), close.rolling(25).mean()
                    is_gc = (ma5.iloc[-2] <= ma25.iloc[-2]) and (ma5.iloc[-1] > ma25.iloc[-1])
                    
                    ema12, ema26 = close.ewm(span=12).mean(), close.ewm(span=26).mean()
                    macd_line = ema12 - ema26
                    sig_line = macd_line.ewm(span=9).mean()
                    is_macd_buy = (macd_line.iloc[-2] <= sig_line.iloc[-2]) and (macd_line.iloc[-1] > sig_line.iloc[-1])
                    
                    bb_mid = close.rolling(20).mean()
                    bb_std = close.rolling(20).std()
                    is_bb_low = close.iloc[-1] <= (bb_mid.iloc[-1] - bb_std.iloc[-1] * 2)

                    rsi = 100 - (100 / (1 + (close.diff().where(close.diff() > 0, 0).rolling(14).mean() / -close.diff().where(close.diff() < 0, 0).rolling(14).mean()).iloc[-1]))

                    # ② 財務診断
                    per, pbr, div = info.get('trailingPE', 0), info.get('priceToBook', 0), info.get('dividendYield', 0) * 100
                    try:
                        bal = stock.balance_sheet
                        equity = (bal.loc['Stockholders Equity'].iloc[0] / bal.loc['Total Assets'].iloc[0]) * 100
                    except: equity = 0 
                    safety = sum([25 for cond in [0 < per < 15, 0 < pbr < 1.2, equity > 40, div > 3] if cond])

                    # ③ 最強判定ラベル
                    if is_gc and (is_macd_buy or is_bb_low): label = "🔥最強の買い🔥"
                    elif is_gc: label = "★GC発生"
                    elif is_macd_buy: label = "MACD買"
                    elif is_bb_low: label = "売られすぎ"
                    else: label = ""

                    all_data.append({
                        "コード": ticker, "企業名": info.get('shortName', ticker), "業種": info.get('sector', '未分類'),
                        "判定": label, "価格": round(close.iloc[-1], 1), "騰落率(%)": round(((close.iloc[-1]-close.iloc[-2])/close.iloc[-2])*100, 2),
                        "配当(%)": round(div, 2), "安全スコア": safety, "RSI": round(rsi, 1), "出来高(倍)": round(df['Volume'].iloc[-1]/df['Volume'].iloc[-6:-1].mean(), 2),
                        "GC": is_gc, "MACD": is_macd_buy, "BB": is_bb_low, "ニュース": stock.news, "概要": info.get('longBusinessSummary', '')[:200],
                        "PER": per, "自己資本": equity
                    })
                except: continue
                finally: progress_bar.progress((i + 1) / len(target_stocks))

            if all_data:
                df_res = pd.DataFrame(all_data)
                # ヒートマップ表示
                color_col = '騰落率(%)' if map_color == "値動き（騰落率）" else '安全スコア'
                fig = px.treemap(df_res, path=['業種', '企業名'], values=np.abs(df_res['騰落率(%)'])+1, color=color_col, 
                               color_continuous_scale='RdYlGn_r' if map_color == "値動き（騰落率）" else 'Greens')
                st.plotly_chart(fig, use_container_width=True)

                # 絞り込みと表示
                results = df_res[(df_res['安全スコア'] >= min_safety) & (df_res['配当(%)'] >= min_dividend)]
                if mode == "勢い重視（順張り）":
                    results = results[(results['騰落率(%)'] >= 3.0) | (results['判定'] != "")]
                else:
                    results = results[(results['RSI'] <= 35) | (results['BB'] == True)]

                if not results.empty:
                    # 判定の強さでソート
                    results['rank'] = results['判定'].apply(lambda x: 1 if "🔥" in x else (2 if "★" in x else 3))
                    results = results.sort_values(['rank', '騰落率(%)'], ascending=[True, False])
                    
                    st.success(f"{len(results)} 件の注目銘柄を検出")
                    st.dataframe(results.drop(columns=["概要", "ニュース", "rank", "業種", "GC", "MACD", "BB"]).style.background_gradient(subset=['騰落率(%)', '安全スコア'], cmap='RdYlGn'))
                    
                    for _, row in results[results['判定'] != ""].iterrows():
                        with st.expander(f"【{row['判定']}】 {row['企業名']} ({row['コード']})"):
                            c1, c2 = st.columns(2)
                            with c1: st.write(f"**財務診断:** PER:{round(row['PER'],1)} / 自己資本:{round(row['自己資本'],1)}% / スコア:{row['安全スコア']}点\n\n**概要:** {row['概要']}...")
                            with c2: st.info(analyze_sentiment_free(row['ニュース']))
                else: st.warning("条件に合う銘柄は見つかりませんでした。")

# --- 5. タブ2: バックテスト ---
with tab2:
    st.title("📊 過去検証（あの時買えばよかった！）")
    sel_t = st.text_input("検証したい銘柄コード", value="6758.T")
    if st.button('過去の勝率を検証！'):
        df_b = yf.Ticker(sel_t).history(period="2y")
        if len(df_b) > 50:
            df_b['MA5'], df_b['MA25'] = df_b['Close'].rolling(5).mean(), df_b['Close'].rolling(25).mean()
            df_b['GC'] = (df_b['MA5'] > df_b['MA25']) & (df_b['MA5'].shift(1) <= df_b['MA25'].shift(1))
            sigs = df_b[df_b['GC'] == True]
            rets = [((df_b['Close'].iloc[df_b.index.get_loc(d)+3] - df_b['Close'].iloc[df_b.index.get_loc(d)])/df_b['Close'].iloc[df_b.index.get_loc(d)])*100 for d in sigs.index if df_b.index.get_loc(d)+3 < len(df_b)]
            if rets:
                c1, c2, c3 = st.columns(3)
                c1.metric("検証期間", "2年間"); c2.metric("★発生回数", f"{len(results)}回")
                c3.metric("3日後勝率", f"{len([r for r in rets if r > 0])/len(rets)*100:.1f}%", f"{sum(rets)/len(rets):.2f}% (平均利益)")
            st.plotly_chart(go.Figure(data=[go.Candlestick(x=df_b.index, open=df_b['Open'], high=df_b['High'], low=df_b['Low'], close=df_b['Close'])]), use_container_width=True)

# --- 6. タブ3: ポートフォリオ ---
with tab3:
    st.title("💰 ポートフォリオ管理")
    pt_i = st.text_area("形式: コード,単価,株数", "7203.T,2500,100")
    if st.button('評価額を更新する'):
        pf = []
        for l in pt_i.split('\n'):
            if ',' in l:
                c, p, n = l.split(',')
                curr = yf.Ticker(c.strip()).history(period="1d")['Close'].iloc[-1]
                pf.append({"コード": c.strip(), "現在値": curr, "損益": (curr - float(p)) * int(n), "騰落(%)": (curr-float(p))/float(p)*100})
        if pf:
            df_pf = pd.DataFrame(pf)
            st.metric("総損益", f"{df_pf['損益'].sum():,.0f}円")
            st.dataframe(df_pf.style.background_gradient(subset=['損益'], cmap='RdYlGn'))