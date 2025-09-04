#!/usr/bin/env python3
"""
Consolidated Debug Tool for Power Demand Prediction Platform

This script combines all debug functionality into a single comprehensive tool.
Replaces multiple debug scripts with unified interface.
"""

import sys
import os
import json
import logging
from typing import Optional, List, Dict, Any
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend', 'app'))

# Enable logging for debugging
logging.basicConfig(level=logging.INFO)

from backend.app.data.loader import ChargingDataLoader
from backend.app.services.station_service import StationService


class ConsolidatedDebugger:
    """Unified debugging tool for the charging station prediction system."""
    
    def __init__(self):
        self.service = StationService()
    
    def debug_station_data(self, station_id: str) -> Dict[str, Any]:
        """Debug data loading and basic statistics for a station."""
        print(f"=== 충전소 {station_id} 데이터 로딩 디버그 ===\n")
        
        try:
            loader = ChargingDataLoader(station_id)
            print(f"데이터 디렉토리: {loader.data_dir}")
            
            csv_files = loader.find_csv_files()
            print(f"발견된 CSV 파일 수: {len(csv_files)}")
            
            active_csv = loader.get_active_csv_file()
            print(f"활성 CSV 파일: {active_csv}")
            
            df = loader.load_historical_sessions(days=90)
            if df.empty:
                print("❌ 데이터 로드 실패: DataFrame이 비어있음")
                return {"success": False, "error": "Empty dataframe"}
                
            print(f"✅ 데이터 로드 성공: {len(df)} 행, {len(df.columns)} 컬럼")
            
            # Power data analysis
            power_columns = [col for col in df.columns if "전력" in col]
            power_stats = {}
            
            if power_columns:
                power_col = power_columns[0]
                power_data = df[power_col].dropna()
                
                if not power_data.empty:
                    power_stats = {
                        "count": len(power_data),
                        "min": power_data.min(),
                        "max": power_data.max(),
                        "mean": power_data.mean(),
                        "percentile_95": power_data.quantile(0.95)
                    }
                    print(f"\n전력 데이터 통계 ({power_col}):")
                    for key, value in power_stats.items():
                        if key == "count":
                            print(f"  - {key}: {value}")
                        else:
                            print(f"  - {key}: {value:.1f} kW")
            
            # Date analysis
            date_columns = [col for col in df.columns if "일시" in col or "date" in col.lower()]
            date_range = {}
            
            if date_columns:
                date_col = date_columns[0]
                date_data = df[date_col].dropna()
                if not date_data.empty:
                    date_range = {
                        "start": str(date_data.min()),
                        "end": str(date_data.max())
                    }
                    print(f"\n날짜 데이터 범위 ({date_col}):")
                    print(f"  - 시작: {date_range['start']}")
                    print(f"  - 종료: {date_range['end']}")
            
            return {
                "success": True,
                "data_shape": df.shape,
                "power_stats": power_stats,
                "date_range": date_range,
                "columns": list(df.columns)
            }
            
        except Exception as e:
            print(f"❌ 오류 발생: {e}")
            return {"success": False, "error": str(e)}
    
    def debug_pattern_analysis(self, station_id: str) -> Dict[str, Any]:
        """Debug charging pattern analysis."""
        print(f"=== 충전소 {station_id} 패턴 분석 디버그 ===\n")
        
        try:
            loader = ChargingDataLoader(station_id)
            patterns = loader.analyze_charging_patterns()
            
            if "error" in patterns:
                print(f"❌ 패턴 분석 실패: {patterns['error']}")
                return {"success": False, "error": patterns["error"]}
            
            print("✅ 패턴 분석 성공")
            
            # Date range info
            date_range = patterns.get("date_range", {})
            print(f"\n데이터 범위: {date_range.get('start')} ~ {date_range.get('end')}")
            
            # Monthly patterns
            monthly_patterns = patterns.get("monthly_patterns", {})
            print(f"\n월별 패턴 ({len(monthly_patterns)}개):")
            for key, data in sorted(monthly_patterns.items()):
                print(f"  {key}: 평균 {data['avg_power']:.1f}kW, 세션 {data['session_count']}개")
            
            # Power statistics
            if "power_statistics" in patterns:
                stats = patterns["power_statistics"]
                print(f"\n전력 통계: 평균 {stats.get('mean', 0):.1f}kW, 95% {stats.get('percentile_95', 0):.1f}kW")
            
            return {"success": True, "patterns": patterns}
            
        except Exception as e:
            print(f"❌ 오류 발생: {e}")
            return {"success": False, "error": str(e)}
    
    def debug_charger_type(self, station_id: str) -> Dict[str, Any]:
        """Debug charger type identification."""
        print(f"=== 충전소 {station_id} 충전기 타입 판별 ===\n")
        
        try:
            loader = ChargingDataLoader(station_id)
            df = loader.load_historical_sessions(365)
            
            if df.empty:
                print("❌ 데이터가 비어있습니다")
                return {"success": False, "error": "Empty data"}
            
            # Charger type analysis
            charger_type = self.service._get_charger_type(df)
            is_fast = self.service._is_fast_charger(df)
            max_contract = self.service._get_charger_max_contract(df)
            
            print(f"충전기 타입: {charger_type}")
            print(f"급속충전기 여부: {is_fast}")
            print(f"최대 계약전력 제한: {max_contract}kW")
            
            # Contract power calculation
            power_data = df["순간최고전력"].dropna() if "순간최고전력" in df.columns else None
            contract_result = {}
            
            if power_data is not None and not power_data.empty:
                percentile_95 = power_data.quantile(0.95)
                print(f"\n95백분위수: {percentile_95:.1f}kW")
                
                optimal_result = self.service._calculate_optimal_contract_power(df, percentile_95)
                contract_result = {
                    "raw_prediction": optimal_result['raw_prediction'],
                    "contract_recommendation": optimal_result['contract_recommendation'],
                    "is_capped": optimal_result['is_capped'],
                    "max_limit": optimal_result['max_limit'],
                    "charger_type": optimal_result['charger_type']
                }
                
                print(f"계약전력 계산:")
                print(f"  - 원본 예측: {contract_result['raw_prediction']:.1f}kW")
                print(f"  - 계약 권고: {contract_result['contract_recommendation']:.1f}kW")
                print(f"  - 제한 여부: {contract_result['is_capped']}")
                print(f"  - 최대 제한: {contract_result['max_limit']}kW")
            
            return {
                "success": True,
                "charger_type": charger_type,
                "is_fast_charger": is_fast,
                "max_contract": max_contract,
                "contract_calculation": contract_result
            }
            
        except Exception as e:
            print(f"❌ 오류 발생: {e}")
            return {"success": False, "error": str(e)}
    
    def debug_prediction_api(self, station_id: str) -> Dict[str, Any]:
        """Debug the complete prediction API."""
        print(f"=== 충전소 {station_id} 예측 API 디버그 ===\n")
        
        try:
            result = self.service.get_station_prediction(station_id)
            
            print(f"API 호출 성공: {result.get('success', False)}")
            
            if result.get('success'):
                # Chart data analysis
                chart_data = result.get('chart_data', [])
                print(f"차트 데이터 개수: {len(chart_data)}")
                
                if chart_data:
                    print("\n차트 데이터 샘플 (처음 5개):")
                    for i, item in enumerate(chart_data[:5]):
                        print(f"  {i+1}. {item}")
                    
                    # Data range analysis
                    months = [item.get('month', '') for item in chart_data if item.get('month')]
                    if months:
                        print(f"\n데이터 범위: {min(months)} ~ {max(months)}")
                    
                    actual_data = [item for item in chart_data if item.get('actual') is not None]
                    predicted_data = [item for item in chart_data if item.get('predicted') is not None]
                    
                    print(f"실제 데이터: {len(actual_data)}개")
                    print(f"예측 데이터: {len(predicted_data)}개")
                
                # Key metrics
                print(f"\n주요 지표:")
                print(f"  예측 전력: {result.get('predicted_peak', 0):.1f}kW")
                print(f"  알고리즘 예측: {result.get('algorithm_prediction_kw', 0):.1f}kW")
                print(f"  권고 계약전력: {result.get('recommended_contract_kw', 0):.1f}kW")
                print(f"  신뢰도: {result.get('confidence', 0):.2f}")
                print(f"  레코드 수: {result.get('record_count', 0)}")
                
                return {"success": True, "prediction_result": result}
            else:
                print(f"❌ API 호출 실패: {result.get('error', 'Unknown error')}")
                return {"success": False, "error": result.get('error', 'Unknown error')}
                
        except Exception as e:
            print(f"❌ 오류 발생: {e}")
            return {"success": False, "error": str(e)}
    
    def run_multiple_stations_test(self, station_ids: List[str]) -> Dict[str, Any]:
        """Test multiple stations for comparison."""
        print("=== 여러 충전소 비교 테스트 ===\n")
        
        results = {}
        
        for station_id in station_ids:
            try:
                print(f"충전소 {station_id} 테스트...")
                result = self.service.get_station_prediction(station_id)
                
                if result.get('success'):
                    data = {
                        'predicted_peak': result.get('predicted_peak', 0),
                        'algorithm_prediction_kw': result.get('algorithm_prediction_kw', 0),
                        'recommended_contract_kw': result.get('recommended_contract_kw', 0),
                        'confidence': result.get('confidence', 0),
                        'chart_data_count': len(result.get('chart_data', []))
                    }
                    results[station_id] = {"success": True, "data": data}
                    print(f"  ✅ 성공: 예측 {data['predicted_peak']:.1f}kW, 권고 {data['recommended_contract_kw']:.1f}kW")
                else:
                    results[station_id] = {"success": False, "error": result.get('error', 'Unknown error')}
                    print(f"  ❌ 실패: {result.get('error', 'Unknown error')}")
                    
            except Exception as e:
                results[station_id] = {"success": False, "error": str(e)}
                print(f"  ❌ 오류: {e}")
        
        # Summary
        successful = {k: v for k, v in results.items() if v.get("success")}
        if successful:
            print(f"\n성공한 충전소: {len(successful)}개")
            contract_powers = [v["data"]["recommended_contract_kw"] for v in successful.values()]
            if len(set(contract_powers)) == 1:
                print(f"⚠️  모든 충전소의 권고 계약전력이 {contract_powers[0]:.1f}kW로 동일합니다!")
            else:
                print(f"✅ 권고 계약전력 범위: {min(contract_powers):.1f} ~ {max(contract_powers):.1f}kW")
        
        return {"success": True, "results": results}
    
    def run_comprehensive_debug(self, station_id: str) -> Dict[str, Any]:
        """Run all debug tests for a single station."""
        print(f"=== 충전소 {station_id} 종합 디버그 ===\n")
        
        results = {}
        
        # Run all debug tests
        print("1. 데이터 로딩 테스트")
        results["data_loading"] = self.debug_station_data(station_id)
        print("\n" + "="*50 + "\n")
        
        print("2. 패턴 분석 테스트")
        results["pattern_analysis"] = self.debug_pattern_analysis(station_id)
        print("\n" + "="*50 + "\n")
        
        print("3. 충전기 타입 판별 테스트")
        results["charger_type"] = self.debug_charger_type(station_id)
        print("\n" + "="*50 + "\n")
        
        print("4. 예측 API 테스트")
        results["prediction_api"] = self.debug_prediction_api(station_id)
        print("\n" + "="*50 + "\n")
        
        # Summary
        success_count = sum(1 for result in results.values() if result.get("success"))
        print(f"테스트 완료: {success_count}/{len(results)}개 성공")
        
        return {"success": True, "detailed_results": results}


def main():
    """Main entry point with command line interface."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Consolidated Debug Tool for Charging Station Prediction")
    parser.add_argument("--station", "-s", default="BNS0061", help="Station ID to debug")
    parser.add_argument("--test", "-t", choices=[
        "data", "pattern", "charger", "api", "multiple", "all"
    ], default="all", help="Test type to run")
    parser.add_argument("--stations", nargs="+", 
                       default=["BNS0061", "BNS0514", "BNS0819", "BNS0410", "BNS0289"],
                       help="Station IDs for multiple station test")
    
    args = parser.parse_args()
    
    debugger = ConsolidatedDebugger()
    
    if args.test == "data":
        debugger.debug_station_data(args.station)
    elif args.test == "pattern":
        debugger.debug_pattern_analysis(args.station)
    elif args.test == "charger":
        debugger.debug_charger_type(args.station)
    elif args.test == "api":
        debugger.debug_prediction_api(args.station)
    elif args.test == "multiple":
        debugger.run_multiple_stations_test(args.stations)
    elif args.test == "all":
        debugger.run_comprehensive_debug(args.station)


if __name__ == "__main__":
    main()