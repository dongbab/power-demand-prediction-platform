# 메인 실행 파일
import asyncio
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager

from prediction.predictor import RealTimePowerPredictor
from prediction.scheduler import PredictionScheduler
from utils.config import PredictionConfig, ConfigManager
from utils.logger import setup_logger
from typing import Dict, Any
from datetime import datetime


# 전역 변수
predictor = None
scheduler = None
logger = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 생명주기 관리"""
    global predictor, scheduler, logger
    
    # 시작 시 초기화
    config = ConfigManager().config
    logger = setup_logger("main", "logs/main.log")
    
    predictor = RealTimePowerPredictor("DEFAULT_STATION")
    scheduler = PredictionScheduler()
    
    logger.info("애플리케이션 시작")
    scheduler.start_scheduled_jobs()
    
    yield
    
    # 종료 시 정리
    if scheduler:
        scheduler.stop()
    logger.info("애플리케이션 종료")


# FastAPI 앱 생성
app = FastAPI(
    title="충전소 전력 예측 API",
    description="전기차 충전소의 순간최고전력을 예측하는 시스템",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {"message": "충전소 전력 예측 시스템", "status": "running"}


@app.get("/health")
async def health_check():
    """헬스 체크"""
    return {"status": "healthy", "timestamp": asyncio.get_event_loop().time()}


@app.get("/predict/{station_id}")
async def predict_peak_power(station_id: str, hours: int = 1) -> Dict[str, Any]:
    """특정 충전소의 최고전력 예측"""
    try:
        station_predictor = RealTimePowerPredictor(station_id)
        result = await station_predictor.predict_next_hour_peak()
        
        if result is None:
            raise HTTPException(status_code=500, detail="예측 실패")
        
        return result
    except Exception as e:
        logger.error(f"예측 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stations/{station_id}/status")
async def get_station_status(station_id: str):
    """충전소 현재 상태"""
    # TODO: 실시간 상태 조회
    return {"station_id": station_id, "status": "active"}


# main.py의 월별 계약 권고 API 수정

@app.get("/api/monthly-contract/{station_id}")
async def get_monthly_contract_recommendation(station_id: str, year: int, month: int):
    """월별 계약 전력 권고 (실제 데이터 기반)"""
    try:
        # 실제 데이터 기반 예측기 사용
        predictor = RealTimePowerPredictor(station_id)
        result = await predictor.predict_monthly_peak(year, month)
        
        # 오류가 있거나 비현실적인 값이면 안전한 계산 사용
        if ('error' in result or 
            result.get('predicted_peak_kw', 0) > 100 or  # 100kW 초과는 비현실적
            result.get('predicted_peak_kw', 0) <= 0):
            
            logger.warning(f"월별 예측 오류 또는 비현실적 값: {result}")
            
            # 실제 데이터 로더에서 직접 통계 가져오기
            from data.loader import ChargingDataLoader
            loader = ChargingDataLoader(station_id)
            patterns = loader.analyze_charging_patterns()
            
            if 'power_statistics' in patterns:
                stats = patterns['power_statistics']
                
                # 실제 데이터 기반 보수적 예측
                actual_max = stats['max']
                actual_95p = stats['percentile_95']
                actual_mean = stats['mean']
                
                # 계절성 조정
                seasonal_factors = {
                    12: 1.15, 1: 1.15, 2: 1.10,  # 겨울
                    3: 1.0, 4: 1.0, 5: 1.0,      # 봄
                    6: 1.05, 7: 1.10, 8: 1.05,   # 여름
                    9: 1.0, 10: 1.0, 11: 1.05    # 가을
                }
                seasonal_factor = seasonal_factors.get(month, 1.0)
                
                # 95분위수 기반 예측 (가장 안전한 방법)
                predicted_peak = actual_95p * seasonal_factor
                
                # 안전 마진 적용 (10%)
                safety_margin = 1.10
                recommended_contract = max(
                    int(predicted_peak * safety_margin / 10) * 10,  # 10kW 단위
                    int(actual_max * 1.05 / 10) * 10  # 최소한 과거 최대값의 105%
                )
                
                # 현재 계약 대비 절약 계산
                current_contract_estimate = 70  # BNS0791 추정값 (50kW 충전기 + 여유분)
                monthly_savings = max(0, (current_contract_estimate - recommended_contract) * 30 * 8.5)
                
                result = {
                    "station_id": station_id,
                    "year": year,
                    "month": month,
                    "predicted_peak_kw": round(predicted_peak, 1),
                    "recommended_contract_kw": recommended_contract,
                    "current_estimated_contract_kw": current_contract_estimate,
                    "confidence_interval": {
                        "lower": round(predicted_peak * 0.85, 1),
                        "upper": round(predicted_peak * 1.15, 1)
                    },
                    "safety_margin": safety_margin,
                    "seasonal_factor": seasonal_factor,
                    "historical_data": {
                        "actual_max": round(actual_max, 1),
                        "actual_95percentile": round(actual_95p, 1),
                        "actual_mean": round(actual_mean, 1),
                        "data_sessions": stats['count']
                    },
                    "expected_monthly_savings": int(monthly_savings),
                    "risk_level": "Low" if predicted_peak < recommended_contract * 0.9 else "Medium",
                    "recommendation_basis": "95분위수 + 계절성 + 10% 안전마진",
                    "charger_info": {
                        "type": "완속충전기", 
                        "rated_power": "50kW",
                        "utilization_rate": f"{actual_mean/50*100:.1f}%"
                    }
                }
            else:
                # 최후의 수단: 고정값
                result = {
                    "station_id": station_id,
                    "year": year,
                    "month": month,
                    "predicted_peak_kw": 50.0,
                    "recommended_contract_kw": 60,
                    "error": "데이터 부족으로 보수적 추정",
                    "recommendation_basis": "충전기 정격 기준 보수적 추정"
                }
        
        return result
        
    except Exception as e:
        logger.error(f"월별 계약 권고 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# 추가: 충전소 상세 정보 API
@app.get("/api/station-analysis/{station_id}")
async def get_station_detailed_analysis(station_id: str):
    """충전소 상세 분석"""
    try:
        from data.loader import ChargingDataLoader
        
        loader = ChargingDataLoader(station_id)
        
        # 기본 요약
        summary = loader.get_data_summary()
        
        # 상세 패턴 분석
        patterns = loader.analyze_charging_patterns()
        
        # 실시간 상태
        realtime_status = loader.load_realtime_status()
        
        # 외부 요인
        external_factors = loader.load_external_factors()
        
        # 종합 분석
        analysis_result = {
            "station_id": station_id,
            "timestamp": datetime.now().isoformat(),
            "summary": summary,
            "patterns": patterns,
            "realtime_status": realtime_status,
            "external_factors": external_factors,
            "insights": {
                "charger_type": "완속충전기 (50kW)",
                "peak_time": patterns.get('peak_hour', {}).get('hour', 'N/A'),
                "average_utilization": f"{patterns.get('power_statistics', {}).get('mean', 0)/50*100:.1f}%",
                "efficiency_rating": "높음" if patterns.get('power_statistics', {}).get('mean', 0) > 30 else "보통"
            }
        }
        
        return analysis_result
        
    except Exception as e:
        logger.error(f"충전소 분석 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# 테스트용 간단한 대시보드 HTML
@app.get("/dashboard")
async def dashboard():
    """간단한 대시보드"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>충전소 전력 예측 대시보드</title>
        <meta charset="UTF-8">
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .container { max-width: 1200px; margin: 0 auto; }
            .card { border: 1px solid #ddd; border-radius: 8px; padding: 20px; margin: 10px 0; }
            .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
            .metric { background: #f5f5f5; padding: 15px; border-radius: 5px; text-align: center; }
            .metric h3 { margin: 0; color: #333; }
            .metric .value { font-size: 2em; font-weight: bold; color: #007bff; }
            button { background: #007bff; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; }
            button:hover { background: #0056b3; }
            #results { background: #f8f9fa; padding: 15px; border-radius: 5px; margin-top: 10px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>⚡ 충전소 전력 예측 대시보드</h1>
            
            <div class="card">
                <h2>BNS0791 - 충남 아산 아산세교초등학교</h2>
                <div class="grid">
                    <div class="metric">
                        <h3>현재 예측 전력</h3>
                        <div class="value" id="current-power">-</div>
                        <div>kW</div>
                    </div>
                    <div class="metric">
                        <h3>권고 계약 전력</h3>
                        <div class="value" id="contract-power">-</div>
                        <div>kW</div>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <h2>API 테스트</h2>
                <button onclick="testRealtime()">실시간 예측 조회</button>
                <button onclick="testMonthly()">월별 계약 권고</button>
                <button onclick="testAnalysis()">상세 분석</button>
                <div id="results"></div>
            </div>
        </div>
        
        <script>
            async function testRealtime() {
                try {
                    const response = await fetch('/predict/BNS0791');
                    const data = await response.json();
                    document.getElementById('current-power').textContent = data.predicted_peak;
                    document.getElementById('results').innerHTML = '<pre>' + JSON.stringify(data, null, 2) + '</pre>';
                } catch (error) {
                    document.getElementById('results').innerHTML = '오류: ' + error.message;
                }
            }
            
            async function testMonthly() {
                try {
                    const response = await fetch('/api/monthly-contract/BNS0791?year=2025&month=6');
                    const data = await response.json();
                    document.getElementById('contract-power').textContent = data.recommended_contract_kw;
                    document.getElementById('results').innerHTML = '<pre>' + JSON.stringify(data, null, 2) + '</pre>';
                } catch (error) {
                    document.getElementById('results').innerHTML = '오류: ' + error.message;
                }
            }
            
            async function testAnalysis() {
                try {
                    const response = await fetch('/api/station-analysis/BNS0791');
                    const data = await response.json();
                    document.getElementById('results').innerHTML = '<pre>' + JSON.stringify(data, null, 2) + '</pre>';
                } catch (error) {
                    document.getElementById('results').innerHTML = '오류: ' + error.message;
                }
            }
            
            // 페이지 로드시 자동 조회
            window.onload = function() {
                testRealtime();
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


if __name__ == "__main__":
    config = ConfigManager().config
    uvicorn.run(
        "main:app",
        host=config.api_host,
        port=config.api_port,
        workers=config.api_workers,
        reload=True
    )


if __name__ == "__main__":
    config = ConfigManager().config
    uvicorn.run(
        "main:app",
        host=config.api_host,
        port=config.api_port,
        workers=config.api_workers,
        reload=True
    )
