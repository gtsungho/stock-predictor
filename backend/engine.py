"""
분석 엔진 - 전체 파이프라인 오케스트레이션
4개 탭: 종합 TOP 20, 우량주, 급등주, 거래량 폭발
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import time
import json
import gc
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from data.fetcher import (
    get_stock_list, get_fallback_stocks, fetch_stock_data,
    fetch_stock_info, batch_fetch, prefilter_stocks,
    scan_daily_gainers, scan_volume_surge, get_usd_krw_rate
)
from analysis.technical import analyze_technical
from analysis.momentum import analyze_momentum
from analysis.fundamental import analyze_fundamental
from analysis.ml_model import predict_stock, train_model
from scoring.ensemble import calculate_ensemble_score, rank_stocks

RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)


def filter_by_probability(stocks: list, start_threshold: float = 70.0, step: float = 2.0, min_threshold: float = 50.0) -> tuple:
    """
    1일 또는 5일 상승 확률이 threshold 이상인 종목만 필터링.
    해당 종목이 0건이면 threshold를 step%씩 낮추면서 재시도.
    Returns: (filtered_stocks, applied_threshold)
    """
    if not stocks:
        return [], 0

    threshold = start_threshold
    while threshold >= min_threshold:
        filtered = [
            s for s in stocks
            if s.get('rise_probability_1d', 0) >= threshold
            or s.get('rise_probability_5d', 0) >= threshold
        ]
        if filtered:
            # 확률 높은 순 정렬
            filtered.sort(
                key=lambda x: max(x.get('rise_probability_1d', 0), x.get('rise_probability_5d', 0)),
                reverse=True
            )
            return filtered, threshold
        threshold -= step

    # 최소 임계값에서도 없으면 전체 중 상위 5개
    stocks_sorted = sorted(
        stocks,
        key=lambda x: max(x.get('rise_probability_1d', 0), x.get('rise_probability_5d', 0)),
        reverse=True
    )
    actual_threshold = max(
        stocks_sorted[0].get('rise_probability_1d', 0),
        stocks_sorted[0].get('rise_probability_5d', 0)
    ) if stocks_sorted else 0
    return stocks_sorted[:5], round(actual_threshold, 1)


def analyze_single_stock(ticker: str, period: str = "6mo") -> dict:
    """단일 종목 전체 분석"""
    try:
        df = fetch_stock_data(ticker, period)
        if df.empty or len(df) < 30:
            return None

        info = fetch_stock_info(ticker)
        technical_result = analyze_technical(df)
        momentum_result = analyze_momentum(df)
        fundamental_result = analyze_fundamental(info)
        ml_result = predict_stock(df)

        result = calculate_ensemble_score(
            technical_result=technical_result,
            momentum_result=momentum_result,
            fundamental_result=fundamental_result,
            ml_result=ml_result,
            info=info,
            df=df,
        )
        result['ticker'] = ticker
        return result

    except Exception as e:
        print(f"  {ticker} 분석 실패: {e}")
        return None


def _is_low_memory_env() -> bool:
    """Render Free 등 저메모리 환경 감지"""
    # Render는 PORT 환경변수를 자동 설정
    return os.environ.get("RENDER") == "true" or os.environ.get("PORT") is not None


def analyze_batch(tickers: list, workers: int = 4, progress_callback=None,
                  progress_start: int = 0, progress_end: int = 100) -> list:
    """종목 배치 분석 (서버 환경에서는 순차 처리로 메모리 절약)"""
    results = []
    completed = 0
    total = len(tickers)

    # 저메모리 환경: 순차 처리 + GC
    if _is_low_memory_env():
        for t in tickers:
            completed += 1
            try:
                result = analyze_single_stock(t)
                if result:
                    results.append(result)
            except Exception:
                pass

            if completed % 5 == 0:
                gc.collect()
                if progress_callback:
                    pct = progress_start + int((completed / total) * (progress_end - progress_start))
                    progress_callback('analyzing', f'{completed}/{total} 분석 완료', pct)
    else:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(analyze_single_stock, t): t for t in tickers}

            for future in as_completed(futures):
                completed += 1
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                except Exception:
                    pass

                if completed % 10 == 0 and progress_callback:
                    pct = progress_start + int((completed / total) * (progress_end - progress_start))
                    progress_callback('analyzing', f'{completed}/{total} 분석 완료', pct)

    return results


def run_full_analysis(
    max_stocks: int = 100,
    min_score: float = 0,
    top_n: int = 20,
    workers: int = 4,
    progress_callback=None,
) -> dict:
    """
    전체 분석 파이프라인 (4개 탭)
    1. 우량주 분석 (고정 리스트)
    2. 급등주 스크리닝
    3. 거래량 폭발 스크리닝
    4. 종합 TOP 20 (전체 합산)
    """
    start_time = time.time()

    # 서버 환경에서는 분석 수 축소 (메모리 제한)
    low_mem = _is_low_memory_env()
    if low_mem:
        max_stocks = min(max_stocks, 50)
        workers = 1
        print(f"[서버 모드] max_stocks={max_stocks}, 순차 처리")

    # === 1단계: 우량주 리스트 ===
    if progress_callback:
        progress_callback('loading', '우량주 리스트 로딩 중...', 0)

    bluechip_tickers = get_fallback_stocks()[:max_stocks]
    print(f"우량주 {len(bluechip_tickers)}개 분석 시작")

    # === 2단계: 우량주 분석 ===
    if progress_callback:
        progress_callback('analyzing', f'우량주 {len(bluechip_tickers)}개 분석 중...', 5)

    bluechip_results = analyze_batch(
        bluechip_tickers, workers=workers,
        progress_callback=progress_callback,
        progress_start=5, progress_end=50,
    )
    print(f"  우량주 분석 완료: {len(bluechip_results)}개")
    gc.collect()

    # === 3단계: 급등주 스크리닝 ===
    if progress_callback:
        progress_callback('scanning', '급등주 스크리닝 중...', 55)

    gainer_tickers = scan_daily_gainers(bluechip_tickers, top_n=30)
    # 이미 분석된 종목은 재사용
    analyzed_tickers = {r['ticker'] for r in bluechip_results}
    gainer_new = [t for t in gainer_tickers if t not in analyzed_tickers]

    gainer_extra = analyze_batch(gainer_new, workers=workers) if gainer_new else []
    all_results_map = {r['ticker']: r for r in bluechip_results + gainer_extra}

    gainers = []
    for t in gainer_tickers:
        if t in all_results_map:
            gainers.append(all_results_map[t])
    # 상승률 순 정렬
    gainers.sort(key=lambda x: x.get('price_info', {}).get('change_pct', 0), reverse=True)
    gainers = gainers[:top_n]

    print(f"  급등주: {len(gainers)}개")
    gc.collect()

    # === 4단계: 거래량 폭발 스크리닝 ===
    if progress_callback:
        progress_callback('scanning', '거래량 급증 종목 스크리닝 중...', 70)

    volume_tickers = scan_volume_surge(bluechip_tickers, top_n=30)
    volume_new = [t for t in volume_tickers if t not in all_results_map]

    volume_extra = analyze_batch(volume_new, workers=workers) if volume_new else []
    all_results_map.update({r['ticker']: r for r in volume_extra})

    volume_surge = []
    for t in volume_tickers:
        if t in all_results_map:
            volume_surge.append(all_results_map[t])
    # 거래량 비율 순 정렬
    volume_surge.sort(
        key=lambda x: x.get('details', {}).get('Volume_Ratio_20D', 0), reverse=True
    )
    volume_surge = volume_surge[:top_n]

    print(f"  거래량 폭발: {len(volume_surge)}개")

    # === 5단계: 확률 기반 필터링 ===
    if progress_callback:
        progress_callback('ranking', '확률 기반 필터링 중...', 90)

    all_results = list(all_results_map.values())

    # 각 탭별 확률 필터링 (70% 시작, 2%씩 하향)
    top_filtered, top_threshold = filter_by_probability(all_results)
    bluechip_filtered, bc_threshold = filter_by_probability(bluechip_results)
    gainers_filtered, gn_threshold = filter_by_probability(gainers) if gainers else ([], 0)
    volume_filtered, vol_threshold = filter_by_probability(volume_surge) if volume_surge else ([], 0)

    # 순위 부여
    for i, s in enumerate(top_filtered):
        s['rank'] = i + 1
    for i, s in enumerate(bluechip_filtered):
        s['rank'] = i + 1
    for i, s in enumerate(gainers_filtered):
        s['rank'] = i + 1
    for i, s in enumerate(volume_filtered):
        s['rank'] = i + 1

    elapsed = time.time() - start_time

    # === 환율 ===
    usd_krw = get_usd_krw_rate()

    # === 결과 저장 ===
    output = {
        'timestamp': datetime.now().isoformat(),
        'analyzed_count': len(all_results_map),
        'elapsed_seconds': round(elapsed, 1),
        'usd_krw': usd_krw,
        'tabs': {
            'top20': {
                'label': f'종합 TOP ({top_threshold}%↑)',
                'count': len(top_filtered),
                'stocks': top_filtered,
                'threshold': top_threshold,
            },
            'bluechip': {
                'label': f'우량주 ({bc_threshold}%↑)',
                'count': len(bluechip_filtered),
                'stocks': bluechip_filtered,
                'threshold': bc_threshold,
            },
            'gainers': {
                'label': f'급등주 ({gn_threshold}%↑)',
                'count': len(gainers_filtered),
                'stocks': gainers_filtered,
                'threshold': gn_threshold,
            },
            'volume': {
                'label': f'거래량 ({vol_threshold}%↑)',
                'count': len(volume_filtered),
                'stocks': volume_filtered,
                'threshold': vol_threshold,
            },
        },
        'qualified_count': len(top_filtered),
        'top_picks': top_filtered,
    }

    import math
    def _sanitize(obj):
        if isinstance(obj, dict):
            return {k: _sanitize(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [_sanitize(v) for v in obj]
        elif isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
            return obj
        return obj

    output = _sanitize(output)

    result_file = RESULTS_DIR / f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(result_file, 'w') as f:
        json.dump(output, f, indent=2, default=str)

    latest_file = RESULTS_DIR / "latest.json"
    with open(latest_file, 'w') as f:
        json.dump(output, f, indent=2, default=str)

    if progress_callback:
        progress_callback('done', f'분석 완료! {len(top_filtered)}개 추천', 100)

    print(f"\n분석 완료: {elapsed:.1f}초")
    return output


def get_latest_results() -> dict:
    """최신 분석 결과 가져오기"""
    latest_file = RESULTS_DIR / "latest.json"
    if latest_file.exists():
        with open(latest_file) as f:
            return json.load(f)
    return None
