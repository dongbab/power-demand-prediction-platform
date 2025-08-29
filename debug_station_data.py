#!/usr/bin/env python3
"""BNS0061 충전소 데이터 로딩 디버그 스크립트"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend', 'app'))

from backend.app.data.loader import ChargingDataLoader

def debug_station_data(station_id="BNS0061"):
    """충전소 데이터 로딩 디버그"""
    print(f"=== 충전소 {station_id} 데이터 로딩 디버그 ===\n")
    
    try:
        # 1. 데이터 로더 생성
        loader = ChargingDataLoader(station_id)
        print(f"데이터 디렉토리: {loader.data_dir}")
        
        # 2. CSV 파일 확인
        csv_files = loader.find_csv_files()
        print(f"발견된 CSV 파일 수: {len(csv_files)}")
        
        # 3. 활성 CSV 파일 확인
        active_csv = loader.get_active_csv_file()
        print(f"활성 CSV 파일: {active_csv}")
        
        # 4. 데이터 로드 시도
        print("\n=== 데이터 로드 시도 ===")
        df = loader.load_historical_sessions(days=90)
        
        if df.empty:
            print("❌ 데이터 로드 실패: DataFrame이 비어있음")
            return
            
        print(f"✅ 데이터 로드 성공: {len(df)} 행, {len(df.columns)} 컬럼")
        
        # 5. 전력 데이터 확인
        power_columns = [col for col in df.columns if "전력" in col]
        print(f"\n전력 관련 컬럼: {power_columns}")
        
        if power_columns:
            power_col = power_columns[0]
            power_data = df[power_col].dropna()
            
            if not power_data.empty:
                print(f"전력 데이터 통계 ({power_col}):")
                print(f"  - 개수: {len(power_data)}")
                print(f"  - 범위: {power_data.min():.1f} ~ {power_data.max():.1f} kW")
                print(f"  - 평균: {power_data.mean():.1f} kW")
                print(f"  - 95백분위: {power_data.quantile(0.95):.1f} kW")
        
        # 6. 날짜 데이터 확인  
        date_columns = [col for col in df.columns if "일시" in col or "date" in col.lower()]
        print(f"\n날짜 관련 컬럼: {date_columns}")
        
        if date_columns:
            date_col = date_columns[0]
            date_data = df[date_col].dropna()
            
            if not date_data.empty:
                print(f"날짜 데이터 범위 ({date_col}):")
                print(f"  - 시작: {date_data.min()}")
                print(f"  - 종료: {date_data.max()}")
        
        # 7. 패턴 분석 테스트
        print("\n=== 패턴 분석 테스트 ===")
        patterns = loader.analyze_charging_patterns()
        
        if "error" in patterns:
            print(f"❌ 패턴 분석 실패: {patterns['error']}")
        else:
            print("✅ 패턴 분석 성공")
            
            if "power_statistics" in patterns:
                stats = patterns["power_statistics"]
                print(f"전력 통계: 평균 {stats['mean']}kW, 95% {stats['percentile_95']}kW")
                
        return df, patterns
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return None, None

if __name__ == "__main__":
    debug_station_data("BNS0061")