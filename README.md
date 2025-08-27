# ⚡ 충전소 전력 수요 예측 시스템 

EV 충전소의 전력 수요를 예측하고 최적의 계약전력을 추천하는 지능형 시스템입니다.

## 🚀 빠른 시작

### 🏃‍♂️ 1단계: 시스템 요구사항 확인
```bash
# Python 3.8+ 필요
python --version

# 진단 도구 실행 (권장)
python debug_tool.py
```

### 🔧 2단계: 의존성 설치
```bash
# 백엔드 의존성 설치
cd backend
pip install -r requirements.txt

# 또는 가상 환경 사용 (권장)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 📊 3단계: CSV 데이터 준비
```bash
# 데이터 디렉토리에 CSV 파일 복사
mkdir -p data/raw
cp your_charging_data.csv data/raw/

# 또는 웹 UI에서 업로드 가능
```

### 🌐 4단계: 서버 실행
```bash
# 개발 서버 실행
cd backend
python -m uvicorn app.main:app --reload

# 또는 간편 스크립트 사용
./start-dev.bat  # Windows
./start-dev.sh   # Linux/Mac
```

### ✅ 5단계: 동작 확인
- 브라우저에서 `http://localhost:8000` 접속
- API 문서: `http://localhost:8000/docs`
- 프론트엔드: `http://localhost:5173` (별도 실행 시)

## 🔍 주요 기능

### 📈 전력 수요 예측
- 시간대별 전력 사용 패턴 분석
- 계절성 및 외부 요인 반영
- 95백분위수 기반 보수적 예측

### 💡 계약전력 추천
- 데이터 기반 최적 계약전력 산출
- 안전 마진 자동 적용
- 월별 변동성 고려

### 📊 실시간 대시보드
- 인터랙티브 차트 및 그래프
- 실시간 데이터 모니터링
- 반응형 웹 디자인

## 🏗️ 시스템 아키텍처

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Backend       │    │   Data Layer    │
│   (SvelteKit)   │◄──►│   (FastAPI)     │◄──►│   (CSV/DB)      │
│                 │    │                 │    │                 │
│ • 대시보드      │    │ • REST API      │    │ • 충전 이력     │
│ • 차트/그래프   │    │ • 예측 엔진     │    │ • 파일 저장     │
│ • 관리 도구     │    │ • 데이터 처리   │    │ • 캐시 시스템   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🛠️ 기술 스택

### Backend
- **FastAPI**: 고성능 Python 웹 프레임워크
- **Pandas**: 데이터 분석 및 처리
- **NumPy**: 수치 계산
- **Scikit-learn**: 머신러닝 (통계 예측)
- **Uvicorn**: ASGI 서버

### Frontend (선택사항)
- **SvelteKit**: 모던 웹 프레임워크
- **Chart.js**: 인터랙티브 차트
- **Tailwind CSS**: 유틸리티 CSS 프레임워크

### DevOps
- **Docker**: 컨테이너화
- **Docker Compose**: 멀티 컨테이너 관리

## 📁 프로젝트 구조

```
power-demand-prediction-platform/
├── backend/                 # 백엔드 API 서버
│   ├── app/
│   │   ├── api/            # API 라우트
│   │   ├── core/           # 핵심 설정/로깅
│   │   ├── data/           # 데이터 로더/검증
│   │   ├── features/       # 특성 추출
│   │   ├── models/         # 예측 모델
│   │   ├── services/       # 비즈니스 로직
│   │   └── main.py        # 앱 진입점
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/               # 프론트엔드 (SvelteKit)
│   ├── src/
│   │   ├── components/    # 재사용 컴포넌트
│   │   ├── routes/        # 페이지 라우트
│   │   └── services/      # API 통신
│   └── package.json
├── data/                  # 데이터 저장소
│   └── raw/              # CSV 파일
├── logs/                 # 로그 파일
├── .env                  # 환경 변수
├── debug_tool.py        # 시스템 진단 도구
└── docker-compose.yml   # 컨테이너 설정
```

## 🔧 API 엔드포인트

### 📊 데이터 관리
```http
GET /api/stations                    # 충전소 목록
GET /api/station-analysis/{id}       # 충전소 상세 분석
POST /api/admin/upload-csv           # CSV 파일 업로드
GET /api/status                      # 시스템 상태
```

### 🔮 예측 서비스
```http
GET /api/predict/{station_id}        # 전력 예측
GET /api/stations/{id}/prediction    # 예측 차트 데이터
GET /api/stations/{id}/monthly-contract  # 계약전력 추천
```

### 📈 분석 도구
```http
GET /api/stations/{id}/timeseries    # 시계열 데이터
GET /api/data-range/{id}            # 데이터 범위 확인
GET /api/stations/{id}/timeseries.csv  # CSV 내보내기
```

## 🐛 문제 해결

### ❗ 자주 발생하는 문제

#### 1. 패키지 의존성 오류
**증상**: `ModuleNotFoundError: No module named 'fastapi'`
**해결책**:
```bash
# 진단 도구 실행
python debug_tool.py

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
netstat -tulpn | grep :8000  # Linux
netstat -ano | findstr :8000  # Windows

# 다른 포트 사용
uvicorn app.main:app --port 8001
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
curl http://localhost:8000/api/stations
curl http://localhost:8000/api/predict/BNS0001
curl http://localhost:8000/health
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

## 📝 데이터 형식

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

## 🚀 배포

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
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```