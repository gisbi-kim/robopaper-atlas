# Step 1 — 인용수·데이터 재조사 가이드

전체 리프레시 3단계 중 첫 번째 단계 (raw 데이터 → enriched → xlsx + 자동 HTML).

OpenAlex의 인용수는 시간이 지나며 바뀌고, DBLP에도 새 연도 데이터가 추가됩니다.
한번씩 이 파일을 Claude에게 주고 아래 프롬프트를 실행시키면 본 단계가 최신화됩니다.

> 데이터/네트워크/랜딩까지 한 큐로 가려면 **[REFRESH.md](REFRESH.md)** 한 줄로 시작.

---

## 👉 Claude에게 줄 프롬프트 (아래 전체 복사)

```
REFRESH_step1_데이터업데이트.md 보고 인용수·데이터 재조사 해줘.
```

---

## Claude가 할 일 (체크리스트)

### 1) 새 연도 확인 & 사용자에게 질문

- `step1_dblp.py`의 `venues_config`에서 각 venue의 현재 `range` 확인
- 이번 년도(시스템의 today 기준) 이후 연도가 `range`에 없으면 사용자에게:
  > "현재 수집 범위는 ~XXXX년까지입니다. 새 연도(YYYY)도 추가할까요?"
- 사용자 답변에 따라:
  - **예**: `venues_config`의 `range` 종료값을 확장 → `python step1_dblp.py` 실행 (캐시된 연도는 스킵, 새 연도만 수집)
  - **아니오**: 이 단계 건너뛰기

### 2) 인용수 갱신 방식 사용자에게 질문

> "인용수 갱신 범위를 선택해주세요:
>   - (1) **최근 7년** (2019~현재) — 약 5분, 주요 변동 논문 커버
>   - (2) **전체** — 약 1~3시간, 모든 71k 논문 다시 조회"

- **(1) 최근 7년**: `python refresh_recent.py 2019` 실행 → checkpoint에서 해당 연도 DOI 제거 → `python step2_openalex.py` 실행
- **(2) 전체**: `enriched_checkpoint.json` 삭제 → `python step2_openalex.py` 실행

step2는 체크포인트 없는 항목만 조회하므로 위 방식으로 자동 선택적 refresh가 됨.

### 3) 산출물 재생성 (전부 돌림)

```bash
python step3_excel.py             # robopaper_atlas_all.xlsx
python _make_word_book.py         # word_book.json / word_book.csv
python _make_all_html.py          # explorer.html
python _make_by_year_html.py      # by_year.html
python _make_xlsx_preview.py      # dataset_preview.html
python _make_coauthor_network.py  # coauthor_network.{html,json}
python _enrich_communities.py     # Leiden + TF-IDF → community 필드 주입
```

> `_enrich_communities.py`는 `_make_coauthor_network.py`가 만든
> `coauthor_network.json`을 in-place로 수정합니다. 반드시 네트워크 생성 **다음**에
> 실행하세요. 필요 패키지: `networkx · leidenalg · igraph · scikit-learn`.

### 4) 검증

- 재생성된 HTML 상단의 "Citations as of YYYY-MM-DD"가 오늘 날짜인지
- xlsx `summary` 시트 첫 행 "인용수 기준일"도 오늘 날짜인지
- 엑셀이 열려있어 저장 실패했다면 닫게 해달라고 요청

### 5) 다음 단계로

본 단계가 끝났으면:
- 공저자 네트워크 재빌드는 **[REFRESH_step2_공저자네트워크.md](REFRESH_step2_공저자네트워크.md)**
- 그 후 landing 페이지(`index.html`)·`README.md` 통계 동기화는 **[REFRESH_step3_랜딩페이지.md](REFRESH_step3_랜딩페이지.md)**
- 셋 다 한 번에 돌리는 흐름은 [`REFRESH.md`](REFRESH.md) 참고

---

## 파일 구조

| 파일 | 역할 |
|---|---|
| `step1_dblp.py` | DBLP에서 venue별 연도별 메타데이터 수집 (캐시: `dblp_raw/`) |
| `step2_openalex.py` | OpenAlex로 초록·인용수·concepts 보강 (체크포인트: `enriched_checkpoint.json`) |
| `step1_extra_openalex.py` | DBLP 미색인 저널(SoRo/TMech)을 OpenAlex ISSN으로 수집 |
| `step3_excel.py` | 정제·dedup 후 xlsx 생성 |
| `_make_all_html.py` | 전체 탐색기 HTML |
| `_make_by_year_html.py` | 연도별 편수 HTML |
| `_make_xlsx_preview.py` | xlsx 시트 미리보기 HTML |
| `_make_coauthor_network.py` | 공저자 네트워크 HTML + JSON |
| `_enrich_communities.py` | 네트워크 JSON에 Leiden 커뮤니티·토픽 라벨 주입 |
| `refresh_recent.py` | 체크포인트에서 특정 연도 이후 항목 제거 (선택적 refresh용) |

## 수집 venue 현황

| venue | Source | 시작 연도 |
|---|---|---|
| ICRA | DBLP `conf/icra` | 1984 |
| IROS | DBLP `conf/iros` | 1988 |
| RA-L | DBLP `journals/ral` | 2016 |
| T-RO | DBLP `journals/trob` | 2004 |
| RSS  | DBLP `conf/rss` | 2005 |
| IJRR | DBLP `journals/ijrr` | 1982 |
| Sci-Rob | DBLP `journals/scirobotics` | 2016 |
| SoRo | OpenAlex ISSN `2169-5172` | 2014 |
| T-Mech | OpenAlex ISSN `1083-4435` | 1996 |
| T-FR | OpenAlex ISSN `2997-1101` | 2024 |
| RA-P | OpenAlex ISSN `2995-4304` | 2024 |

## 새 venue 추가하려면

**DBLP에 색인된 경우** — `step1_dblp.py`의 `CORE_VENUES` 또는 `OPTIONAL_VENUES`에 한 줄 추가:
```python
('key', 'dblp/stream', 'LABEL', range(start_year, 2027)),
```

**DBLP에 없는 저널** — `step1_extra_openalex.py`의 `EXTRA_VENUES`에 한 줄 추가:
```python
('key', 'LABEL', 'ISSN-NUMBER', range(start_year, 2027)),
```

그 후 step1 → step2 → step3 → HTML 생성 순서로 실행. 각 `_make_*.py` 상단의 `VENUES_CFG` 리스트에 `{'label', 'id', 'color'}` 한 줄 추가하면 모든 카드/차트/필터에 자동 반영.
