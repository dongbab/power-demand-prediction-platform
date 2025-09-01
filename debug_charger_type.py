#!/usr/bin/env python3


import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend', 'app'))

from backend.app.data.loader import ChargingDataLoader
from backend.app.services.station_service import StationService

def debug_charger_type(station_id="BNS0061"):
    
    print(f"=== {station_id} 충전기 타입 판별 디버그 ===\n")
    
    try:
        # 1. 데이터 로더로 직접 확인
        loader = ChargingDataLoader(station_id)
        df = loader.load_historical_sessions(365)
        
        if df.empty:
            print("데이터가 비어있습니다")
            return
            
        print("=== 전력 데이터 분석 ===")
        power_columns = [col for col in df.columns if "전력" in col]
        print(f"전력 관련 컬럼: {power_columns}")
        
        for col in power_columns:
            power_data = df[col].dropna()
            if not power_data.empty:
                print(f"{col}: 최대 {power_data.max():.1f}kW, 평균 {power_data.mean():.1f}kW")
        
        # 2. StationService의 타입 판별 테스트
        print("\n=== StationService 타입 판별 ===")
        service = StationService()
        
        charger_type = service._get_charger_type(df)
        is_fast = service._is_fast_charger(df)
        max_contract = service._get_charger_max_contract(df)
        
        print(f"충전기 타입: {charger_type}")
        print(f"급속충전기 여부: {is_fast}")
        print(f"최대 계약전력 제한: {max_contract}kW")
        
        # 3. 실제 계약전력 계산 테스트
        print("\n=== 계약전력 계산 테스트 ===")
        power_data = df["순간최고전력"].dropna() if "순간최고전력" in df.columns else None
        
        if power_data is not None and not power_data.empty:
            percentile_95 = power_data.quantile(0.95)
            print(f"95백분위수: {percentile_95:.1f}kW")
            
            optimal_result = service._calculate_optimal_contract_power(df, percentile_95)
            print(f"최적 계약전력 계산 결과:")
            print(f"  - 원본 예측: {optimal_result['raw_prediction']:.1f}kW")
            print(f"  - 계약 권고: {optimal_result['contract_recommendation']:.1f}kW")
            print(f"  - 제한 여부: {optimal_result['is_capped']}")
            print(f"  - 최대 제한: {optimal_result['max_limit']}kW")
            print(f"  - 충전기 타입: {optimal_result['charger_type']}")
            
        return df
        
    except Exception as e:
        print(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    debug_charger_type("BNS0061")