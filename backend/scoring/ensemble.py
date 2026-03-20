"""
앙상블 스코어링 모듈
기술적 분석 + 모멘텀 + 펀더멘털 + ML을 종합하여 최종 점수 산출
매수가, 목표가, 손절가, 보유기간 추천 포함
"""
import pandas as pd
import numpy as np
from datetime import datetime
from analysis.market_events import analyze_market_events


# 각 분석 모듈 기본 가중치 (합계 = 1.0)
DEFAULT_WEIGHTS = {
    'technical': 0.25,    # 기술적 분석
    'momentum': 0.25,     # 모멘텀 분석
    'fundamental': 0.20,  # 펀더멘털 분석
    'ml': 0.30,           # 머신러닝 예측
}


def _get_dynamic_weights(technical_result: dict) -> dict:
    """
    ADX 기반 동적 가중치 조정
    - ADX > 25 (추세장): 기술적 분석 가중치 상향, 펀더멘털 하향
    - ADX < 20 (횡보장): 펀더멘털 가중치 상향, 기술적 하향
    """
    weights = DEFAULT_WEIGHTS.copy()
    adx = technical_result.get('details', {}).get('ADX', None)

    if adx is not None and isinstance(adx, (int, float)):
        if adx > 25:
            # 추세장: 기술적 +0.05, 펀더멘털 -0.05
            weights['technical'] = 0.30
            weights['fundamental'] = 0.15
        elif adx < 20:
            # 횡보장: 펀더멘털 +0.05, 기술적 -0.05
            weights['technical'] = 0.20
            weights['fundamental'] = 0.25

    return weights


def calculate_ensemble_score(
    technical_result: dict,
    momentum_result: dict,
    fundamental_result: dict,
    ml_result: dict,
    info: dict = None,
    df: pd.DataFrame = None,
) -> dict:
    scores = {
        'technical': technical_result.get('score', 0),
        'momentum': momentum_result.get('score', 0),
        'fundamental': fundamental_result.get('score', 0),
        'ml': ml_result.get('score', 0),
    }

    # ADX 기반 동적 가중치
    weights = _get_dynamic_weights(technical_result)

    # 가중 평균 점수
    final_score = sum(scores[k] * weights[k] for k in weights)

    # 보너스/페널티 (모순 수정: 20 미만이 있으면 페널티만 적용)
    bonus = 0
    if any(s < 20 for s in scores.values()):
        # 극단적 저점수가 있으면 페널티만, 다른 보너스 스킵
        bonus = -5
    else:
        # 모든 점수가 20 이상일 때만 보너스 적용
        high_scores = sum(1 for s in scores.values() if s >= 60)
        if high_scores >= 3:
            bonus += 10
        elif high_scores >= 2:
            bonus += 5
        if all(s >= 50 for s in scores.values()):
            bonus += 5

    # === 시장 이벤트 반영 ===
    market_events = analyze_market_events(info)
    bonus += market_events['score_adjustment']
    event_signals = market_events.get('signals', [])

    final_score = max(0, min(100, final_score + bonus))

    grade = calculate_grade(final_score)
    prob_1d = estimate_probability(final_score, ml_result, '1d')
    prob_5d = estimate_probability(final_score, ml_result, '5d')

    all_signals = []
    for result in [technical_result, momentum_result, fundamental_result, ml_result]:
        all_signals.extend(result.get('signals', []))
    all_signals.extend(event_signals)
    top_signals = all_signals[:8]

    risk_level = assess_risk(scores, df, info)
    recommendation = generate_recommendation(grade, prob_1d, prob_5d, risk_level)

    details = {}
    for result in [technical_result, momentum_result, fundamental_result, ml_result]:
        details.update(result.get('details', {}))

    stock_info = {}
    if info:
        stock_info = {
            'name': info.get('shortName', ''),
            'sector': info.get('sector', ''),
            'industry': info.get('industry', ''),
            'market_cap': info.get('marketCap', 0),
        }

    # 현재가 정보
    price_info = {}
    if df is not None and not df.empty:
        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) >= 2 else last
        change = (last['Close'] - prev['Close']) / prev['Close'] * 100
        price_info = {
            'current_price': round(last['Close'], 2),
            'change_pct': round(change, 2),
            'volume': int(last['Volume']),
        }

    # === 매매 전략 계산 ===
    trade_plan = calculate_trade_plan(df, info, final_score, prob_1d, prob_5d, risk_level)

    return {
        'final_score': round(final_score, 1),
        'grade': grade,
        'recommendation': recommendation,
        'rise_probability_1d': round(prob_1d, 1),
        'rise_probability_5d': round(prob_5d, 1),
        'scores': scores,
        'weights_used': weights,
        'top_signals': top_signals,
        'risk_level': risk_level,
        'stock_info': stock_info,
        'price_info': price_info,
        'trade_plan': trade_plan,
        'market_events': market_events.get('events', {}),
        'details': details,
        'analyzed_at': datetime.now().isoformat(),
    }


def calculate_trade_plan(
    df: pd.DataFrame,
    info: dict,
    final_score: float,
    prob_1d: float,
    prob_5d: float,
    risk_level: str,
) -> dict:
    """
    매매 전략 계산
    - 매수가 (진입 가격)
    - 목표가 (몇 %에서 매도)
    - 손절가 (손실 제한)
    - 보유 기간 추천
    - 예상 수익률
    """
    if df is None or df.empty or len(df) < 20:
        return {}

    last = df.iloc[-1]
    current_price = last['Close']

    # === 변동성 계산 (ATR 기반) ===
    tr = pd.concat([
        df['High'] - df['Low'],
        (df['High'] - df['Close'].shift(1)).abs(),
        (df['Low'] - df['Close'].shift(1)).abs()
    ], axis=1).max(axis=1)
    atr_14 = tr.tail(14).mean()
    atr_pct = (atr_14 / current_price) * 100  # ATR을 %로

    # 시장 이벤트 변동성 반영
    market_events = analyze_market_events(info)
    vol_multiplier = market_events.get('volatility_multiplier', 1.0)
    atr_pct *= vol_multiplier

    # 최근 20일 변동성
    daily_vol = df['Close'].pct_change().tail(20).std() * 100

    # === 지지선/저항선 계산 (None/NaN 방어) ===
    recent = df.tail(60)
    support_raw = recent['Low'].rolling(5).min().dropna().tail(10).median()
    resistance_raw = recent['High'].rolling(5).max().dropna().tail(10).median()

    # None/NaN 체크: 유효하지 않으면 현재가 기반 대체값 사용
    try:
        support = float(support_raw) if support_raw is not None and not pd.isna(support_raw) else current_price * 0.95
    except (TypeError, ValueError):
        support = current_price * 0.95

    try:
        resistance = float(resistance_raw) if resistance_raw is not None and not pd.isna(resistance_raw) else current_price * 1.05
    except (TypeError, ValueError):
        resistance = current_price * 1.05

    # 52주 고/저
    high_52w = df['High'].max()
    low_52w = df['Low'].min()

    # === 매수가 (진입 가격) ===
    # 현재가 기준, 약간의 눌림목 매수 고려
    entry_price = round(current_price, 2)
    # 지정가 매수 추천 (현재가 대비 약간 아래)
    limit_price = round(current_price * (1 - atr_pct * 0.003), 2)

    # === 목표가 계산 ===
    # 등급과 확률에 따라 목표 수익률 조정
    if final_score >= 85:  # S등급
        target_pct_1d = max(2.0, min(atr_pct * 0.8, 8.0))
        target_pct_5d = max(4.0, min(atr_pct * 2.0, 15.0))
    elif final_score >= 70:  # A등급
        target_pct_1d = max(1.5, min(atr_pct * 0.6, 5.0))
        target_pct_5d = max(3.0, min(atr_pct * 1.5, 12.0))
    elif final_score >= 55:  # B등급
        target_pct_1d = max(1.0, min(atr_pct * 0.5, 4.0))
        target_pct_5d = max(2.0, min(atr_pct * 1.2, 8.0))
    else:  # C등급 이하
        target_pct_1d = max(0.8, min(atr_pct * 0.4, 3.0))
        target_pct_5d = max(1.5, min(atr_pct * 1.0, 6.0))

    # 저항선 고려 (저항선이 가까우면 목표가 낮춤)
    resistance_dist_pct = ((resistance - current_price) / current_price) * 100
    if resistance_dist_pct > 0 and resistance_dist_pct < target_pct_5d:
        # 저항선 근처에서 목표가 조정하되, 최소 1.5% 보장
        target_pct_5d = max(1.5, target_pct_5d * 0.7, resistance_dist_pct * 0.9)

    # 애널리스트 목표가 참고
    analyst_target = None
    if info:
        at = info.get('targetMeanPrice')
        if at and isinstance(at, (int, float)) and at > current_price:
            analyst_target = round(at, 2)

    target_price_1d = round(current_price * (1 + target_pct_1d / 100), 2)
    target_price_5d = round(current_price * (1 + target_pct_5d / 100), 2)

    # === 손절가 계산 ===
    # ATR 기반 손절 (1.5~2배 ATR)
    if risk_level == '낮음':
        stop_multiplier = 1.5
    elif risk_level == '보통':
        stop_multiplier = 2.0
    else:
        stop_multiplier = 2.5

    stop_loss_pct = max(1.5, min(atr_pct * stop_multiplier * 0.5, 8.0))

    # 지지선 고려 (지지선이 가까우면 그 아래로 손절)
    support_dist_pct = ((current_price - support) / current_price) * 100
    if 0 < support_dist_pct < stop_loss_pct:
        stop_loss_pct = support_dist_pct + 0.5  # 지지선 살짝 아래

    stop_loss_price = round(current_price * (1 - stop_loss_pct / 100), 2)

    # === 보유 기간 추천 ===
    if prob_1d >= 65 and final_score >= 70:
        hold_period = "당일~2일"
        strategy = "단타"
    elif prob_5d >= 65 and final_score >= 60:
        hold_period = "3~5일"
        strategy = "스윙"
    elif prob_5d >= 55:
        hold_period = "1~2주"
        strategy = "단기 보유"
    else:
        hold_period = "1주 이내"
        strategy = "관망 후 진입"

    # === 리스크/리워드 비율 ===
    reward = target_pct_5d
    risk = stop_loss_pct
    rr_ratio = round(reward / risk, 2) if risk > 0 else 0

    # === 매수 타이밍 ===
    if final_score >= 80:
        timing = "즉시 매수"
    elif final_score >= 65:
        timing = "시가 확인 후 매수"
    elif final_score >= 50:
        timing = "눌림목 대기 후 매수"
    else:
        timing = "추가 확인 필요"

    return {
        'entry_price': entry_price,
        'limit_price': limit_price,
        'target_price_1d': target_price_1d,
        'target_price_5d': target_price_5d,
        'target_pct_1d': round(target_pct_1d, 1),
        'target_pct_5d': round(target_pct_5d, 1),
        'stop_loss_price': stop_loss_price,
        'stop_loss_pct': round(stop_loss_pct, 1),
        'hold_period': hold_period,
        'strategy': strategy,
        'timing': timing,
        'rr_ratio': rr_ratio,
        'daily_volatility': round(daily_vol, 2),
        'atr_pct': round(atr_pct, 2),
        'analyst_target': analyst_target,
        'support': round(support, 2),
        'resistance': round(resistance, 2),
        'high_52w': round(float(high_52w), 2),
        'low_52w': round(float(low_52w), 2),
    }


def calculate_grade(score: float) -> str:
    if score >= 85:
        return 'S'
    elif score >= 70:
        return 'A'
    elif score >= 55:
        return 'B'
    elif score >= 40:
        return 'C'
    elif score >= 25:
        return 'D'
    else:
        return 'F'


def estimate_probability(final_score: float, ml_result: dict, horizon: str) -> float:
    """
    보정된 확률 추정
    - ML 모델 정확도가 높으면(>55%) ML 확률에 가중치 0.7
    - ML 모델 정확도가 낮으면(<=55%) final_score에 가중치 0.6
    """
    ml_prob = ml_result.get('details', {}).get(f'ML_{horizon}_prob', 50)
    ml_accuracy = ml_result.get('details', {}).get('ML_accuracy', 50)

    if isinstance(ml_accuracy, (int, float)) and ml_accuracy > 55:
        # ML 모델 신뢰도 높음: ML 확률 가중치 0.7
        estimated = ml_prob * 0.7 + final_score * 0.3
    else:
        # ML 모델 신뢰도 낮음: final_score 가중치 0.6
        estimated = final_score * 0.6 + ml_prob * 0.4

    return max(15, min(90, estimated))


def assess_risk(scores: dict, df: pd.DataFrame = None, info: dict = None) -> str:
    """
    리스크 평가 (확장된 팩터)
    - 점수 분산도
    - 펀더멘털 저점수
    - 변동성
    - 시가총액
    - 52주 고가 근접 여부 (모멘텀 리스크 감소)
    - 부채비율 (debt-to-equity)
    """
    risk_factors = 0

    # 1. 점수 분산이 크면 리스크
    score_values = list(scores.values())
    if np.std(score_values) > 25:
        risk_factors += 1

    # 2. 펀더멘털 저점수
    if scores.get('fundamental', 0) < 30:
        risk_factors += 1

    # 3. 최근 변동성
    if df is not None and len(df) >= 20:
        vol = df['Close'].pct_change().tail(20).std()
        if vol > 0.05:
            risk_factors += 1

    # 4. 소형주 리스크
    if info:
        mcap = info.get('marketCap', 0)
        if isinstance(mcap, (int, float)) and 0 < mcap < 1e9:
            risk_factors += 1

    # 5. 52주 고가 근접 여부 (모멘텀: 고가 근처면 리스크 감소)
    if df is not None and len(df) >= 20:
        current_price = df.iloc[-1]['Close']
        high_52w = df['High'].max()
        if high_52w > 0:
            pct_from_high = (high_52w - current_price) / high_52w * 100
            if pct_from_high < 5:
                # 52주 고가 5% 이내: 모멘텀 강함 -> 리스크 감소
                risk_factors -= 1

    # 6. 부채비율 (debt-to-equity) 체크
    if info:
        de_ratio = info.get('debtToEquity')
        if de_ratio is not None and isinstance(de_ratio, (int, float)):
            if de_ratio > 200:
                # 부채비율 200% 초과: 높은 재무 리스크
                risk_factors += 1

    # 7. 시장 이벤트 리스크
    market_events = analyze_market_events(info)
    risk_factors += market_events.get('risk_adjustment', 0)

    # 최소 0으로 클램프
    risk_factors = max(0, risk_factors)

    if risk_factors >= 3:
        return '높음'
    elif risk_factors >= 2:
        return '보통'
    else:
        return '낮음'


def generate_recommendation(grade: str, prob_1d: float, prob_5d: float, risk: str) -> str:
    max_prob = max(prob_1d, prob_5d)
    prob_gap = abs(prob_1d - prob_5d)

    # 1일/5일 확률 차이가 40% 이상이면 신뢰도 경고 추가
    gap_warning = ""
    if prob_gap >= 40:
        gap_warning = " (단기/중기 괴리 주의)"

    # 확률이 높으면 등급과 무관하게 추천 상향
    if max_prob >= 75:
        if prob_5d >= 75:
            return f'매수 추천 - 5일 상승 확률 {prob_5d:.0f}%{gap_warning}'
        else:
            return f'단타 매수 - 1일 상승 확률 {prob_1d:.0f}%{gap_warning}'

    if max_prob >= 65:
        if grade in ('S', 'A'):
            return f'강력 매수 - 점수+확률 모두 양호{gap_warning}'
        else:
            return f'매수 고려 - 상승 확률 {max_prob:.0f}%{gap_warning}'

    # 기존 등급 기반 추천
    if grade == 'S':
        return '강력 매수 - 즉시 진입 추천'
    elif grade == 'A':
        if risk == '낮음':
            return '매수 추천 - 안정적 상승 기대'
        else:
            return '매수 고려 - 리스크 존재'
    elif grade == 'B':
        if prob_5d > 60:
            return '매수 고려 - 단기 상승 가능성'
        else:
            return '관심 종목 - 눌림목 매수 대기'
    elif grade == 'C':
        return '관망 - 명확한 방향성 부재'
    elif grade == 'D':
        return '매수 보류 - 하락 리스크'
    else:
        if max_prob >= 50:
            return f'관망 - 점수 낮으나 확률 {max_prob:.0f}%'
        return '매수 비추천 - 부정적 시그널'


def rank_stocks(results: list) -> list:
    sorted_results = sorted(results, key=lambda x: x['final_score'], reverse=True)
    for i, r in enumerate(sorted_results):
        r['rank'] = i + 1
    return sorted_results
