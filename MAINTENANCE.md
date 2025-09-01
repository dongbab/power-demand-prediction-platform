# 🛠️ 유지보수 가이드

> EV 충전소 전력 수요 예측 플랫폼 유지보수 매뉴얼

## 📋 목차
- [시스템 개요](#시스템-개요)
- [개발 환경 설정](#개발-환경-설정)
- [일상 유지보수](#일상-유지보수)
- [문제 해결](#문제-해결)
- [배포 관리](#배포-관리)
- [모니터링](#모니터링)
- [데이터베이스 관리](#데이터베이스-관리)
- [백업 및 복구](#백업-및-복구)

---

## 🏗️ 시스템 개요

### 아키텍처
```
Frontend (SvelteKit)  ←→  Backend (FastAPI)  ←→  데이터 (CSV/DB)
     ↓                        ↓                      ↓
  - 대시보드               - REST API              - 충전 이력
  - 차트/그래프            - 예측 엔진             - 캐시 시스템
  - 파일 업로드            - 데이터 처리           - 로그 파일
```

### 기술 스택
**Backend**
- FastAPI (Python 웹 프레임워크)
- Pandas (데이터 분석)
- NumPy (수치 계산)
- SciPy (고급 통계 및 극값 이론)
- Uvicorn (ASGI 서버)

**Frontend**  
- SvelteKit (웹 프레임워크)
- Chart.js (차트 라이브러리)
- TypeScript (타입 안정성)
- Tailwind CSS (스타일링)

---

## 🛠️ 개발 환경 설정

### 1. 필수 도구 설치
```bash
# Python 3.8+ 확인
python --version

# Node.js 18+ 확인
node --version

# Git 설치 확인
git --version
```

### 2. 프로젝트 클론 및 설정
```bash
# 프로젝트 클론
git clone <repository-url>
cd power-demand-prediciton-platform

# 환경 변수 설정
cp .env.example .env
# .env 파일 편집하여 필요한 설정 변경
```

### 3. 백엔드 환경 설정
```bash
cd backend

# 가상환경 생성 (권장)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# 개발 서버 실행
uvicorn app.main:app --reload --port 8000
```

### 4. 프론트엔드 환경 설정
```bash
cd frontend

# 의존성 설치
npm install

# 개발 서버 실행
npm run dev
```

### 5. 전체 시스템 실행 (Docker)
```bash
# 전체 시스템 시작
docker-compose up -d

# 로그 확인
docker-compose logs -f
```

---

## 🔄 일상 유지보수

### 매일 체크리스트

#### 1. 시스템 상태 확인
```bash
# 서버 상태 확인
curl http://localhost:8000/health
curl http://localhost:8000/api/status

# 로그 확인
tail -f logs/main.log
grep ERROR logs/main.log | tail -20
```

#### 2. 데이터 상태 확인
```bash
# 데이터 업로드 상태 확인
ls -la data/raw/
du -h data/raw/  # 디스크 사용량 확인

# 데이터 품질 확인
python debug_tool.py --check-data
```

#### 3. 성능 모니터링
```bash
# CPU/메모리 사용량 확인
top -p $(pgrep -f "uvicorn")

# 디스크 공간 확인
df -h

# 로그 파일 크기 확인
du -h logs/
```

### 주간 체크리스트

#### 1. 로그 관리
```bash
# 오래된 로그 파일 압축
gzip logs/main.log.$(date -d "7 days ago" +%Y%m%d)

# 로그 파일 크기 제한 (100MB 초과 시)
if [ $(stat -f%z logs/main.log) -gt 104857600 ]; then
  cp logs/main.log logs/main.log.backup
  > logs/main.log
fi
```

#### 2. 데이터베이스 최적화
```bash
# CSV 파일 정리
find data/raw/ -name "*.csv.bak" -mtime +30 -delete

# 임시 파일 정리
find . -name "*.tmp" -delete
find . -name "__pycache__" -type d -exec rm -rf {} +
```

#### 3. 보안 업데이트 확인
```bash
# Python 패키지 업데이트 확인
pip list --outdated

# Node.js 패키지 업데이트 확인
cd frontend && npm outdated
```

### 월간 체크리스트

#### 1. 백업 확인
```bash
# 데이터 백업 생성
tar -czf backup/data_backup_$(date +%Y%m%d).tar.gz data/

# 설정 파일 백업
cp .env backup/env_backup_$(date +%Y%m%d)
cp docker-compose.yml backup/
```

#### 2. 성능 분석
```bash
# 시스템 성능 분석 리포트 생성
python debug_tool.py --performance-report

# 메모리 사용량 추이 분석
grep "Memory usage" logs/main.log | tail -100 > reports/memory_usage.log
```

---

## 🚨 문제 해결

### 자주 발생하는 문제들

#### 1. 서버 시작 실패
**증상**: `Address already in use` 오류

**해결 방법**:
```bash
# 포트 사용 프로세스 확인
lsof -i :8000
# 또는 Windows에서
netstat -ano | findstr :8000

# 프로세스 종료
kill -9 <PID>

# 다른 포트 사용
uvicorn app.main:app --port 8001
```

#### 2. CSV 파일 처리 오류
**증상**: "CSV 파일을 읽을 수 없습니다" 오류

**해결 방법**:
```bash
# 1. 파일 권한 확인
ls -la data/raw/

# 2. 파일 인코딩 확인
file -bi data/raw/*.csv

# 3. CSV 파일 구조 확인
head -5 data/raw/charging_data.csv

# 4. 데이터 검증 도구 실행
python -c "
import pandas as pd
df = pd.read_csv('data/raw/charging_data.csv')
print(f'컬럼: {df.columns.tolist()}')
print(f'행 수: {len(df)}')
print(df.head())
"
```

#### 3. 메모리 부족 오류
**증상**: 대용량 파일 처리 시 시스템 느려짐

**해결 방법**:
```bash
# 1. 메모리 사용량 확인
free -h
ps aux --sort=-%mem | head -10

# 2. 환경 변수 조정
echo "MAX_SESSIONS_PER_QUERY=5000" >> .env
echo "CHUNK_SIZE=10000" >> .env

# 3. 서버 재시작
docker-compose restart backend
```

#### 4. 예측 결과 이상
**증상**: 예측값이 현실적이지 않거나 오류 발생

**해결 방법**:
```bash
# 1. 데이터 품질 확인
python debug_station_data.py <STATION_ID>

# 2. 예측 모델 디버깅
python debug_contract_prediction.py <STATION_ID>

# 3. 통계 분석 확인
python -c "
from app.services.station_service import StationService
service = StationService()
stats = service.get_station_statistics('<STATION_ID>')
print(stats)
"
```

### 긴급 상황 대응

#### 시스템 전체 중단
```bash
# 1. 즉시 서비스 중단
docker-compose down

# 2. 로그 분석
tail -100 logs/main.log
grep "CRITICAL\|ERROR" logs/main.log

# 3. 백업에서 복구
cp backup/env_backup_latest .env
tar -xzf backup/data_backup_latest.tar.gz

# 4. 서비스 재시작
docker-compose up -d
```

#### 데이터 손실 발생
```bash
# 1. 서비스 즉시 중단
docker-compose down

# 2. 데이터 상태 확인
ls -la data/raw/
find data/ -name "*.csv" -mtime -1

# 3. 백업에서 복구
tar -xzf backup/data_backup_$(date -d "yesterday" +%Y%m%d).tar.gz

# 4. 데이터 무결성 검증
python debug_tool.py --verify-data
```

---

## 🚀 배포 관리

### 개발 환경 배포
```bash
# 코드 업데이트
git pull origin main

# 의존성 업데이트
cd backend && pip install -r requirements.txt
cd frontend && npm install

# 서비스 재시작
docker-compose restart
```

### 프로덕션 배포

#### 배포 전 체크리스트
- [ ] 테스트 통과 확인
- [ ] 백업 완료
- [ ] 설정 파일 확인
- [ ] 보안 설정 점검

#### 배포 절차
```bash
# 1. 백업 생성
./scripts/backup.sh

# 2. 코드 배포
git pull origin main

# 3. 의존성 업데이트
pip install -r requirements.txt --no-deps

# 4. 마이그레이션 (필요시)
python scripts/migrate_data.py

# 5. 서비스 재시작 (무중단 배포)
docker-compose up -d --no-deps backend

# 6. 헬스체크
curl http://localhost:8000/health
```

### 롤백 절차
```bash
# 1. 이전 버전으로 롤백
git reset --hard <PREVIOUS_COMMIT>

# 2. 데이터 복구
tar -xzf backup/data_backup_before_deploy.tar.gz

# 3. 서비스 재시작
docker-compose restart

# 4. 상태 확인
curl http://localhost:8000/health
```

---

## 📊 모니터링

### 시스템 메트릭 수집

#### CPU/메모리 모니터링
```bash
# 실시간 모니터링 스크립트 생성
cat > monitor.sh << 'EOF'
#!/bin/bash
while true; do
  echo "$(date): CPU=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1) Memory=$(free -m | awk 'NR==2{printf "%.1f%%", $3*100/$2}')" >> logs/system_metrics.log
  sleep 60
done
EOF

chmod +x monitor.sh
nohup ./monitor.sh &
```

#### API 응답 시간 모니터링
```bash
# API 응답 시간 체크 스크립트
cat > api_monitor.sh << 'EOF'
#!/bin/bash
for endpoint in "/health" "/api/status" "/api/stations"; do
  response_time=$(curl -o /dev/null -s -w "%{time_total}" http://localhost:8000$endpoint)
  echo "$(date): $endpoint - ${response_time}s" >> logs/api_metrics.log
done
EOF

chmod +x api_monitor.sh
# 크론탭에 등록: */5 * * * * /path/to/api_monitor.sh
```

### 로그 분석

#### 에러 로그 분석
```bash
# 최근 24시간 에러 통계
grep "$(date -d '1 day ago' '+%Y-%m-%d')" logs/main.log | grep ERROR | wc -l

# 자주 발생하는 에러 TOP 10
grep ERROR logs/main.log | awk -F': ' '{print $NF}' | sort | uniq -c | sort -nr | head -10

# 특정 기간 성능 분석
awk '/2024-01-01/,/2024-01-02/ {print}' logs/main.log | grep "response_time" > performance_analysis.log
```

#### 사용자 활동 분석
```bash
# API 엔드포인트 사용 통계
grep "GET\|POST" logs/main.log | awk '{print $7}' | sort | uniq -c | sort -nr

# 시간대별 트래픽 분석
grep "$(date '+%Y-%m-%d')" logs/main.log | cut -d' ' -f2 | cut -d':' -f1 | sort | uniq -c
```

---

## 💾 데이터베이스 관리

### CSV 파일 관리

#### 데이터 정합성 검증
```bash
# CSV 파일 구조 검증
python -c "
import pandas as pd
import os

data_dir = 'data/raw'
required_columns = ['충전소ID', '충전시작일시', '순간최고전력']

for file in os.listdir(data_dir):
    if file.endswith('.csv'):
        try:
            df = pd.read_csv(os.path.join(data_dir, file))
            missing_cols = [col for col in required_columns if col not in df.columns]
            if missing_cols:
                print(f'{file}: 누락된 컬럼 - {missing_cols}')
            else:
                print(f'{file}: 정상 (총 {len(df)}행)')
        except Exception as e:
            print(f'{file}: 오류 - {e}')
"
```

#### 데이터 품질 관리
```bash
# 중복 데이터 제거 스크립트
python -c "
import pandas as pd
import glob

for file_path in glob.glob('data/raw/*.csv'):
    df = pd.read_csv(file_path)
    original_count = len(df)
    df_clean = df.drop_duplicates()
    clean_count = len(df_clean)
    
    if original_count != clean_count:
        print(f'{file_path}: {original_count} → {clean_count} ({original_count - clean_count}개 중복 제거)')
        df_clean.to_csv(file_path, index=False)
    else:
        print(f'{file_path}: 중복 없음')
"
```

### 데이터 아카이브

#### 오래된 데이터 아카이브
```bash
# 30일 이상 된 CSV 파일 아카이브
find data/raw/ -name "*.csv" -mtime +30 -exec mv {} archive/ \;

# 월별 아카이브 생성
for month in {01..12}; do
  tar -czf "archive/2024_${month}_data.tar.gz" data/raw/*2024-${month}*.csv
done
```

---

## 💾 백업 및 복구

### 자동 백업 설정

#### 일일 백업 스크립트
```bash
cat > scripts/daily_backup.sh << 'EOF'
#!/bin/bash

BACKUP_DIR="backup/$(date +%Y%m%d)"
mkdir -p "$BACKUP_DIR"

# 데이터 백업
echo "데이터 백업 시작..."
tar -czf "$BACKUP_DIR/data_backup.tar.gz" data/

# 설정 파일 백업
echo "설정 파일 백업..."
cp .env "$BACKUP_DIR/"
cp docker-compose.yml "$BACKUP_DIR/"

# 로그 백업
echo "로그 백업..."
cp -r logs/ "$BACKUP_DIR/"

# 오래된 백업 파일 정리 (30일 이전)
find backup/ -type d -mtime +30 -exec rm -rf {} \;

echo "백업 완료: $BACKUP_DIR"
EOF

chmod +x scripts/daily_backup.sh

# 크론탭 등록 (매일 오전 2시)
echo "0 2 * * * /path/to/scripts/daily_backup.sh" | crontab -
```

### 복구 절차

#### 데이터 복구
```bash
# 1. 서비스 중단
docker-compose down

# 2. 현재 데이터 백업 (안전장치)
mv data/ data_corrupted_$(date +%Y%m%d)/

# 3. 백업에서 복구
tar -xzf backup/20240115/data_backup.tar.gz

# 4. 권한 설정
chown -R $(whoami):$(whoami) data/
chmod -R 755 data/

# 5. 서비스 재시작
docker-compose up -d

# 6. 복구 확인
python debug_tool.py --verify-data
```

#### 설정 파일 복구
```bash
# 설정 파일 복구
cp backup/20240115/.env .
cp backup/20240115/docker-compose.yml .

# 환경 변수 다시 로드
docker-compose down
docker-compose up -d
```

---

## 🔧 고급 설정

### 성능 튜닝

#### FastAPI 서버 최적화
```python
# app/main.py 성능 설정 추가
from fastapi import FastAPI
import asyncio
import uvloop

# 이벤트 루프 최적화
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

app = FastAPI(
    title="Power Demand Prediction Platform",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    # 성능 최적화 설정
    generate_unique_id_function=lambda route: f"{route.tags[0]}-{route.name}",
)

# 미들웨어 최적화
@app.middleware("http")
async def add_performance_headers(request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response
```

#### 데이터 처리 최적화
```python
# 청크 단위 데이터 처리 설정
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 10000))
MAX_MEMORY_USAGE = int(os.getenv("MAX_MEMORY_MB", 1024))

# 메모리 효율적인 CSV 읽기
def read_large_csv(file_path):
    return pd.read_csv(
        file_path,
        chunksize=CHUNK_SIZE,
        dtype={'충전소ID': 'category', '순간최고전력': 'float32'},
        parse_dates=['충전시작일시']
    )
```

### 보안 설정

#### API 보안 강화
```python
# 환경변수로 API 키 설정
API_SECRET_KEY = os.getenv("API_SECRET_KEY", "change-this-secret-key")

# Rate Limiting 추가
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.get("/api/predict/{station_id}")
@limiter.limit("10/minute")  # 분당 10회 제한
async def predict_power_demand(request: Request, station_id: str):
    # 예측 로직
    pass
```

---

### 유용한 명령어 모음
```bash
# 빠른 상태 확인
curl http://localhost:8000/health && echo "✅ Backend OK"
curl http://localhost:5173 && echo "✅ Frontend OK"

# 로그 실시간 모니터링
tail -f logs/main.log | grep -E "(ERROR|WARNING|INFO)"

# 메모리 사용량 모니터링
watch -n 1 'free -h && echo "---" && ps aux --sort=-%mem | head -10'

# 프로세스 재시작 (우아한 종료)
pkill -TERM -f "uvicorn"
sleep 5
uvicorn app.main:app --host 0.0.0.0 --port 8000 &
```

---

## 📝 체크리스트 요약

### 설치 후 첫 설정 체크리스트
- [ ] Python 3.8+ 설치 확인
- [ ] Node.js 18+ 설치 확인  
- [ ] 필요한 패키지 설치 완료
- [ ] 환경 변수(.env) 설정 완료
- [ ] 데이터 디렉토리 생성 및 권한 설정
- [ ] 첫 테스트 CSV 파일 업로드 및 처리 확인
- [ ] API 엔드포인트 동작 확인
- [ ] 프론트엔드 페이지 접근 확인

### 정기 점검 체크리스트  
- [ ] 시스템 리소스 사용량 확인 (CPU, 메모리, 디스크)
- [ ] 로그 파일 크기 및 에러 발생 여부 확인
- [ ] 백업 파일 생성 및 무결성 확인
- [ ] 보안 업데이트 확인 및 적용
- [ ] 성능 지표 모니터링 및 분석
- [ ] 사용자 피드백 및 이슈 사항 점검

---

## ⚡ 성능 최적화

### 1. **예측 엔진 성능 분석**

#### 현재 성능 지표
- **평균 응답 시간**: 1-2초 (8개 모델 순차 실행)
- **메모리 사용량**: 50-100MB (부트스트랩 및 데이터 복사본)
- **CPU 사용률**: 단일 코어 집중 사용

#### 병목 지점 식별
```bash
# 예측 성능 프로파일링
python -m cProfile -o profile_stats.prof -c "
from app.prediction.engine import PredictionEngine
import pandas as pd
engine = PredictionEngine()
data = pd.read_csv('data/sample_station.csv')
engine.predict_contract_power(data, 'TEST001')
"

# 프로파일 결과 분석
python -c "
import pstats
stats = pstats.Stats('profile_stats.prof')
stats.sort_stats('cumulative').print_stats(20)
"
```

### 2. **병렬 처리 최적화**

#### ThreadPoolExecutor 설정
```python
# engine.py에서 병렬 처리 구성
max_workers = min(4, os.cpu_count())  # CPU 코어 수 기반 설정
timeout = 10  # 모델별 최대 실행 시간

# 모델 그룹별 병렬 실행
- 극값 이론 모델 (EVT)
- 통계적 추론 모델 (STAT)  
- 시계열 모델 (TS)
- 머신러닝 모델 (ML)
```

#### 성능 모니터링 스크립트
```bash
# 병렬 처리 성능 측정
cat > benchmark_parallel.py << 'EOF'
import time
import pandas as pd
from app.prediction.engine import PredictionEngine

def benchmark_prediction(station_id, iterations=10):
    engine = PredictionEngine()
    data = pd.read_csv(f'data/stations/{station_id}.csv')
    
    times = []
    for i in range(iterations):
        start = time.time()
        result = engine.predict_contract_power(data, station_id)
        elapsed = time.time() - start
        times.append(elapsed)
        print(f"Iteration {i+1}: {elapsed:.3f}s, Models: {len(result.model_predictions)}")
    
    avg_time = sum(times) / len(times)
    print(f"평균 응답 시간: {avg_time:.3f}s")
    return avg_time

if __name__ == "__main__":
    benchmark_prediction("STATION_001")
EOF

python benchmark_parallel.py
```

### 3. **캐싱 전략**

#### 통계량 캐싱
```python
# 기본 통계량 사전 계산 및 캐싱
stats_cache = {
    'mean', 'median', 'std', 'mad',
    'q25', 'q75', 'q90', 'q95', 'q99',
    'min', 'max'
}

# LRU 캐시 크기: 128개 데이터셋
# 메모리 사용량: ~10MB (일반적인 충전소 데이터 기준)
```

#### 캐시 성능 모니터링
```bash
# 캐시 히트율 확인
python -c "
from app.prediction.engine import PredictionEngine
engine = PredictionEngine()
print('캐시 정보:', engine._stats_cache.cache_info())
"

# 캐시 클리어 (필요시)
curl -X POST http://localhost:8000/api/admin/clear-cache
```

### 4. **메모리 최적화**

#### 부트스트랩 최적화
- **기존**: 1000회 반복, 순차 처리
- **개선**: 200회 반복, 벡터화 연산
- **메모리 절약**: ~60% 감소

#### 데이터 재사용
```python
# 불필요한 배열 복사 제거
# 통계량 중복 계산 방지
# 히스토그램 bins 수 감소 (30 → 20)
```

### 5. **성능 측정 및 모니터링**

#### 실시간 성능 대시보드
```bash
# FastAPI 성능 메트릭 수집
pip install prometheus-fastapi-instrumentator

# Grafana 대시보드 설정
curl http://localhost:3000/api/dashboards/db \
  -X POST \
  -H "Content-Type: application/json" \
  -d @monitoring/prediction_performance.json
```

#### 성능 벤치마크 테스트
```bash
# 부하 테스트 실행
cat > load_test.py << 'EOF'
import asyncio
import aiohttp
import time
from concurrent.futures import ThreadPoolExecutor

async def test_prediction_endpoint(session, station_id):
    url = f"http://localhost:8000/api/stations/{station_id}/predict"
    start = time.time()
    async with session.get(url) as response:
        await response.json()
        return time.time() - start

async def run_load_test(concurrent_requests=10, total_requests=100):
    async with aiohttp.ClientSession() as session:
        tasks = []
        for i in range(total_requests):
            station_id = f"STATION_{i % 5 + 1:03d}"
            task = test_prediction_endpoint(session, station_id)
            tasks.append(task)
            
        results = await asyncio.gather(*tasks)
        
    avg_time = sum(results) / len(results)
    print(f"동시 요청 {concurrent_requests}개, 총 {total_requests}개")
    print(f"평균 응답 시간: {avg_time:.3f}s")
    print(f"최대 응답 시간: {max(results):.3f}s")
    print(f"최소 응답 시간: {min(results):.3f}s")

if __name__ == "__main__":
    asyncio.run(run_load_test())
EOF

python load_test.py
```

### 6. **성능 최적화 체크리스트**

#### 일일 점검 사항
```bash
# 1. 평균 응답 시간 확인 (목표: <0.5초)
curl -w "Time: %{time_total}s\n" http://localhost:8000/api/stations/STATION_001/predict

# 2. 메모리 사용량 모니터링
ps aux | grep "python.*main.py" | awk '{print $4 "% " $6/1024 "MB"}'

# 3. 캐시 효율성 점검
python -c "
from app.prediction.engine import PredictionEngine
engine = PredictionEngine()
print('캐시 상태:', len(engine._stats_cache), '개 항목')
"
```

#### 성능 임계값 설정
- **응답 시간**: 
  - 양호: <0.5초
  - 주의: 0.5-1.0초  
  - 경고: >1.0초
- **메모리 사용량**:
  - 양호: <100MB
  - 주의: 100-200MB
  - 경고: >200MB
- **캐시 히트율**:
  - 양호: >80%
  - 주의: 60-80%
  - 경고: <60%

### 7. **성능 문제 해결**

#### 응답 시간 지연 시
```bash
# 1. 병목 지점 분석
python -m line_profiler prediction_profile.py

# 2. 무거운 모델 일시 비활성화
export DISABLE_HEAVY_MODELS=true
systemctl restart fastapi-app

# 3. 캐시 워밍업
python scripts/cache_warmup.py --stations all
```

#### 메모리 누수 감지
```bash
# 1. 메모리 프로파일링
python -m memory_profiler app/main.py

# 2. 가비지 컬렉션 강제 실행
curl -X POST http://localhost:8000/api/admin/gc-collect

# 3. 애플리케이션 재시작 (임시 조치)
systemctl restart fastapi-app
```

#### 예상 성능 향상
- **병렬 처리**: 3-5배 속도 향상
- **캐싱**: 2-3배 속도 향상  
- **메모리 최적화**: 40% 메모리 절약
- **전체 최적화**: 응답 시간 1-2초 → 0.3-0.5초

---

## 📊 예측 신뢰도 평가 시스템

### 신뢰도 평가 개요
EV 충전소 전력 수요 예측의 정확성과 신뢰성을 평가하는 다층적 시스템입니다.

### 1. **개별 모델 신뢰도 (Model-Level Confidence)**

#### 극값 이론 모델
- **GEV (Generalized Extreme Value)**: `0.85` (매우 높음)
  - 극값 분포의 통계적 이론에 기반한 높은 신뢰도
- **Gumbel 분포**: `0.80` (높음)  
  - 최댓값 예측에 특화된 안정적 성능

#### 통계적 추론 모델
- **분위수 회귀**: `0.75` (중간-높음)
  - 데이터 분포를 고려한 견고한 예측
- **커널 밀도 추정**: `0.85` (매우 높음)
  - 비모수적 접근으로 유연성 제공

#### 베이지안 모델
- **베이지안 추정**: `0.75` (중간-높음)
  - 사전 지식과 데이터를 결합한 불확실성 정량화
- **부트스트랩**: `0.80` (높음)
  - 통계적 재표본 기법으로 안정성 확보

#### 시계열 모델
- **지수 평활법**: `0.70` (중간)
  - 시간적 패턴 반영, 단기 예측에 유리
- **추세 분석**: `0.70` (중간)
  - 장기 경향성 파악에 효과적

#### 강건 통계량 모델
- **MAD 기반**: `0.75` (중간-높음)
  - 이상치에 강한 중위수 절대편차 사용

### 2. **앙상블 신뢰도 (Ensemble Confidence)**

#### 가중 평균 방식
```python
# 각 모델의 신뢰도 기반 가중치 계산
total_confidence = sum(model.confidence_score for model in models)
weight = model.confidence_score / total_confidence

# 최종 예측값
final_prediction = sum(model.prediction * weight for model, weight in zip(models, weights))
```

#### 불확실성 측정
- **표준편차 기반**: `np.std(predictions_array)`
- **신뢰구간**: 각 모델별 95% 신뢰구간 계산
- **최종 불확실성**: 모델 간 예측값 분산으로 계산

### 3. **시스템 레벨 신뢰도 (System-Level Confidence)**

#### 데이터 품질 기반 신뢰도
```python
# 데이터 개수에 따른 기본 신뢰도
base_confidence = min(0.95, max(0.4, data_count / 1000))

# 모델 불확실성 반영
model_confidence = max(0.4, 1.0 - (uncertainty / 100.0))

# 최종 신뢰도 (평균)
final_confidence = min(0.95, (base_confidence + model_confidence) / 2)
```

#### 신뢰도 등급 체계
- **매우 높음** (`0.90-0.95`): 1년 이상 풍부한 데이터, 일관된 패턴
- **높음** (`0.80-0.89`): 6개월 이상 데이터, 안정적 패턴  
- **중간** (`0.70-0.79`): 3개월 이상 데이터, 일부 변동성
- **낮음** (`0.60-0.69`): 1개월 이상 데이터, 높은 변동성
- **매우 낮음** (`0.40-0.59`): 부족한 데이터, 불안정한 패턴

### 4. **신뢰도 검증 방법**

#### 일일 검증 체크리스트
```bash
# 1. 신뢰도 점수 확인
curl http://localhost:8000/api/stations/STATION_ID/predict | jq '.confidence'

# 2. 모델별 신뢰도 분석
python -c "
from app.services.station_service import StationService
service = StationService()
result = service.get_prediction_analysis('STATION_ID')
for model in result['models']:
    print(f'{model[\"name\"]}: {model[\"confidence\"]:.2f}')
"

# 3. 불확실성 지표 확인
curl http://localhost:8000/api/stations/STATION_ID/predict | jq '.advanced_model_prediction.uncertainty'
```

#### 주간 신뢰도 분석
```bash
# 신뢰도 추이 분석 스크립트
cat > confidence_analysis.py << 'EOF'
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def analyze_confidence_trends(station_id, days=7):
    """최근 7일간 신뢰도 추이 분석"""
    
    # 로그에서 신뢰도 데이터 추출
    confidence_data = []
    
    for i in range(days):
        date = datetime.now() - timedelta(days=i)
        # 실제 구현에서는 로그 파일이나 DB에서 데이터 추출
        # confidence_data.append({
        #     'date': date,
        #     'confidence': get_daily_confidence(station_id, date)
        # })
    
    df = pd.DataFrame(confidence_data)
    
    print(f"Station {station_id} - 신뢰도 분석")
    print(f"평균 신뢰도: {df['confidence'].mean():.3f}")
    print(f"신뢰도 표준편차: {df['confidence'].std():.3f}")
    print(f"최소/최대: {df['confidence'].min():.3f} / {df['confidence'].max():.3f}")
    
    return df

if __name__ == "__main__":
    analyze_confidence_trends("STATION_001")
EOF

python confidence_analysis.py
```

### 5. **신뢰도 기반 의사결정 가이드**

#### 높은 신뢰도 (0.8+)
- ✅ **권고**: 예측값을 그대로 계약전력 설정에 활용
- ✅ **자동화**: 시스템 자동 추천 허용
- ✅ **알림**: 정상 수준의 모니터링

#### 중간 신뢰도 (0.6-0.8)
- ⚠️ **주의**: 예측값에 안전 마진 추가 고려
- ⚠️ **검토**: 전문가 검토 권장  
- ⚠️ **모니터링**: 주간 단위 성능 점검

#### 낮은 신뢰도 (0.4-0.6)
- ❌ **경고**: 예측값 사용 시 신중한 판단 필요
- ❌ **수동**: 수동 검증 및 조정 권장
- ❌ **빈번**: 일일 단위 성능 모니터링

### 6. **신뢰도 개선 방안**

#### 데이터 품질 개선
```bash
# 1. 데이터 완성도 확인
python -c "
import pandas as pd
from app.data.loader import ChargingDataLoader

loader = ChargingDataLoader('STATION_ID')
data = loader.load_historical_sessions(days=365)

print(f'전체 기간: {data.index.min()} ~ {data.index.max()}')
print(f'결측치 비율: {data.isnull().sum().sum() / len(data):.1%}')
print(f'데이터 밀도: {len(data) / 365:.1f}건/일')
"

# 2. 이상치 제거
python scripts/clean_outliers.py --station-id STATION_ID --threshold 3.0

# 3. 데이터 보간
python scripts/interpolate_missing.py --station-id STATION_ID --method linear
```

#### 모델 파라미터 튜닝
```bash
# 1. 계절성 파라미터 조정
# app/prediction/engine.py에서 계절 가중치 수정

# 2. 앙상블 가중치 최적화
python scripts/optimize_ensemble.py --station-id STATION_ID

# 3. 신뢰구간 재조정
python scripts/calibrate_confidence.py --validation-period 30
```

#### 예측 구간 조정
- **단기 예측** (1-7일): 지수 평활법 가중치 증가
- **중기 예측** (1-3개월): 통계적 추론 모델 우선
- **장기 예측** (6개월+): 극값 이론 모델 중심

### 7. **성능 벤치마크**

#### 업계 표준 비교
- **일반 시계열 예측**: 신뢰도 0.70-0.80
- **전력 수요 예측**: 신뢰도 0.75-0.85  
- **EV 충전 예측**: 신뢰도 0.70-0.90 (데이터 품질 의존)

#### 목표 신뢰도 설정
- **단기** (1-7일): ≥ 0.85
- **중기** (1-3개월): ≥ 0.80  
- **장기** (6개월+): ≥ 0.75

### 8. **문제 해결**

#### 신뢰도 급락 시
```bash
# 1. 최근 데이터 품질 확인
python debug_station_data.py STATION_ID --recent-days 7

# 2. 모델별 성능 분석  
python debug_model_performance.py STATION_ID

# 3. 앙상블 가중치 재계산
python scripts/recalibrate_ensemble.py STATION_ID
```

#### 일관성 없는 예측
```bash
# 1. 데이터 drift 검사
python scripts/detect_data_drift.py STATION_ID

# 2. 계절성 패턴 변화 확인
python scripts/analyze_seasonality.py STATION_ID --years 2

# 3. 모델 재훈련
python scripts/retrain_models.py STATION_ID --validation-split 0.2
```

---

*📅 문서 최종 업데이트: 2025년 9월 1일*  