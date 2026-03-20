"""
분석 엔진 - 전체 파이프라인 오케스트레이션
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import time
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from data.fetcher import (
    get_stock_list, get_fallback_stocks, fetch_stock_data,
    fetch_stock_info, batch_fetch, prefilter_stocks
)
from analysis.technical import analyze_technical
from analysis.momentum import analyze_momentum
from analysis.fundamental import analyze_fundamental
from analysis.ml_model import predict_stock, train_model
from scoring.ensemble import calculate_ensemble_score, rank_stocks

RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)


def analyze_single_stock(ticker: str, period: str = "6mo") -> dict:
    """단일 종목 전체 분석"""
    try:
        # 데이터 수집
        df = fetch_stock_data(ticker, period)
        if df.empty or len(df) < 30:
            return None

        info = fetch_stock_info(ticker)

        # 각 분석 실행
        technical_result = analyze_technical(df)
        momentum_result = analyze_momentum(df)
        fundamental_result = analyze_fundamental(info)

        # ML 예측
        ml_result = predict_stock(df)

        # 앙상블 스코어링
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


def run_full_analysis(
    max_stocks: int = 100,
    min_score: float = 40,
    top_n: int = 20,
    workers: int = 4,
    progress_callback=None,
) -> dict:
    """
    전체 분석 파이프라인 실행

    1. 종목 리스트 가져오기
    2. 초기 필터링
    3. 병렬 분석
    4. 순위화
    5. 결과 저장
    """
    start_time = time.time()

    # 1단계: 종목 리스트
    if progress_callback:
        progress_callback('loading', '종목 리스트 로딩 중...', 0)

    all_tickers = get_fallback_stocks()  # 안정적인 폴백 리스트 사용
    print(f"총 {len(all_tickers)}개 종목 대상")

    # 분석할 종목 수 제한
    tickers = all_tickers[:max_stocks]

    if progress_callback:
        progress_callback('analyzing', f'{len(tickers)}개 종목 분석 시작', 10)

    # 2단계: 병렬 분석
    results = []
    completed = 0
    total = len(tickers)

    def analyze_with_progress(ticker):
        return analyze_single_stock(ticker)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(analyze_with_progress, t): t for t in tickers}

        for future in as_completed(futures):
            ticker = futures[future]
            completed += 1

            try:
                result = future.result()
                if result and result['final_score'] >= min_score:
                    results.append(result)
            except Exception as e:
                print(f"  {ticker} 오류: {e}")

            if completed % 10 == 0:
                pct = 10 + int((completed / total) * 80)
                if progress_callback:
                    progress_callback('analyzing', f'{completed}/{total} 완료', pct)
                print(f"  진행: {completed}/{total} ({len(results)}개 후보)")

    # 3단계: 순위화
    if progress_callback:
        progress_callback('ranking', '순위 산출 중...', 90)

    ranked = rank_stocks(results)
    top_picks = ranked[:top_n]

    elapsed = time.time() - start_time

    # 4단계: 결과 저장
    output = {
        'timestamp': datetime.now().isoformat(),
        'analyzed_count': total,
        'qualified_count': len(results),
        'top_picks': top_picks,
        'elapsed_seconds': round(elapsed, 1),
        'parameters': {
            'max_stocks': max_stocks,
            'min_score': min_score,
            'top_n': top_n,
        },
    }

    result_file = RESULTS_DIR / f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(result_file, 'w') as f:
        json.dump(output, f, indent=2, default=str)

    # 최신 결과 링크
    latest_file = RESULTS_DIR / "latest.json"
    with open(latest_file, 'w') as f:
        json.dump(output, f, indent=2, default=str)

    if progress_callback:
        progress_callback('done', f'분석 완료! {len(top_picks)}개 추천 종목', 100)

    print(f"\n분석 완료: {elapsed:.1f}초, {len(top_picks)}개 추천 종목")
    return output


def get_latest_results() -> dict:
    """최신 분석 결과 가져오기"""
    latest_file = RESULTS_DIR / "latest.json"
    if latest_file.exists():
        with open(latest_file) as f:
            return json.load(f)
    return None


if __name__ == '__main__':
    print("=== Stock Predictor 분석 시작 ===")
    results = run_full_analysis(max_stocks=50, top_n=15)
    print(f"\n=== 상위 추천 종목 ===")
    for pick in results['top_picks']:
        print(f"  {pick['rank']:2d}. {pick['ticker']:6s} | "
              f"점수: {pick['final_score']:5.1f} | "
              f"등급: {pick['grade']} | "
              f"1일 상승확률: {pick['rise_probability_1d']:.0f}% | "
              f"5일 상승확률: {pick['rise_probability_5d']:.0f}% | "
              f"{pick['recommendation']}")
