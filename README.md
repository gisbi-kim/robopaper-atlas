# ICRA / IROS / RA-L / T-RO / RSS 역대 논문 메타데이터 수집

DBLP + OpenAlex를 이용해 ICRA(1984~)·IROS(1988~)·RA-L(2016~)·T-RO(2004~)·RSS(2005~) 전체 논문의
제목, 저자, 연도, DOI, 초록, 인용수, 키워드(concepts)를 엑셀로 모읍니다.
DOI + (제목, 연도) 기반 중복 제거로 저널↔학회 교차 게재도 단일 항목화.

## 예상 규모
- ICRA: ~30,600편
- IROS: ~26,600편
- RA-L: ~9,400편
- T-RO: ~3,300편
- RSS: ~1,300편
- **합계 약 71,000편** (중복 제거 후)

## 필요 패키지
```bash
pip install requests pandas openpyxl
```

## 실행 순서

### Step 1. DBLP 수집 (30분~1시간)
```bash
python step1_dblp.py
```
- `dblp_raw/` 폴더에 연도별 JSON 저장 (체크포인트)
- 중단해도 다시 실행하면 이어서 진행
- 결과: `all_dblp.json`

### Step 2. OpenAlex로 초록·인용수 보강 (1~3시간)
**실행 전 `step2_openalex.py` 상단의 `USER_EMAIL`을 본인 이메일로 바꿔주세요.**
(OpenAlex polite pool — 필수는 아니지만 우선순위 올라감)

```bash
python step2_openalex.py
```
- 50개 DOI씩 배치 쿼리
- 500편마다 체크포인트 저장
- 중단해도 재실행하면 이어서
- 결과: `all_enriched.json`

### Step 3. 엑셀 생성
```bash
python step3_excel.py
```
- 결과: `icra_iros_ral_tro_rss_all.xlsx`, `icra_iros_ral_tro_rss_all.csv`

## 팁

### 일부 연도만 먼저 테스트
`step1_dblp.py`의 `venues_years` 루프 범위를 줄여서 돌려보세요.
예: `range(2020, 2026)` → 최근 6년만.

### OpenAlex 커버리지
최근 논문일수록 초록 커버리지 높음 (90%+).
2010년 이전은 초록이 없는 경우가 많고, 1990년대 이전은 DOI 자체가 없는 경우가 많음.

### 파일이 너무 크면
엑셀이 버거울 수 있음. 대안:
- Parquet로 저장 후 pandas/duckdb로 분석:
  ```python
  df.to_parquet('icra_iros.parquet')
  ```
- 연도별로 시트 분리
- 초록 컬럼 제외한 슬림 버전 따로 생성

### 키워드/세션 트랙
DBLP에는 세션 정보가 없음. OpenAlex의 `concepts`가 대체재 (자동 분류 토픽).
더 정확한 세션 트랙이 필요하면 IEEE Xplore API가 필요 (API 키 발급 별도).

## 컬럼 설명
| 컬럼 | 출처 | 설명 |
|---|---|---|
| venue | DBLP | ICRA / IROS / RA-L / T-RO / RSS (primary, dedup 후) |
| venues_all | dedup | 원래 등장했던 모든 venue (쉼표 구분) |
| year | DBLP | 연도 |
| title | DBLP | 논문 제목 |
| authors | DBLP | 저자 (세미콜론 구분) |
| abstract | OpenAlex | 초록 (있는 경우) |
| cited_by_count | OpenAlex | 인용 수 |
| concepts | OpenAlex | 자동 분류 토픽 상위 5개 |
| doi | DBLP | DOI |
| ee | DBLP | 전자 버전 URL (IEEE Xplore 링크) |
| pages | DBLP | 페이지 |
| dblp_key | DBLP | DBLP 고유 키 |
| openalex_id | OpenAlex | OpenAlex Work ID |
