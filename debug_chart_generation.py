#!/usr/bin/env python3


import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend', 'app'))

from backend.app.data.loader import ChargingDataLoader
from backend.app.services.station_service import StationService

def debug_chart_generation(station_id="BNS0061"):
    
    print(f"=== 충전소 {station_id} 차트 데이터 생성 디버그 ===\n")
    
    try:
        # 1. 데이터 로더로 패턴 분석
        print("1. 패턴 분석...")
        loader = ChargingDataLoader(station_id)
        patterns = loader.analyze_charging_patterns()
        
        if "error" in patterns:
            print(f"패턴 분석 실패: {patterns['error']}")
            return
            
        print("패턴 분석 성공!")
        if "power_statistics" in patterns:
            stats = patterns["power_statistics"]
            print(f"전력 통계: {stats}")
        
        # 2. StationService로 예측 API 호출
        print("\n2. StationService 예측 API 테스트...")
        service = StationService()
        result = service.get_station_prediction(station_id)
        
        print(f"예측 결과 성공 여부: {result.get('success', False)}")
        
        if not result.get('success'):
            print(f"예측 실패: {result.get('error', 'Unknown error')}")
            return
            
        # 3. 차트 데이터 확인
        chart_data = result.get('chart_data', [])
        print(f"차트 데이터 개수: {len(chart_data)}")
        
        if chart_data:
            print("차트 데이터 샘플:")
            for i, item in enumerate(chart_data[:3]):
                print(f"  {i+1}. {item}")
        else:
            print("차트 데이터가 비어있습니다!")
            
        # 4. 필요한 키값들 확인
        required_keys = ['chart_data', 'predicted_peak', 'confidence', 'last_month_peak']
        missing_keys = [key for key in required_keys if key not in result]
        
        if missing_keys:
            print(f"누락된 키: {missing_keys}")
        else:
            print("모든 필수 키가 존재합니다!")
            
        return result
        
    except Exception as e:
        print(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    debug_chart_generation("BNS0061")