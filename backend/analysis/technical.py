"""
기술적 분석 모듈
RSI, MACD, 볼린저밴드, 이동평균선, 스토캐스틱, ADX, 다이버전스, 일목균형표 등
ta 라이브러리 사용
"""
import pandas as pd
import numpy as np
import ta


def compute_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """모든 기술적 지표를 계산하여 DataFrame에 추가"""
    df = df.copy()
    close = df['Close']
    high = df['High']
    low = df['Low']
    volume = df['Volume']

    # === 이동평균선 ===
    df['SMA_5'] = ta.trend.sma_indicator(close, window=5)
    df['SMA_10'] = ta.trend.sma_indicator(close, window=10)
    df['SMA_20'] = ta.trend.sma_indicator(close, window=20)
    df['SMA_50'] = ta.trend.sma_indicator(close, window=50)
    df['SMA_200'] = ta.trend.sma_indicator(close, window=200)
    df['EMA_9'] = ta.trend.ema_indicator(close, window=9)
    df['EMA_21'] = ta.trend.ema_indicator(close, window=21)
    df['EMA_50'] = ta.trend.ema_indicator(close, window=50)

    # === RSI ===
    df['RSI'] = ta.momentum.rsi(close, window=14)
    df['RSI_6'] = ta.momentum.rsi(close, window=6)

    # === MACD ===
    macd_obj = ta.trend.MACD(close, window_slow=26, window_fast=12, window_sign=9)
    df['MACD'] = macd_obj.macd()
    df['MACD_Signal'] = macd_obj.macd_signal()
    df['MACD_Hist'] = macd_obj.macd_diff()

    # === 볼린저 밴드 ===
    bb = ta.volatility.BollingerBands(close, window=20, window_dev=2)
    df['BB_Upper'] = bb.bollinger_hband()
    df['BB_Lower'] = bb.bollinger_lband()
    df['BB_Mid'] = bb.bollinger_mavg()
    df['BB_Width'] = bb.bollinger_wband()

    # === 스토캐스틱 ===
    stoch = ta.momentum.StochasticOscillator(high, low, close, window=14, smooth_window=3)
    df['Stoch_K'] = stoch.stoch()
    df['Stoch_D'] = stoch.stoch_signal()

    # === ADX ===
    adx_obj = ta.trend.ADXIndicator(high, low, close, window=14)
    df['ADX'] = adx_obj.adx()
    df['DMP'] = adx_obj.adx_pos()
    df['DMN'] = adx_obj.adx_neg()

    # === ATR ===
    df['ATR'] = ta.volatility.average_true_range(high, low, close, window=14)

    # === OBV ===
    df['OBV'] = ta.volume.on_balance_volume(close, volume)

    # === CCI ===
    df['CCI'] = ta.trend.cci(high, low, close, window=20)

    # === Williams %R ===
    df['WILLR'] = ta.momentum.williams_r(high, low, close, lbp=14)

    # === MFI ===
    df['MFI'] = ta.volume.money_flow_index(high, low, close, volume, window=14)

    # === 일목균형표 ===
    ichi = ta.trend.IchimokuIndicator(high, low, window1=9, window2=26, window3=52)
    df['Ichimoku_Tenkan'] = ichi.ichimoku_conversion_line()
    df['Ichimoku_Kijun'] = ichi.ichimoku_base_line()
    df['Ichimoku_SpanA'] = ichi.ichimoku_a()
    df['Ichimoku_SpanB'] = ichi.ichimoku_b()

    return df


def analyze_divergence(df: pd.DataFrame) -> tuple[int, list[str]]:
    """RSI 다이버전스 분석 (만점 15)

    가격 추세와 RSI 추세를 비교하여 다이버전스를 감지한다.
    - 강세 다이버전스: 가격은 lower low, RSI는 higher low -> 반등 신호
    - 약세 다이버전스: 가격은 higher high, RSI는 lower high -> 하락 신호
    """
    score = 0
    signals = []

    if len(df) < 30:
        return score, signals

    # 최근 30봉 기준으로 로컬 저점/고점 찾기
    lookback = min(60, len(df))
    recent = df.tail(lookback)
    close_vals = recent['Close'].values
    rsi_vals = recent['RSI'].values

    if np.any(np.isnan(rsi_vals)):
        # NaN이 있으면 유효한 구간만 사용
        valid_mask = ~np.isnan(rsi_vals)
        if valid_mask.sum() < 20:
            return score, signals
        # 마지막 유효 구간 사용
        first_valid = np.argmax(valid_mask)
        close_vals = close_vals[first_valid:]
        rsi_vals = rsi_vals[first_valid:]

    if len(close_vals) < 20:
        return score, signals

    # 로컬 저점 찾기 (5봉 기준)
    local_lows = []
    for i in range(5, len(close_vals) - 5):
        if close_vals[i] == min(close_vals[i-5:i+6]):
            local_lows.append(i)

    # 로컬 고점 찾기 (5봉 기준)
    local_highs = []
    for i in range(5, len(close_vals) - 5):
        if close_vals[i] == max(close_vals[i-5:i+6]):
            local_highs.append(i)

    # 강세 다이버전스: 가격 lower low + RSI higher low
    if len(local_lows) >= 2:
        l1, l2 = local_lows[-2], local_lows[-1]
        price_lower_low = close_vals[l2] < close_vals[l1]
        rsi_higher_low = rsi_vals[l2] > rsi_vals[l1]
        if price_lower_low and rsi_higher_low:
            score += 15
            signals.append("강세 다이버전스 (가격↓ RSI↑, 반등 신호)")

    # 약세 다이버전스: 가격 higher high + RSI lower high
    if len(local_highs) >= 2:
        h1, h2 = local_highs[-2], local_highs[-1]
        price_higher_high = close_vals[h2] > close_vals[h1]
        rsi_lower_high = rsi_vals[h2] < rsi_vals[h1]
        if price_higher_high and rsi_lower_high:
            score -= 10
            signals.append("약세 다이버전스 (가격↑ RSI↓, 하락 주의)")

    return score, signals


def analyze_ichimoku(df: pd.DataFrame) -> tuple[int, list[str]]:
    """일목균형표 분석 (만점 10)

    - 가격이 구름 위에 있으면 상승 추세 (+5)
    - 전환선이 기준선 위로 교차하면 매수 신호 (+5)
    - 가격이 구름 아래면 하락 추세 감점
    """
    score = 0
    signals = []

    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else last
    close = last['Close']

    tenkan = last.get('Ichimoku_Tenkan')
    kijun = last.get('Ichimoku_Kijun')
    span_a = last.get('Ichimoku_SpanA')
    span_b = last.get('Ichimoku_SpanB')

    prev_tenkan = prev.get('Ichimoku_Tenkan')
    prev_kijun = prev.get('Ichimoku_Kijun')

    if not all(pd.notna(v) for v in [tenkan, kijun, span_a, span_b]):
        return score, signals

    cloud_top = max(span_a, span_b)
    cloud_bottom = min(span_a, span_b)

    # 가격 vs 구름 위치
    if close > cloud_top:
        score += 5
        signals.append("일목: 가격이 구름 위 (상승 추세)")
    elif close < cloud_bottom:
        score -= 5
        signals.append("일목: 가격이 구름 아래 (하락 추세)")
    else:
        signals.append("일목: 가격이 구름 내부 (방향 불명확)")

    # 전환선/기준선 크로스
    if pd.notna(prev_tenkan) and pd.notna(prev_kijun):
        if prev_tenkan <= prev_kijun and tenkan > kijun:
            score += 5
            signals.append("일목: 전환선 상향 교차 (매수 신호)")
        elif prev_tenkan >= prev_kijun and tenkan < kijun:
            score -= 3
            signals.append("일목: 전환선 하향 교차 (매도 신호)")

    return score, signals


def analyze_technical(df: pd.DataFrame) -> dict:
    """기술적 지표 기반 매수/매도 시그널 분석"""
    if df.empty or len(df) < 50:
        return {'score': 0, 'signals': [], 'details': {}}

    df = compute_all_indicators(df)
    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else last

    signals = []
    score = 0
    details = {}

    # === RSI 분석 (만점 15) ===
    rsi = last.get('RSI', 50)
    if pd.notna(rsi):
        details['RSI'] = round(rsi, 2)
        if rsi < 30:
            score += 15
            signals.append("RSI 과매도 구간 (강한 매수)")
        elif rsi < 40:
            score += 10
            signals.append("RSI 매수 구간")
        elif rsi > 70:
            score -= 10
            signals.append("RSI 과매수 (주의)")
        elif 40 <= rsi <= 60:
            score += 5
            signals.append("RSI 중립")

    # === MACD 분석 (만점 15) ===
    macd_val = last.get('MACD')
    macd_signal = last.get('MACD_Signal')
    macd_hist = last.get('MACD_Hist')
    prev_hist = prev.get('MACD_Hist')

    if pd.notna(macd_val) and pd.notna(macd_signal):
        details['MACD'] = round(macd_val, 4)
        details['MACD_Signal'] = round(macd_signal, 4)

        if pd.notna(macd_hist) and pd.notna(prev_hist):
            if prev_hist < 0 and macd_hist > 0:
                score += 15
                signals.append("MACD 골든크로스 (강한 매수)")
            elif macd_hist > 0 and macd_hist > prev_hist:
                score += 10
                signals.append("MACD 상승 모멘텀")
            elif prev_hist > 0 and macd_hist < 0:
                score -= 10
                signals.append("MACD 데드크로스 (매도)")

    # === 이동평균선 분석 (만점 15) ===
    close = last['Close']
    sma20 = last.get('SMA_20')
    sma50 = last.get('SMA_50')
    sma200 = last.get('SMA_200')
    ema9 = last.get('EMA_9')
    ema21 = last.get('EMA_21')

    ma_score = 0
    if pd.notna(sma20) and close > sma20:
        ma_score += 3
    if pd.notna(sma50) and close > sma50:
        ma_score += 3
    if pd.notna(sma200) and close > sma200:
        ma_score += 3
    if pd.notna(ema9) and pd.notna(ema21) and ema9 > ema21:
        ma_score += 3
        signals.append("EMA 9 > EMA 21 (단기 상승)")
    if pd.notna(sma50) and pd.notna(sma200) and sma50 > sma200:
        ma_score += 3
        signals.append("골든크로스 (SMA50 > SMA200)")

    score += min(ma_score, 15)
    details['MA_Score'] = ma_score

    # === 볼린저 밴드 분석 (만점 10) ===
    bb_lower = last.get('BB_Lower')
    bb_upper = last.get('BB_Upper')
    bb_mid = last.get('BB_Mid')

    if pd.notna(bb_lower) and pd.notna(bb_upper) and bb_upper > bb_lower:
        bb_width = last.get('BB_Width', 0)
        details['BB_Width'] = round(bb_width, 4) if pd.notna(bb_width) else 0

        # 하단 밴드로부터의 거리를 밴드 폭 대비 비율로 계산
        bb_range = bb_upper - bb_lower
        if bb_range <= 0:
            bb_range = 1  # division by zero 방어
        pct_from_lower = (close - bb_lower) / bb_range  # 0.0 = 하단, 1.0 = 상단

        if close <= bb_lower:
            score += 10
            signals.append("볼린저 하단 터치 (반등 기대)")
        elif pct_from_lower <= 0.05:
            # 하단 밴드에서 밴드 폭의 5% 이내
            score += 7
            signals.append("볼린저 하단 근접")
        elif close >= bb_upper:
            score -= 5
            signals.append("볼린저 상단 (과열 주의)")

    # === 스토캐스틱 분석 (만점 10) ===
    stoch_k = last.get('Stoch_K')
    stoch_d = last.get('Stoch_D')
    prev_k = prev.get('Stoch_K')
    prev_d = prev.get('Stoch_D')

    if pd.notna(stoch_k) and pd.notna(stoch_d):
        details['Stoch_K'] = round(stoch_k, 2)
        details['Stoch_D'] = round(stoch_d, 2)

        if stoch_k < 20 and stoch_d < 20:
            score += 8
            signals.append("스토캐스틱 과매도")
            # 골든크로스: 이전에 K <= D 였다가 현재 K > D 로 교차
            if pd.notna(prev_k) and pd.notna(prev_d):
                if prev_k <= prev_d and stoch_k > stoch_d:
                    score += 2
                    signals.append("스토캐스틱 골든크로스")
        elif stoch_k > 80:
            score -= 5
            signals.append("스토캐스틱 과매수")

    # === ADX 분석 (만점 10) ===
    adx_val = last.get('ADX')
    dmp = last.get('DMP')
    dmn = last.get('DMN')

    if pd.notna(adx_val):
        details['ADX'] = round(adx_val, 2)
        if adx_val > 25 and pd.notna(dmp) and pd.notna(dmn) and dmp > dmn:
            score += 10
            signals.append(f"강한 상승 추세 (ADX={adx_val:.0f})")
        elif adx_val > 25 and pd.notna(dmp) and pd.notna(dmn) and dmn > dmp:
            score -= 5
            signals.append("강한 하락 추세")
        elif adx_val < 20:
            score += 3
            signals.append("추세 약함 (횡보)")

    # === CCI 분석 (만점 5) ===
    cci = last.get('CCI')
    if pd.notna(cci):
        details['CCI'] = round(cci, 2)
        if cci < -100:
            score += 5
            signals.append("CCI 과매도")
        elif cci > 100:
            score -= 3

    # === MFI 분석 (만점 5) ===
    mfi = last.get('MFI')
    if pd.notna(mfi):
        details['MFI'] = round(mfi, 2)
        if mfi < 20:
            score += 5
            signals.append("MFI 과매도 (자금 유입 기대)")
        elif mfi > 80:
            score -= 3
            signals.append("MFI 과매수")

    # === 캔들 패턴 분석 (만점 5) ===
    candle_score = analyze_candle_patterns(df)
    score += candle_score
    if candle_score > 0:
        signals.append(f"긍정적 캔들 패턴 (+{candle_score})")

    # === 지지/저항 분석 (만점 10) ===
    sr_score = analyze_support_resistance(df)
    score += sr_score
    if sr_score > 0:
        signals.append(f"지지선 근접 (+{sr_score})")

    # === 다이버전스 분석 (만점 15) ===
    div_score, div_signals = analyze_divergence(df)
    score += div_score
    signals.extend(div_signals)

    # === 일목균형표 분석 (만점 10) ===
    ichi_score, ichi_signals = analyze_ichimoku(df)
    score += ichi_score
    signals.extend(ichi_signals)

    # 정규화 (0-100) - 각 구성요소의 합이 이미 ~100 만점이므로 단순 클램핑
    normalized_score = max(0, min(100, score))

    return {
        'score': round(normalized_score, 2),
        'signals': signals,
        'details': details,
        'raw_score': score,
    }


def analyze_candle_patterns(df: pd.DataFrame) -> int:
    """최근 캔들 패턴 분석"""
    if len(df) < 3:
        return 0

    score = 0
    last = df.iloc[-1]
    prev = df.iloc[-2]
    prev2 = df.iloc[-3]

    body = last['Close'] - last['Open']
    shadow_lower = min(last['Open'], last['Close']) - last['Low']
    shadow_upper = last['High'] - max(last['Open'], last['Close'])
    body_size = abs(body)

    # 해머
    if body_size > 0 and shadow_lower > body_size * 2 and shadow_upper < body_size * 0.5:
        if prev['Close'] < prev['Open']:
            score += 3

    # 상승 장악형
    if (prev['Close'] < prev['Open'] and
        last['Close'] > last['Open'] and
        last['Open'] <= prev['Close'] and
        last['Close'] >= prev['Open']):
        score += 3

    # 모닝스타
    if (prev2['Close'] < prev2['Open'] and
        abs(prev['Close'] - prev['Open']) < abs(prev2['Close'] - prev2['Open']) * 0.3 and
        last['Close'] > last['Open'] and
        last['Close'] > (prev2['Open'] + prev2['Close']) / 2):
        score += 4

    # 연속 양봉
    if (last['Close'] > last['Open'] and
        prev['Close'] > prev['Open'] and
        prev2['Close'] > prev2['Open']):
        score += 2

    return min(score, 5)


def analyze_support_resistance(df: pd.DataFrame) -> int:
    """지지/저항선 분석"""
    if len(df) < 20:
        return 0

    close = df.iloc[-1]['Close']
    recent = df.tail(60)

    lows = recent['Low'].rolling(5).min().dropna()
    support_levels = []
    for i in range(0, len(lows) - 5, 5):
        support_levels.append(lows.iloc[i])

    score = 0
    for support in support_levels:
        if 0 <= (close - support) / support <= 0.02:
            score += 3
            break

    low_52 = recent['Low'].min()
    if close < low_52 * 1.05:
        score += 3

    return min(score, 10)
