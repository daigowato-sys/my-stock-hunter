import streamlit as st
import yfinance as yf
import pandas as pd

# ページの設定
st.set_page_config(page_title="プロ仕様・銘柄詳細スキャナー", layout="wide")

st.title("💎 お宝銘柄発見スキャナー (企業詳細付き)")

# サイドバー設定
st.sidebar.header("検索フィルタ設定")
min_change = st.sidebar.slider("騰落率のしきい値(%)", 0.0, 10.0, 3.0)
min_vol = st.sidebar.slider("出来高比のしきい値(倍)", 1.0, 5.0, 1.5)

# 銘柄リストの読み込み
try:
    with open('tickers.txt', 'r') as f:
        target_stocks = [line.strip() for line in f if line.strip()]
except FileNotFoundError:
    st.error("tickers.txt が見つかりません。")
    target_stocks = []

if st.button('全銘柄スキャン開始！'):
    if not target_stocks:
        st.warning("銘柄リストが空です。")
    else:
        with st.spinner(f'{len(target_stocks)} 銘柄を分析中...'):
            all_data = []
            progress_bar = st.progress(0)
            
            for i, ticker in enumerate(target_stocks):
                try:
                    stock = yf.Ticker(ticker)
                    # 企業情報の取得（ここで企業名と特徴を取る）
                    info = stock.info
                    company_name = info.get('shortName') or info.get('longName') or ticker
                    # 特徴（最初の200文字だけ取得）
                    summary = info.get('longBusinessSummary', '特徴データなし')[:200] + "..."

                    df = stock.history(period="60d")
                    if len(df) < 25: continue

                    curr_price = df['Close'].iloc[-1]
                    change_pct = ((curr_price - df['Close'].iloc[-2]) / df['Close'].iloc[-2]) * 100
                    vol_ratio = df['Volume'].iloc[-1] / df['Volume'].iloc[-6:-1].mean()
                    
                    ma5 = df['Close'].rolling(window=5).mean()
                    ma25 = df['Close'].rolling(window=25).mean()
                    is_gc = (ma5.iloc[-2] <= ma25.iloc[-2]) and (ma5.iloc[-1] > ma25.iloc[-1])
                    
                    all_data.append({
                        "コード": ticker,
                        "企業名": company_name,
                        "価格": round(curr_price, 2),
                        "騰落率(%)": round(change_pct, 2),
                        "出来高比(倍)": round(vol_ratio, 2),
                        "GC": "★" if is_gc else "",
                        "企業概要(英)": summary # 詳細データとして保持
                    })
                    progress_bar.progress((i + 1) / len(target_stocks))
                except:
                    continue

            df_res = pd.DataFrame(all_data)
            treasures = df_res[(df_res['騰落率(%)'] >= min_change) & (df_res['出来高比(倍)'] >= min_vol)]

            if not treasures.empty:
                st.success(f"{len(treasures)} 件のお宝が見つかりました！")
                treasures = treasures.sort_values(by="騰落率(%)", ascending=False)
                
                # 表示用の列を整理（概要は長いので表には出さず、下に詳細として出す）
                display_df = treasures.drop(columns=["企業概要(英)"])
                st.dataframe(display_df.style.background_gradient(subset=['騰落率(%)'], cmap='YlOrRd'))

                # --- 個別銘柄の詳細（特徴）を表示するセクション ---
                st.subheader("📋 抽出銘柄の企業特徴")
                for _, row in treasures.iterrows():
                    with st.expander(f"{row['コード']} {row['企業名']} の詳細を見る"):
                        st.write(f"**価格:** {row['価格']}円 / **騰落率:** {row['騰落率(%)']}%")
                        st.write(f"**事業内容（原文）:**\n{row['企業概要(英)']}")
            else:
                st.warning("お宝は見つかりませんでした。")