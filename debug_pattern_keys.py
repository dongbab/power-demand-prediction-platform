#!/usr/bin/env python3
"""월별 패턴 키 매칭 디버그"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend', 'app'))

from backend.app.data.loader import ChargingDataLoader

def debug_pattern_keys(station_id="BNS0061"):
    """월별 패턴 키와 실제 데이터 확인"""
    print(f"=== {station_id} 월별 패턴 키 디버그 ===\n")
    
    try:
        loader = ChargingDataLoader(station_id)
        patterns = loader.analyze_charging_patterns()
        
        if "error" in patterns:
            print(f"패턴 분석 실패: {patterns['error']}")
            return
            
        print("=== 실제 데이터 범위 ===")
        date_range = patterns.get("date_range", {})
        start_date = date_range.get("start")
        end_date = date_range.get("end")
        
        print(f"시작일: {start_date}")
        print(f"종료일: {end_date}")
        
        print("\n=== 월별 패턴 키 ===")
        monthly_patterns = patterns.get("monthly_patterns", {})
        print(f"총 {len(monthly_patterns)}개 월별 패턴:")
        
        for key, data in sorted(monthly_patterns.items()):
            print(f"  '{key}': 평균 {data['avg_power']:.1f}kW, 세션 {data['session_count']}개")
        
        # 원본 CSV에서 실제 월별 데이터 확인
        print("\n=== 원본 데이터의 실제 월별 분포 ===")
        df = loader.load_historical_sessions(days=365)  # 1년치 데이터
        
        if not df.empty:
            date_columns = [col for col in df.columns if "일시" in col or "date" in col.lower()]
            if date_columns:
                date_col = date_columns[0]
                
                # 연-월별 세션 수 확인
                df_copy = df.copy()
                df_copy["year_month"] = df_copy[date_col].dt.strftime("%Y-%m")
                monthly_counts = df_copy.groupby("year_month").size().sort_index()
                
                print("원본 데이터의 연-월별 세션 수:")
                for year_month, count in monthly_counts.items():
                    print(f"  {year_month}: {count}개 세션")
                    
                print(f"\n전체 데이터 범위: {df[date_col].min()} ~ {df[date_col].max()}")
        
        return patterns
        
    except Exception as e:
        print(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    debug_pattern_keys("BNS0061")