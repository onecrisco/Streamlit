
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(
    page_title="Stock Screener",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --------------------------
# Helpers
# --------------------------

@st.cache_data
def get_sp500():
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    table = pd.read_html(url)[0]
    return table["Symbol"].tolist()

def compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = -delta.clip(upper=0).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def generate_signals(data):
    latest = data.iloc[-1]
    recent_high = data["Close"].rolling(20).max().iloc[-1]

    buy = (
        latest["Close"] > latest["50MA"] > latest["200MA"] and
        50 < latest["RSI"] < 65 and
        latest["Close"] >= recent_high
    )

    sell = (
        latest["Close"] < latest["50MA"] or
        latest["RSI"] > 75
    )

    if buy:
        return "BUY"
    elif sell:
        return "SELL"
    else:
        return "HOLD"

def analyze_stock(ticker):
    try:
        data = yf.download(ticker, period="1y", progress=False)

        if len(data) < 200:
            return None

        data["50MA"] = data["Close"].rolling(50).mean()
        data["200MA"] = data["Close"].rolling(200).mean()
        data["RSI"] = compute_rsi(data["Close"])

        latest = data.iloc[-1]

        score = 0

        # Trend
        if latest["Close"] > latest["50MA"]:
            score += 2
        if latest["Close"] > latest["200MA"]:
            score += 2
        if latest["50MA"] > latest["200MA"]:
            score += 1

        # Momentum
        ret_3m = (latest["Close"] / data["Close"].iloc[-60]) - 1
        ret_6m = (latest["Close"] / data["Close"].iloc[-120]) - 1

        if ret_3m > 0.10:
            score += 2
        if ret_6m > 0.20:
            score += 1

        if 50 < latest["RSI"] < 70:
            score += 1

        # Fundamentals
        info = yf.Ticker(ticker).info
        earnings_growth = info.get("earningsGrowth", 0)

        if earnings_growth and earnings_growth > 0:
            score += 1

        signal = generate_signals(data)

        return {
            "Ticker": ticker,
            "Score": score,
            "Signal": signal,
            "Price": round(latest["Close"], 2),
            "3M %": round(ret_3m * 100, 1),
            "6M %": round(ret_6m * 100, 1),
            "RSI": round(latest["RSI"], 1)
        }

    except:
        return None


# --------------------------
# UI
# --------------------------

st.title("📈 Daily Stock Screener")

with st.sidebar:
    st.header("Settings")

    run_scan = st.button("🔄 Run Full Scan (S&P 500)")
    min_score = st.slider("Minimum Score", 0, 10, 6)

    watchlist = st.text_input(
        "Watchlist",
        "AAPL,MSFT,NVDA,AMZN,GOOGL"
    )

watchlist = [x.strip().upper() for x in watchlist.split(",")]

# --------------------------
# Scan
# --------------------------

if run_scan:
    st.write("⏳ Scanning S&P 500...")

    tickers = get_sp500()
    results = []

    progress = st.progress(0)

    for i, ticker in enumerate(tickers):
        res = analyze_stock(ticker)
        if res:
            results.append(res)

        progress.progress((i + 1) / len(tickers))

    df = pd.DataFrame(results).sort_values("Score", ascending=False)
    df.to_csv("results.csv", index=False)

    st.success("✅ Scan complete!")

# --------------------------
# Load
# --------------------------

try:
    df = pd.read_csv("results.csv")
except:
    st.warning("Run a scan first")
    st.stop()

# --------------------------
# Filters
# --------------------------

col1, col2 = st.columns(2)

with col1:
    show_buy = st.checkbox("BUY only")

with col2:
    show_strong = st.checkbox("Score ≥ 8")

filtered = df[df["Score"] >= min_score]

if show_buy:
    filtered = filtered[filtered["Signal"] == "BUY"]

if show_strong:
    filtered = filtered[filtered["Score"] >= 8]

# --------------------------
# Top Picks (mobile style)
# --------------------------

st.subheader("🔥 Top Picks")

top = filtered.sort_values("Score", ascending=False).head(10)

for _, row in top.iterrows():
    st.markdown(f"""
    **{row['Ticker']}**  
    Score: {row['Score']} | Signal: {row['Signal']}  
    3M: {row['3M %']}% | RSI: {row['RSI']}
    """)
    st.divider()

# --------------------------
# Watchlist
# --------------------------

st.subheader("⭐ Watchlist")

watch_df = df[df["Ticker"].isin(watchlist)]
st.dataframe(watch_df, use_container_width=True)

# --------------------------
# Chart
# --------------------------

st.subheader("📊 Chart")

ticker = st.selectbox("Select Stock", df["Ticker"].unique())

data = yf.download(ticker, period="1y", progress=False)
data["50MA"] = data["Close"].rolling(50).mean()
data["200MA"] = data["Close"].rolling(200).mean()
data["RSI"] = compute_rsi(data["Close"])

fig = go.Figure()
fig.add_trace(go.Scatter(x=data.index, y=data["Close"], name="Price"))
fig.add_trace(go.Scatter(x=data.index, y=data["50MA"], name="50 MA"))
fig.add_trace(go.Scatter(x=data.index, y=data["200MA"], name="200 MA"))

st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

fig2 = go.Figure()
fig2.add_trace(go.Scatter(x=data.index, y=data["RSI"], name="RSI"))
fig2.add_hline(y=70)
fig2.add_hline(y=30)

st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

# --------------------------
# Export
# --------------------------

st.download_button(
    "⬇️ Download CSV",
    df.to_csv(index=False),
    file_name="stocks.csv",
    mime="text/csv"
)
