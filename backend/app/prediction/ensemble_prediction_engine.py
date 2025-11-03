"""
앙상블 예측 엔진 - LSTM + XGBoost 결합

특허 명세서 Phase 3:
- LSTM: 시계열 패턴 학습 (Monte Carlo Dropout으로 불확실성 추정)
- XGBoost: 내부 특징 기반 예측 (충전 패턴, 시간 특성)
- 앙상블: 가중 평균 + 스테이션 성숙도 기반 동적 가중치
"""

import logging
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, Literal
from dataclasses import dataclass
from enum import Enum

from .lstm_prediction_engine import LSTMPredictionEngine
from .xgboost_prediction_engine import XGBoostPredictionEngine


class StationMaturity(Enum):
    """스테이션 성숙도 분류"""
    NEW = "new"  # < 500 sessions
    DEVELOPING = "developing"  # 500-1000 sessions
    MATURE = "mature"  # > 1000 sessions


@dataclass
class MaturityClassification:
    """성숙도 분류 결과"""
    maturity: StationMaturity
    session_count: int
    lstm_weight: float  # LSTM 예측 가중치
    xgboost_weight: float  # XGBoost 예측 가중치
    reasoning: str  # 가중치 선택 이유


@dataclass
class EnsemblePrediction:
    """앙상블 예측 결과"""
    # 기본 예측
    final_prediction_kw: float  # 앙상블 최종 예측 (P95 기준)
    uncertainty_kw: float  # 불확실성 (±)
    
    # 개별 모델 예측
    lstm_prediction_kw: float
    lstm_uncertainty_kw: float
    xgboost_prediction_kw: float
    xgboost_uncertainty_kw: float
    
    # 가중치
    lstm_weight: float
    xgboost_weight: float
    
    # 스테이션 정보
    maturity: MaturityClassification
    
    # 분포 (Monte Carlo 샘플)
    prediction_distribution: np.ndarray  # shape: (n_samples,)
    
    # 메타 정보
    ensemble_method: Literal["weighted_average", "lstm_only", "xgboost_only"]
    confidence_score: float  # 0-1


class EnsemblePredictionEngine:
    """
    LSTM + XGBoost 앙상블 예측 엔진
    
    Phase 3 핵심 기능:
    1. LSTM + XGBoost 가중 평균
    2. 스테이션 성숙도 기반 동적 가중치
    3. Transfer Learning 준비 (new stations)
    """
    
    def __init__(
        self,
        lstm_model_path: str = "app/prediction/models/lstm_trained",
        xgboost_model_path: str = "app/prediction/models/xgboost_trained",
        use_dynamic_weights: bool = True
    ):
        """
        앙상블 엔진 초기화
        
        Args:
            lstm_model_path: LSTM 모델 경로
            xgboost_model_path: XGBoost 모델 경로
            use_dynamic_weights: 동적 가중치 사용 여부 (False면 고정 0.6/0.4)
        """
        self.logger = logging.getLogger(__name__)
        self.use_dynamic_weights = use_dynamic_weights
        
        # LSTM 엔진 로드
        try:
            self.lstm_engine = LSTMPredictionEngine(model_path=lstm_model_path)
            self.logger.info(f"✓ LSTM engine loaded from {lstm_model_path}")
        except Exception as e:
            self.logger.error(f"Failed to load LSTM engine: {e}")
            self.lstm_engine = None
        
        # XGBoost 엔진 로드
        try:
            self.xgboost_engine = XGBoostPredictionEngine(model_path=xgboost_model_path)
            self.logger.info(f"✓ XGBoost engine loaded from {xgboost_model_path}")
        except Exception as e:
            self.logger.error(f"Failed to load XGBoost engine: {e}")
            self.xgboost_engine = None
        
        # 성숙도 기준
        self.maturity_thresholds = {
            "new": 500,  # < 500 sessions
            "developing": 1000,  # 500-1000 sessions
            "mature": float('inf')  # > 1000 sessions
        }
        
        # 성숙도별 기본 가중치
        self.default_weights = {
            StationMaturity.NEW: {
                "lstm": 0.3,  # 데이터 부족 → LSTM 신뢰도 낮음
                "xgboost": 0.7  # 전이학습 + 일반 패턴 활용
            },
            StationMaturity.DEVELOPING: {
                "lstm": 0.5,  # 균형
                "xgboost": 0.5
            },
            StationMaturity.MATURE: {
                "lstm": 0.6,  # 데이터 충분 → LSTM 시계열 우세
                "xgboost": 0.4
            }
        }
    
    def classify_station_maturity(
        self,
        station_data: pd.DataFrame
    ) -> MaturityClassification:
        """
        스테이션 성숙도 분류
        
        Args:
            station_data: 충전소 데이터 (충전 세션 기록)
            
        Returns:
            MaturityClassification: 분류 결과
        """
        session_count = len(station_data)
        
        # 성숙도 판별
        if session_count < self.maturity_thresholds["new"]:
            maturity = StationMaturity.NEW
            reasoning = (
                f"신규 충전소 ({session_count} sessions < 500). "
                "전이학습 활용 예정 - XGBoost 가중치 높임"
            )
        elif session_count < self.maturity_thresholds["developing"]:
            maturity = StationMaturity.DEVELOPING
            reasoning = (
                f"발전 단계 충전소 ({session_count} sessions). "
                "LSTM + XGBoost 균형 활용"
            )
        else:
            maturity = StationMaturity.MATURE
            reasoning = (
                f"성숙 충전소 ({session_count} sessions > 1000). "
                "충분한 시계열 데이터 - LSTM 가중치 높임"
            )
        
        # 가중치 할당
        weights = self.default_weights[maturity]
        
        return MaturityClassification(
            maturity=maturity,
            session_count=session_count,
            lstm_weight=weights["lstm"],
            xgboost_weight=weights["xgboost"],
            reasoning=reasoning
        )
    
    def predict_contract_power(
        self,
        station_data: pd.DataFrame,
        station_id: str,
        n_iterations: int = 1000,
        manual_weights: Optional[Tuple[float, float]] = None
    ) -> EnsemblePrediction:
        """
        앙상블 예측 실행
        
        Args:
            station_data: 충전소 데이터
            station_id: 충전소 ID
            n_iterations: Monte Carlo 반복 횟수
            manual_weights: 수동 가중치 (lstm_weight, xgboost_weight)
            
        Returns:
            EnsemblePrediction: 앙상블 예측 결과
        """
        try:
            # 1. 스테이션 성숙도 분류
            maturity = self.classify_station_maturity(station_data)
            self.logger.info(
                f"Station {station_id} maturity: {maturity.maturity.value} "
                f"({maturity.session_count} sessions)"
            )
            
            # 2. LSTM 예측 (Monte Carlo Dropout)
            lstm_prediction_kw = 0.0
            lstm_uncertainty_kw = 0.0
            lstm_distribution = None
            
            if self.lstm_engine:
                try:
                    # LSTM 예측 - predict_contract_power 사용
                    lstm_result = self.lstm_engine.predict_contract_power(
                        data=station_data,
                        station_id=station_id
                    )
                    
                    # EnsemblePrediction 객체에서 값 추출
                    lstm_prediction_kw = lstm_result.final_prediction
                    lstm_uncertainty_kw = lstm_result.uncertainty
                    
                    # 분포 추출 (visualization_data에서)
                    if hasattr(lstm_result, 'visualization_data'):
                        viz_data = lstm_result.visualization_data
                        if viz_data and 'distribution' in viz_data:
                            lstm_distribution = np.array(viz_data['distribution'])
                    
                    # 또는 Monte Carlo 직접 호출
                    if lstm_distribution is None:
                        # 전력 데이터 추출
                        power_col = None
                        for col in ['순간최고전력', 'max_power', '전력']:
                            if col in station_data.columns:
                                power_col = col
                                break
                        
                        if power_col:
                            power_data = pd.to_numeric(
                                station_data[power_col], 
                                errors='coerce'
                            ).dropna().values
                            
                            lstm_distribution = self.lstm_engine.predict_with_uncertainty(
                                data=station_data,
                                power_data=power_data,
                                n_iterations=n_iterations
                            )
                            lstm_prediction_kw = float(np.percentile(lstm_distribution, 95))
                            lstm_uncertainty_kw = float(np.std(lstm_distribution))
                    
                    self.logger.info(
                        f"LSTM prediction: {lstm_prediction_kw:.2f}kW "
                        f"(±{lstm_uncertainty_kw:.2f}kW)"
                    )
                except Exception as e:
                    self.logger.error(f"LSTM prediction failed: {e}")
                    lstm_distribution = None
            
            # 3. XGBoost 예측
            xgboost_prediction_kw = 0.0
            xgboost_uncertainty_kw = 0.0
            xgboost_distribution = None
            
            if self.xgboost_engine:
                try:
                    xgb_result = self.xgboost_engine.predict_contract_power(
                        data=station_data,
                        station_id=station_id
                    )
                    
                    # EnsemblePrediction 객체에서 값 추출
                    xgboost_prediction_kw = xgb_result.final_prediction
                    xgboost_uncertainty_kw = xgb_result.uncertainty
                    
                    # 분포 생성 (XGBoost는 단일 예측이므로 정규분포로 근사)
                    xgboost_distribution = np.random.normal(
                        xgboost_prediction_kw,
                        xgboost_uncertainty_kw,
                        n_iterations
                    )
                    
                    self.logger.info(
                        f"XGBoost prediction: {xgboost_prediction_kw:.2f}kW "
                        f"(±{xgboost_uncertainty_kw:.2f}kW)"
                    )
                except Exception as e:
                    self.logger.error(f"XGBoost prediction failed: {e}", exc_info=True)
                    xgboost_distribution = None
            
            # 4. 가중치 결정
            if manual_weights:
                lstm_weight, xgboost_weight = manual_weights
                ensemble_method = "weighted_average"
                self.logger.info(f"Using manual weights: LSTM={lstm_weight}, XGBoost={xgboost_weight}")
            elif not self.use_dynamic_weights:
                lstm_weight, xgboost_weight = 0.6, 0.4
                ensemble_method = "weighted_average"
                self.logger.info("Using fixed weights: LSTM=0.6, XGBoost=0.4")
            else:
                lstm_weight = maturity.lstm_weight
                xgboost_weight = maturity.xgboost_weight
                ensemble_method = "weighted_average"
                self.logger.info(
                    f"Using dynamic weights (maturity-based): "
                    f"LSTM={lstm_weight}, XGBoost={xgboost_weight}"
                )
            
            # 5. 앙상블 분포 생성
            prediction_distribution = self._create_ensemble_distribution(
                lstm_distribution=lstm_distribution,
                xgboost_distribution=xgboost_distribution,
                lstm_weight=lstm_weight,
                xgboost_weight=xgboost_weight,
                n_samples=n_iterations
            )
            
            # 6. 최종 예측 (분포의 P95)
            final_prediction_kw = float(np.percentile(prediction_distribution, 95))
            uncertainty_kw = float(np.std(prediction_distribution))
            
            # 7. 신뢰도 계산
            confidence_score = self._calculate_confidence(
                lstm_available=(lstm_distribution is not None),
                xgboost_available=(xgboost_distribution is not None),
                session_count=maturity.session_count,
                prediction_std=uncertainty_kw
            )
            
            self.logger.info(
                f"Ensemble prediction: {final_prediction_kw:.2f}kW "
                f"(±{uncertainty_kw:.2f}kW, confidence={confidence_score:.2%})"
            )
            
            return EnsemblePrediction(
                final_prediction_kw=final_prediction_kw,
                uncertainty_kw=uncertainty_kw,
                lstm_prediction_kw=lstm_prediction_kw,
                lstm_uncertainty_kw=lstm_uncertainty_kw,
                xgboost_prediction_kw=xgboost_prediction_kw,
                xgboost_uncertainty_kw=xgboost_uncertainty_kw,
                lstm_weight=lstm_weight,
                xgboost_weight=xgboost_weight,
                maturity=maturity,
                prediction_distribution=prediction_distribution,
                ensemble_method=ensemble_method,
                confidence_score=confidence_score
            )
            
        except Exception as e:
            self.logger.error(f"Ensemble prediction failed: {e}", exc_info=True)
            raise
    
    def _create_ensemble_distribution(
        self,
        lstm_distribution: Optional[np.ndarray],
        xgboost_distribution: Optional[np.ndarray],
        lstm_weight: float,
        xgboost_weight: float,
        n_samples: int
    ) -> np.ndarray:
        """
        앙상블 분포 생성 (가중 평균)
        
        Args:
            lstm_distribution: LSTM 예측 분포 (Monte Carlo samples)
            xgboost_distribution: XGBoost 예측 분포
            lstm_weight: LSTM 가중치
            xgboost_weight: XGBoost 가중치
            n_samples: 샘플 수
            
        Returns:
            np.ndarray: 앙상블 분포
        """
        # 둘 다 있으면 가중 평균
        if lstm_distribution is not None and xgboost_distribution is not None:
            # 샘플 수 맞추기
            lstm_dist = np.array(lstm_distribution)
            xgb_dist = np.array(xgboost_distribution)
            
            # 샘플 수가 다르면 리샘플링
            if len(lstm_dist) != len(xgb_dist):
                min_len = min(len(lstm_dist), len(xgb_dist))
                lstm_dist = lstm_dist[:min_len]
                xgb_dist = xgb_dist[:min_len]
            
            # 가중 평균
            ensemble_dist = lstm_weight * lstm_dist + xgboost_weight * xgb_dist
            return ensemble_dist
        
        # LSTM만 있으면
        elif lstm_distribution is not None:
            self.logger.warning("XGBoost distribution not available, using LSTM only")
            return np.array(lstm_distribution)
        
        # XGBoost만 있으면
        elif xgboost_distribution is not None:
            self.logger.warning("LSTM distribution not available, using XGBoost only")
            return np.array(xgboost_distribution)
        
        # 둘 다 없으면 (폴백)
        else:
            self.logger.error("Both distributions unavailable, using fallback")
            # 기본값으로 정규분포 생성
            return np.random.normal(50, 15, n_samples)
    
    def _calculate_confidence(
        self,
        lstm_available: bool,
        xgboost_available: bool,
        session_count: int,
        prediction_std: float
    ) -> float:
        """
        예측 신뢰도 계산
        
        Args:
            lstm_available: LSTM 예측 사용 가능 여부
            xgboost_available: XGBoost 예측 사용 가능 여부
            session_count: 세션 수
            prediction_std: 예측 표준편차
            
        Returns:
            float: 신뢰도 (0-1)
        """
        confidence = 0.5  # 기본값
        
        # 1. 모델 가용성 (최대 0.3)
        if lstm_available and xgboost_available:
            model_confidence = 0.3  # 둘 다 있으면 최고
        elif lstm_available or xgboost_available:
            model_confidence = 0.2  # 하나만 있으면 중간
        else:
            model_confidence = 0.0  # 둘 다 없으면 최저
        
        # 2. 데이터 양 (최대 0.4)
        if session_count > 1000:
            data_confidence = 0.4
        elif session_count > 500:
            data_confidence = 0.3
        elif session_count > 100:
            data_confidence = 0.2
        else:
            data_confidence = 0.1
        
        # 3. 불확실성 (최대 0.3)
        # 표준편차가 낮을수록 신뢰도 높음
        if prediction_std < 10:
            uncertainty_confidence = 0.3
        elif prediction_std < 20:
            uncertainty_confidence = 0.2
        elif prediction_std < 30:
            uncertainty_confidence = 0.1
        else:
            uncertainty_confidence = 0.05
        
        confidence = model_confidence + data_confidence + uncertainty_confidence
        return min(1.0, confidence)
    
    def to_dict(self, prediction: EnsemblePrediction) -> Dict[str, Any]:
        """
        앙상블 예측 결과를 딕셔너리로 변환
        
        Args:
            prediction: EnsemblePrediction 객체
            
        Returns:
            Dict: JSON 직렬화 가능한 딕셔너리
        """
        return {
            "success": True,
            
            # 최종 예측
            "final_prediction_kw": round(prediction.final_prediction_kw, 2),
            "uncertainty_kw": round(prediction.uncertainty_kw, 2),
            "p95_percentile": round(prediction.final_prediction_kw, 2),  # 레거시 호환
            
            # 개별 모델 예측
            "lstm_prediction": {
                "prediction_kw": round(prediction.lstm_prediction_kw, 2),
                "uncertainty_kw": round(prediction.lstm_uncertainty_kw, 2)
            },
            "xgboost_prediction": {
                "prediction_kw": round(prediction.xgboost_prediction_kw, 2),
                "uncertainty_kw": round(prediction.xgboost_uncertainty_kw, 2)
            },
            
            # 가중치
            "weights": {
                "lstm": round(prediction.lstm_weight, 2),
                "xgboost": round(prediction.xgboost_weight, 2)
            },
            
            # 스테이션 정보
            "station_maturity": {
                "level": prediction.maturity.maturity.value,
                "session_count": prediction.maturity.session_count,
                "reasoning": prediction.maturity.reasoning
            },
            
            # 메타 정보
            "ensemble_method": prediction.ensemble_method,
            "confidence_score": round(prediction.confidence_score, 2),
            
            # 분포 (저장용, 옵션)
            "method_details": {
                "prediction_distribution": prediction.prediction_distribution.tolist(),
                "distribution_stats": {
                    "mean": float(np.mean(prediction.prediction_distribution)),
                    "std": float(np.std(prediction.prediction_distribution)),
                    "p50": float(np.percentile(prediction.prediction_distribution, 50)),
                    "p95": float(np.percentile(prediction.prediction_distribution, 95)),
                    "p99": float(np.percentile(prediction.prediction_distribution, 99))
                }
            }
        }
