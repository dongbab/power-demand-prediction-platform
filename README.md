# 충전소 순간최고전력 예측 시스템

## 개요
전기차 충전소의 순간최고전력을 예측하여 효율적인 전력 계약을 지원하는 시스템입니다.

## 주요 기능
- 실시간 전력 수요 예측
- 월별 최고 전력 예측
- 다중 모델 앙상블 예측
- 예측 성능 모니터링
- RESTful API 제공

## 시스템 요구사항
- Python 3.9+
- PostgreSQL (선택적, SQLite 기본)
- Redis (선택적)

## 설치 방법

### 1. 저장소 복제 및 이동
```bash
git clone <repository-url>
cd charging_station_predictor
```

### 2. 가상환경 생성 및 활성화
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

### 3. 의존성 설치
```bash
pip install -r requirements.txt
```

### 4. 환경변수 설정 (선택적)
```bash
# .env 파일 생성
DATABASE_URL=postgresql://user:password@localhost/charging_db
REDIS_URL=redis://localhost:6379
```

## 실행 방법

### 개발 모드
```bash
python main.py
```

### 프로덕션 모드
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

## API 사용법

### 실시간 예측 요청
```bash
curl -X GET "http://localhost:8000/predict/STATION_001?hours=1"
```

### 월별 계약 전력 권고
```bash
curl -X GET "http://localhost:8000/api/monthly-contract/STATION_001?year=2024&month=3"
```

### 시스템 상태 확인
```bash
curl -X GET "http://localhost:8000/health"
```

### 충전소 상태 조회
```bash
curl -X GET "http://localhost:8000/stations/STATION_001/status"
```

## 테스트 실행
```bash
# 전체 테스트
pytest tests/ -v

# 커버리지 포함
pytest tests/ -v --cov=. --cov-report=html

# 특정 테스트만
pytest tests/unit/test_data_loader.py -v
```

## 프로젝트 구조
```
charging_station_predictor/
├── data/               # 데이터 로딩 및 전처리
│   ├── loader.py      # 데이터 로더
│   ├── preprocessor.py # 전처리기
│   └── validator.py   # 데이터 검증
├── features/          # 특성 추출
│   ├── temporal.py    # 시간 특성
│   ├── session.py     # 세션 특성
│   └── aggregator.py  # 집계 특성
├── models/            # 예측 모델
│   ├── statistical.py # 통계 모델
│   ├── time_series.py # 시계열 모델
│   └── ensemble.py    # 앙상블 모델
├── prediction/        # 예측 엔진
│   ├── predictor.py   # 예측기
│   └── scheduler.py   # 스케줄러
├── utils/             # 유틸리티
│   ├── config.py      # 설정 관리
│   └── logger.py      # 로깅
├── tests/             # 테스트
│   ├── unit/          # 단위 테스트
│   └── integration/   # 통합 테스트
├── logs/              # 로그 파일
├── main.py            # 메인 애플리케이션
├── requirements.txt   # 의존성
└── README.md         # 문서
```

## 개발 가이드

### 새로운 모델 추가
1. `models/` 디렉토리에 새 모델 클래스 생성
2. `prediction/predictor.py`에서 모델 등록
3. 단위 테스트 작성

### 새로운 특성 추가
1. `features/` 디렉토리에 특성 추출기 생성
2. 기존 파이프라인에 통합
3. 성능 영향 검증

### 코드 품질 관리
```bash
# 코드 포맷팅
black .

# 린팅
flake8 .

# 타입 체크
mypy .
```

## 배포

### Docker 사용
```bash
# 이미지 빌드
docker build -t charging-predictor .

# 컨테이너 실행
docker run -p 8000:8000 charging-predictor
```

### 환경별 설정
- 개발: SQLite + 로컬 파일 로그
- 스테이징: PostgreSQL + 중앙화된 로그 
- 프로덕션: PostgreSQL + Redis + 모니터링

## 모니터링
- 예측 정확도 메트릭
- API 응답 시간
- 시스템 리소스 사용률
- 오류율 및 로그

## 문제 해결

### 자주 발생하는 문제
1. **포트 충돌**: 8000번 포트가 사용 중인 경우 다른 포트 사용
2. **의존성 오류**: 가상환경 활성화 확인
3. **데이터베이스 연결**: 환경변수 설정 확인

### 로그 확인
```bash
# 애플리케이션 로그
tail -f logs/main.log

# 성능 로그  
tail -f logs/performance.log
```

## 기여 방법
1. Fork 저장소
2. 기능 브랜치 생성
3. 변경사항 커밋
4. Pull Request 생성

## 라이선스
MIT License
