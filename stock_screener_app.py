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

def get_financial_ratios(ticker):
    try:
        info = yf.Ticker(ticker).info
        return {
            "F/K": round(info.get("trailingPE", 0), 2) if info.get("trailingPE") else "N/A",
            "PD/DD": round(info.get("priceToBook", 0), 2) if info.get("priceToBook") else "N/A",
            "Piyasa_Değeri": info.get("marketCap", "N/A")
        }
    except:
        return {"F/K":"N/A","PD/DD":"N/A","Piyasa_Değeri":"N/A"}

# ---------------------- Teknik hesaplamalar ----------------------

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

# ---------------------- Grafik hazırlama ----------------------

def plot_chart(df, name):
    fig, (ax1, ax2, ax3, ax4) = plt.subplots(4,1, figsize=(10,10), sharex=True)

    # MA’lar
    df["MA20"] = df["Close"].rolling(20, min_periods=1).mean()
    df["MA50"] = df["Close"].rolling(50, min_periods=1).mean()
    df["MA200"] = df["Close"].rolling(200, min_periods=1).mean()

    ax1.plot(df.index, df["Close"], label="Fiyat", color="blue")
    ax1.plot(df.index, df["MA20"], label="MA20", color="orange")
    ax1.plot(df.index, df["MA50"], label="MA50", color="green")
    ax1.plot(df.index, df["MA200"], label="MA200", color="red", linestyle="--")

    # Bollinger Bands
    df["STD20"] = df["Close"].rolling(20).std()
    df["Upper"] = df["MA20"] + 2*df["STD20"]
    df["Lower"] = df["MA20"] - 2*df["STD20"]
    ax1.plot(df.index, df["Upper"], label="Upper BB", color="gray", linestyle="--")
    ax1.plot(df.index, df["Lower"], label="Lower BB", color="gray", linestyle="--")
    ax1.legend(); ax1.grid()

    # RSI
    rsi = calculate_rsi(df["Close"])
    ax2.plot(df.index, rsi, label="RSI", color="purple")
    ax2.axhline(70, color="red", linestyle="--")
    ax2.axhline(30, color="green", linestyle="--")
    ax2.legend(); ax2.grid()

    # MACD
    ema12 = df["Close"].ewm(span=12).mean()
    ema26 = df["Close"].ewm(span=26).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9).mean()
    ax3.plot(df.index, macd, label="MACD", color="blue")
    ax3.plot(df.index, signal, label="Signal", color="orange")
    ax3.bar(df.index, macd-signal, label="Hist", color="gray", alpha=0.4)
    ax3.legend(); ax3.grid()

    # Stochastic Oscillator
    low14 = df["Low"].rolling(14).min()
    high14 = df["High"].rolling(14).max()
    df["%K"] = 100*((df["Close"]-low14)/(high14-low14))
    df["%D"] = df["%K"].rolling(3).mean()
    ax4.plot(df.index, df["%K"], label="%K", color="blue")
    ax4.plot(df.index, df["%D"], label="%D", color="orange")
    ax4.axhline(80, color="red", linestyle="--")
    ax4.axhline(20, color="green", linestyle="--")
    ax4.legend(); ax4.grid()

    plt.tight_layout()
    st.pyplot(fig)
    plt.close(fig)

# ---------------------- Tarama ----------------------

def scan(data, tickers, ma_tol, vol_th, use_ma, use_vol, use_rsi, rsi_th, ceil_th, use_ma200):
    results = []
    for t in tickers:
        try:
            df = data.get(t)
            if df is None or df.empty or len(df) < 30:
                continue
            df = df.dropna()

            df["MA20"] = df["Close"].rolling(20, min_periods=1).mean()
            df["MA50"] = df["Close"].rolling(50, min_periods=1).mean()
            df["MA200"] = df["Close"].rolling(200, min_periods=1).mean()
            df["RSI"] = calculate_rsi(df["Close"])
            df["VOLAVG"] = df["Volume"].rolling(20, min_periods=1).mean()

            close = df["Close"].iloc[-1]
            prev = df["Close"].iloc[-2]
            change = ((close - prev)/prev)*100

            if ceil_th and change < ceil_th:
                continue

            vol_ratio = df["Volume"].iloc[-1] / df["VOLAVG"].iloc[-1]

            cond_ma = close < min(df["MA20"].iloc[-1], df["MA50"].iloc[-1]) * (1+ma_tol)
            cond_vol = vol_ratio >= vol_th
            cond_rsi = df["RSI"].iloc[-1] <= rsi_th

            cond_ma200 = True
            if use_ma200:
                cond_ma200 = close > df["MA200"].iloc[-1]

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

st.sidebar.header("Filtreler")
ma_tol = st.sidebar.slider("MA Tol %",1,10,5)/100
vol_th = st.sidebar.slider("Hacim",0.0,5.0,1.5)
use_ma = st.sidebar.checkbox("MA",True)
use_vol = st.sidebar.checkbox("Hacim",True)
use_rsi = st.sidebar.checkbox("RSI",False)
rsi_th = st.sidebar.slider("RSI",10,50,30)
use_ceil = st.sidebar.checkbox("Tavan",False)
use_ma200 = st.sidebar.checkbox("Sadece MA200 Üstü",False)

tickers = get_all_bist_tickers()
selected = st.sidebar.multiselect("Hisse Seç", tickers)

# ---------------------- Ana ----------------------

if st.button("🔍 Tara"):
    tickers_to_scan = selected if selected else tickers
    ceil = 9.5 if use_ceil else None
    data = yf.download(
        tickers_to_scan,
        period="6mo",
        interval="1d",
        group_by="ticker",
        threads=True
    )
    results = scan(data, tickers_to_scan, ma_tol, vol_th, use_ma, use_vol, use_rsi, rsi_th, ceil, use_ma200)

    if not results:
        st.warning("Kriterlere uyan hisse yok")
    else:
        st.success(f"{len(results)} hisse bulundu")
        for r in results:
            hisse =Şu anda yaşadığın hata, kodun içine açıklama metni ve Türkçe cümlelerin karışmasından kaynaklanıyor. Python dosyasında **sadece kod** olmalı; araya yazı girince indentation (girinti) bozuluyor.  

Aşağıda tamamen temizlenmiş, çalışır **tam kod**u paylaşıyorum. Bu sürümde:
- PD/DD, F/K ve piyasa değeri otomatik olarak Yahoo Finance’tan çekiliyor.
- Grafiklerde Bollinger Bands ve Stochastic Oscillator eklendi.
- Kodun içinde açıklama metni yok, sadece Python kodu var.

```python
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

def get_financial_ratios(ticker):
    try:
        info = yf.Ticker(ticker).info
        return {
            "F/K": round(info.get("trailingPE", 0), 2) if info.get("trailingPE") else "N/A",
            "PD/DD": round(info.get("priceToBook", 0), 2) if info.get("priceToBook") else "N/A",
            "Piyasa_Değeri": info.get("marketCap", "N/A")
        }
    except:
        return {"F/K":"N/A","PD/DD":"N/A","Piyasa_Değeri":"N/A"}

# ---------------------- Teknik hesaplamalar ----------------------

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

# ---------------------- Grafik hazırlama ----------------------

def plot_chart(df, name):
    fig, (ax1, ax2, ax3, ax4) = plt.subplots(4,1, figsize=(10,10), sharex=True)

    # MA’lar
    df["MA20"] = df["Close"].rolling(20, min_periods=1).mean()
    df["MA50"] = df["Close"].rolling(50, min_periods=1).mean()
    df["MA200"] = df["Close"].rolling(200, min_periods=1).mean()

    ax1.plot(df.index, df["Close"], label="Fiyat", color="blue")
    ax1.plot(df.index, df["MA20"], label="MA20", color="orange")
    ax1.plot(df.index, df["MA50"], label="MA50", color="green")
    ax1.plot(df.index, df["MA200"], label="MA200", color="red", linestyle="--")

    # Bollinger Bands
    df["STD20"] = df["Close"].rolling(20).std()
    df["Upper"] = df["MA20"] + 2*df["STD20"]
    df["Lower"] = df["MA20"] - 2*df["STD20"]
    ax1.plot(df.index, df["Upper"], label="Upper BB", color="gray", linestyle="--")
    ax1.plot(df.index, df["Lower"], label="Lower BB", color="gray", linestyle="--")
    ax1.legend(); ax1.grid()

    # RSI
    rsi = calculate_rsi(df["Close"])
    ax2.plot(df.index, rsi, label="RSI", color="purple")
    ax2.axhline(70, color="red", linestyle="--")
    ax2.axhline(30, color="green", linestyle="--")
    ax2.legend(); ax2.grid()

    # MACD
    ema12 = df["Close"].ewm(span=12).mean()
    ema26 = df["Close"].ewm(span=26).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9).mean()
    ax3.plot(df.index, macd, label="MACD", color="blue")
    ax3.plot(df.index, signal, label="Signal", color="orange")
    ax3.bar(df.index, macd-signal, label="Hist", color="gray", alpha=0.4)
    ax3.legend(); ax3.grid()

    # Stochastic Oscillator
    low14 = df["Low"].rolling(14).min()
    high14 = df["High"].rolling(14).max()
    df["%K"] = 100*((df["Close"]-low14)/(high14-low14))
    df["%D"] = df["%K"].rolling(3).mean()
    ax4.plot(df.index, df["%K"], label="%K", color="blue")
    ax4.plot(df.index, df["%D"], label="%D", color="orange")
    ax4.axhline(80, color="red", linestyle="--")
    ax4.axhline(20, color="green", linestyle="--")
    ax4.legend(); ax4.grid()

    plt.tight_layout()
    st.pyplot(fig)
    plt.close(fig)

# ---------------------- Tarama ----------------------

def scan(data, tickers, ma_tol, vol_th, use_ma, use_vol, use_rsi, rsi_th, ceil_th, use_ma200):
    results = []
    for t in tickers:
        try:
            df = data.get(t)
            if df is None or df.empty or len(df) < 30:
                continue
            df = df.dropna()

            df["MA20"] = df["Close"].rolling(20, min_periods=1).mean()
            df["MA50"] = df["Close"].rolling(50, min_periods=1).mean()
            df["MA200"] = df["Close"].rolling(200, min_periods=1).mean()
            df["RSI"] = calculate_rsi(df["Close"])
            df["VOLAVG"] = df["Volume"].rolling(20, min_periods=1).mean()

            close = df["Close"].iloc[-1]
            prev = df["Close"].iloc[-2]
            change = ((close - prev)/prev)*100

            if ceil_th and change < ceil_th:
                continue

            vol_ratio = df["Volume"].iloc[-1] / df["VOLAVG"].iloc[-1]

            cond_ma = close < min(df["MA20"].iloc[-1], df["MA50"].iloc[-1]) * (1+ma_tol)
            cond_vol = vol_ratio >= vol_th
            cond_rsi = df["RSI"].iloc[-1] <= rsi_th

            cond_ma200 = True
            if use_ma200:
                cond_ma200 = close > df["MA200"].iloc[-1]

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

st.sidebar.header("Filtreler")
ma_tol = st.sidebar.slider("MA Tol %",1,10,5)/100
vol_th = st.sidebar.slider("Hacim",0.0,5.0,1.5)
use_ma = st.sidebar.checkbox("MA",True)
use_vol = st.sidebar.checkbox("Hacim",True)
use_rsi = st.sidebar.checkbox("RSI",False)
rsi_th = st.sidebar.slider("RSI",10,50,30)
use_ceil = st.sidebar.checkbox("Tavan",False)
use_ma200 = st.sidebar.checkbox("Sadece MA200 Üstü",False)

tickers = get_all_bist_tickers()
selected = st.sidebar.multiselect("Hisse Seç", tickers)

# ---------------------- Ana ----------------------

if st.button("🔍 Tara"):
    tickers_to_scan = selected if selected else tickers
    ceil = 9.5 if use_ceil else None
    data = yf.download(
        tickers_to_scan,
        period="6mo",
        interval="1d",
        group_by="ticker",
        threads=True
    )
    results = scan(data, tickers_to_scan, ma_tol, vol_th, use_ma, use_vol, use_rsi, rsi_th, ceil, use_ma
