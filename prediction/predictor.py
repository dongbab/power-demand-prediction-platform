from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import asyncio
import logging
from data.loader import ChargingDataLoader


class RealTimePowerPredictor:
    
    def __init__(self, station_id: str):
        self.station_id = station_id
        self.logger = logging.getLogger(__name__)
        self.loader = ChargingDataLoader(station_id)
        self._cached_patterns = None
        self._cache_timestamp = None
        
    async def predict_next_hour_peak(self) -> Dict[str, Any]:
        # 다음 1시간 최고전력 예측
        try:
            # 캐시된 패턴 사용 (1시간마다 갱신)
            patterns = self._get_cached_patterns()
            
            current_time = datetime.now()
            current_hour = current_time.hour
            current_weekday = current_time.weekday()
            current_month = current_time.month
            
            # 1. 시간대별 기본 예측값
            base_power = self._get_hourly_prediction(patterns, current_hour)
            
            # 2. 요일 조정 (주말 효과)
            weekday_factor = 0.85 if current_weekday >= 5 else 1.0
            
            # 3. 계절성 조정
            seasonal_factor = self._get_seasonal_factor(current_month)
            
            # 4. 최종 예측값 계산
            predicted_power = base_power * weekday_factor * seasonal_factor
            
            # 5. 신뢰구간 계산 (실제 데이터 기반 변동성)
            std_dev = patterns.get('power_statistics', {}).get('std', 10.0)
            confidence_lower = max(0, predicted_power - 1.96 * std_dev)
            confidence_upper = predicted_power + 1.96 * std_dev
            
            # 6. 실제 충전소 특성 반영
            station_max = patterns.get('power_statistics', {}).get('max', 50.0)
            predicted_power = min(predicted_power, station_max * 0.95)  # 최대값의 95% 제한
            
            return {
                'predicted_peak': round(predicted_power, 1),
                'confidence_interval': {
                    'lower': round(confidence_lower, 1),
                    'upper': round(confidence_upper, 1)
                },
                'timestamp': current_time.isoformat(),
                'station_id': self.station_id,
                'prediction_factors': {
                    'base_power': round(base_power, 1),
                    'weekday_factor': weekday_factor,
                    'seasonal_factor': seasonal_factor,
                    'is_weekend': current_weekday >= 5,
                    'current_hour': current_hour
                },
                'data_source': 'actual_historical_data',
                'data_quality': {
                    'sessions_analyzed': patterns.get('power_statistics', {}).get('count', 0),
                    'station_max_power': station_max
                }
            }
            
        except Exception as e:
            self.logger.error(f"예측 실패: {e}")
            return self._fallback_prediction()
    
    def _get_cached_patterns(self) -> Dict:
        now = datetime.now()
        
        # 캐시가 없거나 1시간 이상 지났으면 갱신
        if (self._cached_patterns is None or 
            self._cache_timestamp is None or 
            (now - self._cache_timestamp) > timedelta(hours=1)):
            
            self.logger.info("충전 패턴 분석 중...")
            self._cached_patterns = self.loader.analyze_charging_patterns()
            self._cache_timestamp = now
            
        return self._cached_patterns
    
    def _get_hourly_prediction(self, patterns: Dict, hour: int) -> float:
        """시간대별 예측값 계산"""
        hourly_patterns = patterns.get('hourly_patterns', {})
        
        if str(hour) in hourly_patterns:
            # 실제 시간대별 평균 사용
            return hourly_patterns[str(hour)]['avg_power']
        elif 'power_statistics' in patterns:
            # 전체 평균 사용
            return patterns['power_statistics']['mean']
        else:
            # 기본값 (BNS0791의 실제 평균 기준)
            return 33.5
    
    def _get_seasonal_factor(self, month: int) -> float:
        """계절성 조정 팩터"""
        # 전기차 충전 특성을 고려한 계절성
        seasonal_factors = {
            12: 1.15, 1: 1.15, 2: 1.10,  # 겨울: 배터리 효율 저하로 충전 전력 증가
            3: 1.0, 4: 1.0, 5: 1.0,      # 봄: 기준
            6: 1.05, 7: 1.10, 8: 1.05,   # 여름: 에어컨 사용으로 약간 증가
            9: 1.0, 10: 1.0, 11: 1.05    # 가을: 기준~약간 증가
        }
        return seasonal_factors.get(month, 1.0)
    
    def _fallback_prediction(self) -> Dict[str, Any]:
        """오류 시 기본 예측값 반환"""
        current_time = datetime.now()
        current_hour = current_time.hour
        
        # BNS0791의 실제 데이터 기반 기본값
        if 6 <= current_hour <= 9:  # 출근시간
            base_power = 45.0
        elif 11 <= current_hour <= 13:  # 점심시간 (실제 피크)
            base_power = 49.0
        elif 18 <= current_hour <= 20:  # 퇴근시간
            base_power = 40.0
        else:
            base_power = 33.5  # 평균값
            
        return {
            'predicted_peak': base_power,
            'confidence_interval': {
                'lower': base_power * 0.8,
                'upper': base_power * 1.2
            },
            'timestamp': current_time.isoformat(),
            'station_id': self.station_id,
            'data_source': 'fallback_default',
            'note': '실제 데이터 로딩 실패로 기본값 사용'
        }
    
    async def predict_monthly_peak(self, year: int, month: int) -> Dict[str, Any]:
        """월별 최고전력 예측 (실제 데이터 기반)"""
        try:
            # 실제 데이터 기반 예측
            prediction_data = self.loader.predict_monthly_peak(year, month)
            
            if 'error' in prediction_data:
                return self._fallback_monthly_prediction(year, month)
            
            # 추가 분석 정보 포함
            patterns = self._get_cached_patterns()
            current_utilization = self._calculate_utilization_rate(patterns)
            
            prediction_data.update({
                'current_utilization_rate': current_utilization,
                'prediction_confidence': self._assess_prediction_confidence(patterns),
                'recommendation_reason': self._generate_recommendation_reason(prediction_data, patterns)
            })
            
            return prediction_data
            
        except Exception as e:
            self.logger.error(f"월별 예측 실패: {e}")
            return self._fallback_monthly_prediction(year, month)
    
    def _calculate_utilization_rate(self, patterns: Dict) -> Dict[str, float]:
        """현재 이용률 계산"""
        if 'power_statistics' not in patterns:
            return {'avg_utilization': 0.0, 'peak_utilization': 0.0}
        
        stats = patterns['power_statistics']
        # 50kW 충전기 기준 (커넥터명에서 확인됨)
        rated_power = 50.0
        
        return {
            'avg_utilization': round(stats['mean'] / rated_power * 100, 1),
            'peak_utilization': round(stats['max'] / rated_power * 100, 1),
            'rated_power': rated_power
        }
    
    def _assess_prediction_confidence(self, patterns: Dict) -> str:
        """예측 신뢰도 평가"""
        if 'power_statistics' not in patterns:
            return 'Low'
        
        session_count = patterns['power_statistics']['count']
        
        if session_count >= 100:
            return 'High'
        elif session_count >= 30:
            return 'Medium'
        else:
            return 'Low'
    
    def _generate_recommendation_reason(self, prediction: Dict, patterns: Dict) -> str:
        """권고 사유 생성"""
        if 'power_statistics' not in patterns:
            return "데이터 부족으로 보수적 추정"
        
        predicted_peak = prediction.get('predicted_peak_kw', 0)
        recommended_contract = prediction.get('recommended_contract_kw', 0)
        current_max = patterns['power_statistics']['max']
        
        reasons = []
        
        if predicted_peak < current_max * 1.1:
            reasons.append("과거 최대값 기준 안정적 예측")
        
        if prediction.get('seasonal_factor', 1.0) > 1.05:
            reasons.append("계절성 증가 요인 반영")
        
        safety_margin = (recommended_contract - predicted_peak) / predicted_peak * 100
        reasons.append(f"{safety_margin:.0f}% 안전마진 적용")
        
        return " | ".join(reasons)
    
    def _fallback_monthly_prediction(self, year: int, month: int) -> Dict[str, Any]:
        """월별 예측 실패 시 기본값"""
        # BNS0791 실제 데이터 기반
        base_prediction = 49.9  # 실제 최대값
        seasonal_factor = self._get_seasonal_factor(month)
        predicted_peak = base_prediction * seasonal_factor
        
        return {
            "station_id": self.station_id,
            "year": year,
            "month": month,
            "predicted_peak_kw": round(predicted_peak, 1),
            "confidence_interval": {
                "lower": round(predicted_peak * 0.85, 1),
                "upper": round(predicted_peak * 1.15, 1),
            },
            "recommended_contract_kw": int(predicted_peak * 1.1 / 10) * 10,
            "seasonal_factor": seasonal_factor,
            "data_source": "fallback_estimation",
            "note": "실제 데이터 부족으로 보수적 추정"
        }

async def get_enhanced_prediction(station_id: str):
    """향상된 예측 API"""
    predictor = RealTimePowerPredictor(station_id)
    
    # 실시간 예측
    hourly_prediction = await predictor.predict_next_hour_peak()
    
    # 다음 달 계약 전력 권고
    next_month = datetime.now().replace(day=1) + timedelta(days=32)
    monthly_prediction = await predictor.predict_monthly_peak(
        next_month.year, next_month.month
    )
    
    return {
        "station_id": station_id,
        "timestamp": datetime.now().isoformat(),
        "hourly_prediction": hourly_prediction,
        "next_month_contract": monthly_prediction,
        "summary": {
            "current_hour_prediction": f"{hourly_prediction['predicted_peak']}kW",
            "next_month_contract": f"{monthly_prediction['recommended_contract_kw']}kW",
            "data_quality": hourly_prediction.get('data_quality', {})
        }
    }


# 테스트 함수
async def test_real_data_prediction():
    """실제 데이터 기반 예측 테스트"""
    print("=== 실제 데이터 기반 예측 테스트 ===")
    
    predictor = RealTimePowerPredictor("BNS0026")
    
    # 1. 실시간 예측
    print("\n1. 다음 1시간 예측:")
    hourly_pred = await predictor.predict_next_hour_peak()
    print(f"   예측 전력: {hourly_pred['predicted_peak']}kW")
    print(f"   신뢰구간: {hourly_pred['confidence_interval']['lower']}-{hourly_pred['confidence_interval']['upper']}kW")
    print(f"   기반 데이터: {hourly_pred.get('data_source', 'unknown')}")
    
    # 2. 월별 예측
    print("\n2. 다음 달 계약 전력 권고:")
    next_month = datetime.now().replace(day=1) + timedelta(days=32)
    monthly_pred = await predictor.predict_monthly_peak(next_month.year, next_month.month)
    print(f"   예상 최고전력: {monthly_pred.get('predicted_peak_kw', 'N/A')}kW")
    print(f"   권고 계약전력: {monthly_pred.get('recommended_contract_kw', 'N/A')}kW")
    print(f"   권고 사유: {monthly_pred.get('recommendation_reason', 'N/A')}")
    
    # 3. 종합 분석
    print("\n3. 종합 분석:")
    enhanced = await get_enhanced_prediction("BNS0026")
    summary = enhanced['summary']
    for key, value in summary.items():
        print(f"   {key}: {value}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_real_data_prediction())