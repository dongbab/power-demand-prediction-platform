"""
LSTM 모델 학습 스크립트

실제 급속충전 데이터로 LSTM 모델을 학습합니다.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

import pandas as pd
import numpy as np
from datetime import datetime
import logging

from app.prediction.lstm_prediction_engine import LSTMPredictionEngine

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_charging_data(file_path: str) -> pd.DataFrame:
    """충전 이력 데이터 로드"""
    logger.info(f"데이터 로드 중: {file_path}")
    
    try:
        # UTF-8 인코딩으로 읽기
        df = pd.read_csv(file_path, encoding='utf-8')
        logger.info(f"✓ 데이터 로드 완료: {len(df):,}개 레코드")
        
        return df
    
    except Exception as e:
        logger.error(f"데이터 로드 실패: {e}")
        raise


def preprocess_for_training(df: pd.DataFrame) -> pd.DataFrame:
    """학습용 데이터 전처리"""
    logger.info("데이터 전처리 시작...")
    
    # 1. 필수 컬럼 확인
    required_cols = ['충전시작일시', '충전종료일시', '순간최고전력', '충전소ID']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"필수 컬럼 누락: {missing_cols}")
    
    # 2. 날짜 컬럼 변환
    df['충전시작일시'] = pd.to_datetime(df['충전시작일시'], errors='coerce')
    df['충전종료일시'] = pd.to_datetime(df['충전종료일시'], errors='coerce')
    
    # 3. 결측값 제거
    df = df.dropna(subset=['충전시작일시', '순간최고전력'])
    logger.info(f"✓ 결측값 제거 후: {len(df):,}개 레코드")
    
    # 4. 순간최고전력을 숫자로 변환
    df['순간최고전력'] = pd.to_numeric(df['순간최고전력'], errors='coerce')
    df = df.dropna(subset=['순간최고전력'])
    
    # 4-1. 충전량도 숫자로 변환
    if '충전량(kWh)' in df.columns:
        df['충전량(kWh)'] = pd.to_numeric(df['충전량(kWh)'], errors='coerce')
    
    # 5. 순간최고전력 이상값 제거
    df = df[df['순간최고전력'] > 0]
    df = df[df['순간최고전력'] <= 200]  # 급속충전기 최대 200kW
    logger.info(f"✓ 이상값 제거 후: {len(df):,}개 레코드")
    
    # 6. 날짜 범위 확인
    date_min = df['충전시작일시'].min()
    date_max = df['충전시작일시'].max()
    logger.info(f"✓ 데이터 기간: {date_min} ~ {date_max}")
    
    return df


def aggregate_hourly_data(df: pd.DataFrame, top_n_stations: int = 10) -> pd.DataFrame:
    """
    시간 단위로 데이터 집계
    
    Args:
        df: 원본 충전 데이터
        top_n_stations: 상위 N개 충전소만 사용 (학습 속도 향상)
    """
    logger.info("시간 단위 집계 시작...")
    
    # 1. 충전량이 많은 상위 충전소 선택
    station_usage = df.groupby('충전소ID')['순간최고전력'].agg(['count', 'mean'])
    station_usage = station_usage.sort_values('count', ascending=False)
    top_stations = station_usage.head(top_n_stations).index.tolist()
    
    logger.info(f"✓ 상위 {top_n_stations}개 충전소 선택:")
    for i, station in enumerate(top_stations, 1):
        count = station_usage.loc[station, 'count']
        mean_power = station_usage.loc[station, 'mean']
        logger.info(f"  {i}. {station}: {count:,}회 충전, 평균 {mean_power:.1f}kW")
    
    # 2. 선택된 충전소만 필터링
    df_filtered = df[df['충전소ID'].isin(top_stations)].copy()
    logger.info(f"✓ 필터링 후: {len(df_filtered):,}개 레코드")
    
    # 3. 시간 단위로 집계 (각 시간대의 최대 전력 사용)
    df_filtered['hour'] = df_filtered['충전시작일시'].dt.floor('H')
    
    hourly_data = df_filtered.groupby('hour').agg({
        '순간최고전력': ['max', 'mean', 'count'],
        '충전량(kWh)': 'sum'
    }).reset_index()
    
    # 컬럼명 단순화
    hourly_data.columns = ['timestamp', '순간최고전력', 'mean_power', 'session_count', '충전량(kWh)']
    
    # 4. 시간 인덱스 설정
    hourly_data = hourly_data.set_index('timestamp')
    hourly_data = hourly_data.sort_index()
    
    logger.info(f"✓ 시간 단위 집계 완료: {len(hourly_data):,}개 시간대")
    logger.info(f"  - 평균 전력: {hourly_data['순간최고전력'].mean():.1f}kW")
    logger.info(f"  - 최대 전력: {hourly_data['순간최고전력'].max():.1f}kW")
    logger.info(f"  - 표준편차: {hourly_data['순간최고전력'].std():.1f}kW")
    
    return hourly_data


def split_train_val(data: pd.DataFrame, val_ratio: float = 0.2):
    """학습/검증 데이터 분할"""
    split_idx = int(len(data) * (1 - val_ratio))
    
    train_data = data.iloc[:split_idx]
    val_data = data.iloc[split_idx:]
    
    logger.info(f"✓ 데이터 분할:")
    logger.info(f"  - 학습: {len(train_data):,}개 ({len(train_data)/len(data)*100:.1f}%)")
    logger.info(f"  - 검증: {len(val_data):,}개 ({len(val_data)/len(data)*100:.1f}%)")
    
    return train_data, val_data


def train_lstm_model(
    data_path: str,
    model_save_path: str = 'app/prediction/models/lstm_trained',
    top_n_stations: int = 10,
    epochs: int = 50,
    batch_size: int = 32
):
    """
    LSTM 모델 학습 메인 함수
    
    Args:
        data_path: 충전 데이터 CSV 경로
        model_save_path: 학습된 모델 저장 경로
        top_n_stations: 학습에 사용할 상위 충전소 수
        epochs: 학습 에포크
        batch_size: 배치 크기
    """
    logger.info("=" * 80)
    logger.info("LSTM 모델 학습 시작")
    logger.info("=" * 80)
    
    # 1. 데이터 로드
    df = load_charging_data(data_path)
    
    # 2. 전처리
    df = preprocess_for_training(df)
    
    # 3. 시간 단위 집계
    hourly_data = aggregate_hourly_data(df, top_n_stations=top_n_stations)
    
    # 4. 학습/검증 분할
    train_data, val_data = split_train_val(hourly_data, val_ratio=0.2)
    
    # 5. LSTM 엔진 초기화
    logger.info("\n" + "=" * 80)
    logger.info("LSTM 모델 학습 시작")
    logger.info("=" * 80)
    
    lstm_engine = LSTMPredictionEngine()
    
    # 6. 모델 학습
    history = lstm_engine.train_model(
        training_data=train_data,
        epochs=epochs,
        batch_size=batch_size,
        validation_split=0.2
    )
    
    # 7. 학습 결과 출력
    if history.get('success'):
        logger.info("\n" + "=" * 80)
        logger.info("✅ 학습 완료!")
        logger.info("=" * 80)
        logger.info(f"최종 Loss: {history['final_loss']:.4f}")
        logger.info(f"검증 Loss: {history['final_val_loss']:.4f}")
        logger.info(f"MAE: {history['final_mae']:.4f}")
        logger.info(f"학습 에포크: {history['epochs_trained']}")
        logger.info(f"학습 샘플 수: {history['training_samples']}")
        
        # 8. 모델 저장
        logger.info(f"\n모델 저장 중: {model_save_path}")
        lstm_engine.save_model(model_save_path)
        logger.info("✓ 모델 저장 완료!")
        
        # 9. 검증 데이터로 테스트
        logger.info("\n" + "=" * 80)
        logger.info("검증 데이터 테스트")
        logger.info("=" * 80)
        
        test_prediction = lstm_engine.predict_contract_power(
            data=val_data,
            station_id="TEST_VALIDATION",
            charger_type="급속충전기 (DC)"
        )
        
        logger.info(f"예측 결과: {test_prediction.final_prediction}kW")
        logger.info(f"실제 P95: {val_data['순간최고전력'].quantile(0.95):.1f}kW")
        logger.info(f"앙상블 방법: {test_prediction.ensemble_method}")
        logger.info(f"불확실성: ±{test_prediction.uncertainty:.1f}kW")
        
        return lstm_engine, history
    
    else:
        logger.error(f"\n❌ 학습 실패: {history.get('error')}")
        return None, history


if __name__ == "__main__":
    # 데이터 경로
    DATA_PATH = r'C:\Users\fordr\Desktop\power-demand-prediciton-platform\data\raw\충전이력리스트_급속_202409-202507.csv'
    
    # 모델 저장 경로
    MODEL_SAVE_PATH = 'app/prediction/models/lstm_trained'
    
    # 학습 실행
    try:
        lstm_engine, history = train_lstm_model(
            data_path=DATA_PATH,
            model_save_path=MODEL_SAVE_PATH,
            top_n_stations=10,  # 상위 10개 충전소
            epochs=50,          # 50 에포크
            batch_size=32       # 배치 크기 32
        )
        
        if lstm_engine:
            print("\n" + "=" * 80)
            print("🎉 LSTM 모델 학습 및 저장 완료!")
            print("=" * 80)
            print(f"모델 경로: {MODEL_SAVE_PATH}")
            print("\n다음 명령어로 모델을 사용할 수 있습니다:")
            print("```python")
            print("from app.prediction.lstm_prediction_engine import LSTMPredictionEngine")
            print(f"lstm_engine = LSTMPredictionEngine(model_path='{MODEL_SAVE_PATH}')")
            print("prediction = lstm_engine.predict_contract_power(data, station_id)")
            print("```")
    
    except Exception as e:
        logger.error(f"학습 중 오류 발생: {e}", exc_info=True)
        print(f"\n❌ 학습 실패: {e}")
