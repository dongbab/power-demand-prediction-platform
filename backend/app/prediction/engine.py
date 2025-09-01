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


class PredictionEngine:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.max_contract_power = 100  # 최대 계약 전력 100kW
        self.max_workers = 4  # 병렬 처리 스레드 수
        self._stats_cache = {}  # 기본 통계량 캐시
        
        # 충전기 타입별 최대 전력 제한
        self.charger_limits = {
            "완속충전기 (AC)": 7,  # 완속은 최대 7kW
            "급속충전기 (DC)": 100,  # 급속은 최대 100kW
            "미상": 50,  # 미상인 경우 보수적으로 50kW
        }

    def predict_contract_power(
        self, data: pd.DataFrame, station_id: str, charger_type: str = None
    ) -> EnsemblePrediction:
        """
        다양한 통계 모델을 사용하여 권고 계약 전력 예측 (병렬 처리 최적화)
        Args:
            data: 충전소 히스토리 데이터 (순간최고전력 포함)
            station_id: 충전소 ID
        Returns:
            EnsemblePrediction: 앙상블 예측 결과
        """
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

        # 병렬로 모델 실행
        model_predictions = []
        
        try:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # 모델 태스크 정의
                tasks = {
                    executor.submit(self._extreme_value_models_optimized, power_data, base_stats): "EVT",
                    executor.submit(self._statistical_inference_models_optimized, power_data, base_stats): "STAT",
                    executor.submit(self._time_series_models, data): "TS",
                    executor.submit(self._machine_learning_models_optimized, power_data, base_stats): "ML"
                }
                
                # 결과 수집
                for future in as_completed(tasks, timeout=10):
                    try:
                        models = future.result()
                        if models:
                            model_predictions.extend(models)
                    except Exception as e:
                        model_type = tasks[future]
                        self.logger.warning(f"{model_type} models failed for {station_id}: {e}")
                        
        except Exception as e:
            self.logger.error(f"Parallel prediction failed for {station_id}: {e}")
            return self._fallback_prediction(station_id)

        # 최소한의 모델 결과가 있는지 확인
        if not model_predictions:
            return self._fallback_prediction(station_id)
        
        # 앙상블 예측 수행
        result = self._ensemble_prediction(
            model_predictions, power_data, station_id, charger_type
        )
        
        elapsed_time = time.time() - start_time
        self.logger.info(f"Prediction completed for {station_id} in {elapsed_time:.3f}s with {len(model_predictions)} models")
        
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

        power_data = power_data[(power_data >= lower_bound) & (power_data <= upper_bound)]
        return power_data.values
    
    
    def _compute_base_statistics(self, power_data: np.ndarray) -> Dict[str, float]:
        """기본 통계량 계산"""
        return {
            'mean': np.mean(power_data),
            'median': np.median(power_data),
            'std': np.std(power_data, ddof=1),
            'mad': np.median(np.abs(power_data - np.median(power_data))),
            'q25': np.percentile(power_data, 25),
            'q75': np.percentile(power_data, 75),
            'q90': np.percentile(power_data, 90),
            'q95': np.percentile(power_data, 95),
            'q99': np.percentile(power_data, 99),
            'min': np.min(power_data),
            'max': np.max(power_data)
        }

    def _extreme_value_models_optimized(self, power_data: np.ndarray, base_stats: Dict[str, float]) -> List[ModelPrediction]:
        """극값 이론 모델들 (최적화된 버전)"""
        models = []

        try:
            # 빠른 초기 참값 설정으로 최적화 속도 향상
            # 1. Generalized Extreme Value (GEV) Distribution
            gev_params = genextreme.fit(power_data, 
                                       loc=base_stats['mean'], 
                                       scale=base_stats['std'])
            gev_prediction = genextreme.ppf(0.95, *gev_params)  # 95% 분위수
            gev_ci = (base_stats['q90'], base_stats['q99'])  # 빠른 근사치

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

            # 2. Gumbel Distribution (최적화된 버전)
            gumbel_params = gumbel_r.fit(power_data, 
                                        loc=base_stats['mean'],
                                        scale=base_stats['std'])
            gumbel_prediction = gumbel_r.ppf(0.95, *gumbel_params)
            gumbel_ci = (base_stats.get('q85', base_stats['q90'] * 0.95), base_stats.get('q98', base_stats['q95'] * 1.02))

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
        self, power_data: np.ndarray, base_stats: Dict[str, float]
    ) -> List[ModelPrediction]:
        """통계적 추론 모델들 (최적화된 버전)"""
        models = []

        try:
            # 1. Bayesian Estimation (사전 계산된 통계량 사용)
            bayesian_result = self._bayesian_estimation_optimized(power_data, base_stats)
            if bayesian_result:
                models.append(bayesian_result)

            # 2. Bootstrap Confidence Interval (축소된 반복 횟수)
            bootstrap_result = self._bootstrap_method_optimized(power_data, base_stats, n_bootstrap=200)
            if bootstrap_result:
                models.append(bootstrap_result)

            # 3. 빠른 분위수 추정 (사전 계산된 값 사용)
            fast_percentile_result = ModelPrediction(
                model_name="Fast_Percentile_95",
                predicted_value=base_stats['q95'],
                confidence_interval=(base_stats['q90'], base_stats['q99']),
                confidence_score=0.75,
                method_details={
                    "method": "Direct Percentile",
                    "percentile": 95,
                    "description": "사전 계산된 95% 분위수 사용"
                }
            )
            models.append(fast_percentile_result)

        except Exception as e:
            self.logger.warning(f"Statistical inference models failed: {e}")

        return models

    def _time_series_models(self, data: pd.DataFrame) -> List[ModelPrediction]:
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
                    # 1. Exponential Smoothing
                    exp_smooth_result = self._exponential_smoothing(monthly_max.values)
                    if exp_smooth_result:
                        models.append(exp_smooth_result)

                    # 2. Linear Trend Analysis
                    trend_result = self._linear_trend_analysis(monthly_max.values)
                    if trend_result:
                        models.append(trend_result)

        except Exception as e:
            self.logger.warning(f"Time series models failed: {e}")

        return models

    def _machine_learning_models_optimized(self, power_data: np.ndarray, base_stats: Dict[str, float]) -> List[ModelPrediction]:
        """머신러닝 모델들 (최적화된 버전)"""
        models = []

        try:
            # 1. Ensemble Percentile Method (사전 계산된 값 사용)
            percentile_predictions = [
                base_stats['q90'], 
                base_stats['q95'], 
                base_stats.get('q98', base_stats['q95'] * 1.02),  # 근사치
                base_stats['q99']
            ]

            # 가중 평균 (높은 분위수에 더 많은 가중치)
            weights = np.array([0.1, 0.3, 0.4, 0.2])
            weighted_prediction = np.average(percentile_predictions, weights=weights)

            models.append(
                ModelPrediction(
                    model_name="Weighted_Percentile_Ensemble",
                    predicted_value=weighted_prediction,
                    confidence_interval=(
                        base_stats.get('q85', base_stats['q90'] * 0.95),
                        base_stats['q99']
                    ),
                    confidence_score=0.75,
                    method_details={
                        "method": "Optimized Weighted Percentile Ensemble",
                        "percentiles": [90, 95, 98, 99],
                        "weights": weights.tolist(),
                        "description": "사전 계산된 분위수로 최적화된 예측",
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
            ci = genextreme.interval(0.9, *params)

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

            # 신뢰구간 계산
            lower = threshold + genpareto.ppf(0.05, *params)
            upper = threshold + genpareto.ppf(0.99, *params)

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

    def _bayesian_estimation_optimized(self, power_data: np.ndarray, base_stats: Dict[str, float]) -> Optional[ModelPrediction]:
        try:
            # 단순 베이지안 추정 (사전 계산된 통계량 사용)
            n = len(power_data)
            sample_mean = base_stats['mean']
            sample_std = base_stats['std']

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
        self, power_data: np.ndarray, base_stats: Dict[str, float], n_bootstrap: int = 200
    ) -> Optional[ModelPrediction]:
        try:
            # 병렬로 부트스트랩 실행 (속도 개선)
            np.random.seed(42)  # 재현성을 위한 시드 설정
            bootstrap_predictions = np.random.choice(power_data, size=(n_bootstrap, len(power_data)), replace=True)
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
        self, monthly_data: np.ndarray
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

            return ModelPrediction(
                model_name="Exponential_Smoothing",
                predicted_value=prediction,
                confidence_interval=(ci_lower, ci_upper),
                confidence_score=0.70,
                method_details={
                    "method": "Simple Exponential Smoothing",
                    "alpha": alpha,
                    "periods": len(monthly_data),
                    "description": f"지수평활법 (α={alpha})을 사용한 시계열 예측",
                },
            )

        except Exception as e:
            self.logger.warning(f"Exponential smoothing failed: {e}")
            return None

    def _linear_trend_analysis(
        self, monthly_data: np.ndarray
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

            return ModelPrediction(
                model_name="Linear_Trend",
                predicted_value=prediction,
                confidence_interval=(ci_lower, ci_upper),
                confidence_score=min(0.9, max(0.5, r_squared)),
                method_details={
                    "method": "Linear Trend Analysis",
                    "slope": slope,
                    "intercept": intercept,
                    "r_squared": r_squared,
                    "rmse": rmse,
                    "description": f"선형 추세 분석 (R²={r_squared:.3f})",
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
            median = base_stats['median']
            mad = base_stats['mad']

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

        # 원본 예측값 (제한 없음)
        raw_prediction = max(1, weighted_sum)

        # 충전기 타입별 최대 전력 제한 적용
        max_power = self.charger_limits.get(charger_type, 100) if charger_type else 100

        # 제한된 최종 예측값
        final_prediction = min(max_power, max(1, round(weighted_sum)))

        # 불확실성 계산 (예측값들의 표준편차)
        predictions_array = np.array(
            [pred.predicted_value for pred in model_predictions]
        )
        uncertainty = np.std(predictions_array)

        # 시각화 데이터 준비
        viz_data = self._prepare_visualization_data(
            model_predictions, power_data, final_prediction, raw_prediction
        )

        return EnsemblePrediction(
            final_prediction=final_prediction,
            raw_prediction=raw_prediction,
            model_predictions=model_predictions,
            ensemble_method="weighted_confidence",
            weights=weights,
            uncertainty=uncertainty,
            visualization_data=viz_data,
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
                "min": float(base_stats['min']),
                "max": float(base_stats['max']),
                "mean": float(base_stats['mean']),
                "median": float(base_stats['median']),
                "std": float(base_stats['std']),
                "percentile_95": float(base_stats['q95']),
                "percentile_99": float(base_stats['q99']),
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
