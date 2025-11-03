"""
XGBoost 모델 학습 스크립트

현재 데이터에서 추출 가능한 특징으로 학습:
- 시간 특징: 시간, 요일, 월, 주차, 주말
- 충전 패턴: 충전량, 충전시간, SOC 변화
- 회원 특징: 개인/법인 비율
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

import pandas as pd
import logging

from app.prediction.xgboost_prediction_engine import XGBoostPredictionEngine

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_and_preprocess_data(file_path: str) -> pd.DataFrame:
    """데이터 로드 및 전처리"""
    logger.info(f"데이터 로드 중: {file_path}")
    
    # UTF-8 인코딩으로 읽기
    df = pd.read_csv(file_path, encoding='utf-8')
    logger.info(f"✓ 데이터 로드 완료: {len(df):,}개 레코드")
    
    # 날짜 변환
    df['충전시작일시'] = pd.to_datetime(df['충전시작일시'], errors='coerce')
    df['충전종료일시'] = pd.to_datetime(df['충전종료일시'], errors='coerce')
    
    # 결측값 제거
    df = df.dropna(subset=['충전시작일시'])
    logger.info(f"✓ 결측값 제거 후: {len(df):,}개 레코드")
    
    # 순간최고전력 변환
    df['순간최고전력'] = pd.to_numeric(df['순간최고전력'], errors='coerce')
    df = df.dropna(subset=['순간최고전력'])
    df = df[df['순간최고전력'] > 0]
    df = df[df['순간최고전력'] <= 200]
    logger.info(f"✓ 이상값 제거 후: {len(df):,}개 레코드")
    
    # 충전량 변환
    if '충전량(kWh)' in df.columns:
        df['충전량(kWh)'] = pd.to_numeric(df['충전량(kWh)'], errors='coerce')
    
    # 날짜 범위 확인
    date_min = df['충전시작일시'].min()
    date_max = df['충전시작일시'].max()
    logger.info(f"✓ 데이터 기간: {date_min} ~ {date_max}")
    
    return df


def train_xgboost_model(
    data_path: str,
    model_save_path: str = 'app/prediction/models/xgboost_trained',
    validation_split: float = 0.2
):
    """
    XGBoost 모델 학습 메인 함수
    
    Args:
        data_path: 충전 데이터 CSV 경로
        model_save_path: 학습된 모델 저장 경로
        validation_split: 검증 데이터 비율
    """
    logger.info("=" * 80)
    logger.info("XGBoost 모델 학습 시작")
    logger.info("=" * 80)
    
    # 1. 데이터 로드
    df = load_and_preprocess_data(data_path)
    
    # 2. XGBoost 엔진 초기화
    logger.info("\n" + "=" * 80)
    logger.info("XGBoost 모델 초기화")
    logger.info("=" * 80)
    
    xgb_engine = XGBoostPredictionEngine()
    
    # 3. 모델 학습
    logger.info("\n" + "=" * 80)
    logger.info("모델 학습 시작")
    logger.info("=" * 80)
    
    history = xgb_engine.train_model(
        training_data=df,
        validation_split=validation_split
    )
    
    # 4. 학습 결과 출력
    if history.get('success'):
        logger.info("\n" + "=" * 80)
        logger.info("✅ 학습 완료!")
        logger.info("=" * 80)
        logger.info(f"Train R² Score: {history['train_r2_score']:.4f}")
        logger.info(f"Validation R² Score: {history['val_r2_score']:.4f}")
        logger.info(f"Train MAE: {history['train_mae']:.2f}kW")
        logger.info(f"Validation MAE: {history['val_mae']:.2f}kW")
        logger.info(f"특징 수: {history['n_features']}")
        logger.info(f"학습 샘플 수: {history['n_samples']}")
        
        # 특징 중요도 출력
        logger.info("\n특징 중요도 (상위 10개):")
        feature_importance = history['feature_importance']
        sorted_features = sorted(
            feature_importance.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:10]
        
        for i, (feature, importance) in enumerate(sorted_features, 1):
            logger.info(f"  {i}. {feature}: {importance:.4f}")
        
        # 5. 모델 저장
        logger.info(f"\n모델 저장 중: {model_save_path}")
        xgb_engine.save_model(model_save_path)
        logger.info("✓ 모델 저장 완료!")
        
        # 6. 테스트 예측
        logger.info("\n" + "=" * 80)
        logger.info("테스트 예측")
        logger.info("=" * 80)
        
        # 최근 데이터로 테스트
        recent_data = df.tail(1000)
        test_prediction = xgb_engine.predict_contract_power(
            data=recent_data,
            station_id="TEST_XGBOOST",
            charger_type="급속충전기 (DC)"
        )
        
        logger.info(f"예측 결과: {test_prediction.final_prediction}kW")
        logger.info(f"실제 P95: {recent_data['순간최고전력'].quantile(0.95):.1f}kW")
        logger.info(f"앙상블 방법: {test_prediction.ensemble_method}")
        logger.info(f"불확실성: ±{test_prediction.uncertainty:.1f}kW")
        
        return xgb_engine, history
    
    else:
        logger.error(f"\n❌ 학습 실패: {history.get('error')}")
        return None, history


if __name__ == "__main__":
    # 데이터 경로
    DATA_PATH = r'C:\Users\fordr\Desktop\power-demand-prediciton-platform\data\raw\충전이력리스트_급속_202409-202507.csv'
    
    # 모델 저장 경로
    MODEL_SAVE_PATH = 'app/prediction/models/xgboost_trained'
    
    # 학습 실행
    try:
        xgb_engine, history = train_xgboost_model(
            data_path=DATA_PATH,
            model_save_path=MODEL_SAVE_PATH,
            validation_split=0.2
        )
        
        if xgb_engine:
            print("\n" + "=" * 80)
            print("🎉 XGBoost 모델 학습 및 저장 완료!")
            print("=" * 80)
            print(f"모델 경로: {MODEL_SAVE_PATH}")
            print("\n다음 명령어로 모델을 사용할 수 있습니다:")
            print("```python")
            print("from app.prediction.xgboost_prediction_engine import XGBoostPredictionEngine")
            print(f"xgb_engine = XGBoostPredictionEngine(model_path='{MODEL_SAVE_PATH}')")
            print("prediction = xgb_engine.predict_contract_power(data, station_id)")
            print("```")
    
    except Exception as e:
        logger.error(f"학습 중 오류 발생: {e}", exc_info=True)
        print(f"\n❌ 학습 실패: {e}")
