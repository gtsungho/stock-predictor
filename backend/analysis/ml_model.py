"""
머신러닝 예측 모듈
XGBoost + Random Forest 앙상블로 단기 주가 상승 확률 예측
"""
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import RobustScaler
from sklearn.metrics import accuracy_score, f1_score
from sklearn.utils.class_weight import compute_sample_weight
import warnings
import joblib
from pathlib import Path

warnings.filterwarnings('ignore')

MODEL_DIR = Path(__file__).parent.parent / "models"
MODEL_DIR.mkdir(exist_ok=True)


def create_features(df: pd.DataFrame) -> pd.DataFrame:
    """ML용 피처 엔지니어링"""
    feat = pd.DataFrame(index=df.index)

    close = df['Close']
    high = df['High']
    low = df['Low']
    volume = df['Volume']
    open_ = df['Open']

    # === 수익률 피처 ===
    for period in [1, 2, 3, 5, 10, 20]:
        feat[f'return_{period}d'] = close.pct_change(period)

    # === 이동평균 대비 ===
    for period in [5, 10, 20, 50]:
        sma = close.rolling(period).mean()
        feat[f'close_sma{period}_ratio'] = close / sma - 1

    # === EMA 대비 ===
    for period in [9, 21]:
        ema = close.ewm(span=period).mean()
        feat[f'close_ema{period}_ratio'] = close / ema - 1

    # === 변동성 ===
    for period in [5, 10, 20]:
        feat[f'volatility_{period}d'] = close.pct_change().rolling(period).std()

    # === RSI ===
    for period in [6, 14]:
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(period).mean()
        loss = (-delta.clip(upper=0)).rolling(period).mean()
        rs = gain / loss.replace(0, np.nan)
        feat[f'rsi_{period}'] = 100 - (100 / (1 + rs))

    # === MACD ===
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    feat['macd'] = ema12 - ema26
    feat['macd_signal'] = feat['macd'].ewm(span=9).mean()
    feat['macd_hist'] = feat['macd'] - feat['macd_signal']

    # === 볼린저 밴드 ===
    sma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    feat['bb_upper_dist'] = (close - (sma20 + 2 * std20)) / close
    feat['bb_lower_dist'] = (close - (sma20 - 2 * std20)) / close
    feat['bb_width'] = (4 * std20) / sma20

    # === 거래량 피처 ===
    vol_ma20 = volume.rolling(20).mean()
    feat['volume_ratio_20'] = volume / vol_ma20.replace(0, np.nan)
    feat['volume_ratio_5'] = volume / volume.rolling(5).mean().replace(0, np.nan)
    feat['volume_change'] = volume.pct_change()

    # === 가격 위치 ===
    for period in [20, 50]:
        highest = high.rolling(period).max()
        lowest = low.rolling(period).min()
        feat[f'price_position_{period}'] = (close - lowest) / (highest - lowest).replace(0, np.nan)

    # === 캔들 피처 ===
    body = close - open_
    feat['candle_body'] = body / close
    feat['upper_shadow'] = (high - pd.concat([close, open_], axis=1).max(axis=1)) / close
    feat['lower_shadow'] = (pd.concat([close, open_], axis=1).min(axis=1) - low) / close

    # === ATR ===
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs()
    ], axis=1).max(axis=1)
    feat['atr_14'] = tr.rolling(14).mean() / close
    feat['atr_ratio'] = tr / tr.rolling(20).mean().replace(0, np.nan)

    # === 모멘텀 가속도 (Fix: 괄호 추가) ===
    ret_5 = close.pct_change(5)
    ret_10 = close.pct_change(10)
    feat['momentum_accel'] = (ret_5 - ret_10) / 2

    # === 요일 (원-핫 안 하고 sin/cos 인코딩) ===
    if hasattr(df.index, 'dayofweek'):
        dow = df.index.dayofweek
        feat['day_sin'] = np.sin(2 * np.pi * dow / 5)
        feat['day_cos'] = np.cos(2 * np.pi * dow / 5)

    # === 상대 강도 (자체 장기 추세 대비 단기 수익률) ===
    # 종목의 20일 평균 수익률 대비 최근 5일 수익률로 상대 강도 측정
    long_term_avg_return = close.pct_change(1).rolling(60).mean()
    short_term_return = close.pct_change(5) / 5  # 일평균 수익률로 변환
    feat['relative_strength'] = (short_term_return - long_term_avg_return) / close.pct_change(1).rolling(60).std().replace(0, np.nan)

    return feat


def create_labels(df: pd.DataFrame, horizon: int = 5, threshold: float = 0.02) -> pd.Series:
    """
    레이블 생성
    horizon일 후 threshold% 이상 상승하면 1, 아니면 0
    """
    future_return = df['Close'].shift(-horizon) / df['Close'] - 1
    labels = (future_return > threshold).astype(int)
    return labels


def train_model(df: pd.DataFrame, horizon: int = 5) -> dict:
    """개별 종목의 과거 데이터로 모델 훈련"""
    if len(df) < 100:
        return None

    features = create_features(df)
    labels_1d = create_labels(df, horizon=1, threshold=0.01)   # 1일 1% 상승
    labels_5d = create_labels(df, horizon=5, threshold=0.02)   # 5일 2% 상승

    models = {}
    for name, labels in [('1d', labels_1d), ('5d', labels_5d)]:
        # 결측치 제거
        valid = features.join(labels.rename('target')).dropna()
        if len(valid) < 60:
            continue

        X = valid.drop('target', axis=1)
        y = valid['target']

        # 시계열 분할
        train_size = int(len(X) * 0.8)
        X_train, X_test = X.iloc[:train_size], X.iloc[train_size:]
        y_train, y_test = y.iloc[:train_size], y.iloc[train_size:]

        if len(y_train.unique()) < 2 or len(y_test) < 10:
            continue

        # RobustScaler: 이상치에 더 강건한 스케일링
        scaler = RobustScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)

        # Random Forest (class_weight='balanced' 지원)
        rf = RandomForestClassifier(
            n_estimators=100,
            max_depth=6,
            min_samples_leaf=10,
            random_state=42,
            class_weight='balanced',
            n_jobs=-1,
        )
        rf.fit(X_train_scaled, y_train)

        # Gradient Boosting (class_weight 미지원 -> sample_weight 사용)
        gb = GradientBoostingClassifier(
            n_estimators=100,
            max_depth=4,
            min_samples_leaf=10,
            learning_rate=0.05,
            random_state=42,
        )
        sample_weights = compute_sample_weight('balanced', y_train)
        gb.fit(X_train_scaled, y_train, sample_weight=sample_weights)

        # 테스트 평가: 정확도 + F1-score
        rf_pred = rf.predict(X_test_scaled)
        gb_pred = gb.predict(X_test_scaled)
        rf_acc = accuracy_score(y_test, rf_pred)
        gb_acc = accuracy_score(y_test, gb_pred)
        rf_f1 = f1_score(y_test, rf_pred, zero_division=0)
        gb_f1 = f1_score(y_test, gb_pred, zero_division=0)

        models[name] = {
            'rf': rf,
            'gb': gb,
            'scaler': scaler,
            'feature_names': list(X.columns),
            'rf_accuracy': rf_acc,
            'gb_accuracy': gb_acc,
            'rf_f1': rf_f1,
            'gb_f1': gb_f1,
            'train_size': len(X_train),
            'positive_rate': y_train.mean(),
        }

    return models if models else None


def predict_stock(df: pd.DataFrame, models: dict = None) -> dict:
    """주식 상승 확률 예측"""
    if df.empty or len(df) < 50:
        return {'score': 0, 'signals': [], 'details': {}}

    # 모델이 없으면 훈련
    if models is None:
        models = train_model(df)

    if not models:
        return {'score': 0, 'signals': ['ML 모델 훈련 데이터 부족'], 'details': {}}

    features = create_features(df)
    last_features = features.iloc[-1:]

    score = 0
    signals = []
    details = {}

    for horizon_name, model_data in models.items():
        try:
            # 피처 정렬
            feat_names = model_data['feature_names']
            X = last_features[feat_names]

            # forward fill 후 남은 결측치만 0으로 대체
            if X.isna().any(axis=1).iloc[0]:
                X = X.ffill(axis=1).fillna(0)

            X_scaled = model_data['scaler'].transform(X)

            # 확률 예측
            rf_prob = model_data['rf'].predict_proba(X_scaled)[0]
            gb_prob = model_data['gb'].predict_proba(X_scaled)[0]

            # 앙상블 (정확도 가중 평균)
            rf_weight = model_data['rf_accuracy']
            gb_weight = model_data['gb_accuracy']
            total_weight = rf_weight + gb_weight

            if len(rf_prob) > 1 and len(gb_prob) > 1:
                ensemble_prob = (rf_prob[1] * rf_weight + gb_prob[1] * gb_weight) / total_weight
            else:
                ensemble_prob = 0.5

            details[f'ML_{horizon_name}_prob'] = round(ensemble_prob * 100, 1)
            details[f'ML_{horizon_name}_rf_acc'] = round(model_data['rf_accuracy'] * 100, 1)
            details[f'ML_{horizon_name}_gb_acc'] = round(model_data['gb_accuracy'] * 100, 1)
            details[f'ML_{horizon_name}_rf_f1'] = round(model_data.get('rf_f1', 0) * 100, 1)
            details[f'ML_{horizon_name}_gb_f1'] = round(model_data.get('gb_f1', 0) * 100, 1)

            # 점수 계산
            if ensemble_prob > 0.7:
                horizon_score = 25
                signals.append(f"ML {horizon_name}: 강한 상승 예측 ({ensemble_prob*100:.0f}%)")
            elif ensemble_prob > 0.6:
                horizon_score = 18
                signals.append(f"ML {horizon_name}: 상승 예측 ({ensemble_prob*100:.0f}%)")
            elif ensemble_prob > 0.5:
                horizon_score = 10
                signals.append(f"ML {horizon_name}: 약한 상승 ({ensemble_prob*100:.0f}%)")
            else:
                horizon_score = 0
                signals.append(f"ML {horizon_name}: 상승 미예측 ({ensemble_prob*100:.0f}%)")

            score += horizon_score

        except Exception as e:
            signals.append(f"ML {horizon_name} 예측 오류: {str(e)[:50]}")

    # 정규화 (0-100, 두 horizon 합산 최대 50이므로 비율로 계산)
    normalized_score = max(0, min(100, (score / 50) * 100))

    return {
        'score': round(normalized_score, 2),
        'signals': signals,
        'details': details,
    }


def get_feature_importance(models: dict, top_n: int = 10) -> dict:
    """주요 피처 중요도"""
    importance = {}
    for horizon_name, model_data in models.items():
        feat_names = model_data['feature_names']
        rf_imp = model_data['rf'].feature_importances_
        gb_imp = model_data['gb'].feature_importances_

        avg_imp = (rf_imp + gb_imp) / 2
        top_idx = np.argsort(avg_imp)[-top_n:][::-1]

        importance[horizon_name] = [
            {'feature': feat_names[i], 'importance': round(avg_imp[i], 4)}
            for i in top_idx
        ]

    return importance
