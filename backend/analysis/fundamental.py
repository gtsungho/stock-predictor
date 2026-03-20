"""
펀더멘털 분석 모듈
PER, PBR, 실적 성장률, 재무 건전성 등
"""
import numpy as np


# 섹터별 PE 기준값
SECTOR_PE_THRESHOLDS = {
    'Technology': {'undervalued': 25, 'fair': 40},
    'Healthcare': {'undervalued': 20, 'fair': 35},
    'Financial Services': {'undervalued': 12, 'fair': 18},
    'Financial': {'undervalued': 12, 'fair': 18},
    'Consumer Cyclical': {'undervalued': 18, 'fair': 25},
    'Consumer Defensive': {'undervalued': 18, 'fair': 25},
    'Consumer': {'undervalued': 18, 'fair': 25},
}
DEFAULT_PE_THRESHOLD = {'undervalued': 15, 'fair': 25}


def _get_pe_thresholds(sector: str | None) -> dict:
    """섹터에 맞는 PE 기준값 반환"""
    if not sector:
        return DEFAULT_PE_THRESHOLD
    # 정확한 매칭 우선, 없으면 부분 매칭 시도
    if sector in SECTOR_PE_THRESHOLDS:
        return SECTOR_PE_THRESHOLDS[sector]
    for key, val in SECTOR_PE_THRESHOLDS.items():
        if key.lower() in sector.lower() or sector.lower() in key.lower():
            return val
    return DEFAULT_PE_THRESHOLD


def analyze_fundamental(info: dict) -> dict:
    """펀더멘털 기반 종합 분석"""
    if not info:
        return {'score': 0, 'signals': [], 'details': {}}

    signals = []
    score = 0
    details = {}

    # info dict에서 섹터 정보 추출
    sector = info.get('sector')

    # === 밸류에이션 분석 (만점 25) ===
    val = analyze_valuation(info, sector=sector)
    score += val['score']
    signals.extend(val['signals'])
    details.update(val['details'])

    # === 성장성 분석 (만점 25) ===
    growth = analyze_growth(info)
    score += growth['score']
    signals.extend(growth['signals'])
    details.update(growth['details'])

    # === 수익성 분석 (만점 20) ===
    profit = analyze_profitability(info)
    score += profit['score']
    signals.extend(profit['signals'])
    details.update(profit['details'])

    # === 재무 건전성 (만점 15) ===
    health = analyze_financial_health(info)
    score += health['score']
    signals.extend(health['signals'])
    details.update(health['details'])

    # === 애널리스트 평가 (만점 15) ===
    analyst = analyze_analyst_rating(info)
    score += analyst['score']
    signals.extend(analyst['signals'])
    details.update(analyst['details'])

    # 정규화 (0-100)
    normalized_score = max(0, min(100, score))

    return {
        'score': round(normalized_score, 2),
        'signals': signals,
        'details': details,
    }


def analyze_valuation(info: dict, sector: str | None = None) -> dict:
    """밸류에이션 분석 (섹터별 PE 기준 적용)"""
    score = 0
    signals = []
    details = {}

    pe_thresh = _get_pe_thresholds(sector)
    if sector:
        details['Sector'] = sector

    # Forward P/E (섹터별 기준 적용)
    fpe = info.get('forwardPE')
    if fpe is not None and isinstance(fpe, (int, float)):
        details['Forward_PE'] = round(fpe, 2)
        underval = pe_thresh['undervalued']
        fair = pe_thresh['fair']
        if 0 < fpe < underval * 0.6:
            score += 10
            signals.append(f"강한 저평가 (Forward P/E: {fpe:.1f}, 섹터 기준: {underval})")
        elif 0 < fpe < underval:
            score += 8
            signals.append(f"저평가 (Forward P/E: {fpe:.1f}, 섹터 기준: {underval})")
        elif underval <= fpe < fair:
            score += 5
            signals.append(f"적정 밸류 (Forward P/E: {fpe:.1f}, 섹터 기준: {fair})")
        elif fair <= fpe < fair * 1.5:
            score += 2
        elif fpe >= fair * 1.5:
            score += 0
            signals.append(f"고평가 주의 (Forward P/E: {fpe:.1f}, 섹터 기준: {fair})")

    # Trailing P/E
    tpe = info.get('trailingPE')
    if tpe is not None and isinstance(tpe, (int, float)):
        details['Trailing_PE'] = round(tpe, 2)

    # PEG Ratio (1 이하가 좋음, 음수는 마이너스 성장 → 페널티)
    peg = info.get('pegRatio')
    if peg is not None and isinstance(peg, (int, float)):
        details['PEG'] = round(peg, 2)
        if peg < 0:
            # 음수 PEG = 이익 역성장 → 페널티
            score -= 3
            signals.append(f"PEG 음수 (이익 역성장, PEG: {peg:.2f})")
        elif 0 < peg < 1:
            score += 8
            signals.append(f"PEG 저평가 ({peg:.2f})")
        elif 1 <= peg < 1.5:
            score += 5
        elif 1.5 <= peg < 2:
            score += 2

    # Price to Book
    pb = info.get('priceToBook')
    if pb is not None and isinstance(pb, (int, float)):
        details['PBR'] = round(pb, 2)
        if 0 < pb < 1:
            score += 5
            signals.append(f"자산가치 대비 저평가 (PBR: {pb:.2f})")
        elif 1 <= pb < 3:
            score += 3

    # Price to Sales
    ps = info.get('priceToSalesTrailing12Months')
    if ps is not None and isinstance(ps, (int, float)):
        details['PSR'] = round(ps, 2)
        if 0 < ps < 2:
            score += 2

    return {'score': min(score, 25), 'signals': signals, 'details': details}


def analyze_growth(info: dict) -> dict:
    """성장성 분석"""
    score = 0
    signals = []
    details = {}

    # 매출 성장률
    rev_growth = info.get('revenueGrowth')
    if rev_growth is not None and isinstance(rev_growth, (int, float)):
        rev_pct = rev_growth * 100
        details['Revenue_Growth'] = f"{rev_pct:.1f}%"
        if rev_pct > 30:
            score += 10
            signals.append(f"고성장 매출 (+{rev_pct:.0f}%)")
        elif rev_pct > 15:
            score += 7
            signals.append(f"견조한 매출 성장 (+{rev_pct:.0f}%)")
        elif rev_pct > 5:
            score += 4
        elif rev_pct < 0:
            score -= 3

    # 이익 성장률
    earn_growth = info.get('earningsGrowth')
    if earn_growth is not None and isinstance(earn_growth, (int, float)):
        earn_pct = earn_growth * 100
        details['Earnings_Growth'] = f"{earn_pct:.1f}%"
        if earn_pct > 30:
            score += 8
            signals.append(f"이익 고성장 (+{earn_pct:.0f}%)")
        elif earn_pct > 15:
            score += 5
        elif earn_pct > 0:
            score += 3

    # 분기 이익 성장 + 어닝 서프라이즈 감지
    q_growth = info.get('earningsQuarterlyGrowth')
    if q_growth is not None and isinstance(q_growth, (int, float)):
        q_pct = q_growth * 100
        details['Quarterly_Earnings_Growth'] = f"{q_pct:.1f}%"
        if q_pct > 20:
            score += 7
            signals.append(f"분기 이익 서프라이즈 (+{q_pct:.0f}%)")
            # 어닝 서프라이즈 보너스: 20% 초과 성장 시 추가 점수
            surprise_bonus = min(3, int((q_pct - 20) / 10))  # 10%p 당 +1, 최대 +3
            score += surprise_bonus
            if surprise_bonus > 0:
                signals.append(f"어닝 서프라이즈 보너스 (+{surprise_bonus}점)")
        elif q_pct > 5:
            score += 4

    return {'score': min(score, 25), 'signals': signals, 'details': details}


def analyze_profitability(info: dict) -> dict:
    """수익성 분석"""
    score = 0
    signals = []
    details = {}

    # 영업이익률
    op_margin = info.get('operatingMargins')
    if op_margin is not None and isinstance(op_margin, (int, float)):
        op_pct = op_margin * 100
        details['Operating_Margin'] = f"{op_pct:.1f}%"
        if op_pct > 30:
            score += 7
            signals.append(f"높은 영업이익률 ({op_pct:.0f}%)")
        elif op_pct > 15:
            score += 5
        elif op_pct > 5:
            score += 3
        elif op_pct < 0:
            score -= 2

    # 순이익률
    net_margin = info.get('profitMargins')
    if net_margin is not None and isinstance(net_margin, (int, float)):
        net_pct = net_margin * 100
        details['Profit_Margin'] = f"{net_pct:.1f}%"
        if net_pct > 20:
            score += 5
        elif net_pct > 10:
            score += 3

    # ROE
    roe = info.get('returnOnEquity')
    if roe is not None and isinstance(roe, (int, float)):
        roe_pct = roe * 100
        details['ROE'] = f"{roe_pct:.1f}%"
        if roe_pct > 20:
            score += 8
            signals.append(f"높은 ROE ({roe_pct:.0f}%)")
        elif roe_pct > 10:
            score += 5

    return {'score': min(score, 20), 'signals': signals, 'details': details}


def analyze_financial_health(info: dict) -> dict:
    """재무 건전성"""
    score = 0
    signals = []
    details = {}

    # 부채비율
    dte = info.get('debtToEquity')
    if dte is not None and isinstance(dte, (int, float)):
        details['Debt_to_Equity'] = round(dte, 2)
        if dte < 30:
            score += 5
            signals.append("낮은 부채비율")
        elif dte < 80:
            score += 3
        elif dte > 200:
            score -= 3
            signals.append("높은 부채비율 (주의)")

    # 유동비율
    cr = info.get('currentRatio')
    if cr is not None and isinstance(cr, (int, float)):
        details['Current_Ratio'] = round(cr, 2)
        if cr > 2:
            score += 5
        elif cr > 1.5:
            score += 3
        elif cr < 1:
            score -= 2

    # 현금 보유 및 순현금 포지션 분석
    cash = info.get('totalCash')
    debt = info.get('totalDebt')
    if cash and isinstance(cash, (int, float)):
        details['Total_Cash'] = cash
    if debt and isinstance(debt, (int, float)):
        details['Total_Debt'] = debt

    if cash and debt and isinstance(cash, (int, float)) and isinstance(debt, (int, float)):
        # Cash to Debt 비율
        if debt > 0:
            cash_ratio = cash / debt
            details['Cash_to_Debt'] = round(cash_ratio, 2)
            if cash_ratio > 2:
                score += 3
                signals.append("풍부한 현금 보유")
            elif cash_ratio > 1:
                score += 2

        # 순현금 포지션 (Free Cash Flow 대용 분석)
        net_cash = cash - debt
        details['Net_Cash_Position'] = net_cash
        if net_cash > 0:
            # 순현금 양수 = 현금이 부채보다 많음
            score += 2
            signals.append(f"순현금 포지션 양호 (순현금: {net_cash:,.0f})")
        elif net_cash < 0:
            # 순부채 상태
            net_debt_ratio = abs(net_cash) / cash if cash > 0 else 9999
            if net_debt_ratio > 3:
                score -= 2
                signals.append(f"순부채 과다 (순부채: {abs(net_cash):,.0f})")
    elif cash and isinstance(cash, (int, float)) and (not debt or debt == 0):
        # 부채 없이 현금만 보유 → 매우 건전
        score += 3
        signals.append("무차입 현금 보유")

    return {'score': min(score, 15), 'signals': signals, 'details': details}


def analyze_analyst_rating(info: dict) -> dict:
    """애널리스트 평가"""
    score = 0
    signals = []
    details = {}

    # 애널리스트 추천 (1=Strong Buy, 5=Sell)
    rec = info.get('recommendationMean')
    if rec is not None and isinstance(rec, (int, float)):
        details['Analyst_Rating'] = round(rec, 2)
        if rec <= 1.5:
            score += 10
            signals.append(f"Strong Buy 컨센서스 ({rec:.1f})")
        elif rec <= 2.0:
            score += 7
            signals.append(f"Buy 컨센서스 ({rec:.1f})")
        elif rec <= 2.5:
            score += 5
        elif rec <= 3:
            score += 2

    # 목표가 대비 현재가
    target = info.get('targetMeanPrice')
    mcap = info.get('marketCap')
    if target and isinstance(target, (int, float)):
        details['Target_Price'] = round(target, 2)
        # 업사이드 계산은 현재가 필요 (별도 계산)

    # 시가총액
    if mcap and isinstance(mcap, (int, float)):
        details['Market_Cap'] = mcap
        if mcap > 10e9:
            score += 3  # 대형주 안정성
        elif mcap > 2e9:
            score += 2

    return {'score': min(score, 15), 'signals': signals, 'details': details}
