"""
시장 이벤트 분석 모듈
마녀의 날, 실적 발표일 등 이벤트 기반 분석
"""
from datetime import datetime, date, timedelta
import calendar


def get_witching_dates(year: int) -> list:
    """해당 연도의 마녀의 날(3,6,9,12월 셋째 금요일) 반환"""
    dates = []
    for month in [3, 6, 9, 12]:
        # 셋째 금요일 계산
        c = calendar.monthcalendar(year, month)
        # 금요일은 index 4
        fridays = [week[4] for week in c if week[4] != 0]
        if len(fridays) >= 3:
            third_friday = date(year, month, fridays[2])
            dates.append(third_friday)
    return dates


def is_witching_week(check_date: date = None) -> dict:
    """현재(또는 지정) 날짜가 마녀의 날 주간인지 확인"""
    if check_date is None:
        check_date = date.today()

    year = check_date.year
    witching_dates = get_witching_dates(year)

    for wd in witching_dates:
        # 마녀의 날 주간 = 해당 금요일 기준 월~금 (5영업일)
        week_start = wd - timedelta(days=wd.weekday())  # Monday
        week_end = wd  # Friday

        if week_start <= check_date <= week_end:
            days_until = (wd - check_date).days
            return {
                'is_witching_week': True,
                'is_witching_day': check_date == wd,
                'witching_date': wd.isoformat(),
                'days_until': days_until,
            }

    # 다음 마녀의 날까지 남은 일수
    future = [d for d in witching_dates if d > check_date]
    if not future:
        future = get_witching_dates(year + 1)
    next_witching = future[0] if future else None
    days_until_next = (next_witching - check_date).days if next_witching else None

    return {
        'is_witching_week': False,
        'is_witching_day': False,
        'next_witching_date': next_witching.isoformat() if next_witching else None,
        'days_until_next': days_until_next,
    }


def analyze_market_events(info: dict = None) -> dict:
    """
    시장 이벤트 분석 - 점수 조정값과 시그널 반환

    Returns:
        {
            'score_adjustment': int (점수 가감),
            'risk_adjustment': int (리스크 가감, 양수=리스크 증가),
            'volatility_multiplier': float (변동성 배수, 1.0=기본),
            'signals': list,
            'events': dict,
        }
    """
    signals = []
    score_adj = 0
    risk_adj = 0
    vol_mult = 1.0
    events = {}

    # === 마녀의 날 체크 ===
    witching = is_witching_week()
    events['witching'] = witching

    if witching['is_witching_day']:
        score_adj -= 5  # 마녀의 날 당일은 예측 어려움
        risk_adj += 2
        vol_mult = 1.5
        signals.append("[!]오늘은 마녀의 날 - 변동성 극대화 주의")
    elif witching['is_witching_week']:
        score_adj -= 3
        risk_adj += 1
        vol_mult = 1.3
        days = witching['days_until']
        signals.append(f"[!]마녀의 날 주간 (D-{days}) - 변동성 증가 주의")

    # === 실적 발표일 체크 ===
    if info:
        earnings_date = None
        # yfinance에서 earningsDate 필드 (없을 수 있음)
        for field in ['earningsDate', 'mostRecentQuarter']:
            val = info.get(field)
            if val:
                events['earnings_raw'] = str(val)
                break

        # earningsTimestamp 또는 earningsDate (epoch)
        earnings_ts = info.get('earningsTimestamp')
        earnings_ts_start = info.get('earningsTimestampStart')
        earnings_ts_end = info.get('earningsTimestampEnd')

        ts = earnings_ts_start or earnings_ts
        if ts and isinstance(ts, (int, float)):
            try:
                earnings_date = datetime.fromtimestamp(ts).date()
            except Exception:
                pass

        if earnings_date:
            today = date.today()
            days_until_earnings = (earnings_date - today).days
            events['earnings'] = {
                'date': earnings_date.isoformat(),
                'days_until': days_until_earnings,
            }

            if 0 <= days_until_earnings <= 3:
                # 실적 발표 3일 이내
                score_adj -= 5
                risk_adj += 2
                vol_mult = max(vol_mult, 1.5)
                signals.append(f"[!]실적 발표 D-{days_until_earnings} - 큰 변동 예상")
            elif 0 <= days_until_earnings <= 7:
                # 실적 발표 1주 이내
                score_adj -= 2
                risk_adj += 1
                vol_mult = max(vol_mult, 1.2)
                signals.append(f"실적 발표 D-{days_until_earnings} 예정")
            elif -3 <= days_until_earnings < 0:
                # 실적 발표 직후 (3일 이내)
                signals.append("실적 발표 직후 - 결과 확인 필요")

    return {
        'score_adjustment': score_adj,
        'risk_adjustment': risk_adj,
        'volatility_multiplier': vol_mult,
        'signals': signals,
        'events': events,
    }
