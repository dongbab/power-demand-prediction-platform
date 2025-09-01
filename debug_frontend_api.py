#!/usr/bin/env python3


import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend', 'app'))

from backend.app.services.station_service import StationService
import json

def debug_frontend_api(station_id="BNS0061"):
    
    print(f"=== {station_id} API 응답 디버그 ===\n")
    
    try:
        service = StationService()
        result = service.get_station_prediction(station_id)
        
        print(f"성공 여부: {result.get('success', False)}")
        
        if result.get('success'):
            # 차트 데이터 확인
            chart_data = result.get('chart_data', [])
            print(f"차트 데이터 개수: {len(chart_data)}")
            
            if chart_data:
                print("\n=== 차트 데이터 샘플 ===")
                for i, item in enumerate(chart_data):
                    print(f"{i+1:2d}. {item}")
                    if i >= 10:  # 처음 10개만 표시
                        print("    ... (더 많은 데이터)")
                        break
                
                # 데이터 범위 확인
                months = [item.get('month', '') for item in chart_data if item.get('month')]
                if months:
                    print(f"\n데이터 범위: {min(months)} ~ {max(months)}")
                
                # 실제 데이터와 예측 데이터 구분
                actual_data = [item for item in chart_data if item.get('actual') is not None]
                predicted_data = [item for item in chart_data if item.get('predicted') is not None]
                
                print(f"실제 데이터: {len(actual_data)}개")
                print(f"예측 데이터: {len(predicted_data)}개")
                
            else:
                print("❌ 차트 데이터가 비어있습니다!")
                
            # 기타 중요 필드들
            print(f"\n=== 기타 응답 데이터 ===")
            print(f"예측 전력: {result.get('predicted_peak', 0)}kW")
            print(f"신뢰도: {result.get('confidence', 0):.2f}")
            print(f"데이터 시작일: {result.get('data_start_date', 'N/A')}")
            print(f"데이터 종료일: {result.get('data_end_date', 'N/A')}")
            print(f"레코드 수: {result.get('record_count', 0)}")
            
        else:
            print(f"❌ API 호출 실패: {result.get('error', 'Unknown error')}")
            
        return result
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    debug_frontend_api("BNS0061")