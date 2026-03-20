"""
모멘텀 분석 모듈
가격 모멘텀, 거래량 분석, 상대 강도 등
"""
import pandas as pd
import numpy as np

try:
    import ta
    HAS_TA = True
except ImportError:
    HAS_TA = False


def analyze_momentum(df: pd.DataFrame) -> dict:
    """모멘텀 기반 종합 분석"""
    if df.empty or len(df) < 20:
        return {'score': 0, 'signals': [], 'details': {}}

    signals = []
    score = 0
    details = {}
    last = df.iloc[-1]

    # === 가격 모멘텀 (만점 20) ===
    price_mom = analyze_price_momentum(df)
    score += price_mom['score']
    signals.extend(price_mom['signals'])
    details.update(price_mom['details'])

    # === 거래량 분석 (만점 25) ===
    vol_analysis = analyze_volume(df)
    score += vol_analysis['score']
    signals.extend(vol_analysis['signals'])
    details.update(vol_analysis['details'])

    # === 가격 돌파 패턴 (만점 20) ===
    breakout = analyze_breakout(df)
    score += breakout['score']
    signals.extend(breakout['signals'])

    # === 추세 가속도 (만점 15) ===
    accel = analyze_acceleration(df)
    score += accel['score']
    signals.extend(accel['signals'])

    # === 갭 분석 (만점 10) ===
    gap = analyze_gaps(df)
    score += gap['score']
    signals.extend(gap['signals'])

    # === 변동성 수축 (만점 10) ===
    squeeze = analyze_volatility_squeeze(df)
    score += squeeze['score']
    signals.extend(squeeze['signals'])

    # === Accumulation/Distribution 분석 (만점 10) ===
    ad_analysis = analyze_accumulation_distribution(df)
    score += ad_analysis['score']
    signals.extend(ad_analysis['signals'])
    details.update(ad_analysis['details'])

    # === 다이버전스 분석 (만점 10) ===
    div_analysis = analyze_divergence(df)
    score += div_analysis['score']
    signals.extend(div_analysis['signals'])
    details.update(div_analysis['details'])

    # 정규화 (0-100)
    normalized_score = max(0, min(100, score))

    return {
        'score': round(normalized_score, 2),
        'signals': signals,
        'details': details,
    }


def analyze_price_momentum(df: pd.DataFrame) -> dict:
    """가격 모멘텀 분석"""
    score = 0
    signals = []
    details = {}
    last_close = df.iloc[-1]['Close']

    # 1일 수익률
    ret_1d = (last_close / df.iloc[-2]['Close'] - 1) * 100 if len(df) >= 2 else 0
    details['Return_1D'] = round(ret_1d, 2)

    # 5일 수익률
    ret_5d = (last_close / df.iloc[-6]['Close'] - 1) * 100 if len(df) >= 6 else 0
    details['Return_5D'] = round(ret_5d, 2)

    # 20일 수익률
    ret_20d = (last_close / df.iloc[-21]['Close'] - 1) * 100 if len(df) >= 21 else 0
    details['Return_20D'] = round(ret_20d, 2)

    # 단기 반등 (최근 하락 후 상승 전환)
    if ret_5d < -5 and ret_1d > 0:
        score += 8
        signals.append(f"단기 반등 시그널 (5일 {ret_5d:.1f}% → 오늘 +{ret_1d:.1f}%)")
    elif ret_1d > 3:
        score += 5
        signals.append(f"강한 일일 상승 (+{ret_1d:.1f}%)")

    # 중기 모멘텀
    if 0 < ret_20d < 15:
        score += 5
        signals.append("건전한 중기 상승 모멘텀")
    elif ret_20d < -10:
        score += 7  # 과매도 반등 기대
        signals.append(f"중기 과매도 ({ret_20d:.1f}%) - 반등 기대")

    # ROC (Rate of Change)
    roc_10 = (last_close / df.iloc[-11]['Close'] - 1) * 100 if len(df) >= 11 else 0
    details['ROC_10'] = round(roc_10, 2)

    return {'score': min(score, 20), 'signals': signals, 'details': details}


def _get_adaptive_volume_thresholds(df: pd.DataFrame) -> dict:
    """종목 자체 거래량 히스토리 기반으로 적응형 임계값 계산"""
    vol = df['Volume']
    if len(vol) < 60:
        # 데이터 부족 시 고정 임계값 사용
        avg_vol_20 = vol.tail(20).mean()
        return {
            'extreme': 3.0 * avg_vol_20,
            'high': 2.0 * avg_vol_20,
            'moderate': 1.5 * avg_vol_20,
            'avg_vol_20': avg_vol_20,
        }

    avg_vol_20 = vol.tail(20).mean()
    if avg_vol_20 == 0:
        return {
            'extreme': 0, 'high': 0, 'moderate': 0, 'avg_vol_20': 0,
        }

    # 일별 거래량 비율 계산 (각 날의 거래량 / 직전 20일 평균)
    rolling_avg = vol.rolling(20).mean()
    vol_ratios = (vol / rolling_avg).dropna()

    if len(vol_ratios) < 20:
        return {
            'extreme': 3.0 * avg_vol_20,
            'high': 2.0 * avg_vol_20,
            'moderate': 1.5 * avg_vol_20,
            'avg_vol_20': avg_vol_20,
        }

    # 퍼센타일 기반 임계값: 변동성 큰 종목은 높은 임계값, 안정적 종목은 낮은 임계값
    extreme_threshold = vol_ratios.quantile(0.95)   # 상위 5% → 극단적 급증
    high_threshold = vol_ratios.quantile(0.85)      # 상위 15% → 높은 급증
    moderate_threshold = vol_ratios.quantile(0.70)   # 상위 30% → 적당한 증가

    # 최소 임계값 보장
    extreme_threshold = max(extreme_threshold, 2.0)
    high_threshold = max(high_threshold, 1.5)
    moderate_threshold = max(moderate_threshold, 1.2)

    return {
        'extreme': extreme_threshold,
        'high': high_threshold,
        'moderate': moderate_threshold,
        'avg_vol_20': avg_vol_20,
    }


def analyze_volume(df: pd.DataFrame) -> dict:
    """거래량 분석"""
    score = 0
    signals = []
    details = {}

    last = df.iloc[-1]
    avg_vol_5 = df['Volume'].tail(5).mean()
    last_vol = last['Volume']

    # 적응형 임계값 계산
    thresholds = _get_adaptive_volume_thresholds(df)
    avg_vol_20 = thresholds['avg_vol_20']

    if avg_vol_20 == 0:
        return {'score': 0, 'signals': [], 'details': {}}

    vol_ratio = last_vol / avg_vol_20
    details['Volume_Ratio_20D'] = round(vol_ratio, 2)
    details['Avg_Volume_20D'] = int(avg_vol_20)
    details['Vol_Threshold_Extreme'] = round(thresholds['extreme'], 2)
    details['Vol_Threshold_High'] = round(thresholds['high'], 2)
    details['Vol_Threshold_Moderate'] = round(thresholds['moderate'], 2)

    # 거래량 급증 + 양봉 = 강한 매수 시그널 (적응형 임계값 사용)
    is_bullish = last['Close'] > last['Open']

    if vol_ratio > thresholds['extreme'] and is_bullish:
        score += 15
        signals.append(f"거래량 폭발 (평균 대비 {vol_ratio:.1f}배, 상위5% 초과) + 양봉")
    elif vol_ratio > thresholds['high'] and is_bullish:
        score += 12
        signals.append(f"거래량 급증 ({vol_ratio:.1f}배, 상위15% 초과) + 양봉")
    elif vol_ratio > thresholds['moderate'] and is_bullish:
        score += 8
        signals.append(f"거래량 증가 ({vol_ratio:.1f}배)")

    # 거래량 증가 추세
    if avg_vol_5 > avg_vol_20 * 1.3:
        score += 5
        signals.append("최근 5일 거래량 증가 추세")

    # OBV 트렌드 (On-Balance Volume) - 기울기 기반 분석
    obv = (np.sign(df['Close'].diff()) * df['Volume']).cumsum()
    obv_sma = obv.rolling(10).mean()

    if len(obv.dropna()) >= 10:
        # OBV 기울기 분석: 최근 10일간의 OBV 추세 방향
        obv_recent = obv.tail(10).values
        x = np.arange(len(obv_recent))
        obv_slope = np.polyfit(x, obv_recent, 1)[0]

        # 기울기를 OBV 평균값 대비 퍼센트로 정규화
        obv_mean = np.abs(obv_recent).mean()
        if obv_mean > 0:
            obv_slope_pct = (obv_slope / obv_mean) * 100
        else:
            obv_slope_pct = 0

        details['OBV_Slope_Pct'] = round(obv_slope_pct, 2)

        if obv_slope_pct > 5:
            score += 5
            signals.append(f"OBV 강한 상승 기울기 (매수세 강화, {obv_slope_pct:.1f}%)")
        elif obv_slope_pct > 1:
            score += 3
            signals.append("OBV 완만한 상승 추세 (매수세 우위)")
        elif obv_slope_pct < -5:
            score -= 3
            signals.append(f"OBV 하락 기울기 (매도세 강화, {obv_slope_pct:.1f}%)")
    else:
        # 데이터 부족 시 기존 SMA 비교 방식
        if len(obv_sma.dropna()) >= 1 and obv.iloc[-1] > obv_sma.iloc[-1]:
            score += 5
            signals.append("OBV 상승 추세 (매수세 우위)")

    return {'score': min(score, 25), 'signals': signals, 'details': details}


def analyze_divergence(df: pd.DataFrame) -> dict:
    """가격 vs OBV 다이버전스 분석"""
    score = 0
    signals = []
    details = {}

    if len(df) < 30:
        return {'score': 0, 'signals': [], 'details': {}}

    # OBV 계산
    obv = (np.sign(df['Close'].diff()) * df['Volume']).cumsum()

    close = df['Close']

    # 최근 구간을 두 구간으로 나눠 비교 (10일 전 구간 vs 최근 구간)
    # 구간1: -20 ~ -10, 구간2: -10 ~ 현재
    period1_close = close.iloc[-20:-10]
    period2_close = close.iloc[-10:]
    period1_obv = obv.iloc[-20:-10]
    period2_obv = obv.iloc[-10:]

    # 각 구간의 고점/저점
    price_high1 = period1_close.max()
    price_high2 = period2_close.max()
    price_low1 = period1_close.min()
    price_low2 = period2_close.min()

    obv_high1 = period1_obv.max()
    obv_high2 = period2_obv.max()
    obv_low1 = period1_obv.min()
    obv_low2 = period2_obv.min()

    divergence_type = 'none'

    # 베어리시 다이버전스: 가격 고점 상승 but OBV 고점 하락
    if price_high2 > price_high1 and obv_high2 < obv_high1:
        divergence_type = 'bearish'
        score -= 5
        signals.append("베어리시 다이버전스 (가격 신고점 but OBV 하락) - 상승 약화 경고")

    # 불리시 다이버전스: 가격 저점 하락 but OBV 저점 상승
    if price_low2 < price_low1 and obv_low2 > obv_low1:
        divergence_type = 'bullish'
        score += 10
        signals.append("불리시 다이버전스 (가격 신저점 but OBV 상승) - 반등 기대")

    details['Divergence'] = divergence_type

    return {'score': score, 'signals': signals, 'details': details}


def analyze_accumulation_distribution(df: pd.DataFrame) -> dict:
    """Accumulation/Distribution Line 분석"""
    score = 0
    signals = []
    details = {}

    if len(df) < 20:
        return {'score': 0, 'signals': [], 'details': {}}

    if HAS_TA:
        # ta 라이브러리 사용
        ad_line = ta.volume.AccDistIndexIndicator(
            high=df['High'], low=df['Low'],
            close=df['Close'], volume=df['Volume']
        ).acc_dist_index()
    else:
        # 수동 계산: AD = cumsum(CLV * Volume)
        # CLV (Close Location Value) = ((Close - Low) - (High - Close)) / (High - Low)
        high_low = df['High'] - df['Low']
        # 0으로 나누기 방지
        high_low = high_low.replace(0, np.nan)
        clv = ((df['Close'] - df['Low']) - (df['High'] - df['Close'])) / high_low
        clv = clv.fillna(0)
        ad_line = (clv * df['Volume']).cumsum()

    if ad_line.isna().all() or len(ad_line.dropna()) < 10:
        return {'score': 0, 'signals': [], 'details': {}}

    # AD Line 기울기 분석 (최근 10일)
    ad_recent = ad_line.tail(10).values
    x = np.arange(len(ad_recent))
    ad_slope = np.polyfit(x, ad_recent, 1)[0]

    # 기울기 정규화
    ad_mean = np.abs(ad_recent).mean()
    if ad_mean > 0:
        ad_slope_pct = (ad_slope / ad_mean) * 100
    else:
        ad_slope_pct = 0

    details['AD_Slope_Pct'] = round(ad_slope_pct, 2)

    # AD Line SMA 비교
    ad_sma = ad_line.rolling(20).mean()
    if len(ad_sma.dropna()) >= 1:
        ad_above_sma = ad_line.iloc[-1] > ad_sma.iloc[-1]
        details['AD_Above_SMA20'] = bool(ad_above_sma)
    else:
        ad_above_sma = None

    # 점수 부여
    if ad_slope_pct > 5:
        score += 7
        signals.append(f"A/D Line 강한 상승 (적극적 매집, {ad_slope_pct:.1f}%)")
    elif ad_slope_pct > 1:
        score += 4
        signals.append("A/D Line 완만한 상승 (매집 진행 중)")
    elif ad_slope_pct < -5:
        score -= 3
        signals.append(f"A/D Line 하락 (분배 진행 중, {ad_slope_pct:.1f}%)")

    # AD가 SMA 위에 있으면 추가 점수
    if ad_above_sma is True:
        score += 3
        signals.append("A/D Line이 20일 이평선 상회 (매집 우위)")

    return {'score': max(-3, min(score, 10)), 'signals': signals, 'details': details}


def analyze_breakout(df: pd.DataFrame) -> dict:
    """돌파 패턴 분석"""
    score = 0
    signals = []
    last = df.iloc[-1]
    close = last['Close']

    # 20일 고점 돌파
    high_20 = df['High'].tail(21).iloc[:-1].max()
    if close > high_20:
        score += 10
        signals.append(f"20일 신고가 돌파 ({close:.2f} > {high_20:.2f})")

    # 50일 고점 돌파
    if len(df) >= 51:
        high_50 = df['High'].tail(51).iloc[:-1].max()
        if close > high_50:
            score += 5
            signals.append("50일 신고가 돌파")

    # 저항선 돌파 (최근 고점 수평선)
    recent_highs = df['High'].tail(20)
    resistance = recent_highs.quantile(0.9)
    if close > resistance and df.iloc[-2]['Close'] <= resistance:
        score += 5
        signals.append("저항선 돌파")

    return {'score': min(score, 20), 'signals': signals}


def analyze_acceleration(df: pd.DataFrame) -> dict:
    """추세 가속도 분석"""
    score = 0
    signals = []

    if len(df) < 10:
        return {'score': 0, 'signals': []}

    closes = df['Close'].tail(10).values

    # 선형 회귀 기울기
    x = np.arange(len(closes))
    slope = np.polyfit(x, closes, 1)[0]
    slope_pct = (slope / closes[0]) * 100

    if slope_pct > 0.5:
        score += 8
        signals.append(f"상승 가속 (일평균 +{slope_pct:.2f}%)")
    elif slope_pct > 0.2:
        score += 5
        signals.append("완만한 상승 추세")

    # 가속도 (2차 회귀)
    if len(df) >= 20:
        closes_20 = df['Close'].tail(20).values
        x20 = np.arange(len(closes_20))
        coeffs = np.polyfit(x20, closes_20, 2)
        if coeffs[0] > 0 and coeffs[1] > 0:
            score += 7
            signals.append("추세 가속 중 (상승 곡선)")

    return {'score': min(score, 15), 'signals': signals}


def analyze_gaps(df: pd.DataFrame) -> dict:
    """갭 분석"""
    score = 0
    signals = []

    if len(df) < 2:
        return {'score': 0, 'signals': []}

    last = df.iloc[-1]
    prev = df.iloc[-2]

    # 갭 상승 (오늘 시가 > 어제 고가)
    gap_up = (last['Open'] - prev['High']) / prev['Close'] * 100
    if gap_up > 2:
        # 갭 상승 후 유지 (갭 채우지 않음)
        if last['Low'] > prev['High']:
            score += 10
            signals.append(f"갭 상승 유지 (+{gap_up:.1f}%)")
        else:
            score += 5
            signals.append(f"갭 상승 ({gap_up:.1f}%)")

    return {'score': min(score, 10), 'signals': signals}


def analyze_volatility_squeeze(df: pd.DataFrame) -> dict:
    """변동성 수축 분석 (스퀴즈 → 확장 예측)"""
    score = 0
    signals = []

    if len(df) < 30:
        return {'score': 0, 'signals': []}

    # 볼린저 밴드 폭
    close = df['Close']
    sma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()

    bb_width = (2 * std20 / sma20).tail(10)
    if bb_width.empty or bb_width.isna().all():
        return {'score': 0, 'signals': []}

    current_width = bb_width.iloc[-1]
    avg_width = bb_width.mean()

    # ATR 수축
    tr = pd.concat([
        df['High'] - df['Low'],
        (df['High'] - df['Close'].shift(1)).abs(),
        (df['Low'] - df['Close'].shift(1)).abs()
    ], axis=1).max(axis=1)

    atr_short = tr.tail(5).mean()
    atr_long = tr.tail(20).mean()

    if pd.notna(current_width) and pd.notna(avg_width) and avg_width > 0:
        if current_width < avg_width * 0.7:
            score += 7
            signals.append("변동성 수축 (스퀴즈) - 돌파 임박 가능")

    if atr_long > 0 and atr_short < atr_long * 0.7:
        score += 3
        signals.append("ATR 수축 중")

    return {'score': min(score, 10), 'signals': signals}
