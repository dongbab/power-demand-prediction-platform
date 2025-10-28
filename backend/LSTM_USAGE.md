# LSTM 예측 엔진 사용 가이드

## 개요

기존의 복잡한 다중 모델 앙상블 시스템을 LSTM 딥러닝 모델로 단순화했습니다.

### 주요 개선 사항

- **코드 라인 수**: 400+ 줄 → ~600줄 (단일 파일)
- **모델 개수**: 3개 클래스 (ExtremeValueModels, StatisticalModels, TimeSeriesModels) → 1개 (LSTMPredictionEngine)
- **병렬 처리**: ThreadPoolExecutor 제거 → 단일 LSTM 모델
- **복잡도**: 수동 앙상블 로직 → 자동 학습
- **성능**: 통계 모델 조합 → 딥러닝 시계열 학습

---

## 설치

### 1. 의존성 설치

```bash
cd backend
pip install -r requirements.txt
```

새로 추가된 패키지:
- `tensorflow>=2.13.0` - LSTM 모델
- `scikit-learn>=1.3.0` - 데이터 전처리

---

## 사용 방법

### 방법 1: 기존 코드에서 간단히 교체

기존 `PredictionEngine`을 `LSTMPredictionEngine`으로 교체하면 됩니다.

```python
# Before
from app.prediction.prediction_engine import PredictionEngine
engine = PredictionEngine()

# After
from app.prediction.lstm_prediction_engine import LSTMPredictionEngine
engine = LSTMPredictionEngine()

# 사용법은 동일
prediction = engine.predict_contract_power(data, station_id="ST001")
```

### 방법 2: 학습된 모델 사용

```python
from app.prediction.lstm_prediction_engine import LSTMPredictionEngine

# 학습된 모델 로드
engine = LSTMPredictionEngine(model_path="models/lstm_model")

# 예측
prediction = engine.predict_contract_power(
    data=station_data,
    station_id="ST001",
    charger_type="급속충전기 (DC)"
)

print(f"예측 계약전력: {prediction.final_prediction} kW")
print(f"신뢰도: {prediction.model_predictions[0].confidence_score}")
```

---

## 모델 학습

### 데이터 준비

학습 데이터는 다음 형식이어야 합니다:

**필수 컬럼:**
- `순간최고전력` (float): 전력 데이터

**선택 컬럼 (시계열 분석용):**
- `충전시작일시` (datetime): 타임스탬프
- `사용일시` (datetime): 대체 타임스탬프

**예시 CSV:**
```csv
충전시작일시,순간최고전력
2024-01-01 08:00:00,45.2
2024-01-01 09:00:00,52.8
2024-01-01 10:00:00,48.5
...
```

### 학습 실행

#### 단일 파일 학습

```bash
python -m app.prediction.train_lstm \
    --data_path data/training_data.csv \
    --model_path models/lstm_model \
    --epochs 50 \
    --batch_size 32
```

#### 여러 파일 동시 학습

디렉토리의 모든 CSV/Excel 파일을 자동으로 합쳐서 학습합니다:

```bash
python -m app.prediction.train_lstm \
    --data_path data/stations/ \
    --model_path models/lstm_model \
    --epochs 100 \
    --batch_size 64
```

#### 학습 파라미터

| 파라미터 | 설명 | 기본값 |
|---------|------|-------|
| `--data_path` | 학습 데이터 경로 (파일 또는 디렉토리) | 필수 |
| `--model_path` | 모델 저장 경로 | models/lstm_model |
| `--epochs` | 학습 에포크 수 | 50 |
| `--batch_size` | 배치 크기 | 32 |
| `--validation_split` | 검증 데이터 비율 | 0.2 |

### 학습 출력 예시

```
============================================================
LSTM Model Training Started
============================================================
Step 1: Loading training data...
Loaded 5000 rows, columns: ['충전시작일시', '순간최고전력']

Step 2: Initializing LSTM engine...
LSTM model built successfully

Step 3: Training LSTM model...
Epoch 1/50
157/157 [==============================] - 5s 28ms/step - loss: 125.4321 - mae: 8.5432 - val_loss: 98.7654 - val_mae: 7.2345
...
Epoch 35/50
157/157 [==============================] - 3s 19ms/step - loss: 12.3456 - mae: 2.5678 - val_loss: 15.6789 - val_mae: 3.1234

============================================================
Training Results:
============================================================
  ✓ Success!
  - Final Loss: 12.3456
  - Final Val Loss: 15.6789
  - Final MAE: 2.5678 kW
  - Epochs Trained: 35
  - Training Samples: 4976

Step 4: Saving model to models/lstm_model...
  ✓ Model saved successfully

Step 5: Running test prediction...
  - Test Prediction: 58 kW
  - Ensemble Method: weighted_lstm_statistical
  - Uncertainty: 3.45

============================================================
Training Completed Successfully!
============================================================
```

---

## 코드 예시

### 기본 예측

```python
from app.prediction.lstm_prediction_engine import LSTMPredictionEngine
import pandas as pd

# 엔진 초기화
engine = LSTMPredictionEngine(model_path="models/lstm_model")

# 데이터 로드
data = pd.read_csv("station_data.csv")
data['충전시작일시'] = pd.to_datetime(data['충전시작일시'])
data.set_index('충전시작일시', inplace=True)

# 예측
result = engine.predict_contract_power(
    data=data,
    station_id="ST001",
    charger_type="급속충전기 (DC)"
)

# 결과 출력
print(f"최종 예측: {result.final_prediction} kW")
print(f"원본 예측: {result.raw_prediction:.2f} kW")
print(f"불확실성: {result.uncertainty:.2f}")
print(f"사용된 모델: {[p.model_name for p in result.model_predictions]}")
```

### 모델 학습 (Python 코드)

```python
from app.prediction.lstm_prediction_engine import LSTMPredictionEngine
import pandas as pd

# 학습 데이터 로드
training_data = pd.read_csv("data/all_stations_2024.csv")
training_data['충전시작일시'] = pd.to_datetime(training_data['충전시작일시'])
training_data.set_index('충전시작일시', inplace=True)

# 엔진 초기화
engine = LSTMPredictionEngine()

# 학습
history = engine.train_model(
    training_data=training_data,
    epochs=100,
    batch_size=64,
    validation_split=0.2
)

if history['success']:
    print(f"학습 완료! MAE: {history['final_mae']:.2f} kW")

    # 모델 저장
    engine.save_model("models/my_lstm_model")
else:
    print(f"학습 실패: {history.get('error')}")
```

### TensorFlow 없이 사용 (통계적 폴백)

TensorFlow가 설치되지 않은 환경에서는 자동으로 통계적 방법을 사용합니다:

```python
from app.prediction.lstm_prediction_engine import LSTMPredictionEngine

# TensorFlow가 없어도 작동
engine = LSTMPredictionEngine()

# 95th percentile 기반 통계 예측 자동 사용
prediction = engine.predict_contract_power(data, "ST001")
```

---

## LSTM 모델 구조

### 아키텍처

```
Input: (sequence_length=24, features=6)
    ↓
LSTM Layer 1: 64 units, dropout=0.2
    ↓
LSTM Layer 2: 32 units, dropout=0.2
    ↓
Dense Layer 1: 16 units, ReLU
    ↓
Dropout: 0.1
    ↓
Output Layer: 1 unit (predicted power)
```

### 입력 특징 (6개)

1. **정규화된 전력값** (0-1 범위)
2. **시간 (sin)** - 하루 주기 (0-23시)
3. **요일 (sin)** - 주간 주기 (월-일)
4. **월 (sin)** - 계절 주기 (1-12월)
5. **시간 (cos)** - 추가 시간 정보
6. **요일 (cos)** - 추가 요일 정보

### 학습 전략

- **Optimizer**: Adam (learning_rate=0.001)
- **Loss**: MSE (Mean Squared Error)
- **Metrics**: MAE (Mean Absolute Error)
- **Early Stopping**: val_loss 기준, patience=10
- **Learning Rate Reduction**: val_loss 기준, patience=5

---

## API 응답 형식

예측 결과는 `EnsemblePrediction` 객체로 반환됩니다:

```python
{
    "final_prediction": 58,  # 최종 예측값 (kW, 정수)
    "raw_prediction": 57.8,  # 원본 예측값 (kW, 실수)
    "ensemble_method": "weighted_lstm_statistical",
    "uncertainty": 3.45,
    "weights": {
        "LSTM_Deep_Learning": 0.70,
        "Statistical_Baseline": 0.30
    },
    "model_predictions": [
        {
            "model_name": "LSTM_Deep_Learning",
            "predicted_value": 59.2,
            "confidence_interval": [52.3, 66.1],
            "confidence_score": 0.85,
            "method_details": {
                "method": "LSTM Deep Learning",
                "sequence_length": 24,
                "feature_dim": 6,
                "description": "LSTM 딥러닝 기반 시계열 예측"
            }
        },
        {
            "model_name": "Statistical_Baseline",
            "predicted_value": 54.5,
            "confidence_interval": [48.2, 60.8],
            "confidence_score": 0.70,
            "method_details": {
                "method": "95th Percentile",
                "description": "통계적 기준선"
            }
        }
    ]
}
```

---

## 기존 코드와의 비교

### 기존 PredictionEngine

```python
# 복잡한 구조
- PredictionEngine (main)
  - ExtremeValueModels (3개 모델)
  - StatisticalModels (5개 모델)
  - TimeSeriesModels (2개 모델)
  - DynamicPatternAnalyzer
  - ThreadPoolExecutor (병렬 처리)
  - 수동 앙상블 로직
  - 복잡한 캐싱 메커니즘

# 총 10개 이상의 모델을 실행하고 가중치 조합
```

### 새로운 LSTMPredictionEngine

```python
# 단순한 구조
- LSTMPredictionEngine
  - LSTM 모델 (단일 딥러닝 모델)
  - Statistical Fallback (보조)

# 1-2개 모델만 사용, 자동 학습
```

### 성능 비교

| 항목 | 기존 | LSTM |
|-----|------|------|
| 코드 복잡도 | 매우 높음 | 낮음 |
| 모델 수 | 10+ | 1-2 |
| 학습 필요 | 없음 (규칙 기반) | 있음 (데이터 기반) |
| 예측 속도 | 느림 (병렬 실행) | 빠름 (단일 모델) |
| 유지보수 | 어려움 | 쉬움 |
| 확장성 | 제한적 | 높음 (재학습) |

---

## 문제 해결

### TensorFlow 설치 오류

```bash
# Windows
pip install tensorflow

# macOS (Apple Silicon)
pip install tensorflow-macos tensorflow-metal

# Linux
pip install tensorflow
```

### GPU 사용 (선택 사항)

```bash
# CUDA 지원 TensorFlow
pip install tensorflow[and-cuda]

# 또는
pip install tensorflow-gpu
```

### 메모리 부족

배치 크기를 줄이세요:

```bash
python -m app.prediction.train_lstm \
    --data_path data/training_data.csv \
    --batch_size 16  # 기본값 32에서 16으로
```

---

## 다음 단계

1. **학습 데이터 수집**: 충전소 데이터를 CSV/Excel로 준비
2. **모델 학습**: `train_lstm.py` 스크립트 실행
3. **모델 배포**: 학습된 모델을 프로덕션에 적용
4. **성능 모니터링**: 예측 정확도 추적
5. **재학습**: 새로운 데이터로 주기적으로 재학습

---

## 참고

- 기존 `PredictionEngine`은 계속 사용 가능합니다 (하위 호환성)
- LSTM 모델은 최소 500개 이상의 데이터 포인트를 권장합니다
- 학습 데이터가 부족하면 자동으로 통계적 방법을 사용합니다
- 모델은 `.h5` 형식으로 저장됩니다 (Keras 표준)
