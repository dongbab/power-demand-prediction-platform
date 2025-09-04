# JSON 응답 구조 및 데이터 변환 가이드

## 📋 목차
- [JSON 응답 개요](#json-응답-개요)
- [데이터 변환 파이프라인](#데이터-변환-파이프라인)
- [API별 JSON 응답 구조](#api별-json-응답-구조)
- [CSV → JSON 변환 과정](#csv--json-변환-과정)
- [프론트엔드 JSON 처리](#프론트엔드-json-처리)
- [에러 응답 처리](#에러-응답-처리)

## 🎯 JSON 응답 개요

전력 수요 예측 플랫폼은 CSV 파일에서 데이터를 읽어 JSON 형태로 변환하여 프론트엔드에 제공합니다. 모든 API 응답은 일관된 JSON 구조를 따르며, 성공/실패 상태와 데이터를 포함합니다.

### 기본 응답 구조
```json
{
  "success": boolean,
  "data": object | array,
  "message": string,
  "error": string
}
```

## 🔄 데이터 변환 파이프라인

### 1. CSV 원본 데이터
```csv
권역,시군구,충전소ID,충전소명,충전소주소,충전시작일시,충전종료일시,충전량(kWh),순간최고전력
서울특별시,동작구,BNS1058,서울 흑석운수,서울특별시 동작구...,2025-06-06 09:15:00,2025-06-06 10:30:00,201.17,97.16
```

### 2. pandas DataFrame 변환
```python
# backend/app/data/loader.py
df = pd.read_csv(csv_file)
df['충전시작일시'] = pd.to_datetime(df['충전시작일시'])
df['date'] = df['충전시작일시'].dt.date
```

### 3. 데이터 집계 및 통계 계산
```python
# 일별 에너지 집계
daily_energy = df_clean.groupby("date")["충전량(kWh)"].sum()

# 통계 계산
energy_stats = {
    "total_energy": float(daily_energy.sum()),
    "avg_daily": float(daily_energy.mean()),
    "min_daily": float(daily_energy.min()),
    "max_daily": float(daily_energy.max()),
    "std_daily": float(daily_energy.std())
}
```

### 4. JSON 응답 생성
```python
response = {
    "success": True,
    "energy_statistics": energy_stats,
    "timeseries_data": timeseries_data,
    "monthly_summary": monthly_summary,
    "growth_rate": growth_rate,
    "insights": insights
}
return JSONResponse(content=response)
```

## 📊 API별 JSON 응답 구조

### 1. 전력량 수요 예측 API
**엔드포인트**: `GET /api/stations/{station_id}/energy-demand-forecast`

**응답 구조**:
```json
{
  "success": true,
  "energy_statistics": {
    "total_energy": 33311.39,      // 전체 에너지 합계 (kWh)
    "avg_daily": 594.85,           // 일평균 에너지 (kWh)
    "min_daily": 176.02,           // 일최소 에너지 (kWh)
    "max_daily": 1057.37,          // 일최대 에너지 (kWh)
    "std_daily": 210.13            // 표준편차
  },
  "timeseries_data": [
    {
      "date": "2025-06-06",        // 날짜 (YYYY-MM-DD)
      "energy": 573.75,            // 해당일 에너지 (kWh)
      "type": "actual"             // 데이터 타입: "actual" | "predicted"
    },
    {
      "date": "2025-08-01",
      "energy": 415.01,
      "type": "predicted"
    }
  ],
  "monthly_summary": [
    {
      "month": "2025-06",          // 월 (YYYY-MM)
      "total_energy": 15420.5,     // 월간 총 에너지
      "avg_daily": 514.02,         // 월간 일평균 에너지
      "days_count": 30             // 데이터 일수
    }
  ],
  "growth_rate": 0.05,             // 성장률 (소수점)
  "data_range": {
    "start_date": "2025-06-06",    // 데이터 시작일
    "end_date": "2025-07-31"       // 데이터 종료일
  },
  "insights": [
    "최고 에너지 사용량은 1057.37 kWh입니다",
    "평균 대비 높은 변동성을 보입니다"
  ],
  "station_id": "BNS1058",
  "station_name": "서울 흑석운수"
}
```

### 2. 충전소 목록 API
**엔드포인트**: `GET /api/stations`

**응답 구조**:
```json
{
  "success": true,
  "data": [
    {
      "id": "BNS1058",             // 충전소 ID
      "name": "서울 흑석운수",      // 충전소명
      "region": "서울특별시",       // 권역
      "district": "동작구",         // 시군구
      "address": "서울특별시 동작구...", // 주소
      "total_sessions": 156,        // 총 충전 세션 수
      "total_energy": 33311.39,     // 총 에너지량 (kWh)
      "avg_energy_per_session": 213.53, // 세션당 평균 에너지
      "last_charging_date": "2025-07-31", // 마지막 충전일
      "status": "active"            // 운영 상태
    }
  ],
  "pagination": {
    "total": 1,
    "limit": 9999,
    "offset": 0
  },
  "filters": {
    "search": "",
    "sort_by": "id",
    "sort_order": "asc"
  }
}
```

### 3. 최고전력 예측 API
**엔드포인트**: `GET /api/stations/{station_id}/predictions`

**응답 구조**:
```json
{
  "success": true,
  "peak_power_data": [
    {
      "date": "2025-06-06",
      "peak_power": 97.16,          // 순간최고전력 (kW)
      "type": "actual"
    },
    {
      "date": "2025-08-01",
      "peak_power": 89.5,
      "type": "predicted"
    }
  ],
  "power_statistics": {
    "max_peak": 125.8,            // 최고 피크전력
    "avg_peak": 89.2,             // 평균 피크전력
    "min_peak": 45.3              // 최저 피크전력
  },
  "station_id": "BNS1058"
}
```

## 🔧 CSV → JSON 변환 과정

### 1. 데이터 로딩
```python
class ChargingDataLoader:
    def load_historical_sessions(self, days: int = 90):
        csv_file = "data/raw/충전이력리스트_급속_202409-202507.csv"
        
        # CSV 읽기 및 기본 전처리
        df = pd.read_csv(csv_file, encoding='utf-8')
        
        # 날짜 컬럼 변환
        df['충전시작일시'] = pd.to_datetime(df['충전시작일시'])
        df['date'] = df['충전시작일시'].dt.date
        
        return df
```

### 2. 에너지 컬럼 감지
```python
def find_energy_columns(df):
    """에너지 관련 컬럼을 자동으로 찾기"""
    energy_keywords = ["에너지", "energy", "kwh", "충전량", "kWh"]
    
    energy_cols = [
        col for col in df.columns 
        if any(keyword in col.lower() for keyword in energy_keywords)
    ]
    
    return energy_cols
```

### 3. 시계열 데이터 생성
```python
def create_timeseries_data(daily_energy, station_id):
    """일별 에너지 데이터를 JSON 형태로 변환"""
    timeseries_data = []
    
    # 실제 데이터
    for date, energy in daily_energy.items():
        timeseries_data.append({
            "date": date.strftime("%Y-%m-%d"),
            "energy": round(float(energy), 2),
            "type": "actual"
        })
    
    # 예측 데이터 생성 (향후 30일)
    last_date = daily_energy.index.max()
    avg_energy = daily_energy.mean()
    
    for i in range(1, 31):
        future_date = last_date + pd.Timedelta(days=i)
        
        # 계절적 요인 적용
        seasonal_factor = calculate_seasonal_factor(future_date.month)
        weekly_factor = calculate_weekly_factor(future_date.weekday())
        
        predicted_energy = avg_energy * seasonal_factor * weekly_factor
        
        timeseries_data.append({
            "date": future_date.strftime("%Y-%m-%d"),
            "energy": round(float(predicted_energy), 2),
            "type": "predicted"
        })
    
    return timeseries_data
```

### 4. 월별 요약 생성
```python
def create_monthly_summary(daily_energy):
    """월별 집계 데이터를 JSON으로 변환"""
    monthly_summary = []
    
    # 월별 그룹핑
    monthly_data = daily_energy.groupby(daily_energy.index.to_period('M'))
    
    for month_period, month_data in monthly_data:
        monthly_summary.append({
            "month": month_period.strftime("%Y-%m"),
            "total_energy": round(float(month_data.sum()), 2),
            "avg_daily": round(float(month_data.mean()), 2),
            "days_count": len(month_data)
        })
    
    return monthly_summary
```

## 🎨 프론트엔드 JSON 처리

### 1. API 응답 수신
```javascript
// PowerDemandPredictor.svelte
async function loadEnergyForecast() {
    const url = `/api/stations/${stationId}/energy-demand-forecast?days=${days}`;
    
    try {
        const response = await fetch(url, {
            cache: "no-cache",
            signal: AbortSignal.timeout(15000)
        });
        
        const result = await response.json();
        
        if (result.success && result.timeseries_data) {
            // JSON 데이터를 내부 상태로 변환
            energyForecast = {
                daily_consumption: result.timeseries_data,    // 차트용 데이터
                energy_statistics: result.energy_statistics,  // 통계 정보
                monthly_summary: result.monthly_summary,      // 월별 요약
                insights: result.insights,                    // 인사이트
                growth_rate: result.growth_rate              // 성장률
            };
        }
    } catch (error) {
        console.error('JSON 파싱 오류:', error);
        energyForecast = null;
    }
}
```

### 2. JSON 데이터 바인딩
```javascript
// 반응형 계산 - JSON 데이터를 기반으로 UI 업데이트
$: predictedEnergyDemand = (() => {
    if (!energyForecast?.energy_statistics) {
        return 0;
    }
    
    const stats = energyForecast.energy_statistics;
    const avgDaily = stats.avg_daily || 0;
    const currentPeriod = forecastPeriods.find(p => p.value === energyForecastPeriod);
    
    return avgDaily * currentPeriod.multiplier;
})();
```

### 3. Chart.js 데이터 변환
```javascript
function prepareChartData(daily_consumption) {
    // JSON 배열을 차트 데이터로 변환
    const actualData = daily_consumption
        .filter(item => item.type === 'actual')
        .map(item => ({
            x: item.date,
            y: item.energy
        }));
    
    const predictedData = daily_consumption
        .filter(item => item.type === 'predicted')
        .map(item => ({
            x: item.date,
            y: item.energy
        }));
    
    return {
        datasets: [
            {
                label: '실제 에너지',
                data: actualData,
                borderColor: 'rgb(59, 130, 246)',
                backgroundColor: 'rgba(59, 130, 246, 0.1)'
            },
            {
                label: '예측 에너지',
                data: predictedData,
                borderColor: 'rgb(239, 68, 68)',
                backgroundColor: 'rgba(239, 68, 68, 0.1)'
            }
        ]
    };
}
```

## ❌ 에러 응답 처리

### 1. 백엔드 에러 응답
```python
# 데이터가 없는 경우
if df_station.empty:
    return JSONResponse(
        status_code=404,
        content={
            "success": False,
            "error": "해당 충전소의 데이터를 찾을 수 없습니다",
            "station_id": station_id
        }
    )

# 에너지 컬럼이 없는 경우
if not energy_cols:
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "error": "에너지 데이터 컬럼을 찾을 수 없습니다",
            "available_columns": list(df.columns)
        }
    )

# 예외 발생
except Exception as e:
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": f"서버 오류: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }
    )
```

### 2. 프론트엔드 에러 처리
```javascript
try {
    const response = await fetch(url);
    const result = await response.json();
    
    if (!result.success) {
        throw new Error(result.error || '알 수 없는 오류');
    }
    
    // 성공 처리
    energyForecast = result;
    
} catch (error) {
    console.error('API 호출 실패:', error.message);
    
    // 사용자에게 표시할 에러 메시지
    errorMessage = error.message.includes('fetch') 
        ? '네트워크 연결을 확인해주세요' 
        : error.message;
    
    energyForecast = null;
}
```

## 🚀 성능 최적화

### 1. JSON 응답 크기 최적화
```python
def optimize_response_size(data):
    """불필요한 데이터 제거 및 압축"""
    # 소수점 자리수 제한
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, float):
                data[key] = round(value, 2)
    
    return data
```

### 2. 캐시된 JSON 응답
```python
@lru_cache(maxsize=100)
def get_cached_energy_forecast(station_id: str, days: int):
    """메모리 캐시를 통한 JSON 응답 최적화"""
    cache_key = f"energy_forecast_{station_id}_{days}"
    
    # Redis 캐시 확인
    cached_json = redis_client.get(cache_key)
    if cached_json:
        return json.loads(cached_json)
    
    # 데이터 생성 및 캐시 저장
    result = generate_energy_forecast(station_id, days)
    redis_client.setex(cache_key, 1800, json.dumps(result))  # 30분 캐시
    
    return result
```

## 📈 JSON 응답 모니터링

### 1. 응답 시간 로깅
```python
import time
import logging

def log_json_response_time(func):
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        
        logging.info(f"JSON 응답 생성 시간: {end_time - start_time:.2f}초")
        logging.info(f"응답 크기: {len(json.dumps(result))} bytes")
        
        return result
    return wrapper
```

### 2. JSON 스키마 검증
```python
from jsonschema import validate, ValidationError

energy_forecast_schema = {
    "type": "object",
    "properties": {
        "success": {"type": "boolean"},
        "energy_statistics": {
            "type": "object",
            "properties": {
                "total_energy": {"type": "number"},
                "avg_daily": {"type": "number"}
            },
            "required": ["total_energy", "avg_daily"]
        },
        "timeseries_data": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "date": {"type": "string"},
                    "energy": {"type": "number"},
                    "type": {"type": "string", "enum": ["actual", "predicted"]}
                }
            }
        }
    },
    "required": ["success"]
}

def validate_json_response(data, schema):
    try:
        validate(instance=data, schema=schema)
        return True
    except ValidationError as e:
        logging.error(f"JSON 스키마 검증 실패: {e.message}")
        return False
```

---

## 📊 요약

이 플랫폼의 JSON 응답 시스템은 다음과 같이 동작합니다:

1. **CSV 입력** → pandas DataFrame으로 로드
2. **데이터 전처리** → 날짜 변환, 컬럼 매핑, 집계
3. **통계 계산** → 평균, 합계, 표준편차 등 계산
4. **예측 생성** → 계절적/주간 요인을 고려한 향후 데이터
5. **JSON 직렬화** → Python dict → JSON 문자열
6. **HTTP 응답** → FastAPI JSONResponse
7. **프론트엔드 수신** → fetch API로 JSON 파싱
8. **UI 렌더링** → Svelte 반응형 상태로 차트/메트릭 업데이트

각 단계에서 에러 처리, 캐싱, 성능 최적화가 적용되어 안정적이고 빠른 JSON 응답을 제공합니다.