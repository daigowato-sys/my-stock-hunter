import streamlit as st
import yfinance as yf
import pandas as pd

# ページの設定
st.set_page_config(page_title="NISA対応・お宝スキャナー", layout="wide")

# サイドバー：分析モードの選択
st.sidebar.title("🔍 分析モード選択")
mode = st.sidebar.radio("戦略を選んでください", ["勢い重視（順張り）", "底値狙い（逆張り）"])

st.title(f"💎 お宝銘柄発見スキャナー - {mode}")

# --- サイドバー：詳細条件設定 ---
if mode == "勢い重視（順張り）":
    st.sidebar.subheader("🚀 順張り設定")
    min_change = st.sidebar.slider("騰落率のしきい値(%)", 0.0, 10.0, 3.0)
    min_vol = st.sidebar.slider("出来高比のしきい値(倍)", 1.0, 5.0, 1.5)
else:
    st.sidebar.subheader("📉 底値・NISA設定")
    max_rsi = st.sidebar.slider("RSIの上限（低いほど売られすぎ）", 10, 50, 30)
    min_kairi = st.sidebar.slider("25日乖離率(%)（マイナスに大きいほど底値）", -20, 0, -5)

# 銘柄リストの読み込み
try:
    with open('tickers.txt', 'r') as f:
        target_stocks = [line.strip() for line in f if line.strip()]
except:
    st.error("tickers.txt が見つかりません。")
    target_stocks = []

if st.button('スキャン開始！'):
    if not target_stocks:
        st.warning("銘柄リストが空です。")
    else:
        with st.spinner(f'{len(target_stocks)} 銘柄を全スキャン中...'):
            all_data = []
            progress_bar = st.progress(0)
            
            for i, ticker in enumerate(target_stocks):
                try:
                    stock = yf.Ticker(ticker)
                    # 企業情報と配当利回りの取得
                    info = stock.info
                    company_name = info.get('shortName') or info.get('longName') or ticker
                    summary = info.get('longBusinessSummary', '特徴データなし')[:300] + "..."
                    
                    # 配当利回りの取得 (0.025 のような形式で来るので100倍して%にする)
                    div_yield = info.get('dividendYield')
                    div_yield_pct = round(div_yield * 100, 2) if div_yield else 0.0

                    # 株価データの取得
                    df = stock.history(period="60d")
                    if len(df) < 30: continue

                    curr_price = df['Close'].iloc[-1]
                    change_pct = ((curr_price - df['Close'].iloc[-2]) / df['Close'].iloc[-2]) * 100
                    vol_ratio = df['Volume'].iloc[-1] / df['Volume'].iloc[-6:-1].mean()
                    
                    # 指標計算
                    ma25 = df['Close'].rolling(window=25).mean()
                    kairi = ((curr_price - ma25.iloc[-1]) / ma25.iloc[-1]) * 100
                    
                    # RSI計算
                    delta = df['Close'].diff()
                    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                    rsi = 100 - (100 / (1 + (gain / loss).iloc[-1]))

                    all_data.append({
                        "コード": ticker,
                        "企業名": company_name,
                        "価格": round(curr_price, 1),
                        "騰落率(%)": round(change_pct, 2),
                        "出来高(倍)": round(vol_ratio, 2),
                        "配当利回り(%)": div_yield_pct, # 👈 新しく追加
                        "RSI": round(rsi, 1),
                        "25日乖離": round(kairi, 2),
                        "概要": summary
                    })
                except:
                    continue
                finally:
                    progress_bar.progress((i + 1) / len(target_stocks))

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
                    
                    # 表示（色付け：配当利回りにも色を付けると見やすい）
                    display_df = results.drop(columns=["概要"])
                    st.dataframe(
                        display_df.sort_values(by=sort_col, ascending=(mode == "底値狙い（逆張り）"))
                        .style.background_gradient(subset=['騰落率(%)', '配当利回り(%)'], cmap='RdYlGn')
                    )

                    st.subheader("📋 企業の詳細と特徴")
                    for _, row in results.iterrows():
                        with st.expander(f"{row['コード']} {row['企業名']} (配当: {row['配当利回り(%)']}%)"):
                            st.write(f"**配当利回り:** {row['配当利回り(%)']}%")
                            st.write(f"**事業内容:**\n{row['概要']}")
                else:
                    st.warning("条件に合う銘柄は見つかりませんでした。")