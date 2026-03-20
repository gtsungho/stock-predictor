"""
앙상블 스코어링 모듈
기술적 분석 + 모멘텀 + 펀더멘털 + ML을 종합하여 최종 점수 산출
"""
import pandas as pd
import numpy as np
from datetime import datetime


# 각 분석 모듈 가중치 (합계 = 1.0)
WEIGHTS = {
    'technical': 0.25,    # 기술적 분석
    'momentum': 0.25,     # 모멘텀 분석
    'fundamental': 0.20,  # 펀더멘털 분석
    'ml': 0.30,           # 머신러닝 예측
}


def calculate_ensemble_score(
    technical_result: dict,
    momentum_result: dict,
    fundamental_result: dict,
    ml_result: dict,
    info: dict = None,
    df: pd.DataFrame = None,
) -> dict:
    """
    모든 분석 결과를 종합하여 최종 스코어 산출

    Returns:
        {
            'ticker': str,
            'final_score': float (0-100),
            'grade': str (S/A/B/C/D/F),
            'recommendation': str,
            'rise_probability_1d': float,
            'rise_probability_5d': float,
            'scores': {모듈별 점수},
            'top_signals': [주요 시그널],
            'risk_level': str,
            'details': {세부 정보},
        }
    """
    scores = {
        'technical': technical_result.get('score', 0),
        'momentum': momentum_result.get('score', 0),
        'fundamental': fundamental_result.get('score', 0),
        'ml': ml_result.get('score', 0),
    }

    # 가중 평균 점수
    final_score = sum(scores[k] * WEIGHTS[k] for k in WEIGHTS)

    # 보너스/페널티 조정
    bonus = 0

    # 다중 시그널 일치 보너스 (여러 분석이 동시에 높으면 추가 점수)
    high_scores = sum(1 for s in scores.values() if s >= 60)
    if high_scores >= 3:
        bonus += 10
    elif high_scores >= 2:
        bonus += 5

    # 모든 분석이 긍정적이면 추가 보너스
    if all(s >= 50 for s in scores.values()):
        bonus += 5

    # 극단적 부정 시그널이 있으면 페널티
    if any(s < 20 for s in scores.values()):
        bonus -= 5

    final_score = max(0, min(100, final_score + bonus))

    # 등급 산정
    grade = calculate_grade(final_score)

    # 상승 확률 추정
    prob_1d = estimate_probability(final_score, ml_result, '1d')
    prob_5d = estimate_probability(final_score, ml_result, '5d')

    # 주요 시그널 수집 (상위 5개)
    all_signals = []
    for result in [technical_result, momentum_result, fundamental_result, ml_result]:
        all_signals.extend(result.get('signals', []))
    top_signals = all_signals[:8]

    # 리스크 레벨
    risk_level = assess_risk(scores, df, info)

    # 추천 문구
    recommendation = generate_recommendation(grade, prob_1d, prob_5d, risk_level)

    # 추가 정보
    details = {}
    for result in [technical_result, momentum_result, fundamental_result, ml_result]:
        details.update(result.get('details', {}))

    # 종목 기본 정보
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

    return {
        'final_score': round(final_score, 1),
        'grade': grade,
        'recommendation': recommendation,
        'rise_probability_1d': round(prob_1d, 1),
        'rise_probability_5d': round(prob_5d, 1),
        'scores': scores,
        'top_signals': top_signals,
        'risk_level': risk_level,
        'stock_info': stock_info,
        'price_info': price_info,
        'details': details,
        'analyzed_at': datetime.now().isoformat(),
    }


def calculate_grade(score: float) -> str:
    """점수 기반 등급"""
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
    """상승 확률 추정"""
    ml_prob = ml_result.get('details', {}).get(f'ML_{horizon}_prob', 50)

    # 최종 점수와 ML 확률의 가중 평균
    # ML이 더 직접적인 확률이므로 비중 높임
    estimated = ml_prob * 0.6 + final_score * 0.4

    # 범위 제한 (15% ~ 90%)
    return max(15, min(90, estimated))


def assess_risk(scores: dict, df: pd.DataFrame = None, info: dict = None) -> str:
    """리스크 레벨 평가"""
    risk_factors = 0

    # 점수 분산이 크면 리스크 높음
    score_values = list(scores.values())
    if np.std(score_values) > 25:
        risk_factors += 1

    # 펀더멘털 낮으면 리스크
    if scores.get('fundamental', 0) < 30:
        risk_factors += 1

    # 변동성 체크
    if df is not None and len(df) >= 20:
        vol = df['Close'].pct_change().tail(20).std()
        if vol > 0.05:  # 일간 변동성 5% 이상
            risk_factors += 1

    # 소형주 리스크
    if info:
        mcap = info.get('marketCap', 0)
        if isinstance(mcap, (int, float)) and 0 < mcap < 1e9:
            risk_factors += 1

    if risk_factors >= 3:
        return '높음'
    elif risk_factors >= 2:
        return '보통'
    else:
        return '낮음'


def generate_recommendation(grade: str, prob_1d: float, prob_5d: float, risk: str) -> str:
    """추천 문구 생성"""
    if grade == 'S':
        return '강력 매수 추천 - 다중 시그널 일치'
    elif grade == 'A':
        if risk == '낮음':
            return '매수 추천 - 안정적 상승 기대'
        else:
            return '매수 고려 - 상승 가능성 높으나 리스크 존재'
    elif grade == 'B':
        if prob_5d > 60:
            return '관심 종목 - 단기 상승 가능성'
        else:
            return '관심 종목 - 추가 확인 필요'
    elif grade == 'C':
        return '중립 - 명확한 방향성 부재'
    elif grade == 'D':
        return '보류 - 하락 리스크 존재'
    else:
        return '매수 비추천 - 부정적 시그널 다수'


def rank_stocks(results: list) -> list:
    """종목들을 최종 점수로 순위화"""
    sorted_results = sorted(results, key=lambda x: x['final_score'], reverse=True)

    for i, r in enumerate(sorted_results):
        r['rank'] = i + 1

    return sorted_results
