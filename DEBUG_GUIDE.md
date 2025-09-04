# 디버깅 가이드

이 가이드는 통합된 디버그 도구 사용법과 기존의 개별 디버그 스크립트들을 대체하는 방법을 설명합니다.

## 통합 디버그 도구 (`debug_consolidated.py`)

기존의 8개 개별 디버그 스크립트를 하나로 통합한 포괄적인 디버깅 도구입니다.

### 기본 사용법

```bash
# 기본 종합 테스트 (모든 테스트 실행)
python debug_consolidated.py --station BNS0061

# 특정 테스트만 실행
python debug_consolidated.py --station BNS0061 --test data
python debug_consolidated.py --station BNS0061 --test pattern
python debug_consolidated.py --station BNS0061 --test charger
python debug_consolidated.py --station BNS0061 --test api

# 여러 충전소 비교 테스트
python debug_consolidated.py --test multiple --stations BNS0061 BNS0514 BNS0819
```

### 테스트 유형

1. **`data`** - 데이터 로딩 및 기본 통계
   - CSV 파일 확인
   - 데이터 로드 테스트
   - 전력/날짜 데이터 분석

2. **`pattern`** - 충전 패턴 분석
   - 월별 패턴 분석
   - 전력 통계 확인
   - 데이터 범위 검증

3. **`charger`** - 충전기 타입 판별
   - 충전기 타입 식별 (완속/급속)
   - 계약전력 계산
   - 제한값 확인

4. **`api`** - 예측 API 전체 테스트
   - 예측값 확인
   - 차트 데이터 검증
   - 주요 지표 분석

5. **`multiple`** - 여러 충전소 비교
   - 다중 충전소 테스트
   - 예측값 범위 확인
   - 일관성 검증

6. **`all`** - 종합 테스트 (기본값)
   - 위의 모든 테스트 실행

### 제거된 기존 스크립트들

다음 개별 스크립트들이 통합 도구로 대체되었습니다:

- `debug_chart_generation.py` → `--test api`
- `debug_frontend_api.py` → `--test api`
- `debug_contract_prediction.py` → `--test charger`
- `debug_charger_type.py` → `--test charger`
- `debug_pattern_keys.py` → `--test pattern`
- `debug_station_data.py` → `--test data`
- `debug_multiple_stations.py` → `--test multiple`
- `test_station_service.py` → `--test api`

## 장점

1. **일관된 인터페이스**: 모든 디버그 기능을 하나의 도구로 통합
2. **중복 제거**: 동일한 로직의 반복을 제거
3. **확장성**: 새로운 테스트 추가가 용이
4. **유지보수성**: 코드 관리가 단순화

## 예시 출력

```bash
$ python debug_consolidated.py --station BNS0061 --test all

=== 충전소 BNS0061 종합 디버그 ===

1. 데이터 로딩 테스트
=== 충전소 BNS0061 데이터 로딩 디버그 ===
...
테스트 완료: 4/4개 성공
```

## 문제 해결

디버그 도구 사용 중 문제가 발생하면:

1. 먼저 `--test data`로 기본 데이터 로딩을 확인
2. CSV 파일 경로와 형식을 점검
3. 로그 파일(`logs/main.log`)에서 상세 오류 확인
4. 필요시 개별 테스트로 문제 범위를 좁혀가며 진단

## 기여하기

새로운 디버그 기능을 추가하려면 `ConsolidatedDebugger` 클래스에 메소드를 추가하고 `main()` 함수의 명령행 인터페이스를 업데이트하세요.