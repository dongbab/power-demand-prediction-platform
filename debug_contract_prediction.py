#!/usr/bin/env python3


import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend', 'app'))

from backend.app.services.station_service import StationService

def debug_contract_prediction(station_id="BNS0061"):
    
    print(f"=== {station_id} 권고계약 전력 분석 ===\n")
    
    try:
        service = StationService()
        result = service.get_station_prediction(station_id)
        
        if not result.get('success'):
            print(f"❌ API 호출 실패: {result.get('error', 'Unknown error')}")
            return
        
        print("=== 예측 관련 값들 ===")
        predicted_peak = result.get('predicted_peak', 0)
        algorithm_prediction_kw = result.get('algorithm_prediction_kw', 0)
        recommended_contract_kw = result.get('recommended_contract_kw', 0)
        current_peak = result.get('current_peak', 0)
        last_month_peak = result.get('last_month_peak', 0)
        confidence = result.get('confidence', 0)
        
        print(f"예측 전력 (predicted_peak): {predicted_peak:.1f}kW")
        print(f"알고리즘 예측 (algorithm_prediction_kw): {algorithm_prediction_kw:.1f}kW") 
        print(f"권고 계약전력 (recommended_contract_kw): {recommended_contract_kw:.1f}kW")
        print(f"현재 피크 (current_peak): {current_peak:.1f}kW")
        print(f"마지막달 피크 (last_month_peak): {last_month_peak:.1f}kW")
        print(f"신뢰도: {confidence:.2f}")
        
        print(f"\n=== 값들 간의 관계 ===")
        print(f"예측값 vs 권고계약: {predicted_peak:.1f} vs {recommended_contract_kw:.1f} (차이: {abs(predicted_peak - recommended_contract_kw):.1f}kW)")
        print(f"알고리즘 vs 권고계약: {algorithm_prediction_kw:.1f} vs {recommended_contract_kw:.1f} (차이: {abs(algorithm_prediction_kw - recommended_contract_kw):.1f}kW)")
        print(f"현재피크 vs 권고계약: {current_peak:.1f} vs {recommended_contract_kw:.1f} (차이: {abs(current_peak - recommended_contract_kw):.1f}kW)")
        
        # 예측과 권고계약의 관계가 이상한지 확인
        if abs(predicted_peak - recommended_contract_kw) > 20:
            print(f"⚠️  예측값과 권고계약 전력의 차이가 20kW 이상입니다!")
            
        if algorithm_prediction_kw == recommended_contract_kw:
            print("✅ 알고리즘 예측값이 권고계약 전력과 동일합니다")
        elif algorithm_prediction_kw > recommended_contract_kw:
            print(f"⚠️  알고리즘 예측값이 권고계약 전력보다 {algorithm_prediction_kw - recommended_contract_kw:.1f}kW 높습니다 (제한됨)")
        else:
            print(f"ℹ️  알고리즘 예측값이 권고계약 전력보다 {recommended_contract_kw - algorithm_prediction_kw:.1f}kW 낮습니다")
        
        # 차트 데이터의 최근 실제값과 비교
        chart_data = result.get('chart_data', [])
        if chart_data:
            recent_actual_values = [item['actual'] for item in chart_data if item.get('actual') is not None]
            if recent_actual_values:
                max_actual = max(recent_actual_values)
                avg_actual = sum(recent_actual_values) / len(recent_actual_values)
                
                print(f"\n=== 차트 데이터 비교 ===")
                print(f"차트 실제값 최대: {max_actual:.1f}kW")
                print(f"차트 실제값 평균: {avg_actual:.1f}kW")
                print(f"권고계약 전력: {recommended_contract_kw:.1f}kW")
                
                if recommended_contract_kw < max_actual:
                    print(f"⚠️  권고계약 전력이 실제 최대값보다 {max_actual - recommended_contract_kw:.1f}kW 낮습니다!")
                elif recommended_contract_kw > max_actual * 1.5:
                    print(f"⚠️  권고계약 전력이 실제 최대값의 1.5배를 초과합니다!")
                else:
                    print("✅ 권고계약 전력이 적절한 범위에 있습니다")
        
        return result
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    debug_contract_prediction("BNS0061")