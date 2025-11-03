"""
간단한 API 테스트 스크립트
"""
import requests
import json
from datetime import datetime

BASE_URL = "http://127.0.0.1:8000"

def test_health():
    """헬스체크 테스트"""
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"✅ Health Check: {response.status_code}")
        print(f"   Response: {response.json()}")
        return True
    except Exception as e:
        print(f"❌ Health Check Failed: {e}")
        return False

def test_ensemble_prediction():
    """앙상블 예측 API 테스트"""
    station_id = "BNS0822"
    current_contract = 100
    
    try:
        url = f"{BASE_URL}/api/stations/{station_id}/ensemble-prediction"
        params = {"current_contract_kw": current_contract}
        
        print(f"\n🔍 Testing Ensemble Prediction API...")
        print(f"   URL: {url}")
        print(f"   Params: {params}")
        
        response = requests.get(url, params=params)
        print(f"\n✅ Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n📊 Ensemble Prediction Results:")
            print(f"   Final Prediction: {data['ensemble_prediction']['final_prediction_kw']:.2f} kW")
            print(f"   LSTM: {data['ensemble_prediction']['lstm']['prediction_kw']:.2f} kW (weight: {data['ensemble_prediction']['lstm']['weight']})")
            print(f"   XGBoost: {data['ensemble_prediction']['xgboost']['prediction_kw']:.2f} kW (weight: {data['ensemble_prediction']['xgboost']['weight']})")
            print(f"\n🏷️  Maturity: {data['ensemble_prediction']['maturity_classification']['category']}")
            print(f"   Sessions: {data['ensemble_prediction']['maturity_classification']['total_sessions']}")
            print(f"\n💡 Contract Recommendation:")
            print(f"   Recommended: {data['contract_recommendation']['recommended_kw']} kW")
            print(f"   Current: {data['contract_recommendation']['current_kw']} kW")
            print(f"   Annual Savings: ₩{data['contract_recommendation']['annual_savings_won']:,}")
            print(f"   Risk Assessment: {data['contract_recommendation']['risk_assessment']}")
            
            return True
        else:
            print(f"❌ Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Ensemble Prediction Test Failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """메인 테스트 실행"""
    print("=" * 60)
    print(f"🚀 API Test Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 1. 헬스체크
    if not test_health():
        print("\n⚠️  서버가 실행중이지 않습니다. 먼저 서버를 시작하세요:")
        print("   cd backend && python -m uvicorn app.main:app --reload")
        return
    
    # 2. 앙상블 예측 테스트
    test_ensemble_prediction()
    
    print("\n" + "=" * 60)
    print("✅ API Test Completed")
    print("=" * 60)

if __name__ == "__main__":
    main()
