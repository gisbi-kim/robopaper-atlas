# RoboPaper Atlas

**40여 년치 로봇공학 논문(ICRA · IROS · RA-L · T-RO · RSS · IJRR · Sci-Rob · SoRo · T-Mech · T-FR · RA-P · T-ASE)을 한 곳에 모은 인터랙티브 아틀라스.**
DBLP + OpenAlex로 88,000+ 편의 제목·저자·초록·인용수·키워드를 긁어와서
중복 제거하고, 바로 탐색·정렬·필터할 수 있는 웹 페이지와 엑셀로 정리합니다.

🔗 **Live demo**: https://gisbi-kim.github.io/robopaper-atlas/

## 수집 범위

| Venue | Source | 시작 연도 | 편수 (dedup 후) |
|---|---|---:|---:|
| ICRA | DBLP `conf/icra` | 1984 | ~30,600 |
| IROS | DBLP `conf/iros` | 1988 | ~26,600 |
| RA-L | DBLP `journals/ral` | 2016 | ~10,200 |
| T-Mech | OpenAlex ISSN `1083-4435` | 1996 | ~6,100 |
| T-RO | DBLP `journals/trob` | 2004 | ~3,400 |
| IJRR | DBLP `journals/ijrr` | 1982 | ~2,700 |
| RSS | DBLP `conf/rss` | 2005 | ~1,500 |
| Sci-Rob | DBLP `journals/scirobotics` | 2016 | ~890 |
| SoRo | OpenAlex ISSN `2169-5172` | 2014 | ~820 |
| T-FR | OpenAlex ISSN `2997-1101` | 2024 | ~85 |
| RA-P | OpenAlex ISSN `2995-4304` | 2025 | ~20 |
| T-ASE | OpenAlex ISSN `1545-5955` | 2004 | ~5,580 |
| **합계** | | 1984 ~ 2026 | **~88,500** |

DOI + (정규화 제목, 연도) 기반으로 저널↔학회 교차 게재를 병합 (예: RA-L 논문이 ICRA에서 발표된 경우 1개 엔트리).

## 무엇을 할 수 있나

### 🔍 [Full Explorer](explorer.html)
88,000+편 전체 탐색기. 한 페이지에서:
- **연도 범위** / **venue** / **최소 인용수** / **제목·저자 검색** 복합 필터
- 모든 컬럼(venue, year, cites 등) **클릭 정렬**
- 페이지당 50 ~ 10,000 선택 가능한 페이지네이션
- 결과에 연동되는 **stacked bar chart** (연도별 편수) + **scatter plot** (연도 × 인용수)
- 필터 결과의 **h-index / i10 / 인용수 히스토그램** (저자 검색 + 연도 범위로 개인 scientometrics)
- 필터 결과 초록에서 추출한 **word cloud** (저자나 연도 구간의 주제 키워드 확인)
- 제목에 마우스 hover → **초록 미리보기 툴팁** (OpenAlex on-demand fetch)
- 제목 클릭 → DOI 링크 새 탭으로 열기

### 📈 [Papers by Year](by_year.html)
연도별 venue별 편수 추이. Stacked / Grouped / Line 세 가지 뷰로 토글.

### 🕸️ [Co-author Network](coauthor_network.html)
저자 26k+, 공저 엣지 80k+ 인터랙티브 그래프.

### 🌐 [Conference Location Globe](https://gisbi-kim.github.io/icra-iros-globe/src/icra_iros_globe.html)
ICRA / IROS 개최지를 3D 지구본에 시각화 (별도 프로젝트).

### 📊 [Dataset download](robopaper_atlas_all.xlsx)
**XLSX** — 5 시트: `summary` / `by_year_pivot` / `by_year_detail` / `top_cited_100` / `papers`

**Word book**: [`word_book.csv`](word_book.csv) (0.3 MB) · [`word_book.json`](word_book.json) (18 MB)
초록에서 stop word 제외 후 추출한 단어장. CSV는 `word,total_count,num_papers`. JSON은 vocab + per-paper 상위 50 단어 인덱스 — word cloud용.

## 데이터 기준일

OpenAlex 인용수는 시간이 지나면서 바뀝니다. 모든 HTML 상단 우측과 xlsx `summary` 시트 첫 행에 **"Citations as of YYYY-MM-DD"** 로 마지막 갱신일을 표기.

## 업데이트 (재조사)

최신 인용수로 갱신하거나 새 연도 논문을 추가하고 싶으면 **[REFRESH.md](REFRESH.md)** 의 한 줄 프롬프트를 Claude에게 주세요. 다음 3 단계를 순서대로 진행합니다:

1. [`REFRESH_step1_데이터업데이트.md`](REFRESH_step1_데이터업데이트.md) — DBLP 새 연도 + OpenAlex 인용수 + xlsx/HTML 재생성
2. [`REFRESH_step2_공저자네트워크.md`](REFRESH_step2_공저자네트워크.md) — 공저자 그래프 + Leiden 커뮤니티 재계산
3. [`REFRESH_step3_랜딩페이지.md`](REFRESH_step3_랜딩페이지.md) — `index.html`·`README.md` 수기 통계 동기화

수동으로 돌리려면:
```bash
python refresh_recent.py 2019     # 2019~현재 DOI를 checkpoint에서 제거
python step2_openalex.py          # 제거된 DOI만 재조회
python step3_excel.py             # xlsx 재생성
python _make_all_html.py          # explorer.html
python _make_by_year_html.py      # by_year.html
python _make_coauthor_network.py  # coauthor_network.html
```

## 파이프라인 (처음부터 빌드)

### 필요 패키지
```bash
pip install requests pandas openpyxl
```

### Step 1. DBLP 메타데이터 수집 (30분~1시간)
```bash
python step1_dblp.py                    # core 6 venues
python step1_dblp.py --include-optional # + Science Robotics
```
- `step1_dblp.py`의 `CORE_VENUES` / `OPTIONAL_VENUES` 에서 venue/연도 범위 설정
- `dblp_raw/{venue}_{year}.json` 에 연도별 캐시 저장 — 중단해도 이어서
- 출력: `all_dblp.json`

### Step 1b. DBLP 미색인 저널을 OpenAlex에서 직접 수집 (10~20분)
```bash
python step1_extra_openalex.py
```
- DBLP에 없는 Soft Robotics / IEEE TMech 을 OpenAlex ISSN 필터로 연도별 수집
- `openalex_raw/{venue}_{year}.json` 캐시 + `all_dblp.json` 에 머지

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
- 제목 끝 온점 제거 (DBLP 관습)
- 학회 전체 proceedings 표제 행 제외 (저자 없는 것)
- **DOI 중복 제거** — T-RO > IJRR > RA-L > RSS > ICRA > IROS 우선
- **제목+연도 보조 dedup** — DOI 다르지만 같은 논문 (cross-venue 게재)
- 5개 시트 포함 xlsx 출력

### Step 4. 단어장 생성
```bash
python _make_word_book.py
```
초록 → 토큰화 → stop word 제거 → `word_book.json` / `word_book.csv` 출력.

### Step 5. HTML 시각화 생성
```bash
python _make_all_html.py          # explorer.html — 전체 탐색기 (h-index, i10, 히스토그램, word cloud)
python _make_by_year_html.py      # by_year.html — 연도별 편수
python _make_coauthor_network.py  # coauthor_network.html — 공저자 그래프
```
`_make_all_html.py`는 `word_book.json`을 읽어 논문당 상위 15 단어를 탐색기에 임베드합니다. 각 `_make_*.py` 상단의 `VENUES_CFG` 한 곳만 편집하면 모든 UI/CSS/JS가 자동 재생성됩니다.

## 데이터 스키마 (`papers` 시트 / CSV)

| 컬럼 | 출처 | 설명 |
|---|---|---|
| `venue` | dedup | ICRA / IROS / RA-L / T-RO / RSS / IJRR / Sci-Rob / SoRo / T-Mech (primary, 우선순위 규칙 적용 후) |
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
- **저자 탐색**: Full Explorer에서 저자명 검색하면 해당 저자의 h-index, i10-index, 인용수 히스토그램이 하단에 표시됨
- **큰 파일 분석**: xlsx가 버거우면 `df.to_parquet('x.parquet')` 후 pandas/DuckDB 권장

## 새 venue 추가하려면

`step1_dblp.py`의 `venues_config`에 한 줄:
```python
('key', 'dblp/stream', 'LABEL', range(start_year, 2027)),
```
그 후 step1 → step2 → step3 순서로 실행. 각 `_make_*.py` 생성기의 `VENUES` 리스트·색·필터 체크박스에도 LABEL 추가 필요.

## Credit

- **DBLP** (https://dblp.org/) — 메타데이터
- **OpenAlex** (https://openalex.org/) — 초록·인용수·concepts
- **Chart.js** — 시각화
