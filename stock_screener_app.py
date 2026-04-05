import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from tickers import get_all_bist_tickers

st.set_page_config(page_title="BIST Hisse Analiz", layout="centered")
st.title("📈 Hisse Analiz")

# ---------------------- Veri yükleme ----------------------

@st.cache_data
def load_halaciklik_data():
    df = pd.read_excel("temelozet.xlsx")
    df["Kod"] = df["Kod"].str.strip().str.upper()
    return df.set_index("Kod")["Halka Açıklık Oranı (%)"].to_dict()

@st.cache_data
def load_lot_data():
    df = pd.read_csv("dolasim_lot.csv", sep=None, engine='python')
    df["Kod"] = df["Kod"].str.strip().str.upper()
    return df.set_index("Kod")["Dolasimdaki_Lot"].to_dict()

halka_aciklik_dict = load_halaciklik_data()
dolasim_lot_dict = load_lot_data()

# ---------------------- TEK API ----------------------

@st.cache_data(ttl=600)
def get_bulk_data(tickers):
    return yf.download(
        tickers,
        period="6mo",
        interval="1d",
        group_by="ticker",
        threads=True
    )

# ---------------------- Teknik ----------------------

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

# ---------------------- Grafik ----------------------

def plot_chart(df, name):
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10,8), sharex=True)

    # MA'lar
    df["MA20"] = df["Close"].rolling(20).mean()
    df["MA50"] = df["Close"].rolling(50).mean()
    df["MA200"] = df["Close"].rolling(200).mean()

    ax1.plot(df.index, df["Close"], label="Fiyat")
    ax1.plot(df.index, df["MA20"], label="MA20")
    ax1.plot(df.index, df["MA50"], label="MA50")
    ax1.plot(df.index, df["MA200"], label="MA200")  # 🔥 EKLENDİ
    ax1.legend()
    ax1.grid()

    # RSI
    rsi = calculate_rsi(df["Close"])
    ax2.plot(df.index, rsi, label="RSI")
    ax2.axhline(70)
    ax2.axhline(30)
    ax2.legend()
    ax2.grid()

    # MACD
    ema12 = df["Close"].ewm(span=12).mean()
    ema26 = df["Close"].ewm(span=26).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9).mean()

    ax3.plot(df.index, macd, label="MACD")
    ax3.plot(df.index, signal, label="Signal")
    ax3.legend()
    ax3.grid()

    st.pyplot(fig)
    plt.close(fig)

# ---------------------- TARAYICI ----------------------

def scan(data, tickers, ma_tol, vol_th, use_ma, use_vol, use_rsi, rsi_th, ceil_th, use_ma200):
    results = []

    for t in tickers:
        try:
            df = data.get(t)

            if df is None or df.empty or len(df) < 30:
                continue

            df = df.dropna()

            df["MA20"] = df["Close"].rolling(20).mean()
            df["MA50"] = df["Close"].rolling(50).mean()
            df["MA200"] = df["Close"].rolling(200).mean()

            df["RSI"] = calculate_rsi(df["Close"])
            df["VOLAVG"] = df["Volume"].rolling(20).mean()

            close = df["Close"].iloc[-1]
            prev = df["Close"].iloc[-2]
            change = ((close - prev) / prev) * 100

            if ceil_th and change < ceil_th:
                continue

            avg_vol = df["VOLAVG"].iloc[-1]
            if avg_vol is None or avg_vol == 0 or pd.isna(avg_vol):
                continue

            vol_ratio = df["Volume"].iloc[-1] / avg_vol

            cond_ma = close < min(df["MA20"].iloc[-1], df["MA50"].iloc[-1]) * (1 + ma_tol)
            cond_vol = vol_ratio >= vol_th
            cond_rsi = df["RSI"].iloc[-1] <= rsi_th

            # 🔥 MA200 filtresi (opsiyonel)
            cond_ma200 = True
            if use_ma200:
                ma200 = df["MA200"].iloc[-1]
                if pd.isna(ma200):
                    continue
                cond_ma200 = close > ma200  # sadece üstündekiler

            if (not use_ma or cond_ma) and (not use_vol or cond_vol) and (not use_rsi or cond_rsi) and cond_ma200:
                results.append({
                    "Hisse": t.replace(".IS",""),
                    "Close": round(close,2),
                    "Change": round(change,2),
                    "RSI": round(df["RSI"].iloc[-1],2),
                    "Vol": round(vol_ratio,2),
                    "Data": df
                })

        except:
            continue

    return results

# ---------------------- Sidebar ----------------------

st.sidebar.header("Filtre")

ma_tol = st.sidebar.slider("MA Tol %",1,10,5)/100
vol_th = st.sidebar.slider("Hacim",0.0,5.0,1.5)
use_ma = st.sidebar.checkbox("MA",True)
use_vol = st.sidebar.checkbox("Hacim",True)
use_rsi = st.sidebar.checkbox("RSI",False)
rsi_th = st.sidebar.slider("RSI",10,50,30)
use_ceil = st.sidebar.checkbox("Tavan",False)

# 🔥 YENİ
use_ma200 = st.sidebar.checkbox("Sadece MA200 Üstü", False)

tickers = get_all_bist_tickers()
selected = st.sidebar.multiselect("Hisse", tickers)

# ---------------------- ANA ----------------------

if st.button("🔍 Tara"):

    tickers_to_scan = selected if selected else tickers
    ceil = 9.5 if use_ceil else None

    data = get_bulk_data(tickers_to_scan)

    results = scan(
        data,
        tickers_to_scan,
        ma_tol,
        vol_th,
        use_ma,
        use_vol,
        use_rsi,
        rsi_th,
        ceil,
        use_ma200
    )

    if not results:
        st.warning("Hisse yok")
    else:
        st.success(f"{len(results)} bulundu")

        for r in results:
            hisse = r["Hisse"]

            lot = dolasim_lot_dict.get(hisse,"N/A")
            halka = halka_aciklik_dict.get(hisse,"N/A")

            color = "green" if r["Change"]>=0 else "red"

            st.markdown(f"""
            <div style="border:1px solid #ccc;padding:10px;margin:10px;border-radius:10px">
            <b>{hisse}</b><br>
            Fiyat: {r["Close"]} <span style='color:{color}'>{r["Change"]}%</span><br>
            RSI: {r["RSI"]} | Hacim: {r["Vol"]}<br>
            Lot: {lot} | Halka: {halka}
            </div>
            """, unsafe_allow_html=True)

            plot_chart(r["Data"], hisse)
