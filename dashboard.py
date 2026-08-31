import streamlit as st
import pandas as pd
import yfinance as yf
import gs_quant.timeseries as ts
from gs_quant.timeseries import Window
import plotly.graph_objects as go

st.set_page_config(page_title="나만의 커스텀 주식 대시보드", layout="wide")
st.title("📊 나만의 맞춤형 주식 분석 대시보드")

# --- 나스닥 주요 종목 사전 정의 ---
NASDAQ_TOP_STOCKS = {
    "애플 (AAPL)": "AAPL",
    "엔비디아 (NVDA)": "NVDA",
    "마이크로소프트 (MSFT)": "MSFT",
    "테슬라 (TSLA)": "TSLA",
    "알파벳/구글 (GOOGL)": "GOOGL",
    "아마존 (AMZN)": "AMZN",
    "메타 (META)": "META",
    "브로드컴 (AVGO)": "AVGO",
    "AMD (AMD)": "AMD",
    "넷플릭스 (NFLX)": "NFLX",
    "나스닥 100 지수 ETF (QQQ)": "QQQ",
    "S&P 500 지수 ETF (SPY)": "SPY"
}

# --- 사이드바: 기본 설정 ---
st.sidebar.header("⚙️ 종목 및 기본 설정")

search_mode = st.sidebar.radio("종목 검색 방식", ["주요 나스닥 종목 선택", "티커 직접 입력"])

if search_mode == "주요 나스닥 종목 선택":
    selected_name = st.sidebar.selectbox("나스닥 인기 종목", list(NASDAQ_TOP_STOCKS.keys()))
    ticker_symbol = NASDAQ_TOP_STOCKS[selected_name]
else:
    ticker_symbol = st.sidebar.text_input("종목 티커 직접 입력 (예: TSLA, 005930.KS)", value="AAPL")

period = st.sidebar.selectbox("조회 기간", ["3mo", "6mo", "1y", "2y", "5y"], index=2)

# --- 사이드바: 화면 표시 설정 (On/Off) ---
st.sidebar.header("👁️ 화면 표시 설정")
show_fundamental = st.sidebar.checkbox("재무제표 및 주요 투자지표", value=True)
show_consensus = st.sidebar.checkbox("월가 컨센서스 (목표주가)", value=True)
show_bollinger = st.sidebar.checkbox("볼린저 밴드 표시", value=True)
show_macd = st.sidebar.checkbox("MACD 차트 표시", value=False)

# --- 사이드바: 세부 파라미터 ---
st.sidebar.header("📐 지표 파라미터")
ma_window = st.sidebar.slider("이동평균 기간 (일)", 5, 120, 20)
vol_window = st.sidebar.slider("변동성 계산 기간 (일)", 5, 120, 22)

# --- 데이터 및 실시간 환율 로드 ---
@st.cache_data(ttl=3600)
def get_stock_and_fx_data(symbol, p):
    t = yf.Ticker(symbol)
    hist = t.history(period=p)
    info = t.info
    
    # 원/달러 환율 가져오기
    fx_hist = yf.Ticker("USDKRW=X").history(period="1d")
    fx_rate = fx_hist["Close"].iloc[-1] if not fx_hist.empty else 1350.0
    
    return hist, info, fx_rate

data, info, usd_krw = get_stock_and_fx_data(ticker_symbol, period)

if data.empty:
    st.error("데이터를 불러오지 못했습니다. 티커를 다시 확인해 주세요.")
    st.stop()

close = data["Close"]
volume = data["Volume"]

# --- gs-quant 및 지표 계산 ---
returns = ts.returns(close)
volatility = ts.volatility(close, Window(vol_window, 0))
moving_avg = ts.moving_average(close, ma_window)
rsi = ts.relative_strength_index(close, 14)

# 볼린저 밴드
std = close.rolling(window=ma_window).std()
bollinger_upper = moving_avg + (std * 2)
bollinger_lower = moving_avg - (std * 2)

# MACD
ema12 = close.ewm(span=12, adjust=False).mean()
ema26 = close.ewm(span=26, adjust=False).mean()
macd = ema12 - ema26
macd_signal = macd.ewm(span=9, adjust=False).mean()
macd_hist = macd - macd_signal

# --- 원화 환산 도우미 함수 ---
is_korean_stock = ticker_symbol.endswith(".KS") or ticker_symbol.endswith(".KQ")

def fmt_price(val):
    if pd.isna(val) or val == 0:
        return "N/A"
    if is_korean_stock:
        return f"₩{val:,.0f}"
    else:
        krw_val = val * usd_krw
        return f"${val:,.2f} (₩{krw_val:,.0f})"


# --- 1. 주요 투자지표 & 컨센서스 ---
if show_fundamental or show_consensus:
    st.subheader(f"📌 {info.get('shortName', ticker_symbol)} - 기업 분석 & 컨센서스")
    cols = st.columns(5)
    col_idx = 0

    if show_fundamental:
        mcap = info.get('marketCap', 0)
        mcap_str = f"₩{mcap:,.0f}" if is_korean_stock else f"${mcap:,.0f} (₩{mcap*usd_krw:,.0f})" if mcap else "N/A"
        cols[0].metric("시가총액", mcap_str)
        cols[1].metric("PER", f"{info.get('trailingPE', 0):.2f}" if info.get('trailingPE') else "N/A")
        cols[2].metric("PBR", f"{info.get('priceToBook', 0):.2f}" if info.get('priceToBook') else "N/A")
        col_idx = 3

    if show_consensus:
        target_p = info.get('targetMeanPrice', 0)
        cols[col_idx].metric("목표주가 (평균)", fmt_price(target_p))
        cols[col_idx+1].metric("투자의견", f"{info.get('recommendationKey', 'N/A').upper()}")

    st.markdown("---")


# --- 2. 상단 핵심 수치 요약 (거래량 숫자 표기 포함) ---
col1, col2, col3, col4, col5 = st.columns(5)

latest_close = close.iloc[-1]
latest_vol = volume.iloc[-1]

col1.metric("현재가", fmt_price(latest_close))
col2.metric("일일 수익률", f"{returns.iloc[-1]*100:.2f}%")
col3.metric("최근 거래량", f"{latest_vol:,.0f} 주")
col4.metric(f"{vol_window}일 변동성", f"{volatility.iloc[-1]:.2f}%")
col5.metric("RSI (14일)", f"{rsi.iloc[-1]:.1f}")


# --- 3. 가격 차트 ---
st.subheader("📈 가격 추이 & 기술적 지표")
fig_price = go.Figure()
fig_price.add_trace(go.Scatter(x=close.index, y=close, name="종가", line=dict(color="blue")))
fig_price.add_trace(go.Scatter(x=moving_avg.index, y=moving_avg, name=f"{ma_window}일 이동평균", line=dict(color="orange")))

if show_bollinger:
    fig_price.add_trace(go.Scatter(x=bollinger_upper.index, y=bollinger_upper, name="상한 밴드", line=dict(color="gray", dash="dash")))
    fig_price.add_trace(go.Scatter(x=bollinger_lower.index, y=bollinger_lower, name="하한 밴드", line=dict(color="gray", dash="dash")))

fig_price.update_layout(height=450, margin=dict(l=20, r=20, t=20, b=20))
st.plotly_chart(fig_price, use_container_width=True)


# --- 4. MACD 차트 (선택 시) ---
if show_macd:
    st.subheader("📉 MACD (이동평균 수렴·확산)")
    fig_macd = go.Figure()
    fig_macd.add_trace(go.Scatter(x=macd.index, y=macd, name="MACD", line=dict(color="blue")))
    fig_macd.add_trace(go.Scatter(x=macd_signal.index, y=macd_signal, name="Signal", line=dict(color="red")))
    fig_macd.add_trace(go.Bar(x=macd_hist.index, y=macd_hist, name="Histogram", marker_color="gray"))
    fig_macd.update_layout(height=250, margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig_macd, use_container_width=True)


# --- 5. 변동성 & RSI ---
c1, c2 = st.columns(2)
with c1:
    st.subheader("📉 변동성 추이")
    fig_v = go.Figure()
    fig_v.add_trace(go.Scatter(x=volatility.index, y=volatility, name="변동성", line=dict(color="darkorange")))
    st.plotly_chart(fig_v, use_container_width=True)

with c2:
    st.subheader("📊 RSI (상대강도지수)")
    fig_r = go.Figure()
    fig_r.add_trace(go.Scatter(x=rsi.index, y=rsi, name="RSI", line=dict(color="purple")))
    fig_r.add_hline(y=70, line_dash="dash", line_color="red", annotation_text="과매수")
    fig_r.add_hline(y=30, line_dash="dash", line_color="green", annotation_text="과매도")
    st.plotly_chart(fig_r, use_container_width=True)

st.caption("데이터: Yahoo Finance | 지표 계산: gs-quant timeseries")