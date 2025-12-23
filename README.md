
# ⚡ 충전소 전력 수요 예측 플랫폼

EV 충전소의 전력 수요를 예측하고, 최적의 계약전력과 비용 절감 방안을 추천하는 AI 기반 통합 플랫폼

## 🚀 빠른 시작

### 🏃‍♂️ 1단계: 시스템 요구사항 확인
```bash
# Python 3.8+ 필요 (권장: Python 3.10+)
python --version

# 통합 진단 도구 실행 (권장)
python debug_consolidated.py --station BNS0061 --test all
```

### 🔧 2단계: 환경 설정
```bash
# 1. 환경변수 파일 복사 (선택사항)
cp .env .env.local  # 로컬 개발용
cp .env.production .env.prod  # 프로덕션용

# 2. 필요시 환경변수 수정
# .env 파일에서 IP, 포트, 보안키 등 설정
```

### 🔧 3단계: 의존성 설치
```bash
# 백엔드 의존성 설치
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 📊 3단계: CSV 데이터 준비
```bash
# 데이터 디렉토리에 CSV 파일 복사
mkdir -p data/raw
cp your_charging_data.csv data/raw/
# 또는 웹 UI에서 업로드 가능 (대시보드 → CSV 업로드)
```

### 🌐 4단계: 서버 실행
```bash
# 방법 1: 간편 스크립트 사용 (Windows)
./start-dev.bat     # 개발용
./start-prod.bat    # 프로덕션용

# 방법 2: 수동 실행
# 백엔드 서버 (환경변수 자동 로드)
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 32375 --reload

# 프론트엔드 서버 (별도 터미널)
cd frontend
npm install
npm run dev
```

### ✅ 5단계: 동작 확인
- API 서버: `http://127.0.0.1:8000` 또는 `http://220.69.200.55:32375`
- API 문서: `/docs` (Swagger UI)
- 프론트엔드: `http://localhost:5173` 또는 `http://220.69.200.55:32376`
- 대시보드: `/dashboard/{stationId}`


## 🔍 주요 기능 및 아키텍처


### 🔄 동적 패턴 분석 & 앙상블 예측
- **Dynamic Pattern**: 실제 데이터에서 계절/요일/시간대별 패턴 자동 추출, 신뢰도 기반 적응형 예측
- **Ensemble AI**: LSTM(PyTorch) + XGBoost + 통계모델 8종 앙상블, 계약전력/비용/위험도 예측
- **확률·비용 시뮬레이션**: 과소/최적/과다/현재/사용자 지정 계약별 연간 비용, 초과·낭비 확률 분석
- **실시간 대시보드**: Chart.js 기반 예측/비용/위험도 시각화, 다크모드, 반응형 UI
- **통합 진단/디버그**: `debug_consolidated.py`로 데이터·패턴·API·모델·여러 충전소 일괄 점검
- **보안 진단**: 인증/인가, 파일 업로드, 입력 검증, CORS, Docker, 로깅 등 취약점 리포트 및 권고

### 💡 계약전력 추천
- 데이터 기반 최적 계약전력 산출
- 안전 마진 자동 적용
- 월별 변동성 고려

### 💰 비용 및 초과금 산정 기준
- **총 비용(연간)** = `(계약전력 kW × 기본요금 8,320원 × 12개월) + (예상 초과전력 kW × 8,320원 × 1.5 × 12개월)`
	- 첫 항은 계약전력에 대한 연간 기본요금입니다.
	- 두 번째 항은 예측된 피크가 계약전력을 넘는 경우에만 발생하는 **초과 부가금(KEPCO 벌금)** 으로, `backend/app/contract/cost_calculator.py` 의 `KEPCOCostCalculator.compute_total_cost`와 동일한 식을 따릅니다.
- **예상 초과금** = `예상 초과전력 kW × 8,320원 × 1.5 × 12개월`
	- 대시보드의 “예상 초과금” 열은 위 벌금 항만 분리해 보여주며, `peak_kw`가 계약전력을 초과할 확률과 초과 폭을 기반으로 산출됩니다.
- **예상 위험 기여도** = `연간 초과 부가금 × 과소(부족) 발생 확률`
	- 과소 확률(예: 계약전력 부족 위험)이 높을수록 해당 초과금의 기대값이 커지므로, UI에서는 이 값을 위험지표로 함께 노출합니다.

> 참고: 위 식들은 ⚙️ `KEPCOCostCalculator` ( `backend/app/contract/cost_calculator.py` )에서 사용되는 상수 `BASIC_RATE_PER_KW = 8320`과 `SHORTAGE_MULTIPLIER = 1.5`를 그대로 반영합니다. 프런트엔드의 툴팁/도움말과 문서화에도 동일한 수치를 사용해 일관성을 유지하세요.

### 📊 실시간 대시보드
- 인터랙티브 차트 및 그래프
- 실시간 데이터 모니터링
- 반응형 웹 디자인


## 🏗️ 시스템 아키텍처


```
┌────────────────────────────────────────────────────────────┐
│                Power Demand Prediction Platform           │
├────────────────────────────────────────────────────────────┤
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐   │
│  │   Frontend    │  │   Backend     │  │   Data Layer  │   │
│  │ (SvelteKit)   │◄─┼─►(FastAPI)    │◄─┼─►(CSV/DB)      │   │
│  │  • 대시보드   │  │  • REST API   │  │  • 충전 이력   │   │
│  │  • 비용분석   │  │  • 예측엔진   │  │  • 파일저장    │   │
│  │  • 위험분석   │  │  • AI모델     │  │  • 캐시        │   │
│  │  • 관리도구   │  │  • 패턴분석   │  │               │   │
│  └───────────────┘  └───────────────┘  └───────────────┘   │
└────────────────────────────────────────────────────────────┘
```


## 🛠️ 기술 스택


### Backend
- **FastAPI**: 고성능 Python 웹 프레임워크
- **PyTorch**: LSTM 딥러닝 예측 (GPU 지원)
- **XGBoost**: 부스팅 기반 예측
- **Pandas/NumPy/SciPy**: 데이터 분석/통계/극값 이론
- **Uvicorn**: ASGI 서버

### Frontend
- **SvelteKit**: 모던 웹 프레임워크
- **Chart.js**: 인터랙티브 차트
- **Tailwind CSS**: 유틸리티 CSS 프레임워크

### DevOps/Infra
- **Docker/Docker Compose**: 멀티 컨테이너 관리


## 📁 프로젝트 구조

```
power-demand-prediction-platform/
├── backend/                 # 백엔드 API 서버
│   ├── app/
│   │   ├── api/            # API 라우트
│   │   ├── core/           # 핵심 설정/로깅
│   │   ├── data/           # 데이터 로더/검증
│   │   ├── features/       # 특성 추출 (Phase3 이후 미사용)
│   │   ├── models/         # 예측 모델
│   │   ├── services/       # 비즈니스 로직
│   │   └── main.py        # 앱 진입점
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/               # 프론트엔드 (SvelteKit)
│   ├── src/
│   │   ├── components/    # 재사용 컴포넌트 (EnsemblePrediction, ProbabilityCostAnalysis 등)
│   │   ├── routes/        # 페이지 라우트
│   │   └── services/      # API 통신
│   └── package.json
├── data/                  # 데이터 저장소
│   └── raw/              # CSV 파일
├── logs/                 # 로그 파일
├── .env                  # 환경 변수
├── debug_consolidated.py # 통합 진단 도구
└── docker-compose.yml   # 컨테이너 설정
```


## ⚙️ 환경 설정 및 보안

### 🔐 주요 환경변수


시스템은 민감한 정보를 환경변수로 관리합니다. (API 키 인증, CORS, 파일 업로드 제한 등 보안 권고 적용 필요)

```bash
# 서버 설정
BACKEND_HOST=0.0.0.0
BACKEND_PORT=32375
FRONTEND_PORT=32376

# 프로덕션 설정
PRODUCTION_IP=220.69.200.55
PRODUCTION_BACKEND_URL=http://220.69.200.55:32375
PRODUCTION_FRONTEND_URL=http://220.69.200.55:32376

# 보안 설정
SECRET_KEY=your_secret_key_here_change_in_production

# 성능 설정
CACHE_TTL=300
MAX_SESSIONS_PER_QUERY=10000
UVICORN_WORKERS=4
```

### 📁 환경별 설정 파일

- **`.env`**: 개발 환경 (기본값)
- **`.env.production`**: 프로덕션 환경
- **`frontend/.env`**: 프론트엔드 전용 설정

### 🚀 환경별 실행

```bash
# 개발 환경
./start-dev.bat

# 프로덕션 환경 (환경변수 자동 적용)
./start-prod.bat

# Docker 환경 (환경변수 자동 로드)
docker-compose up -d
```


## 🔧 주요 API 엔드포인트 (요약)


### 📊 데이터 관리
- `GET /api/stations` : 충전소 목록
- `POST /api/admin/upload-csv` : CSV 업로드 (인증 필요 권고)
- `GET /api/status` : 시스템 상태

### 🔮 예측/분석 서비스
- `GET /api/stations/{station_id}/ensemble-prediction?current_contract_kw=100` : LSTM+XGBoost 앙상블 예측, 계약전력/비용/위험도/성숙도 분석
- `GET /api/stations/{station_id}/prediction` : 동적 패턴 기반 최고전력 예측 (Dynamic+SARIMA)
- `GET /api/stations/{station_id}/monthly-contract` : 월별 계약전력 추천
- `GET /api/stations/{station_id}/timeseries` : 시계열 데이터


## 🐛 문제 해결 & 디버깅


### ❗ 자주 발생하는 문제 (통합 진단 도구 활용)

#### 1. 패키지 의존성 오류
**증상**: `ModuleNotFoundError: No module named 'fastapi'`
**해결책**:
```bash
# 통합 진단 도구 실행
python debug_consolidated.py --station BNS0061 --test all

# 수동 설치
pip install fastapi pandas numpy uvicorn
```

#### 2. CSV 파일 인식 오류
**증상**: "충전소 데이터를 로드할 수 없습니다"
**해결책**:
```bash
# 1. CSV 파일 위치 확인
ls -la data/raw/

# 2. CSV 파일 인코딩 확인 (UTF-8 권장)
file -i data/raw/your_file.csv

# 3. 웹 UI에서 재업로드
```

#### 3. 포트 충돌
**증상**: "Address already in use"
**해결책**:
```bash
# 포트 사용 확인
netstat -tulpn | grep :32375  # Linux
netstat -ano | findstr :32375  # Windows

# 기본 포트 사용
uvicorn app.main:app --host 0.0.0.0 --port 32375
```

#### 4. 메모리 부족
**증상**: 대용량 CSV 처리 시 느린 성능
**해결책**:
- `.env` 파일에서 `MAX_SESSIONS_PER_QUERY=5000`으로 제한
- CSV 파일을 작은 단위로 분할
- 메모리 사용량 모니터링

### 🔧 디버깅 가이드

#### 로그 확인
```bash
# 실시간 로그 확인
tail -f logs/main.log

# 에러만 필터링
grep ERROR logs/main.log
```

#### JavaScript 디버깅
```javascript
// 브라우저 콘솔에서 디버그 정보 확인
window.dashboardDebug.currentData()
window.dashboardDebug.charts()

// 네트워크 오류 시뮬레이션
window.dashboardDebug.simulateError('network')
```

#### API 테스트
```bash
# curl을 이용한 API 테스트
curl http://220.69.200.55:32375/api/stations
curl http://220.69.200.55:32375/api/predict/BNS0001
curl http://220.69.200.55:32375/health
```

### 🛠️ 성능 최적화

#### 1. 데이터베이스 최적화
- 대용량 데이터는 PostgreSQL 사용 고려
- 인덱싱으로 쿼리 성능 향상

#### 2. 캐싱 전략
- Redis를 이용한 결과 캐싱
- API 응답 캐싱으로 속도 향상

#### 3. 모니터링
```python
# 성능 로깅 활성화
import logging
logging.getLogger("performance").setLevel(logging.INFO)
```


## 📝 데이터/CSV 형식

### CSV 파일 요구사항
```csv
충전소ID,충전시작일시,충전종료일시,순간최고전력,충전량
BNS0001,2024-01-01 09:00:00,2024-01-01 10:30:00,45.2,28.5
BNS0001,2024-01-01 14:20:00,2024-01-01 15:45:00,52.1,32.8
```

#### 필수 컬럼
- **충전소ID**: 충전소 고유 식별자
- **충전시작일시**: 충전 시작 시간 (YYYY-MM-DD HH:MM:SS)
- **순간최고전력**: 충전 중 최대 전력 (kW)

#### 선택 컬럼
- **충전종료일시**: 충전 종료 시간
- **충전량**: 총 충전량 (kWh)
- **충전소명**: 충전소 이름


## 🚀 배포 및 운영


### Docker를 이용한 배포
```bash
# 전체 시스템 시작
docker-compose up -d
# 개별 서비스 시작
docker-compose up backend -d
```


### 프로덕션 배포
```bash
# 환경 변수 설정
cp .env.example .env
# .env 파일 편집

# 프로덕션 서버 실행
uvicorn app.main:app --host 0.0.0.0 --port 32375 --workers 4
```