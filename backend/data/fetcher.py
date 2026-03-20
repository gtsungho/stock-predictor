"""
주식 데이터 수집 모듈
Yahoo Finance API를 사용하여 NASDAQ, AMEX 종목 데이터를 가져옴
"""
import yfinance as yf
import pandas as pd
import numpy as np
import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

CACHE_DIR = Path(__file__).parent.parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)

# NASDAQ + AMEX 주요 종목 리스트 (시가총액 기준 상위 + 활발한 거래 종목)
# 실제 운영시에는 동적으로 가져올 수 있음
STOCK_LIST_URL = "https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main/all/all_tickers.txt"


def get_stock_list() -> list:
    """NASDAQ + AMEX 종목 리스트를 가져옴"""
    cache_file = CACHE_DIR / "stock_list.json"

    # 캐시가 1일 이내면 재사용
    if cache_file.exists():
        mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
        if datetime.now() - mtime < timedelta(days=1):
            with open(cache_file) as f:
                return json.load(f)

    try:
        import requests
        resp = requests.get(STOCK_LIST_URL, timeout=10)
        if resp.status_code == 200:
            tickers = [t.strip() for t in resp.text.strip().split('\n') if t.strip()]
            # 특수문자 포함 종목 제외 (우선주 등)
            tickers = [t for t in tickers if t.isalpha() and len(t) <= 5]
            with open(cache_file, 'w') as f:
                json.dump(tickers, f)
            return tickers
    except Exception as e:
        print(f"종목 리스트 다운로드 실패: {e}")

    # 폴백: 주요 종목 하드코딩
    return get_fallback_stocks()


def get_fallback_stocks() -> list:
    """폴백용 주요 NASDAQ/AMEX 종목"""
    return [
        # 대형 기술주
        "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AMD", "INTC", "AVGO",
        "ADBE", "CRM", "NFLX", "PYPL", "QCOM", "TXN", "AMAT", "MU", "LRCX", "KLAC",
        "SNPS", "CDNS", "MRVL", "ON", "SWKS", "MCHP", "ADI", "NXPI", "FTNT", "PANW",
        # 바이오/헬스케어
        "AMGN", "GILD", "BIIB", "REGN", "VRTX", "MRNA", "BNTX", "ILMN", "DXCM", "ISRG",
        "IDXX", "ALGN", "HOLX",
        # 소비재/서비스
        "COST", "PEP", "SBUX", "MDLZ", "MNST", "KDP", "DLTR", "ROST", "ORLY",
        "PCAR", "ODFL", "FAST", "CPRT", "CSGP",
        # 통신/미디어
        "CMCSA", "TMUS", "CHTR", "EA", "TTWO", "ZM", "ROKU", "SPOT",
        # 금융/핀테크
        "COIN", "SOFI", "HOOD", "AFRM", "UPST", "LC",
        # 에너지/소재
        "FSLR", "ENPH", "SEDG", "RUN",
        # AMEX 주요 종목
        "SPY", "QQQ", "IWM", "GLD", "SLV", "USO", "UVXY",
        # 중소형 성장주
        "PLTR", "NET", "DDOG", "SNOW", "CRWD", "ZS", "MDB", "SHOP", "TTD", "RBLX",
        "U", "PATH", "CFLT", "DOCN", "GTLB", "IONQ", "RGTI", "QUBT",
        # 추가 활발 거래 종목
        "RIVN", "LCID", "NIO", "XPEV", "LI", "MARA", "RIOT", "CLSK", "BITF",
        "SMCI", "ARM", "CRSP", "EDIT", "NTLA", "BEAM",
    ]


def validate_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """OHLCV 데이터 무결성 검증 및 정제

    검증 항목:
    - High >= Low 인지 확인
    - Open이 High/Low 범위 내에 있는지 확인
    - Close가 High/Low 범위 내에 있는지 확인
    - Volume이 음수가 아닌지 확인
    - NaN/Inf 값 제거

    무효한 행은 제거하고 유효한 데이터만 반환
    """
    if df.empty:
        return df

    required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
    if not all(col in df.columns for col in required_cols):
        return pd.DataFrame()

    # NaN/Inf 값이 있는 행 제거
    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.dropna(subset=required_cols)

    if df.empty:
        return df

    # High >= Low
    valid_hl = df['High'] >= df['Low']

    # Open이 High/Low 범위 내
    valid_open = (df['Open'] >= df['Low']) & (df['Open'] <= df['High'])

    # Close가 High/Low 범위 내
    valid_close = (df['Close'] >= df['Low']) & (df['Close'] <= df['High'])

    # Volume >= 0
    valid_volume = df['Volume'] >= 0

    valid_mask = valid_hl & valid_open & valid_close & valid_volume
    invalid_count = (~valid_mask).sum()

    if invalid_count > 0:
        print(f"  OHLCV 검증: {invalid_count}개 무효 행 제거됨")

    return df[valid_mask].copy()


def fetch_stock_data(ticker: str, period: str = "6mo") -> pd.DataFrame:
    """개별 종목 데이터 가져오기"""
    cache_file = CACHE_DIR / f"{ticker}_{period}.csv"

    # 캐시가 4시간 이내면 재사용 (장중에는 더 자주 갱신 가능)
    if cache_file.exists():
        mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
        if datetime.now() - mtime < timedelta(hours=4):
            try:
                df = pd.read_csv(cache_file, index_col=0, parse_dates=True)
                return validate_ohlcv(df)
            except Exception:
                pass

    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period)
        if df.empty:
            return pd.DataFrame()

        df.index = pd.to_datetime(df.index)
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
        df = validate_ohlcv(df)
        df.to_csv(cache_file)
        return df
    except Exception as e:
        print(f"{ticker} 데이터 수집 실패: {e}")
        return pd.DataFrame()


def fetch_stock_info(ticker: str) -> dict:
    """종목 기본 정보 (펀더멘털 데이터 포함)"""
    cache_file = CACHE_DIR / f"{ticker}_info.json"

    if cache_file.exists():
        mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
        if datetime.now() - mtime < timedelta(hours=12):
            try:
                with open(cache_file) as f:
                    return json.load(f)
            except Exception:
                pass

    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        # 필요한 필드만 추출
        fields = [
            'shortName', 'sector', 'industry', 'marketCap', 'enterpriseValue',
            'trailingPE', 'forwardPE', 'pegRatio', 'priceToBook', 'priceToSalesTrailing12Months',
            'revenueGrowth', 'earningsGrowth', 'earningsQuarterlyGrowth',
            'profitMargins', 'operatingMargins', 'returnOnEquity', 'returnOnAssets',
            'debtToEquity', 'currentRatio', 'quickRatio',
            'totalRevenue', 'totalDebt', 'totalCash',
            'fiftyTwoWeekHigh', 'fiftyTwoWeekLow', 'fiftyDayAverage', 'twoHundredDayAverage',
            'averageVolume', 'averageVolume10days',
            'beta', 'dividendYield', 'targetMeanPrice', 'recommendationMean',
            'exchange', 'quoteType',
            'earningsTimestamp', 'earningsTimestampStart', 'earningsTimestampEnd', 'earningsDate',
        ]
        filtered = {}
        for f in fields:
            val = info.get(f)
            if val is not None:
                if isinstance(val, (int, float)):
                    if np.isnan(val) or np.isinf(val):
                        continue
                filtered[f] = val

        with open(cache_file, 'w') as f:
            json.dump(filtered, f)
        return filtered
    except Exception as e:
        print(f"{ticker} 정보 수집 실패: {e}")
        return {}


def batch_fetch(tickers: list, period: str = "6mo", delay: float = 0.1) -> dict:
    """여러 종목 배치 수집"""
    results = {}
    total = len(tickers)
    for i, ticker in enumerate(tickers):
        if (i + 1) % 50 == 0:
            print(f"  데이터 수집 중... {i+1}/{total}")
        df = fetch_stock_data(ticker, period)
        if not df.empty and len(df) >= 20:  # 최소 20일 데이터 필요
            results[ticker] = df
        time.sleep(delay)  # Rate limit 방지
    return results


def get_usd_krw_rate() -> float:
    """USD/KRW 환율 가져오기 (캐시 1시간)"""
    cache_file = CACHE_DIR / "usd_krw.json"

    if cache_file.exists():
        mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
        if datetime.now() - mtime < timedelta(hours=1):
            try:
                with open(cache_file) as f:
                    data = json.load(f)
                    return data.get('rate', 1350)
            except Exception:
                pass

    try:
        ticker = yf.Ticker("KRW=X")
        hist = ticker.history(period="1d")
        if not hist.empty:
            rate = round(hist['Close'].iloc[-1], 2)
            with open(cache_file, 'w') as f:
                json.dump({'rate': rate, 'updated': datetime.now().isoformat()}, f)
            return rate
    except Exception as e:
        print(f"환율 조회 실패: {e}")

    return 1350  # 폴백값


def prefilter_stocks(tickers: list, min_price: float = 3.0, min_volume: int = 100000) -> list:
    """초기 필터링: 너무 싼 주식, 거래량 낮은 주식 제외"""
    filtered = []
    for ticker in tickers:
        try:
            df = fetch_stock_data(ticker, period="5d")
            if df.empty or len(df) < 1:
                continue
            last = df.iloc[-1]
            avg_vol = df['Volume'].mean()
            if last['Close'] >= min_price and avg_vol >= min_volume:
                filtered.append(ticker)
        except Exception:
            continue
    return filtered


def scan_daily_gainers(tickers: list, top_n: int = 30) -> list:
    """당일 상승률 상위 종목 스크리닝"""
    gainers = []
    for ticker in tickers:
        try:
            df = fetch_stock_data(ticker, period="5d")
            if df.empty or len(df) < 2:
                continue
            last = df.iloc[-1]
            prev = df.iloc[-2]
            change_pct = (last['Close'] - prev['Close']) / prev['Close'] * 100
            avg_vol = df['Volume'].mean()
            if avg_vol >= 50000 and last['Close'] >= 3.0:
                gainers.append((ticker, change_pct))
        except Exception:
            continue

    gainers.sort(key=lambda x: x[1], reverse=True)
    return [t for t, _ in gainers[:top_n]]


def scan_volume_surge(tickers: list, top_n: int = 30) -> list:
    """거래량 급증 종목 스크리닝"""
    surges = []
    for ticker in tickers:
        try:
            df = fetch_stock_data(ticker, period="1mo")
            if df.empty or len(df) < 10:
                continue
            last = df.iloc[-1]
            avg_vol_20 = df['Volume'].tail(20).mean()
            if avg_vol_20 == 0:
                continue
            vol_ratio = last['Volume'] / avg_vol_20
            if vol_ratio >= 1.5 and last['Close'] >= 3.0 and avg_vol_20 >= 50000:
                surges.append((ticker, vol_ratio))
        except Exception:
            continue

    surges.sort(key=lambda x: x[1], reverse=True)
    return [t for t, _ in surges[:top_n]]
