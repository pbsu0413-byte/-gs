"""
개인용 주식 분석 대시보드
실행: streamlit run dashboard.py
브라우저에서 http://localhost:8501 로 접속됩니다 (나만 볼 수 있음).
"""

import streamlit as st
import pandas as pd
import yfinance as yf
import gs_quant.timeseries as ts
from gs_quant.timeseries import Window
import plotly.graph_objects as go

st.set_page_config(page_title="나만의 주식 대시보드", layout="wide")
st.title("📊 나만의 주식 분석 대시보드")

# --- 사이드바: 입력 ---
st.sidebar.header("설정")
ticker = st.sidebar.text_input("종목 티커 (예: AAPL, 005930.KS, ^KS11)", value="AAPL")
period = st.sidebar.selectbox("조회 기간", ["6mo", "1y", "2y", "5y"], index=1)
ma_window = st.sidebar.slider("이동평균 기간 (일)", 5, 120, 20)
vol_window = st.sidebar.slider("변동성 계산 기간 (일)", 5, 120, 22)

# --- 데이터 다운로드 ---
@st.cache_data(ttl=3600)
def load_data(ticker, period):
    df = yf.download(ticker, period=period, progress=False)
    return df

data = load_data(ticker, period)

if data.empty:
    st.error("데이터를 불러오지 못했어요. 티커를 다시 확인해주세요.")
    st.stop()

close = data["Close"].squeeze()

# --- gs-quant로 지표 계산 ---
returns = ts.returns(close)
volatility = ts.volatility(close, Window(vol_window, 0))
moving_avg = ts.moving_average(close, ma_window)
rsi = ts.relative_strength_index(close, 14)

# --- 상단 요약 지표 ---
col1, col2, col3, col4 = st.columns(4)
col1.metric("현재가", f"{close.iloc[-1]:.2f}")
col2.metric("일일 수익률", f"{returns.iloc[-1]*100:.2f}%")
col3.metric(f"{vol_window}일 변동성", f"{volatility.iloc[-1]:.2f}%")
col4.metric("RSI (14일)", f"{rsi.iloc[-1]:.1f}")

# --- 가격 + 이동평균 차트 ---
st.subheader("가격 추이 & 이동평균")
fig1 = go.Figure()
fig1.add_trace(go.Scatter(x=close.index, y=close, name="종가"))
fig1.add_trace(go.Scatter(x=moving_avg.index, y=moving_avg, name=f"{ma_window}일 이동평균"))
st.plotly_chart(fig1, use_container_width=True)

# --- 변동성 차트 ---
st.subheader("변동성 추이")
fig2 = go.Figure()
fig2.add_trace(go.Scatter(x=volatility.index, y=volatility, name="변동성", line=dict(color="orange")))
st.plotly_chart(fig2, use_container_width=True)

# --- RSI 차트 ---
st.subheader("RSI (상대강도지수)")
fig3 = go.Figure()
fig3.add_trace(go.Scatter(x=rsi.index, y=rsi, name="RSI", line=dict(color="purple")))
fig3.add_hline(y=70, line_dash="dash", line_color="red", annotation_text="과매수")
fig3.add_hline(y=30, line_dash="dash", line_color="green", annotation_text="과매도")
st.plotly_chart(fig3, use_container_width=True)

st.caption("데이터: Yahoo Finance | 지표 계산: gs-quant timeseries")
