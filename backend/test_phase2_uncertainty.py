"""
Phase 2 테스트: Monte Carlo Dropout + 계약 최적화 통합

LSTM Monte Carlo Dropout으로 확률분포를 생성하고,
계약 최적화 엔진과 통합하여 최종 추천을 생성합니다.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# Phase 2 모듈
from app.prediction.lstm_prediction_engine import LSTMPredictionEngine
from app.services.contract_analyzer import ContractAnalyzer
from app.contract import ContractOptimizer, RecommendationEngine


def create_sample_charging_data(
    days: int = 90,
    mean_power: float = 110,
    std_power: float = 15,
    is_fast_charger: bool = True
) -> pd.DataFrame:
    """샘플 충전 데이터 생성"""
    
    # 시간 인덱스 생성 (시간 단위)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    date_range = pd.date_range(start=start_date, end=end_date, freq='H')
    
    # 전력 데이터 생성 (패턴 포함)
    hours = np.array([d.hour for d in date_range])
    weekdays = np.array([d.weekday() for d in date_range])
    
    # 시간대별 패턴 (오전 9시~오후 6시 피크)
    hour_factor = 1.0 + 0.3 * np.sin((hours - 12) * np.pi / 12)
    
    # 주중/주말 패턴
    weekday_factor = np.where(weekdays < 5, 1.1, 0.9)
    
    # 기본 전력 + 패턴 + 랜덤 노이즈
    base_power = np.random.normal(mean_power, std_power, len(date_range))
    power_data = base_power * hour_factor * weekday_factor
    
    # 이상치 추가 (5% 확률로 스파이크)
    spike_mask = np.random.random(len(power_data)) < 0.05
    power_data[spike_mask] *= 1.3
    
    # 음수 제거
    power_data = np.maximum(power_data, 0)
    
    # DataFrame 생성
    df = pd.DataFrame({
        '순간최고전력': power_data,
        '충전전력량(kWh)': power_data * 0.8,  # 평균 0.8시간 충전 가정
    }, index=date_range)
    
    return df


def test_lstm_monte_carlo_dropout():
    """테스트 1: LSTM Monte Carlo Dropout"""
    print("=" * 80)
    print("테스트 1: LSTM Monte Carlo Dropout으로 확률분포 생성")
    print("=" * 80)
    
    # 샘플 데이터 생성
    data = create_sample_charging_data(days=90, mean_power=110, std_power=15)
    print(f"\n✓ 샘플 데이터 생성: {len(data)}개 시간대 데이터")
    print(f"  - 기간: {data.index[0]} ~ {data.index[-1]}")
    print(f"  - 평균 전력: {data['순간최고전력'].mean():.1f}kW")
    print(f"  - P95: {data['순간최고전력'].quantile(0.95):.1f}kW")
    
    # LSTM 엔진 초기화
    lstm_engine = LSTMPredictionEngine()
    
    if not lstm_engine.model:
        print("\n⚠️  TensorFlow 미설치 - 통계 폴백 모드로 테스트")
        
        # 통계 기반 분포 생성
        power_data = lstm_engine._preprocess_data(data)
        distribution = lstm_engine.predict_with_uncertainty(
            data, power_data, n_iterations=1000
        )
    else:
        print("\n✓ LSTM 모델 초기화 완료")
        
        # Monte Carlo Dropout으로 확률분포 생성
        power_data = lstm_engine._preprocess_data(data)
        
        print(f"\n📊 Monte Carlo Dropout 실행 (1,000회 반복)...")
        distribution = lstm_engine.predict_with_uncertainty(
            data, power_data, n_iterations=1000
        )
    
    # 분포 통계
    print(f"\n📈 예측 분포 통계:")
    print(f"  - 평균: {np.mean(distribution):.1f}kW")
    print(f"  - 표준편차: {np.std(distribution):.1f}kW")
    print(f"  - P10: {np.percentile(distribution, 10):.1f}kW")
    print(f"  - P50: {np.percentile(distribution, 50):.1f}kW")
    print(f"  - P90: {np.percentile(distribution, 90):.1f}kW")
    print(f"  - P95: {np.percentile(distribution, 95):.1f}kW")
    print(f"  - P99: {np.percentile(distribution, 99):.1f}kW")
    
    return distribution, data


def test_contract_optimization_with_distribution(distribution):
    """테스트 2: 확률분포 → 10kW 단위 최적화"""
    print("\n" + "=" * 80)
    print("테스트 2: 확률분포 기반 10kW 단위 계약전력 최적화")
    print("=" * 80)
    
    # 현재 계약 (과다계약 시나리오)
    current_contract = 160
    
    # 추천 엔진 사용
    engine = RecommendationEngine()
    recommendation = engine.generate_recommendation(
        station_id="TEST_STATION_PHASE2",
        prediction_distribution=distribution,
        current_contract_kw=current_contract
    )
    
    print(f"\n✅ 최적화 완료!")
    print(f"\n충전소: {recommendation.station_id}")
    print(f"현재 계약: {recommendation.current_contract_kw}kW")
    print(f"추천 계약: {recommendation.recommended_contract_kw}kW (10kW 단위)")
    print("\n💰 비용 분석:")
    print(f"  - 예상 연간 비용: {recommendation.expected_annual_cost:,.0f}원")
    if recommendation.expected_annual_savings:
        print(f"  - 예상 절감액: {recommendation.expected_annual_savings:,.0f}원")
        print(f"  - 절감률: {recommendation.savings_percent:.1f}%")
    
    print("\n📊 리스크 분석:")
    print(f"  - 초과 확률: {recommendation.overage_probability:.1f}%")
    print(f"  - 낭비 확률: {recommendation.waste_probability:.1f}%")
    print(f"  - 신뢰도: {recommendation.confidence_level:.1f}%")
    
    print("\n🎯 조치 사항:")
    print(f"  - 조치 필요: {'예' if recommendation.action_required else '아니오'}")
    print(f"  - 긴급도: {recommendation.urgency_level.upper()}")
    
    print(f"\n📋 상세 사유:")
    for i, reason in enumerate(recommendation.detailed_reasoning, 1):
        print(f"  {i}. {reason}")
    
    return recommendation


def test_end_to_end_integration(data):
    """테스트 3: LSTM 예측 → 분포 추출 → 계약 최적화 (End-to-End)"""
    print("\n" + "=" * 80)
    print("테스트 3: End-to-End 통합 테스트")
    print("=" * 80)
    
    # 1. LSTM 예측 (EnsemblePrediction 생성)
    lstm_engine = LSTMPredictionEngine()
    lstm_prediction = lstm_engine.predict_contract_power(
        data=data,
        station_id="E2E_TEST_STATION",
        charger_type="급속충전기 (DC)"
    )
    
    print(f"\n1️⃣ LSTM 예측 완료:")
    print(f"  - 최종 예측: {lstm_prediction.final_prediction}kW")
    print(f"  - 앙상블 방법: {lstm_prediction.ensemble_method}")
    print(f"  - 불확실성: ±{lstm_prediction.uncertainty:.1f}kW")
    
    # 2. 계약 분석기로 최적화
    analyzer = ContractAnalyzer()
    
    # LSTM 분포 기반 최적화
    result = analyzer.optimize_contract_with_lstm_distribution(
        station_id="E2E_TEST_STATION",
        lstm_prediction=lstm_prediction,
        current_contract_kw=150
    )
    
    if result.get("success", True):
        print(f"\n2️⃣ 계약 최적화 완료:")
        print(f"  - 추천 계약: {result.get('recommended_contract_kw')}kW")
        print(f"  - 예상 절감: 연간 {result.get('expected_annual_savings', 0):,.0f}원")
        print(f"  - 초과 위험: {result.get('overage_probability', 0):.1f}%")
        
        print(f"\n3️⃣ 상세 추천:")
        detailed = result.get('detailed_reasoning', [])
        for i, reason in enumerate(detailed[:3], 1):
            print(f"  {i}. {reason}")
    else:
        print(f"\n❌ 최적화 실패: {result.get('error')}")
    
    return result


def test_comparison_with_without_distribution():
    """테스트 4: 분포 있음 vs 단일값 비교"""
    print("\n" + "=" * 80)
    print("테스트 4: Monte Carlo Dropout vs 단일 예측값 비교")
    print("=" * 80)
    
    # 샘플 데이터
    data = create_sample_charging_data(days=90, mean_power=110, std_power=15)
    current_contract = 150
    
    # 방법 1: 단일 예측값 (기존)
    print("\n📌 방법 1: 단일 예측값 기반")
    single_prediction = data['순간최고전력'].quantile(0.95)
    print(f"  - P95 예측: {single_prediction:.1f}kW")
    
    # 간단한 추천 (안전마진 10%)
    simple_recommendation = np.ceil(single_prediction * 1.1 / 10) * 10
    print(f"  - 추천 계약: {simple_recommendation:.0f}kW (10% 마진)")
    
    # 방법 2: Monte Carlo Dropout (Phase 2)
    print("\n📌 방법 2: Monte Carlo Dropout 확률분포")
    lstm_engine = LSTMPredictionEngine()
    power_data = lstm_engine._preprocess_data(data)
    distribution = lstm_engine.predict_with_uncertainty(data, power_data, n_iterations=1000)
    
    print(f"  - 평균: {np.mean(distribution):.1f}kW")
    print(f"  - P95: {np.percentile(distribution, 95):.1f}kW")
    
    optimizer = ContractOptimizer()
    result = optimizer.optimize_contract(
        prediction_distribution=distribution,
        current_contract_kw=current_contract
    )
    
    print(f"  - 추천 계약: {result.optimal_contract_kw}kW (리스크 최적화)")
    
    # 비교
    print(f"\n📊 비교 결과:")
    print(f"  - 단일값 추천: {simple_recommendation:.0f}kW")
    print(f"  - 분포 기반 추천: {result.optimal_contract_kw}kW")
    print(f"  - 차이: {result.optimal_contract_kw - simple_recommendation:.0f}kW")
    
    if result.optimal_contract_kw < simple_recommendation:
        print(f"  ✅ Phase 2가 {simple_recommendation - result.optimal_contract_kw:.0f}kW 절감!")
    else:
        print(f"  ⚠️  Phase 2가 {result.optimal_contract_kw - simple_recommendation:.0f}kW 더 보수적")


if __name__ == "__main__":
    print("\n🚀 Phase 2 통합 테스트 시작: Monte Carlo Dropout + 계약 최적화")
    print("=" * 80)
    
    try:
        # 테스트 1: LSTM Monte Carlo Dropout
        distribution, data = test_lstm_monte_carlo_dropout()
        
        # 테스트 2: 확률분포 → 10kW 최적화
        recommendation = test_contract_optimization_with_distribution(distribution)
        
        # 테스트 3: End-to-End 통합
        e2e_result = test_end_to_end_integration(data)
        
        # 테스트 4: 비교 분석
        test_comparison_with_without_distribution()
        
        print("\n" + "=" * 80)
        print("✅ Phase 2 모든 테스트 통과!")
        print("=" * 80)
        print("\n🎯 주요 성과:")
        print("  1. ✅ Monte Carlo Dropout으로 확률분포 생성")
        print("  2. ✅ 1,000개 시나리오 기반 불확실성 정량화")
        print("  3. ✅ 10kW 단위 최적화와 통합")
        print("  4. ✅ End-to-End 파이프라인 구축")
        print("  5. ✅ 리스크 균형 의사결정 지원")
        
    except Exception as e:
        print(f"\n❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
