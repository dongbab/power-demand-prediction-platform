import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from scipy import stats
from scipy.stats import genextreme, gumbel_r, weibull_min
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from functools import lru_cache
from .dynamic_patterns import DynamicPatternAnalyzer, PatternFactors

warnings.filterwarnings("ignore")


@dataclass
class ModelPrediction:
    model_name: str
    predicted_value: float
    confidence_interval: Tuple[float, float]
    confidence_score: float
    method_details: Dict[str, Any]
    r_squared: Optional[float] = None
    rmse: Optional[float] = None


@dataclass
class EnsemblePrediction:
    final_prediction: int  # 제한 적용된 최종 예측값
    raw_prediction: float  # 제한 없는 원본 예측값
    model_predictions: List[ModelPrediction]
    ensemble_method: str
    weights: Dict[str, float]
    uncertainty: float
    visualization_data: Dict[str, Any]
    pattern_factors: Optional[PatternFactors] = None  # Dynamic pattern information
    method_comparison: Optional[Dict[str, Any]] = None  # Comparison between methods


class PredictionEngine:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.max_contract_power = 100  # 최대 계약 전력 100kW
        self.max_workers = 4  # 병렬 처리 스레드 수
        self._stats_cache = {}  # 기본 통계량 캐시
        self._pattern_cache = {}  # Pattern analysis cache
        
        # Dynamic pattern analyzer
        self.pattern_analyzer = DynamicPatternAnalyzer()
        

        # 충전기 타입별 최대 전력 제한
        self.charger_limits = {
            "완속충전기 (AC)": 7,  # 완속은 최대 7kW
            "급속충전기 (DC)": 100,  # 급속은 최대 100kW
            "미상": 50,  # 미상인 경우 보수적으로 50kW
        }

    def predict_contract_power(
        self, data: pd.DataFrame, station_id: str, charger_type: str = None
    ) -> EnsemblePrediction:
        start_time = time.time()

        if data.empty or "순간최고전력" not in data.columns:
            return self._fallback_prediction(station_id)

        # 데이터 전처리 및 기본 통계량 계산
        power_data = self._preprocess_data(data)

        if len(power_data) < 10:
            return self._fallback_prediction(station_id)

        # 기본 통계량 사전 계산 (캐싱)
        cache_key = hash(power_data.tobytes())
        if cache_key not in self._stats_cache:
            self._stats_cache[cache_key] = self._compute_base_statistics(power_data)

        base_stats = self._stats_cache[cache_key]
        
        # Dynamic pattern analysis (cached)
        pattern_cache_key = f"{station_id}_{hash(str(data.index.tolist()))}"
        if pattern_cache_key not in self._pattern_cache:
            self._pattern_cache[pattern_cache_key] = self.pattern_analyzer.analyze_patterns(data, station_id)
        
        pattern_factors = self._pattern_cache[pattern_cache_key]
        

        # Dynamic Pattern을 활용한 모델 실행
        model_predictions = []
        
        # Dynamic Pattern 기반 예측 추가
        if pattern_factors and pattern_factors.confidence > 0.4:
            pattern_prediction = self._dynamic_pattern_prediction(power_data, pattern_factors, base_stats)
            if pattern_prediction:
                model_predictions.append(pattern_prediction)
                self.logger.info(f"Station {station_id}: Added dynamic pattern prediction (confidence: {pattern_factors.confidence:.2f})")

        try:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # 모델 태스크 정의 - Dynamic Pattern 정보를 일부 모델에 전달
                tasks = {
                    executor.submit(
                        self._extreme_value_models_optimized, power_data, base_stats
                    ): "EVT",
                    executor.submit(
                        self._statistical_inference_models_optimized,
                        power_data,
                        base_stats,
                        pattern_factors,  # Pattern 정보 전달
                    ): "STAT",
                    executor.submit(self._time_series_models, data, pattern_factors): "TS",  # Pattern 정보 전달
                    executor.submit(
                        self._machine_learning_models_optimized, power_data, base_stats, pattern_factors
                    ): "ML",
                }

                # 결과 수집
                for future in as_completed(tasks, timeout=10):
                    try:
                        models = future.result()
                        if models:
                            model_predictions.extend(models)
                    except Exception as e:
                        model_type = tasks[future]
                        self.logger.warning(
                            f"{model_type} models failed for {station_id}: {e}"
                        )

        except Exception as e:
            self.logger.error(f"Parallel prediction failed for {station_id}: {e}")
            return self._fallback_prediction(station_id)

        # 최소한의 모델 결과가 있는지 확인
        if not model_predictions:
            return self._fallback_prediction(station_id)

        # 앙상블 예측 수행 (dynamic patterns 포함)
        result = self._ensemble_prediction(
            model_predictions, power_data, station_id, charger_type, pattern_factors
        )

        elapsed_time = time.time() - start_time
        self.logger.info(
            f"Prediction completed for {station_id} in {elapsed_time:.3f}s with {len(model_predictions)} models"
        )

        return result

    def _preprocess_data(self, data: pd.DataFrame) -> np.ndarray:
        power_col = "순간최고전력"

        # 결측값 및 이상값 제거 (벡터화된 연산)
        power_data = data[power_col].dropna()
        power_data = power_data[(power_data > 0) & (power_data <= 200)]

        # 극단적 이상값 제거 (IQR 방법) - 한 번에 계산
        q1, q3 = np.percentile(power_data, [25, 75])
        iqr = q3 - q1
        lower_bound = max(0, q1 - 1.5 * iqr)
        upper_bound = q3 + 1.5 * iqr

        power_data = power_data[
            (power_data >= lower_bound) & (power_data <= upper_bound)
        ]
        return power_data.values

    def _compute_base_statistics(self, power_data: np.ndarray) -> Dict[str, float]:
        return {
            "mean": np.mean(power_data),
            "median": np.median(power_data),
            "std": np.std(power_data, ddof=1),
            "mad": np.median(np.abs(power_data - np.median(power_data))),
            "q25": np.percentile(power_data, 25),
            "q75": np.percentile(power_data, 75),
            "q90": np.percentile(power_data, 90),
            "q95": np.percentile(power_data, 95),
            "q99": np.percentile(power_data, 99),
            "min": np.min(power_data),
            "max": np.max(power_data),
        }

    def _extreme_value_models_optimized(
        self, power_data: np.ndarray, base_stats: Dict[str, float]
    ) -> List[ModelPrediction]:
        models = []

        try:
            # 빠른 초기 참값 설정으로 최적화 속도 향상
            # 1. Generalized Extreme Value (GEV) Distribution
            gev_params = genextreme.fit(
                power_data, loc=base_stats["mean"], scale=base_stats["std"]
            )
            gev_prediction = genextreme.ppf(0.95, *gev_params)  # 95% 분위수
            
            # 비정상적인 예측값 검증 및 제한
            if not np.isfinite(gev_prediction) or gev_prediction < 0 or gev_prediction > 10000:
                self.logger.warning(f"GEV 예측값이 비정상적입니다: {gev_prediction}, 기본값으로 대체")
                gev_prediction = min(base_stats["q95"], 100)
            
            gev_ci = (base_stats["q90"], base_stats["q99"])  # 빠른 근사치

            models.append(
                ModelPrediction(
                    model_name="GEV_Distribution",
                    predicted_value=gev_prediction,
                    confidence_interval=gev_ci,
                    confidence_score=0.85,
                    method_details={
                        "distribution": "Generalized Extreme Value",
                        "parameters": gev_params,
                        "percentile": 95,
                        "description": "일반화 극값 분포를 사용한 극값 추정",
                    },
                )
            )

            # 2. Gumbel Distribution
            gumbel_params = gumbel_r.fit(
                power_data, loc=base_stats["mean"], scale=base_stats["std"]
            )
            gumbel_prediction = gumbel_r.ppf(0.95, *gumbel_params)
            
            # 비정상적인 예측값 검증 및 제한
            if not np.isfinite(gumbel_prediction) or gumbel_prediction < 0 or gumbel_prediction > 10000:
                self.logger.warning(f"Gumbel 예측값이 비정상적입니다: {gumbel_prediction}, 기본값으로 대체")
                gumbel_prediction = min(base_stats["q95"], 100)
            
            gumbel_ci = (
                base_stats.get("q85", base_stats["q90"] * 0.95),
                base_stats.get("q98", base_stats["q95"] * 1.02),
            )

            models.append(
                ModelPrediction(
                    model_name="Gumbel_Distribution",
                    predicted_value=gumbel_prediction,
                    confidence_interval=gumbel_ci,
                    confidence_score=0.80,
                    method_details={
                        "distribution": "Gumbel",
                        "parameters": gumbel_params,
                        "percentile": 95,
                        "description": "검벨 분포를 사용한 극값 추정",
                    },
                )
            )

            # 3. Block Maxima Method
            block_maxima = self._block_maxima_method(power_data)
            if block_maxima:
                models.append(block_maxima)

            # 4. Peak Over Threshold (POT) Method
            pot_result = self._peak_over_threshold_method(power_data)
            if pot_result:
                models.append(pot_result)

        except Exception as e:
            self.logger.warning(f"Extreme value models failed: {e}")

        return models

    def _statistical_inference_models_optimized(
        self, power_data: np.ndarray, base_stats: Dict[str, float], pattern_factors: Optional[PatternFactors] = None
    ) -> List[ModelPrediction]:
        models = []

        try:
            # 1. Bayesian Estimation (사전 계산된 통계량 사용)
            bayesian_result = self._bayesian_estimation_optimized(
                power_data, base_stats
            )
            if bayesian_result:
                models.append(bayesian_result)

            # 2. Bootstrap Confidence Interval (축소된 반복 횟수)
            bootstrap_result = self._bootstrap_method_optimized(
                power_data, base_stats, n_bootstrap=200
            )
            if bootstrap_result:
                models.append(bootstrap_result)

            # 3. 빠른 분위수 추정 (사전 계산된 값 사용)
            fast_percentile_result = ModelPrediction(
                model_name="Fast_Percentile_95",
                predicted_value=base_stats["q95"],
                confidence_interval=(base_stats["q90"], base_stats["q99"]),
                confidence_score=0.75,
                method_details={
                    "method": "Direct Percentile",
                    "percentile": 95,
                    "description": "사전 계산된 95% 분위수 사용",
                },
            )
            models.append(fast_percentile_result)

        except Exception as e:
            self.logger.warning(f"Statistical inference models failed: {e}")

        return models

    def _time_series_models(self, data: pd.DataFrame, pattern_factors: Optional[PatternFactors] = None) -> List[ModelPrediction]:
        models = []

        try:
            if "충전시작일시" in data.columns:
                # 월별 최대값 추출
                data_copy = data.copy()
                data_copy["충전시작일시"] = pd.to_datetime(
                    data_copy["충전시작일시"], errors="coerce"
                )
                data_copy = data_copy.dropna(subset=["충전시작일시", "순간최고전력"])

                # 월별 집계
                monthly_max = data_copy.groupby(
                    data_copy["충전시작일시"].dt.to_period("M")
                )["순간최고전력"].max()

                if len(monthly_max) >= 3:
                    # 1. Exponential Smoothing (Enhanced with patterns)
                    exp_smooth_result = self._exponential_smoothing(monthly_max.values, pattern_factors)
                    if exp_smooth_result:
                        models.append(exp_smooth_result)

                    # 2. Linear Trend Analysis (Enhanced with patterns)
                    trend_result = self._linear_trend_analysis(monthly_max.values, pattern_factors)
                    if trend_result:
                        models.append(trend_result)
                        
                    # 3. Pattern-Based Seasonal Adjustment
                    if pattern_factors and pattern_factors.confidence > 0.6:
                        seasonal_result = self._seasonal_pattern_prediction(monthly_max.values, pattern_factors)
                        if seasonal_result:
                            models.append(seasonal_result)

        except Exception as e:
            self.logger.warning(f"Time series models failed: {e}")

        return models

    def _machine_learning_models_optimized(
        self, power_data: np.ndarray, base_stats: Dict[str, float], pattern_factors: Optional[PatternFactors] = None
    ) -> List[ModelPrediction]:
        models = []

        try:
            # 1. Pattern-Enhanced Ensemble Percentile Method
            percentile_predictions = [
                base_stats["q90"],
                base_stats["q95"],
                base_stats.get("q98", base_stats["q95"] * 1.02),  # 근사치
                base_stats["q99"],
            ]
            
            # Pattern 정보를 활용한 가중치 조정
            weights = np.array([0.1, 0.3, 0.4, 0.2])
            if pattern_factors and pattern_factors.confidence > 0.6:
                # 패턴 신뢰도가 높으면 95%, 98% 분위수에 더 집중
                weights = np.array([0.05, 0.35, 0.45, 0.15])
            
            weighted_prediction = np.average(percentile_predictions, weights=weights)
            
            # Pattern adjustment 적용
            if pattern_factors and pattern_factors.confidence > 0.5:
                weighted_prediction = self.pattern_analyzer.apply_pattern_adjustment(
                    weighted_prediction, pattern_factors
                )

            confidence = 0.75
            if pattern_factors:
                confidence = min(0.85, 0.75 + pattern_factors.confidence * 0.1)

            models.append(
                ModelPrediction(
                    model_name="Pattern_Enhanced_Percentile_Ensemble",
                    predicted_value=weighted_prediction,
                    confidence_interval=(
                        base_stats.get("q85", base_stats["q90"] * 0.95),
                        base_stats["q99"],
                    ),
                    confidence_score=confidence,
                    method_details={
                        "method": "Pattern-Enhanced Percentile Ensemble",
                        "percentiles": [90, 95, 98, 99],
                        "weights": weights.tolist(),
                        "pattern_applied": pattern_factors is not None,
                        "description": "패턴 정보가 강화된 분위수 앙상블 예측",
                    },
                )
            )

            # 2. Robust Statistics (사전 계산된 값 사용)
            robust_result = self._robust_statistics_method_optimized(base_stats)
            if robust_result:
                models.append(robust_result)

        except Exception as e:
            self.logger.warning(f"Machine learning models failed: {e}")

        return models
    
    def _dynamic_pattern_prediction(self, power_data: np.ndarray, pattern_factors: PatternFactors, 
                                   base_stats: Dict[str, float]) -> Optional[ModelPrediction]:
        """
        Generate prediction based on dynamic pattern analysis.
        
        This model uses learned patterns from actual data to make predictions,
        making it more adaptive than static models.
        """
        try:
            # Base prediction using 95th percentile
            base_prediction = base_stats["q95"]
            
            # Apply pattern adjustments
            adjusted_prediction = self.pattern_analyzer.apply_pattern_adjustment(
                base_prediction, pattern_factors
            )
            
            # Calculate confidence interval based on pattern quality
            pattern_confidence = pattern_factors.confidence
            spread = base_prediction * (0.1 + (1 - pattern_confidence) * 0.2)  # More uncertainty for lower confidence
            
            ci_lower = adjusted_prediction - spread
            ci_upper = adjusted_prediction + spread
            
            # Enhanced confidence score based on multiple factors
            model_confidence = min(0.95, pattern_confidence * 1.2)  # Boost confidence for high-quality patterns
            
            return ModelPrediction(
                model_name="Dynamic_Pattern_Adaptive",
                predicted_value=adjusted_prediction,
                confidence_interval=(ci_lower, ci_upper),
                confidence_score=model_confidence,
                method_details={
                    "method": "Dynamic Pattern Analysis",
                    "base_prediction": base_prediction,
                    "adjusted_prediction": adjusted_prediction,
                    "pattern_confidence": pattern_confidence,
                    "seasonal_applied": len(pattern_factors.seasonal_factors) > 0,
                    "weekly_applied": len(pattern_factors.weekly_factors) > 0,
                    "trend_applied": abs(pattern_factors.trend_factor - 1.0) > 0.05,
                    "data_quality": pattern_factors.data_quality,
                    "description": "실제 데이터 패턴을 학습하여 적응형 예측 수행",
                },
            )
            
        except Exception as e:
            self.logger.warning(f"Dynamic pattern prediction failed: {e}")
            return None
    
    def _pattern_enhanced_bayesian(self, power_data: np.ndarray, base_stats: Dict[str, float], 
                                 pattern_factors: PatternFactors) -> Optional[ModelPrediction]:
        """
        Bayesian estimation enhanced with pattern information.
        """
        try:
            n = len(power_data)
            sample_mean = base_stats["mean"]
            sample_std = base_stats["std"]
            
            # Use pattern factors to inform prior
            if pattern_factors.trend_factor > 1.05:  # Increasing trend
                prior_mean = sample_mean * pattern_factors.trend_factor
            elif pattern_factors.trend_factor < 0.95:  # Decreasing trend
                prior_mean = sample_mean * pattern_factors.trend_factor
            else:
                prior_mean = sample_mean
            
            # Pattern confidence affects prior strength
            prior_strength = pattern_factors.confidence * 2.0  # Convert to effective sample size
            prior_std = sample_std / np.sqrt(prior_strength)
            
            # Bayesian update
            posterior_precision = 1 / (prior_std**2) + n / (sample_std**2)
            posterior_var = 1 / posterior_precision
            posterior_mean = (
                prior_mean / (prior_std**2) + n * sample_mean / (sample_std**2)
            ) * posterior_var
            posterior_std = np.sqrt(posterior_var)
            
            # 95% quantile prediction
            from scipy import stats
            prediction = stats.norm.ppf(0.95, posterior_mean, posterior_std)
            
            # Apply final pattern adjustment
            adjusted_prediction = self.pattern_analyzer.apply_pattern_adjustment(
                prediction, pattern_factors
            )
            
            # Confidence interval
            ci_lower = stats.norm.ppf(0.05, posterior_mean, posterior_std)
            ci_upper = stats.norm.ppf(0.99, posterior_mean, posterior_std)
            
            return ModelPrediction(
                model_name="Pattern_Enhanced_Bayesian",
                predicted_value=adjusted_prediction,
                confidence_interval=(ci_lower, ci_upper),
                confidence_score=min(0.90, 0.7 + pattern_factors.confidence * 0.2),
                method_details={
                    "method": "Pattern-Enhanced Bayesian",
                    "prior_mean": prior_mean,
                    "posterior_mean": posterior_mean,
                    "pattern_confidence": pattern_factors.confidence,
                    "trend_factor": pattern_factors.trend_factor,
                    "description": "패턴 정보를 활용한 베이지안 추정",
                },
            )
            
        except Exception as e:
            self.logger.warning(f"Pattern-enhanced Bayesian failed: {e}")
            return None
    
    def _seasonal_pattern_prediction(self, monthly_data: np.ndarray, 
                                   pattern_factors: PatternFactors) -> Optional[ModelPrediction]:
        """
        Pure seasonal pattern-based prediction using learned patterns.
        """
        try:
            if not pattern_factors.seasonal_factors:
                return None
                
            # 기본값으로 최근 데이터 평균 사용
            base_value = np.mean(monthly_data[-3:]) if len(monthly_data) >= 3 else np.mean(monthly_data)
            
            # 다음 달의 계절 요인 적용
            next_month = (datetime.now().month % 12) + 1
            seasonal_factor = pattern_factors.seasonal_factors.get(next_month, 1.0)
            
            # 트렌드 적용
            prediction = base_value * seasonal_factor * pattern_factors.trend_factor
            
            # 신뢰구간: 계절 변동성을 반영
            seasonal_values = list(pattern_factors.seasonal_factors.values())
            seasonal_std = np.std(seasonal_values)
            
            spread = base_value * seasonal_std * 0.5  # 계절 변동성 반영
            ci_lower = prediction - spread
            ci_upper = prediction + spread
            
            # 신뢰도: 패턴 품질과 계절성 일관성에 기반
            seasonal_consistency = 1.0 - (seasonal_std / np.mean(seasonal_values))
            confidence = min(0.88, pattern_factors.confidence * seasonal_consistency)
            
            return ModelPrediction(
                model_name="Seasonal_Pattern_Prediction",
                predicted_value=prediction,
                confidence_interval=(ci_lower, ci_upper),
                confidence_score=confidence,
                method_details={
                    "method": "Pure Seasonal Pattern Analysis",
                    "base_value": base_value,
                    "seasonal_factor": seasonal_factor,
                    "trend_factor": pattern_factors.trend_factor,
                    "target_month": next_month,
                    "seasonal_consistency": seasonal_consistency,
                    "description": f"학습된 계절 패턴을 활용한 {next_month}월 예측",
                },
            )
            
        except Exception as e:
            self.logger.warning(f"Seasonal pattern prediction failed: {e}")
            return None

    def _block_maxima_method(
        self, power_data: np.ndarray, block_size: int = 30
    ) -> Optional[ModelPrediction]:
        try:
            if len(power_data) < block_size * 2:
                return None

            # 블록별 최대값 추출
            blocks = [
                power_data[i : i + block_size]
                for i in range(0, len(power_data), block_size)
            ]
            block_maxima = [
                np.max(block) for block in blocks if len(block) == block_size
            ]

            if len(block_maxima) < 3:
                return None

            # GEV 분포에 피팅
            params = genextreme.fit(block_maxima)
            prediction = genextreme.ppf(0.95, *params)
            
            # 비정상적인 예측값 검증 및 제한
            if not np.isfinite(prediction) or prediction < 0 or prediction > 10000:
                self.logger.warning(f"Block Maxima GEV 예측값이 비정상적입니다: {prediction}, 기본값으로 대체")
                prediction = min(np.percentile(block_maxima, 95), 100)
            
            ci = genextreme.interval(0.9, *params)
            
            # CI 값들도 검증
            if not (np.isfinite(ci[0]) and np.isfinite(ci[1])):
                ci = (prediction * 0.9, prediction * 1.1)

            return ModelPrediction(
                model_name="Block_Maxima_GEV",
                predicted_value=prediction,
                confidence_interval=ci,
                confidence_score=0.85,
                method_details={
                    "method": "Block Maxima with GEV",
                    "block_size": block_size,
                    "num_blocks": len(block_maxima),
                    "gev_parameters": params,
                    "description": f"블록 크기 {block_size}의 최대값을 GEV 분포에 피팅",
                },
            )

        except Exception as e:
            self.logger.warning(f"Block maxima method failed: {e}")
            return None

    def _peak_over_threshold_method(
        self, power_data: np.ndarray
    ) -> Optional[ModelPrediction]:
        try:
            # 임계값 설정 (90% 분위수)
            threshold = np.percentile(power_data, 90)
            excesses = power_data[power_data > threshold] - threshold

            if len(excesses) < 10:
                return None

            # 일반화 파레토 분포에 피팅
            from scipy.stats import genpareto

            params = genpareto.fit(excesses)

            # 예측값 계산 (95% 분위수)
            prediction = threshold + genpareto.ppf(0.95, *params)
            
            # 비정상적인 예측값 검증 및 제한
            if not np.isfinite(prediction) or prediction < 0 or prediction > 10000:
                self.logger.warning(f"POT 예측값이 비정상적입니다: {prediction}, 기본값으로 대체")
                prediction = min(np.percentile(power_data, 95), 100)

            # 신뢰구간 계산
            lower = threshold + genpareto.ppf(0.05, *params)
            upper = threshold + genpareto.ppf(0.99, *params)
            
            # CI 값들도 검증
            if not (np.isfinite(lower) and np.isfinite(upper)):
                lower = prediction * 0.9
                upper = prediction * 1.1

            return ModelPrediction(
                model_name="Peak_Over_Threshold",
                predicted_value=prediction,
                confidence_interval=(lower, upper),
                confidence_score=0.80,
                method_details={
                    "method": "Peak Over Threshold",
                    "threshold": threshold,
                    "num_excesses": len(excesses),
                    "pareto_parameters": params,
                    "description": f"임계값 {threshold:.1f}kW 초과 데이터의 일반화 파레토 분포 피팅",
                },
            )

        except Exception as e:
            self.logger.warning(f"POT method failed: {e}")
            return None

    def _bayesian_estimation_optimized(
        self, power_data: np.ndarray, base_stats: Dict[str, float]
    ) -> Optional[ModelPrediction]:
        try:
            # 단순 베이지안 추정 (사전 계산된 통계량 사용)
            n = len(power_data)
            sample_mean = base_stats["mean"]
            sample_std = base_stats["std"]

            # 사전 분포: 약한 정보적 사전분포
            prior_mean = sample_mean
            prior_std = sample_std * 2  # 불확실성 반영

            # 사후 분포 계산
            posterior_precision = 1 / (prior_std**2) + n / (sample_std**2)
            posterior_var = 1 / posterior_precision
            posterior_mean = (
                prior_mean / (prior_std**2) + n * sample_mean / (sample_std**2)
            ) * posterior_var
            posterior_std = np.sqrt(posterior_var)

            # 95% 분위수 예측
            prediction = stats.norm.ppf(0.95, posterior_mean, posterior_std)

            # 신뢰구간
            ci_lower = stats.norm.ppf(0.05, posterior_mean, posterior_std)
            ci_upper = stats.norm.ppf(0.95, posterior_mean, posterior_std)

            return ModelPrediction(
                model_name="Bayesian_Normal",
                predicted_value=prediction,
                confidence_interval=(ci_lower, ci_upper),
                confidence_score=0.75,
                method_details={
                    "method": "Bayesian Estimation",
                    "prior_mean": prior_mean,
                    "prior_std": prior_std,
                    "posterior_mean": posterior_mean,
                    "posterior_std": posterior_std,
                    "sample_size": n,
                    "description": "베이지안 정규 분포 모델을 사용한 95% 분위수 추정",
                },
            )

        except Exception as e:
            self.logger.warning(f"Bayesian estimation failed: {e}")
            return None

    def _bootstrap_method_optimized(
        self,
        power_data: np.ndarray,
        base_stats: Dict[str, float],
        n_bootstrap: int = 200,
    ) -> Optional[ModelPrediction]:
        try:
            # 병렬로 부트스트랩 실행 (속도 개선)
            np.random.seed(42)  # 재현성을 위한 시드 설정
            bootstrap_predictions = np.random.choice(
                power_data, size=(n_bootstrap, len(power_data)), replace=True
            )
            # 백터화된 연산으로 95% 분위수 계산
            bootstrap_percentiles = np.percentile(bootstrap_predictions, 95, axis=1)

            # 부트스트랩 예측값들의 평균
            prediction = np.mean(bootstrap_percentiles)

            # 신뢰구간 (부트스트랩 분위수 방법)
            ci_lower = np.percentile(bootstrap_percentiles, 5)
            ci_upper = np.percentile(bootstrap_percentiles, 95)

            return ModelPrediction(
                model_name="Bootstrap_95th_Percentile",
                predicted_value=prediction,
                confidence_interval=(ci_lower, ci_upper),
                confidence_score=0.80,
                method_details={
                    "method": "Bootstrap",
                    "n_bootstrap": n_bootstrap,
                    "target_percentile": 95,
                    "bootstrap_std": np.std(bootstrap_percentiles),
                    "description": f"{n_bootstrap}회 부트스트랩을 통한 95% 분위수 추정",
                },
            )

        except Exception as e:
            self.logger.warning(f"Bootstrap method failed: {e}")
            return None

    def _quantile_regression(self, power_data: np.ndarray) -> Optional[ModelPrediction]:
        try:
            from scipy.optimize import minimize_scalar

            # 시간 인덱스 생성 (단순 선형 추세 가정)
            x = np.arange(len(power_data))
            y = power_data

            def quantile_loss(theta, quantile=0.95):
                residuals = y - (theta[0] + theta[1] * x)
                return np.sum(
                    np.maximum(quantile * residuals, (quantile - 1) * residuals)
                )

            # 95% 분위수 회귀
            from scipy.optimize import minimize

            # 초기값: OLS 추정치
            ols_slope = np.polyfit(x, y, 1)[0]
            ols_intercept = np.polyfit(x, y, 1)[1]

            result = minimize(
                lambda theta: quantile_loss(theta, 0.95),
                x0=[ols_intercept, ols_slope],
                method="Nelder-Mead",
            )

            if result.success:
                intercept, slope = result.x
                # 미래 예측 (다음 시점)
                prediction = intercept + slope * len(power_data)

                # 신뢰구간 (부트스트랩으로 추정)
                bootstrap_preds = []
                for _ in range(100):
                    indices = np.random.choice(
                        len(power_data), len(power_data), replace=True
                    )
                    boot_x = x[indices]
                    boot_y = y[indices]
                    boot_result = minimize(
                        lambda theta: np.sum(
                            np.maximum(
                                0.95 * (boot_y - (theta[0] + theta[1] * boot_x)),
                                -0.05 * (boot_y - (theta[0] + theta[1] * boot_x)),
                            )
                        ),
                        x0=[intercept, slope],
                        method="Nelder-Mead",
                    )
                    if boot_result.success:
                        boot_intercept, boot_slope = boot_result.x
                        bootstrap_preds.append(
                            boot_intercept + boot_slope * len(power_data)
                        )

                if bootstrap_preds:
                    ci_lower = np.percentile(bootstrap_preds, 5)
                    ci_upper = np.percentile(bootstrap_preds, 95)
                else:
                    ci_lower = prediction * 0.9
                    ci_upper = prediction * 1.1

                return ModelPrediction(
                    model_name="Quantile_Regression_95",
                    predicted_value=prediction,
                    confidence_interval=(ci_lower, ci_upper),
                    confidence_score=0.70,
                    method_details={
                        "method": "Quantile Regression",
                        "quantile": 0.95,
                        "intercept": intercept,
                        "slope": slope,
                        "description": "95% 분위수 회귀를 통한 추세 기반 예측",
                    },
                )

        except Exception as e:
            self.logger.warning(f"Quantile regression failed: {e}")
            return None

    def _kernel_density_estimation(
        self, power_data: np.ndarray
    ) -> Optional[ModelPrediction]:
        try:
            from scipy.stats import gaussian_kde

            # KDE 추정
            kde = gaussian_kde(power_data)

            # 95% 분위수 찾기 (수치적 방법)
            x_range = np.linspace(power_data.min(), power_data.max() * 1.2, 1000)
            kde_values = kde(x_range)

            # CDF 계산
            cdf_values = np.cumsum(kde_values) / np.sum(kde_values)

            # 95% 분위수 찾기
            idx_95 = np.argmax(cdf_values >= 0.95)
            prediction = x_range[idx_95]

            # 신뢰구간
            idx_05 = np.argmax(cdf_values >= 0.05)
            idx_99 = np.argmax(cdf_values >= 0.99)
            ci_lower = x_range[idx_05]
            ci_upper = x_range[idx_99]

            return ModelPrediction(
                model_name="Kernel_Density_Estimation",
                predicted_value=prediction,
                confidence_interval=(ci_lower, ci_upper),
                confidence_score=0.75,
                method_details={
                    "method": "Kernel Density Estimation",
                    "bandwidth": kde.factor,
                    "target_percentile": 95,
                    "description": "가우시안 커널 밀도 추정을 통한 95% 분위수 계산",
                },
            )

        except Exception as e:
            self.logger.warning(f"KDE method failed: {e}")
            return None

    def _exponential_smoothing(
        self, monthly_data: np.ndarray, pattern_factors: Optional[PatternFactors] = None
    ) -> Optional[ModelPrediction]:
        try:
            if len(monthly_data) < 3:
                return None

            # 단순 지수 평활법
            alpha = 0.3  # 평활 계수
            forecast = monthly_data[0]

            for i in range(1, len(monthly_data)):
                forecast = alpha * monthly_data[i] + (1 - alpha) * forecast

            # 다음 달 예측
            prediction = forecast
            
            # Pattern 정보를 활용한 예측 조정
            if pattern_factors and pattern_factors.confidence > 0.5:
                # Trend factor 적용
                if abs(pattern_factors.trend_factor - 1.0) > 0.05:
                    prediction *= pattern_factors.trend_factor
                    
                # 다음 달 계절 요인 적용
                next_month = (datetime.now().month % 12) + 1
                if next_month in pattern_factors.seasonal_factors:
                    seasonal_adjustment = pattern_factors.seasonal_factors[next_month]
                    # 계절 조정을 제한적으로 적용 (30%)
                    seasonal_factor = 1.0 + (seasonal_adjustment - 1.0) * 0.3
                    prediction *= seasonal_factor

            # 신뢰구간 (과거 오차 기반)
            errors = []
            temp_forecast = monthly_data[0]
            for i in range(1, len(monthly_data)):
                temp_forecast = alpha * monthly_data[i] + (1 - alpha) * temp_forecast
                errors.append(abs(monthly_data[i] - temp_forecast))

            if errors:
                error_std = np.std(errors)
                ci_lower = prediction - 1.96 * error_std
                ci_upper = prediction + 1.96 * error_std
            else:
                ci_lower = prediction * 0.9
                ci_upper = prediction * 1.1
                
            # Pattern 정보로 신뢰도 조정
            confidence = 0.70
            if pattern_factors:
                confidence = min(0.85, 0.70 + pattern_factors.confidence * 0.15)

            return ModelPrediction(
                model_name="Pattern_Enhanced_Exponential_Smoothing",
                predicted_value=prediction,
                confidence_interval=(ci_lower, ci_upper),
                confidence_score=confidence,
                method_details={
                    "method": "Pattern-Enhanced Exponential Smoothing",
                    "alpha": alpha,
                    "periods": len(monthly_data),
                    "pattern_applied": pattern_factors is not None,
                    "trend_factor": pattern_factors.trend_factor if pattern_factors else 1.0,
                    "description": f"패턴 정보가 강화된 지수평활법 (α={alpha})",
                },
            )

        except Exception as e:
            self.logger.warning(f"Exponential smoothing failed: {e}")
            return None

    def _linear_trend_analysis(
        self, monthly_data: np.ndarray, pattern_factors: Optional[PatternFactors] = None
    ) -> Optional[ModelPrediction]:
        try:
            if len(monthly_data) < 3:
                return None

            # 선형 회귀
            x = np.arange(len(monthly_data))
            coeffs = np.polyfit(x, monthly_data, 1)
            slope, intercept = coeffs

            # 다음 달 예측
            prediction = slope * len(monthly_data) + intercept
            
            # Pattern 정보를 활용한 예측 조정
            if pattern_factors and pattern_factors.confidence > 0.5:
                # Pattern에서 추출한 트렌드와 비교
                if abs(pattern_factors.trend_factor - 1.0) > 0.05:
                    pattern_trend_adjustment = pattern_factors.trend_factor
                    # 두 트렌드 정보를 합성 (70% 선형, 30% 패턴)
                    combined_trend = 0.7 * (1 + slope) + 0.3 * pattern_trend_adjustment
                    prediction *= combined_trend
                    
                # 계절성 조정
                next_month = (datetime.now().month % 12) + 1
                if next_month in pattern_factors.seasonal_factors:
                    seasonal_adjustment = pattern_factors.seasonal_factors[next_month]
                    prediction *= seasonal_adjustment

            # R-squared 계산
            y_pred = slope * x + intercept
            ss_res = np.sum((monthly_data - y_pred) ** 2)
            ss_tot = np.sum((monthly_data - np.mean(monthly_data)) ** 2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

            # 신뢰구간 (잔차 기반)
            residuals = monthly_data - y_pred
            mse = np.mean(residuals**2)
            rmse = np.sqrt(mse)

            ci_lower = prediction - 1.96 * rmse
            ci_upper = prediction + 1.96 * rmse
            
            # Pattern 정보로 신뢰도 향상
            base_confidence = min(0.9, max(0.5, r_squared))
            if pattern_factors and pattern_factors.confidence > 0.6:
                confidence = min(0.92, base_confidence + pattern_factors.confidence * 0.1)
            else:
                confidence = base_confidence

            return ModelPrediction(
                model_name="Pattern_Enhanced_Linear_Trend",
                predicted_value=prediction,
                confidence_interval=(ci_lower, ci_upper),
                confidence_score=confidence,
                method_details={
                    "method": "Pattern-Enhanced Linear Trend Analysis",
                    "slope": slope,
                    "intercept": intercept,
                    "r_squared": r_squared,
                    "rmse": rmse,
                    "pattern_applied": pattern_factors is not None,
                    "description": f"패턴 정보가 강화된 선형 추세 분석 (R²={r_squared:.3f})",
                },
                r_squared=r_squared,
                rmse=rmse,
            )

        except Exception as e:
            self.logger.warning(f"Linear trend analysis failed: {e}")
            return None

    def _robust_statistics_method_optimized(
        self, base_stats: Dict[str, float]
    ) -> Optional[ModelPrediction]:
        try:
            # 중앙값과 MAD (Median Absolute Deviation) 사용 (사전 계산된 값)
            median = base_stats["median"]
            mad = base_stats["mad"]

            # 강건한 표준편차 추정
            robust_std = mad * 1.4826  # 정규분포에서 MAD를 표준편차로 변환

            # 강건한 95% 분위수 추정
            prediction = median + 1.645 * robust_std  # 정규분포 가정하에 95% 분위수

            # 신뢰구간
            ci_lower = median + 1.28 * robust_std  # 90% 분위수
            ci_upper = median + 2.33 * robust_std  # 99% 분위수

            return ModelPrediction(
                model_name="Robust_Statistics",
                predicted_value=prediction,
                confidence_interval=(ci_lower, ci_upper),
                confidence_score=0.75,
                method_details={
                    "method": "Robust Statistics",
                    "median": median,
                    "mad": mad,
                    "robust_std": robust_std,
                    "description": "중앙값과 MAD를 사용한 강건한 분위수 추정",
                },
            )

        except Exception as e:
            self.logger.warning(f"Robust statistics method failed: {e}")
            return None

    def _ensemble_prediction(
        self,
        model_predictions: List[ModelPrediction],
        power_data: np.ndarray,
        station_id: str,
        charger_type: str = None,
        pattern_factors: Optional[PatternFactors] = None,
    ) -> EnsemblePrediction:
        if not model_predictions:
            return self._fallback_prediction(station_id)

        # 모델별 가중치 계산 (신뢰도 기반)
        weights = {}
        total_confidence = sum(pred.confidence_score for pred in model_predictions)

        for pred in model_predictions:
            weights[pred.model_name] = pred.confidence_score / total_confidence

        # 가중 평균 계산
        weighted_sum = sum(
            pred.predicted_value * weights[pred.model_name]
            for pred in model_predictions
        )

        # 원본 예측값 (제한 없음) - Dynamic Pattern 방식
        dynamic_raw_prediction = max(1, weighted_sum)
        
        # Apply dynamic pattern adjustments
        dynamic_final_prediction = dynamic_raw_prediction
        if pattern_factors and pattern_factors.confidence > 0.5:
            adjusted_prediction = self.pattern_analyzer.apply_pattern_adjustment(
                dynamic_raw_prediction, pattern_factors
            )
            self.logger.info(f"Station {station_id}: Applied dynamic patterns - "
                           f"Original: {dynamic_raw_prediction:.1f}kW, Adjusted: {adjusted_prediction:.1f}kW "
                           f"(confidence: {pattern_factors.confidence:.2f})")
            dynamic_final_prediction = adjusted_prediction

        # 충전기 타입별 최대 전력 제한 적용
        max_power = self.charger_limits.get(charger_type, 100) if charger_type else 100

        # Dynamic Pattern 최종 예측값
        dynamic_prediction = min(max_power, max(1, round(dynamic_final_prediction)))


        # 메소드 비교 정보 생성
        method_comparison = {
            "dynamic_patterns": {
                "predicted_value": dynamic_prediction,
                "raw_prediction": dynamic_raw_prediction,
                "confidence": pattern_factors.confidence if pattern_factors else 0.3,
                "method": "weighted_confidence_with_dynamic_patterns",
                "applied_adjustments": pattern_factors is not None and pattern_factors.confidence > 0.5
            },
        }

        # 기본값은 Dynamic Pattern 결과 사용
        final_prediction = dynamic_prediction

        # 불확실성 계산 (예측값들의 표준편차)
        predictions_array = np.array(
            [pred.predicted_value for pred in model_predictions]
        )
        uncertainty = np.std(predictions_array)

        # 시각화 데이터 준비
        viz_data = self._prepare_visualization_data(
            model_predictions, power_data, final_prediction, dynamic_raw_prediction
        )

        return EnsemblePrediction(
            final_prediction=final_prediction,
            raw_prediction=dynamic_raw_prediction,
            model_predictions=model_predictions,
            ensemble_method="weighted_confidence_with_dynamic_patterns",
            weights=weights,
            uncertainty=uncertainty,
            visualization_data=viz_data,
            pattern_factors=pattern_factors,
            method_comparison=method_comparison,
        )

    def _prepare_visualization_data(
        self,
        model_predictions: List[ModelPrediction],
        power_data: np.ndarray,
        final_prediction: int,
        raw_prediction: float = None,
    ) -> Dict[str, Any]:
        # 히스토그램 데이터 (가볍게 생성)
        hist_counts, hist_bins = np.histogram(power_data, bins=20)  # bins 수 감소

        # 모델별 예측값과 신뢰구간
        model_viz = []
        for pred in model_predictions:
            model_viz.append(
                {
                    "name": pred.model_name,
                    "prediction": pred.predicted_value,
                    "confidence_interval": pred.confidence_interval,
                    "confidence_score": pred.confidence_score,
                    "method_details": pred.method_details,
                }
            )

        # 통계 정보 (캐시된 값 사용 가능하면 사용)
        cache_key = hash(power_data.tobytes())
        if cache_key in self._stats_cache:
            base_stats = self._stats_cache[cache_key]
            stats = {
                "min": float(base_stats["min"]),
                "max": float(base_stats["max"]),
                "mean": float(base_stats["mean"]),
                "median": float(base_stats["median"]),
                "std": float(base_stats["std"]),
                "percentile_95": float(base_stats["q95"]),
                "percentile_99": float(base_stats["q99"]),
            }
        else:
            stats = {
                "min": float(np.min(power_data)),
                "max": float(np.max(power_data)),
                "mean": float(np.mean(power_data)),
                "median": float(np.median(power_data)),
                "std": float(np.std(power_data)),
                "percentile_95": float(np.percentile(power_data, 95)),
                "percentile_99": float(np.percentile(power_data, 99)),
            }

        return {
            "histogram": {"counts": hist_counts.tolist(), "bins": hist_bins.tolist()},
            "models": model_viz,
            "statistics": stats,
            "final_prediction": final_prediction,
            "raw_prediction": raw_prediction
            if raw_prediction is not None
            else final_prediction,
            "data_size": len(power_data),
        }

    def predict_energy_demand(self, data: pd.DataFrame, station_id: str, days: int = 90) -> Dict[str, Any]:
        """
        전력 수요(에너지) 예측 함수
        """
        try:
            if data.empty:
                return {
                    "success": False,
                    "message": "에너지 데이터가 없습니다.",
                    "station_id": station_id,
                }

            # 에너지 컬럼 찾기 (실제 CSV 컬럼명에 맞춰 수정)
            energy_cols = [
                col
                for col in data.columns
                if any(
                    keyword in col.lower()
                    for keyword in ["에너지", "energy", "kwh", "충전량", "kwh"]
                )
            ]
            
            # 디버깅: 컬럼명 출력
            self.logger.info(f"Station {station_id} - Available columns: {list(data.columns)}")
            self.logger.info(f"Station {station_id} - Found energy columns: {energy_cols}")

            if not energy_cols:
                return {
                    "success": False,
                    "message": "에너지 데이터 컬럼을 찾을 수 없습니다.",
                    "station_id": station_id,
                }

            energy_col = energy_cols[0]

            # 날짜 컬럼 찾기
            date_cols = [
                col
                for col in data.columns
                if any(
                    keyword in col.lower()
                    for keyword in ["일시", "date", "time", "시작", "종료"]
                )
            ]

            if not date_cols:
                return {
                    "success": False,
                    "message": "날짜 컬럼을 찾을 수 없습니다.",
                    "station_id": station_id,
                }

            date_col = date_cols[0]

            # 데이터 정리
            df_clean = data[[date_col, energy_col]].copy()
            df_clean = df_clean.dropna()
            df_clean[date_col] = pd.to_datetime(df_clean[date_col], errors="coerce")
            df_clean[energy_col] = pd.to_numeric(df_clean[energy_col], errors="coerce")
            df_clean = df_clean.dropna()

            if df_clean.empty:
                return {
                    "success": False,
                    "message": "유효한 에너지 데이터가 없습니다.",
                    "station_id": station_id,
                }

            # 일별 에너지 소비량 집계
            df_clean["date"] = df_clean[date_col].dt.date
            daily_energy = df_clean.groupby("date")[energy_col].sum().reset_index()
            daily_energy["date"] = pd.to_datetime(daily_energy["date"])

            # 실제 데이터와 예측 데이터 생성
            result = self._generate_energy_forecast(daily_energy, energy_col, station_id)
            result["station_id"] = station_id
            
            return result

        except Exception as e:
            self.logger.error(
                f"Error getting energy demand forecast for {station_id}: {e}",
                exc_info=True,
            )
            return {"success": False, "error": str(e), "station_id": station_id}
    
    def _generate_energy_forecast(
        self, daily_energy: pd.DataFrame, energy_col: str, station_id: str
    ) -> Dict[str, Any]:
        # 기본 통계
        energy_stats = {
            "total_energy": float(daily_energy[energy_col].sum()),
            "avg_daily": float(daily_energy[energy_col].mean()),
            "min_daily": float(daily_energy[energy_col].min()),
            "max_daily": float(daily_energy[energy_col].max()),
            "std_daily": float(daily_energy[energy_col].std()),
        }

        # 시계열 데이터 생성 (실제 데이터)
        actual_data = []
        for _, row in daily_energy.iterrows():
            actual_data.append(
                {
                    "date": row["date"].strftime("%Y-%m-%d"),
                    "energy": round(float(row[energy_col]), 2),
                    "type": "actual",
                }
            )

        # 예측 데이터 생성 (향후 30일)
        last_date = daily_energy["date"].max()
        avg_energy = daily_energy[energy_col].mean()
        std_energy = daily_energy[energy_col].std()

        # 계절성 및 트렌드 고려한 간단한 예측
        predicted_data = []
        for i in range(1, 31):  # 30일 예측
            future_date = last_date + pd.Timedelta(days=i)

            # 계절성 패턴 (월별)
            month = future_date.month
            seasonal_factor = 1.0 + 0.1 * np.sin(2 * np.pi * (month - 1) / 12)

            # 주간 패턴 (주말 vs 주중)
            weekday = future_date.weekday()
            weekly_factor = 0.8 if weekday >= 5 else 1.0  # 주말은 80%

            # 노이즈 추가
            noise_factor = 1.0 + np.random.normal(0, 0.1)

            predicted_energy = (
                avg_energy * seasonal_factor * weekly_factor * noise_factor
            )
            predicted_energy = max(0, predicted_energy)  # 음수 방지

            predicted_data.append(
                {
                    "date": future_date.strftime("%Y-%m-%d"),
                    "energy": round(predicted_energy, 2),
                    "type": "predicted",
                }
            )

        # 월별 집계 (실제 + 예측)
        monthly_summary = self._generate_monthly_energy_summary(
            daily_energy, energy_col
        )

        # 성장률 계산
        if len(daily_energy) >= 30:
            recent_avg = daily_energy[energy_col].tail(30).mean()
            older_avg = (
                daily_energy[energy_col].head(30).mean()
                if len(daily_energy) >= 60
                else recent_avg
            )
            growth_rate = (
                ((recent_avg - older_avg) / older_avg * 100) if older_avg > 0 else 0
            )
        else:
            growth_rate = 0

        return {
            "success": True,
            "energy_statistics": energy_stats,
            "timeseries_data": actual_data + predicted_data,
            "actual_data": actual_data,
            "predicted_data": predicted_data,
            "monthly_summary": monthly_summary,
            "growth_rate": round(growth_rate, 1),
            "data_range": {
                "start_date": daily_energy["date"].min().strftime("%Y-%m-%d"),
                "end_date": daily_energy["date"].max().strftime("%Y-%m-%d"),
                "prediction_start": predicted_data[0]["date"]
                if predicted_data
                else None,
                "prediction_end": predicted_data[-1]["date"]
                if predicted_data
                else None,
            },
            "insights": self._generate_energy_insights(energy_stats, growth_rate),
            "timestamp": datetime.now().isoformat(),
        }

    def _generate_monthly_energy_summary(
        self, daily_energy: pd.DataFrame, energy_col: str
    ) -> List[Dict[str, Any]]:
        daily_energy["year_month"] = daily_energy["date"].dt.to_period("M")
        monthly_data = (
            daily_energy.groupby("year_month")[energy_col]
            .agg(["sum", "mean", "count"])
            .reset_index()
        )

        monthly_summary = []
        for _, row in monthly_data.iterrows():
            period = row["year_month"]
            monthly_summary.append(
                {
                    "month": f"{period.year}-{period.month:02d}",
                    "month_label": f"{period.year}.{period.month:02d}",
                    "total_energy": round(float(row["sum"]), 2),
                    "avg_daily": round(float(row["mean"]), 2),
                    "active_days": int(row["count"]),
                }
            )

        return monthly_summary

    def _generate_energy_insights(
        self, stats: Dict[str, Any], growth_rate: float
    ) -> List[str]:
        insights = []

        # 일평균 소비량 분석
        avg_daily = stats["avg_daily"]
        if avg_daily > 50:
            insights.append(
                f"일평균 {avg_daily:.1f}kWh로 높은 에너지 소비량을 보입니다"
            )
        elif avg_daily > 20:
            insights.append(
                f"일평균 {avg_daily:.1f}kWh로 보통 수준의 에너지 소비량을 보입니다"
            )
        else:
            insights.append(
                f"일평균 {avg_daily:.1f}kWh로 낮은 에너지 소비량을 보입니다"
            )

        # 변동성 분석
        cv = stats["std_daily"] / stats["avg_daily"] if stats["avg_daily"] > 0 else 0
        if cv > 0.5:
            insights.append("에너지 소비 패턴이 불규칙합니다")
        elif cv > 0.3:
            insights.append("에너지 소비 패턴이 보통 수준의 변동성을 보입니다")
        else:
            insights.append("에너지 소비 패턴이 안정적입니다")

        # 성장률 분석
        if growth_rate > 10:
            insights.append(f"에너지 소비가 {growth_rate:.1f}% 증가 추세입니다")
        elif growth_rate < -10:
            insights.append(f"에너지 소비가 {abs(growth_rate):.1f}% 감소 추세입니다")
        else:
            insights.append("에너지 소비가 안정적인 추세를 보입니다")

        return insights

    def _fallback_prediction(self, station_id: str) -> EnsemblePrediction:
        fallback_pred = ModelPrediction(
            model_name="Fallback_Conservative",
            predicted_value=50.0,
            confidence_interval=(40.0, 60.0),
            confidence_score=0.6,
            method_details={
                "method": "Conservative Fallback",
                "reason": "Insufficient data or model failures",
                "description": "데이터 부족으로 인한 보수적 추정",
            },
        )

        return EnsemblePrediction(
            final_prediction=50,
            raw_prediction=50.0,
            model_predictions=[fallback_pred],
            ensemble_method="fallback",
            weights={"Fallback_Conservative": 1.0},
            uncertainty=10.0,
            visualization_data={
                "histogram": {"counts": [], "bins": []},
                "models": [
                    {
                        "name": "Fallback_Conservative",
                        "prediction": 50.0,
                        "confidence_interval": (40.0, 60.0),
                        "confidence_score": 0.6,
                    }
                ],
                "statistics": {},
                "final_prediction": 50,
                "data_size": 0,
            },
        )
