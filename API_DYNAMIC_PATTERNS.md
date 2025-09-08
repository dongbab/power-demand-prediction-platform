# 🔄 Dynamic Pattern API 명세

## 개요

기존 API에 **동적 패턴 분석(Dynamic Pattern Analysis)** 기능이 추가되어, 실제 데이터에서 추출한 패턴 정보를 제공합니다.

---

## 🔮 예측 API (Enhanced)

### 엔드포인트
```
GET /api/stations/{station_id}/prediction
```

### 요청 예시
```bash
curl -X GET "http://220.69.200.55:32375/api/stations/BNS0001/prediction" \
  -H "Authorization: Bearer your_api_key"
```

### 응답 구조 (Enhanced)

```json
{
  "success": true,
  "station_id": "BNS0001",
  "station_name": "서울역 충전소",
  "predicted_peak": 87.5,
  "confidence": 0.87,
  "recommended_contract_kw": 100.0,
  "algorithm_prediction_kw": 92.3,
  "prediction_exceeds_limit": false,
  "method": "advanced_ensemble_models",
  "timestamp": "2024-09-04T15:30:00",
  
  // Dynamic Pattern Analysis Information
  "pattern_analysis": {
    "analysis_method": "dynamic_pattern_analysis",
    "pattern_confidence": 0.87,
    "data_quality": "excellent",
    "seasonal_strength": 0.23,
    "weekly_strength": 0.45,
    "trend_factor": 1.05
  },
  
  // Enhanced model information
  "advanced_model_prediction": {
    "final_prediction": 100,
    "raw_prediction": 92.3,
    "ensemble_method": "weighted_confidence_with_dynamic_patterns",
    "model_count": 8,
    "uncertainty": 12.5,
    "model_weights": {
      "GEV_Distribution": 0.15,
      "Bootstrap_95th_Percentile": 0.18,
      "Weighted_Percentile_Ensemble": 0.22,
      "Fast_Percentile_95": 0.12,
      "Exponential_Smoothing": 0.08,
      "Linear_Trend": 0.10,
      "Robust_Statistics": 0.15
    },
    "visualization_data": {
      "histogram": {
        "counts": [2, 8, 15, 23, 18, 12, 8, 4, 1],
        "bins": [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
      },
      "statistics": {
        "min": 12.5,
        "max": 95.2,
        "mean": 45.8,
        "median": 43.2,
        "std": 18.7,
        "percentile_95": 87.5,
        "percentile_99": 92.1
      }
    }
  },
  
  "chart_data": [
    {
      "month": "2024-01",
      "actual": 82.1,
      "predicted": null
    },
    {
      "month": "2024-02", 
      "actual": null,
      "predicted": 87.5
    }
  ],
  
  "data_start_date": "2023-09-01T00:00:00",
  "data_end_date": "2024-09-01T00:00:00",
  "record_count": 1250
}
```

---

## 📊 패턴 분석 정보 상세

### pattern_analysis 객체

```typescript
interface PatternAnalysis {
  analysis_method: "dynamic_pattern_analysis" | "fallback_static_patterns";
  pattern_confidence: number;        // 0.3-0.9 패턴 신뢰도
  data_quality: "excellent" | "good" | "fair" | "limited" | "fallback";
  seasonal_strength?: number;        // 0.0-1.0 계절성 패턴 강도
  weekly_strength?: number;          // 0.0-1.0 요일 패턴 강도  
  trend_factor?: number;             // 0.8-1.2 트렌드 조정 계수
}
```

### 데이터 품질 등급

| data_quality | 설명 | 데이터량 | 기간 | confidence 범위 |
|--------------|------|-----------|------|------------------|
| `excellent` | 우수한 품질 | 1000+ | 6개월+ | 0.85-0.95 |
| `good` | 양호한 품질 | 500+ | 3개월+ | 0.75-0.85 |
| `fair` | 보통 품질 | 200+ | 2개월+ | 0.65-0.75 |
| `limited` | 제한적 품질 | <200 | <2개월 | 0.50-0.65 |
| `fallback` | 기본값 사용 | 없음 | 없음 | 0.30 |

### 패턴 강도 해석

```javascript
// 계절성 패턴 강도
if (seasonal_strength > 0.4) {
  console.log("강한 계절성 패턴 (여름/겨울 차이 뚜렷)");
} else if (seasonal_strength > 0.2) {
  console.log("중간 계절성 패턴"); 
} else {
  console.log("약한 계절성 패턴 (연중 비슷)");
}

// 요일 패턴 강도
if (weekly_strength > 0.4) {
  console.log("강한 요일 패턴 (주중/주말 차이 뚜렷)");
} else if (weekly_strength > 0.2) {
  console.log("중간 요일 패턴");
} else {
  console.log("약한 요일 패턴 (요일별 비슷)");
}

// 트렌드 요인
if (trend_factor > 1.1) {
  console.log("상승 트렌드 (사용량 증가)");
} else if (trend_factor < 0.9) {
  console.log("하락 트렌드 (사용량 감소)");
} else {
  console.log("안정 트렌드 (변화 없음)");
}
```

---

## 🔧 앙상블 모델 정보

### ensemble_method 값

| 값 | 설명 |
|----|------|
| `weighted_confidence_with_dynamic_patterns` | 동적 패턴이 적용된 앙상블 예측 |
| `weighted_confidence` | 기본 앙상블 예측 (패턴 미적용) |
| `fallback` | 단순 폴백 예측 |

### model_weights 해석

```json
{
  "model_weights": {
    "GEV_Distribution": 0.15,           // 일반화 극값 분포
    "Bootstrap_95th_Percentile": 0.18,  // 부트스트랩 95% 분위수
    "Weighted_Percentile_Ensemble": 0.22, // 가중 분위수 앙상블
    "Fast_Percentile_95": 0.12,         // 빠른 95% 분위수
    "Exponential_Smoothing": 0.08,      // 지수평활법
    "Linear_Trend": 0.10,               // 선형 추세 분석
    "Robust_Statistics": 0.15           // 강건 통계 방법
  }
}
```

**가중치 해석**:
- 높은 가중치 (>0.15): 해당 모델이 예측에 큰 영향
- 중간 가중치 (0.08-0.15): 보조적 역할
- 낮은 가중치 (<0.08): 제한적 영향

---

## 🎯 실제 사용 예시

### 프론트엔드 활용 (JavaScript)

```javascript
async function loadStationPrediction(stationId) {
  const response = await fetch(`/api/stations/${stationId}/prediction`);
  const data = await response.json();
  
  if (data.success && data.pattern_analysis) {
    const pattern = data.pattern_analysis;
    
    // 패턴 신뢰도에 따른 UI 조정
    if (pattern.pattern_confidence > 0.8) {
      showHighConfidenceIndicator();
      displayPatternInsights(pattern);
    }
    
    // 데이터 품질 표시
    displayDataQuality(pattern.data_quality);
    
    // 트렌드 정보 표시  
    if (pattern.trend_factor > 1.05) {
      showTrendAlert("상승 트렌드 감지: 사용량이 증가하고 있습니다");
    }
    
    // 예측값 표시
    displayPrediction({
      predicted: data.predicted_peak,
      recommended: data.recommended_contract_kw,
      confidence: data.confidence
    });
  }
}

function displayPatternInsights(pattern) {
  const insights = [];
  
  if (pattern.seasonal_strength > 0.3) {
    insights.push("계절별 사용 패턴이 뚜렷합니다");
  }
  
  if (pattern.weekly_strength > 0.3) {
    insights.push("주중/주말 사용 패턴 차이가 있습니다");
  }
  
  return insights;
}
```

### Python 클라이언트 예시

```python
import requests

def get_station_prediction(station_id: str, api_key: str):
    """
    동적 패턴 분석이 포함된 충전소 예측 정보 조회
    """
    url = f"http://220.69.200.55:32375/api/stations/{station_id}/prediction"
    headers = {"Authorization": f"Bearer {api_key}"}
    
    response = requests.get(url, headers=headers)
    data = response.json()
    
    if data.get("success"):
        pattern_info = data.get("pattern_analysis", {})
        
        print(f"충전소: {data['station_id']}")
        print(f"예측 전력: {data['predicted_peak']}kW")
        print(f"권고 계약전력: {data['recommended_contract_kw']}kW")
        print(f"신뢰도: {data['confidence']:.2%}")
        
        # 패턴 분석 정보
        if pattern_info.get("analysis_method") == "dynamic_pattern_analysis":
            print(f"\n📊 동적 패턴 분석 결과:")
            print(f"  - 패턴 신뢰도: {pattern_info['pattern_confidence']:.2%}")
            print(f"  - 데이터 품질: {pattern_info['data_quality']}")
            print(f"  - 계절성 강도: {pattern_info.get('seasonal_strength', 0):.2%}")
            print(f"  - 요일 강도: {pattern_info.get('weekly_strength', 0):.2%}")
            print(f"  - 트렌드 요인: {pattern_info.get('trend_factor', 1.0):.3f}")
        
        return data
    else:
        print(f"Error: {data.get('error', 'Unknown error')}")
        return None

# 사용 예시
prediction = get_station_prediction("BNS0001", "your_api_key")
```

---

## ⚠️ 주의사항 및 제한

### 1. 패턴 분석 조건
- **최소 데이터**: 50개 이상의 충전 세션
- **권장 기간**: 최소 60일, 권장 180일 이상
- **데이터 품질**: 이상값이 30% 미만

### 2. 신뢰도 해석
```python
if confidence < 0.5:
    print("⚠️ 낮은 신뢰도: 데이터가 부족하거나 패턴이 불규칙함")
elif confidence < 0.7:
    print("⚡ 보통 신뢰도: 참고용으로 활용")  
elif confidence < 0.9:
    print("✅ 높은 신뢰도: 예측 결과 신뢰 가능")
else:
    print("🎯 매우 높은 신뢰도: 정확한 예측 결과")
```

### 3. 패턴 미적용 경우
- `pattern_confidence < 0.5`: 동적 패턴 미적용
- `data_quality == "fallback"`: 기본 통계 방법 사용
- `analysis_method == "fallback_static_patterns"`: 정적 요인 사용

---

## 🔄 버전 호환성

### v0.0.4 (현재 버전)
- ✅ `pattern_analysis` 필드 추가
- ✅ `ensemble_method` 업데이트  
- ✅ 동적 패턴 분석 지원

### v0.0.3 (이전 버전)
- ❌ `pattern_analysis` 필드 없음
- ❌ 정적 요인만 지원

### 하위 호환성
기존 클라이언트는 새 필드를 무시하고 기존 필드만 사용하면 정상 동작합니다.

---

## 📈 성능 정보

### 응답 시간
- **일반적인 경우**: 2-5초
- **캐시 히트**: <1초  
- **대용량 데이터**: 5-10초

### 캐시 정책
- **패턴 분석**: 데이터 변경시까지 유지
- **예측 결과**: 30분 캐시
- **기본 통계**: 1시간 캐시

---

## 🆘 문제 해결

### 1. pattern_analysis 필드가 없는 경우
```bash
# 응답 확인
curl -v "http://220.69.200.55:32375/api/stations/BNS0001/prediction"

# 서버 로그 확인 
tail -f logs/main.log | grep "pattern"
```

### 2. 낮은 신뢰도 (confidence < 0.5)
```bash
# 데이터 품질 확인
python debug_consolidated.py --station BNS0001 --test data

# 패턴 분석 확인  
python debug_consolidated.py --station BNS0001 --test pattern
```

### 3. analysis_method가 fallback인 경우
- 데이터가 부족하거나 품질이 낮음
- 더 많은 충전 세션 데이터 필요
- 최소 60일, 50회 이상 충전 세션 권장

---

**문서 버전**: v1.0  
**API 버전**: v0.0.4  
**마지막 업데이트**: 2024-09-04