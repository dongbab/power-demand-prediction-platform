#!/usr/bin/env python3
"""여러 충전소의 예측값 비교 테스트"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend', 'app'))

from backend.app.services.station_service import StationService

def test_multiple_stations():
    """여러 충전소의 예측값 비교"""
    print("=== 여러 충전소 예측값 비교 테스트 ===\n")
    
    # 테스트할 충전소 목록 (BNS0061 포함)
    test_stations = [
        "BNS0061",  # 이미 확인한 충전소
        "BNS0514", 
        "BNS0819",
        "BNS0410", 
        "BNS0289"
    ]
    
    service = StationService()
    results = {}
    
    for station_id in test_stations:
        try:
            print(f"=== 충전소 {station_id} 테스트 ===")
            result = service.get_station_prediction(station_id)
            
            if result.get('success'):
                # 주요 예측값들 추출
                data = {
                    'station_id': station_id,
                    'predicted_peak': result.get('predicted_peak', 0),
                    'algorithm_prediction_kw': result.get('algorithm_prediction_kw', 0),
                    'recommended_contract_kw': result.get('recommended_contract_kw', 0),
                    'chart_data_count': len(result.get('chart_data', [])),
                    'confidence': result.get('confidence', 0),
                    'method': result.get('method', 'unknown')
                }
                results[station_id] = data
                
                print(f"  예측 전력: {data['predicted_peak']:.1f}kW")
                print(f"  알고리즘 예측: {data['algorithm_prediction_kw']:.1f}kW")
                print(f"  권고 계약전력: {data['recommended_contract_kw']:.1f}kW")
                print(f"  차트 데이터: {data['chart_data_count']}개")
                print(f"  신뢰도: {data['confidence']:.2f}")
                print(f"  방법: {data['method']}")
                
            else:
                print(f"  실패: {result.get('error', 'Unknown error')}")
                results[station_id] = {'error': result.get('error', 'Unknown error')}
                
        except Exception as e:
            print(f"  오류: {e}")
            results[station_id] = {'error': str(e)}
            
        print()
    
    # 결과 요약
    print("=== 결과 요약 ===")
    successful_results = {k: v for k, v in results.items() if 'error' not in v}
    
    if successful_results:
        print("성공한 충전소들의 예측값 비교:")
        print(f"{'충전소':<10} {'예측전력':<10} {'알고리즘':<10} {'권고계약':<10} {'신뢰도':<8}")
        print("-" * 60)
        
        for station_id, data in successful_results.items():
            print(f"{station_id:<10} {data['predicted_peak']:<10.1f} "
                  f"{data['algorithm_prediction_kw']:<10.1f} "
                  f"{data['recommended_contract_kw']:<10.1f} "
                  f"{data['confidence']:<8.2f}")
        
        # 다양성 확인
        contract_powers = [data['recommended_contract_kw'] for data in successful_results.values()]
        algorithm_predictions = [data['algorithm_prediction_kw'] for data in successful_results.values()]
        
        print(f"\n권고 계약전력 범위: {min(contract_powers):.1f} ~ {max(contract_powers):.1f}kW")
        print(f"알고리즘 예측 범위: {min(algorithm_predictions):.1f} ~ {max(algorithm_predictions):.1f}kW")
        
        # 100kW로 고정되어 있는지 확인
        unique_contracts = set(contract_powers)
        unique_algorithms = set(algorithm_predictions)
        
        if len(unique_contracts) == 1:
            print(f"⚠️  모든 충전소의 권고 계약전력이 {contract_powers[0]}kW로 동일합니다!")
        else:
            print(f"✅ 권고 계약전력이 충전소별로 다릅니다: {sorted(unique_contracts)}")
            
        if len(unique_algorithms) == 1:
            print(f"⚠️  모든 충전소의 알고리즘 예측값이 {algorithm_predictions[0]}kW로 동일합니다!")
        else:
            print(f"✅ 알고리즘 예측값이 충전소별로 다릅니다: {sorted(unique_algorithms)}")
    
    else:
        print("성공한 결과가 없습니다.")
    
    return results

if __name__ == "__main__":
    test_multiple_stations()