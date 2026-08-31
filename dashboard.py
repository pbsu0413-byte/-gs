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

# --- 데이터 주기 및 조회 기간 설정 (분봉 추가) ---
interval_choice = st.sidebar.selectbox("데이터 주기 (봉)", ["1일 (일봉)", "1분봉", "5분봉", "15분봉"])

# 주기별 조회 기간 제한
if interval_choice == "1분봉":
    interval = "1m"
    period_options = ["1d", "5d"]
elif interval_choice == "5분봉":
    interval = "5m"
    period_options = ["1d", "5d", "1mo"]
elif interval_choice == "15분봉":
    interval = "15m"
    period_options = ["1d", "5d", "1mo"]
else:
    interval = "1d"
    period_options = ["3mo", "6mo", "1y", "2y", "5y"]

period = st.sidebar.selectbox("조회 기간", period_options, index=0)

# --- 사이드바: 화면 표시 설정 (On/Off) ---
st.sidebar.header("👁️ 화면 표시 설정")
show_fundamental = st.sidebar.checkbox("주요 투자지표 (PER/PBR 등)", value=True)
show_financials_table = st.sidebar.checkbox("상세 재무제표 표 표시", value=True)
show_consensus = st.sidebar.checkbox("월가 컨센서스 (목표주가)", value=True)
show_bollinger = st.sidebar.checkbox("볼린저 밴드 표시", value=True)
show_macd = st.sidebar.checkbox("MACD 차트 표시", value=False)

# --- 사이드바: 세부 파라미터 ---
st.sidebar.header("📐 지표 파라미터")
ma_window = st.sidebar.slider("이동평균 기간", 5, 120, 20)
vol_window = st.sidebar.slider("변동성 계산 기간", 5, 120, 22)

# --- 데이터 및 실시간 환율 로드 ---
@st.cache_data(ttl=60) # 분봉 조회를 위해 캐시 타임을 60초로 짧게 설정
def get_stock_and_fx_data(symbol, p, inv):
    t = yf.Ticker(symbol)
    hist = t.history(period=p, interval=inv)
    info = t.info
    
    try:
        financials = t.financials
    except:
        financials = pd.DataFrame()

    fx_hist = yf.Ticker("USDKRW=X").history(period="1d")
    fx_rate = fx_hist["Close"].iloc[-1] if not fx_hist.empty else 1350.0
    
    return hist, info, financials, fx_rate

data, info, financials, usd_krw = get_stock_and_fx_data(ticker_symbol, period, interval)

if data.empty:
    st.error("데이터를 불러오지 못했습니다. 선택한 주기/기간에 데이터가 존재하는지 확인해 주세요.")
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

# --- 원화/달러 병행 표시 도우미 ---
is_korean_stock = ticker_symbol.endswith(".KS") or ticker_symbol.endswith(".KQ")

def render_custom_metric(title, usd_val, is_price=True):
    if pd.isna(usd_val) or usd_val == 0 or usd_val is None:
        return f"<b>{title}</b><br><span style='font-size:18px; color:gray;'>N/A</span>"
    
    if is_korean_stock:
        val_str = f"₩{usd_val:,.0f}"
        sub_str = ""
    else:
        krw_val = usd_val * usd_krw
        if is_price:
            val_str = f"${usd_val:,.2f}"
            sub_str = f"<br><span style='font-size:13px; color:#666;'>(₩{krw_val:,.0f})</span>"
        else:
            val_str = f"${usd_val/1e9:,.1f}B"
            sub_str = f"<br><span style='font-size:13px; color:#666;'>(₩{krw_val/1e12:,.1f}조)</span>"
            
    return f"<b>{title}</b><br><span style='font-size:22px; font-weight:bold;'>{val_str}</span>{sub_str}"


# --- 1. 주요 투자지표 & 컨센서스 ---
if show_fundamental or show_consensus:
    st.subheader(f"📌 {info.get('shortName', ticker_symbol)} - 기업 정보 & 컨센서스")
    cols = st.columns(5)

    if show_fundamental:
        mcap = info.get('marketCap', 0)
        cols[0].markdown(render_custom_metric("시가총액", mcap, is_price=False), unsafe_allow_html=True)
        cols[1].markdown(f"<b>PER</b><br><span style='font-size:22px; font-weight:bold;'>{info.get('trailingPE', 0):.2f}</span>" if info.get('trailingPE') else "<b>PER</b><br>N/A", unsafe_allow_html=True)
        cols[2].markdown(f"<b>PBR</b><br><span style='font-size:22px; font-weight:bold;'>{info.get('priceToBook', 0):.2f}</span>" if info.get('priceToBook') else "<b>PBR</b><br>N/A", unsafe_allow_html=True)

    if show_consensus:
        target_p = info.get('targetMeanPrice', 0)
        cols[3].markdown(render_custom_metric("목표주가 (평균)", target_p, is_price=True), unsafe_allow_html=True)
        cols[4].markdown(f"<b>투자의견</b><br><span style='font-size:22px; font-weight:bold; color:green;'>{info.get('recommendationKey', 'N/A').upper()}</span>", unsafe_allow_html=True)

    st.markdown("---")


# --- 2. 상세 재무제표 표 ---
if show_financials_table:
    st.subheader("📑 최근 손익계산서 (Financials)")
    if not financials.empty:
        items_to_show = ["Total Revenue", "Operating Income", "Net Income", "EBITDA"]
        existing_items = [item for item in items_to_show if item in financials.index]
        
        if existing_items:
            df_fin = financials.loc[existing_items].copy()
            df_fin.columns = [col.strftime('%Y') if hasattr(col, 'strftime') else str(col) for col in df_fin.columns]
            
            if is_korean_stock:
                df_fin_display = df_fin.applymap(lambda x: f"₩{x/1e8:,.0f} 억" if pd.notnull(x) else "N/A")
            else:
                df_fin_display = df_fin.applymap(lambda x: f"${x/1e6:,.1f}M (₩{x*usd_krw/1e8:,.0f}억)" if pd.notnull(x) else "N/A")
            
            df_fin_display.index = df_fin_display.index.map({
                "Total Revenue": "매출액",
                "Operating Income": "영업이익",
                "Net Income": "당기순이익",
                "EBITDA": "EBITDA"
            }).fillna(df_fin_display.index.to_series())
            
            st.dataframe(df_fin_display, use_container_width=True)
        else:
            st.info("해당 종목의 상세 재무제표 항목을 불러올 수 없습니다.")
    else:
        st.info("상세 재무제표 데이터를 제공하지 않는 종목입니다.")
    st.markdown("---")


# --- 3. 상단 핵심 수치 요약 ---
st.subheader(f"⚡ 실시간 주가 & 지표 요약 ({interval_choice})")
col1, col2, col3, col4, col5 = st.columns(5)

latest_close = close.iloc[-1]
latest_vol = volume.iloc[-1]

col1.markdown(render_custom_metric("현재가", latest_close, is_price=True), unsafe_allow_html=True)
col2.metric("변동 수익률", f"{returns.iloc[-1]*100:.2f}%")
col3.metric("최근 거래량", f"{latest_vol:,.0f} 주")
col4.metric(f"변동성 ({vol_window}주기)", f"{volatility.iloc[-1]:.2f}%")
col5.metric("RSI (14주기)", f"{rsi.iloc[-1]:.1f}")


# --- 4. 가격 차트 ---
st.subheader(f"📈 가격 추이 & 기술적 지표 ({interval_choice})")
fig_price = go.Figure()
fig_price.add_trace(go.Scatter(x=close.index, y=close, name="종가", line=dict(color="blue")))
fig_price.add_trace(go.Scatter(x=moving_avg.index, y=moving_avg, name=f"{ma_window}주기 이동평균", line=dict(color="orange")))

if show_bollinger:
    fig_price.add_trace(go.Scatter(x=bollinger_upper.index, y=bollinger_upper, name="상한 밴드", line=dict(color="gray", dash="dash")))
    fig_price.add_trace(go.Scatter(x=bollinger_lower.index, y=bollinger_lower, name="하한 밴드", line=dict(color="gray", dash="dash")))

fig_price.update_layout(height=450, margin=dict(l=20, r=20, t=20, b=20))
st.plotly_chart(fig_price, use_container_width=True)


# --- 5. MACD 차트 ---
if show_macd:
    st.subheader("📉 MACD (이동평균 수렴·확산)")
    fig_macd = go.Figure()
    fig_macd.add_trace(go.Scatter(x=macd.index, y=macd, name="MACD", line=dict(color="blue")))
    fig_macd.add_trace(go.Scatter(x=macd_signal.index, y=macd_signal, name="Signal", line=dict(color="red")))
    fig_macd.add_trace(go.Bar(x=macd_hist.index, y=macd_hist, name="Histogram", marker_color="gray"))
    fig_macd.update_layout(height=250, margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig_macd, use_container_width=True)


# --- 6. 변동성 & RSI ---
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