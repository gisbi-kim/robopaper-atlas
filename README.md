# RoboPaper Atlas

**40년치 로봇공학 논문(ICRA · IROS · RA-L · T-RO · RSS)을 한 곳에 모은 인터랙티브 아틀라스.**
DBLP + OpenAlex로 71,000+ 편의 제목·저자·초록·인용수·키워드를 긁어와서
중복 제거하고, 바로 탐색·정렬·필터할 수 있는 웹 페이지와 엑셀로 정리합니다.

🔗 **Live demo**: https://gisbi-kim.github.io/robopaper-atlas/

## 수집 범위

| Venue | DBLP stream | 시작 연도 | 편수 (dedup 후) |
|---|---|---:|---:|
| ICRA | `conf/icra` | 1984 | ~30,600 |
| IROS | `conf/iros` | 1988 | ~26,600 |
| RA-L | `journals/ral` | 2016 | ~9,400 |
| T-RO | `journals/trob` | 2004 | ~3,300 |
| RSS | `conf/rss` | 2005 | ~1,300 |
| **합계** | | 1984 ~ 2025 | **~71,000** |

DOI + (정규화 제목, 연도) 기반으로 저널↔학회 교차 게재를 병합 (예: RA-L 논문이 ICRA에서 발표된 경우 1개 엔트리).

## 무엇을 할 수 있나

### 🔍 [Full Explorer](icra_iros_ral_tro_rss_explorer.html)
71,000+편 전체 탐색기. 한 페이지에서:
- **연도 범위** / **venue** / **최소 인용수** / **제목·저자 검색** 복합 필터
- 모든 컬럼(venue, year, cites 등) **클릭 정렬**
- 페이지당 50/100/200/500 선택 가능한 페이지네이션
- 결과에 연동되는 **stacked bar chart** (연도별 편수) + **scatter plot** (연도 × 인용수)
- 제목 클릭 → DOI 링크 새 탭으로 열기

### 📈 [Papers by Year](icra_iros_ral_tro_rss_by_year.html)
연도별 venue별 편수 추이. Stacked / Grouped / Line 세 가지 뷰로 토글.

### 🏆 [Top 100 Cited](icra_iros_ral_tro_rss_top100.html)
역대 최다 인용 논문 100편. 연도 × 인용수 scatter plot, venue 분포, DOI 링크 테이블.

### 📊 [Dataset download](icra_iros_ral_tro_rss_all.xlsx)
- **XLSX** (38 MB) — 5 시트: `summary` / `by_year_pivot` / `by_year_detail` / `top_cited_100` / `papers`
- **CSV** (97 MB) — 분석용 (pandas, DuckDB 등)

## 데이터 기준일

OpenAlex 인용수는 시간이 지나면서 바뀝니다. 모든 HTML 상단 우측과 xlsx `summary` 시트 첫 행에 **"Citations as of YYYY-MM-DD"** 로 마지막 갱신일을 표기.

## 업데이트 (재조사)

최신 인용수로 갱신하거나 새 연도 논문을 추가하고 싶으면 **[REFRESH.md](REFRESH.md)** 의 한 줄 프롬프트를 Claude에게 주세요. 아래 3가지를 자동 처리합니다:

1. **새 연도 확인** — DBLP에 새 데이터 있으면 사용자에게 물어보고 추가
2. **인용수 갱신** — 최근 7년만 (빠름, ~5분) 또는 전체 (~1~3시간) 선택
3. **산출물 재생성** — xlsx / csv / HTML 3개 모두 갱신

수동으로 돌리려면:
```bash
python refresh_recent.py 2019     # 2019~현재 DOI를 checkpoint에서 제거
python step2_openalex.py          # 제거된 DOI만 재조회
python step3_excel.py             # xlsx / csv 재생성
python _make_all_html.py          # explorer.html
python _make_by_year_html.py      # by_year.html
python _make_top100_html.py       # top100.html
```

## 파이프라인 (처음부터 빌드)

### 필요 패키지
```bash
pip install requests pandas openpyxl
```

### Step 1. DBLP 메타데이터 수집 (30분~1시간)
```bash
python step1_dblp.py
```
- `step1_dblp.py`의 `venues_config`에서 venue/연도 범위 설정
- `dblp_raw/{venue}_{year}.json` 에 연도별 캐시 저장 — 중단해도 이어서
- 출력: `all_dblp.json`

### Step 2. OpenAlex로 초록·인용수·concepts 보강 (1~3시간)
```bash
python step2_openalex.py
```
> ⚠️ 첫 실행 전 `step2_openalex.py` 상단의 `USER_EMAIL`을 본인 이메일로 바꾸세요 (OpenAlex polite pool).

- 50개 DOI씩 배치 쿼리, 500편마다 `enriched_checkpoint.json` 저장
- 중단해도 재실행하면 체크포인트부터 이어서
- 출력: `all_enriched.json`

### Step 3. 정제·중복 제거·엑셀 생성
```bash
python step3_excel.py
```
작업 내용:
- HTML 엔티티 디코딩 (`&quot;` → `"`)
- DBLP 동명이인 식별자 제거 (`"Tong Qin 0001"` → `"Tong Qin"`)
- 학회 전체 proceedings 표제 행 제외 (저자 없는 것)
- **DOI 중복 제거** — RA-L > T-RO > RSS > ICRA > IROS 우선
- **제목+연도 보조 dedup** — DOI 다르지만 같은 논문 (cross-venue 게재)
- 5개 시트 포함 xlsx + CSV 출력

### Step 4. HTML 시각화 생성
```bash
python _make_all_html.py       # 전체 탐색기
python _make_by_year_html.py   # 연도별 편수
python _make_top100_html.py    # Top 100
```

## 데이터 스키마 (`papers` 시트 / CSV)

| 컬럼 | 출처 | 설명 |
|---|---|---|
| `venue` | dedup | ICRA / IROS / RA-L / T-RO / RSS (primary, 우선순위 규칙 적용 후) |
| `venues_all` | dedup | 같은 논문이 등장했던 모든 venue (쉼표 구분) |
| `year` | DBLP | 발표/발간 연도 |
| `title` | DBLP | 논문 제목 (HTML 엔티티 디코딩 후) |
| `authors` | DBLP | 저자 (세미콜론 구분, 동명이인 식별자 제거) |
| `abstract` | OpenAlex | 초록 (커버리지 ~99%) |
| `cited_by_count` | OpenAlex | 인용 수 |
| `concepts` | OpenAlex | 자동 분류 토픽 상위 5개 (세미콜론 구분) |
| `doi` | DBLP | DOI (소문자, `https://doi.org/` 프리픽스 제거) |
| `ee` | DBLP | 전자 버전 URL (주로 IEEE Xplore) |
| `pages` | DBLP | 페이지 범위 |
| `dblp_key` | DBLP | DBLP 고유 키 |
| `openalex_id` | OpenAlex | OpenAlex Work ID |

## 참고

- **OpenAlex 초록 커버리지**: 최근 논문 95%+, 2010년 이전은 낮음
- **DOI 커버리지**: 전체 99.9%, 1990년 이전 일부 없음
- **세션 정보**: DBLP에 없음. OpenAlex `concepts`가 대체재 (세밀한 세션 트랙은 IEEE Xplore API 필요)
- **큰 파일 분석**: xlsx가 버거우면 `df.to_parquet('x.parquet')` 후 pandas/DuckDB 권장

## 새 venue 추가하려면

`step1_dblp.py`의 `venues_config`에 한 줄:
```python
('key', 'dblp/stream', 'LABEL', range(start_year, 2026)),
```
그 후 step1 → step2 → step3 순서로 실행. 각 `_make_*.py` 생성기의 `VENUES` 리스트·색·필터 체크박스에도 LABEL 추가 필요.

## Credit

- **DBLP** (https://dblp.org/) — 메타데이터
- **OpenAlex** (https://openalex.org/) — 초록·인용수·concepts
- **Chart.js** — 시각화
