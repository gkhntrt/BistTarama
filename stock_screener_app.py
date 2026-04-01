import streamlit as st
import pandas as pd
import requests
import time
import matplotlib.pyplot as plt
from tickers import get_all_bist_tickers  # Bu modülün mevcut olduğunu varsayıyorum

# Finnhub API Key
FINNHUB_API_KEY = "YOUR_API_KEY_HERE"
FINNHUB_BASE = "https://finnhub.io/api/v1"

st.set_page_config(page_title="BIST Hisse Analiz", layout="centered")
st.title("📈 Hisse Analiz (Finnhub)")

# ---------------------- Veri yükleme ----------------------
@st.cache_data
def load_halaciklik_data():
    df_ozet = pd.read_excel("temelozet.xlsx")
    df_ozet["Kod"] = df_ozet["Kod"].str.strip().str.upper()
    return df_ozet.set_index("Kod")["Halka Açıklık Oranı (%)"].to_dict()

halka_aciklik_dict = load_halaciklik_data()

@st.cache_data
def load_lot_data():
    df_lot = pd.read_csv("dolasim_lot.csv", sep=None, engine='python')
    df_lot["Kod"] = df_lot["Kod"].str.strip().str.upper()
    return df_lot.set_index("Kod")["Dolasimdaki_Lot"].to_dict()

dolasim_lot_dict = load_lot_data()

# ---------------------- Teknik hesaplamalar ----------------------
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_macd(close, fast=12, slow=26, signal=9):
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

# ---------------------- Finnhub veri çekme ----------------------
def fetch_stock_data_finnhub(ticker, days=90):
    url = f"{FINNHUB_BASE}/quote"
    params = {"symbol": f"BINANCE:{ticker}", "token": FINNHUB_API_KEY}
    try:
        resp = requests.get(url, params=params, timeout=5)
        data = resp.json()
        if "c" not in data or data["c"] == 0:
            return None  # Delisted veya veri yok
        df = pd.DataFrame([data])
        df.index = pd.to_datetime([pd.Timestamp.now()])
        return df
    except Exception:
        return None

# ---------------------- Grafik hazırlama ----------------------
def plot_stock_chart(data, ticker_name):
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 9), sharex=True,
                                       gridspec_kw={'height_ratios': [2, 1, 1]})

    ax1.plot(data.index, data["c"], label="Kapanış", color="blue")
    ax1.set_title(f"{ticker_name} - Son Teknik Görünüm")
    ax1.legend()
    ax1.grid(True)

    if "RSI" in data:
        ax2.plot(data.index, data["RSI"], label="RSI", color="purple")
        ax2.axhline(70, color='red', linestyle='--', linewidth=1)
        ax2.axhline(30, color='green', linestyle='--', linewidth=1)
        ax2.set_ylabel("RSI")
        ax2.legend()
        ax2.grid(True)

    if "MACD_Line" in data:
        ax3.plot(data.index, data["MACD_Line"], label="MACD", color="blue")
        ax3.plot(data.index, data["MACD_Signal"], label="Signal", color="orange")
        ax3.bar(data.index, data["MACD_Hist"], label="Histogram", color="gray", alpha=0.4)
        ax3.set_ylabel("MACD")
        ax3.legend()
        ax3.grid(True)

    fig.text(0.5, 0.5, 'BAY-GT',
             fontsize=50, color='gray', alpha=0.15,
             ha='center', va='center',
             weight='bold', style='italic', rotation=20)

    plt.tight_layout()
    st.pyplot(fig)
    plt.clf()

# ---------------------- Tarama fonksiyonu ----------------------
def scan_stocks(tickers):
    results = []
    for ticker in tickers:
        data = fetch_stock_data_finnhub(ticker)
        if data is None:
            continue

        close = float(data["c"].iloc[-1])
        prev_close = float(data["pc"].iloc[-1])
        change_pct = ((close - prev_close) / prev_close) * 100

        results.append({
            "Hisse": ticker,
            "Kapanış": round(close, 2),
            "Değişim": round(change_pct, 2),
        })
        time.sleep(0.1)
    return pd.DataFrame(results)

# ---------------------- Sidebar ----------------------
st.sidebar.header("📌 Tarama Ayarları")
all_tickers = get_all_bist_tickers()
selected_tickers = st.sidebar.multiselect("Hisseleri Seç", options=all_tickers)

# ---------------------- Ana içerik ----------------------
if st.button("🔍 Taramayı Başlat"):
    with st.spinner("Hisseler taranıyor..."):
        tickers_to_scan = selected_tickers if selected_tickers else all_tickers
        df = scan_stocks(tickers_to_scan)
        if df.empty:
            st.warning("Hiç hisse bulunamadı.")
        else:
            st.success(f"{len(df)} hisse bulundu.")
            st.dataframe(df)
