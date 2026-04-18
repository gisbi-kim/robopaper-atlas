# 인용수·데이터 재조사 가이드

OpenAlex의 인용수는 시간이 지나며 바뀌고, DBLP에도 새 연도 데이터가 추가됩니다.
한번씩 이 파일을 Claude에게 주고 아래 프롬프트를 실행시키면 전체가 최신화됩니다.

---

## 👉 Claude에게 줄 프롬프트 (아래 전체 복사)

```
REFRESH.md 보고 인용수·데이터 재조사 해줘.
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
python step3_excel.py          # xlsx
python _make_all_html.py       # icra_iros_ral_tro_rss_explorer.html
python _make_by_year_html.py   # icra_iros_ral_tro_rss_by_year.html
```

### 4) 검증

- 재생성된 HTML 상단의 "Citations as of YYYY-MM-DD"가 오늘 날짜인지
- xlsx `summary` 시트 첫 행 "인용수 기준일"도 오늘 날짜인지
- 엑셀이 열려있어 저장 실패했다면 닫게 해달라고 요청

---

## 파일 구조

| 파일 | 역할 |
|---|---|
| `step1_dblp.py` | DBLP에서 venue별 연도별 메타데이터 수집 (캐시: `dblp_raw/`) |
| `step2_openalex.py` | OpenAlex로 초록·인용수·concepts 보강 (체크포인트: `enriched_checkpoint.json`) |
| `step3_excel.py` | 정제·dedup 후 xlsx/csv 생성 |
| `_make_all_html.py` | 전체 탐색기 HTML |
| `_make_by_year_html.py` | 연도별 편수 HTML |
| `_make_top100_html.py` | Top 100 HTML |
| `refresh_recent.py` | 체크포인트에서 특정 연도 이후 항목 제거 (선택적 refresh용) |

## 수집 venue 현황

| venue | DBLP stream | 시작 연도 |
|---|---|---|
| ICRA | `conf/icra` | 1984 |
| IROS | `conf/iros` | 1988 |
| RA-L | `journals/ral` | 2016 |
| T-RO | `journals/trob` | 2004 |
| RSS  | `conf/rss` | 2005 |

## 새 venue 추가하려면

`step1_dblp.py`의 `venues_config`에 한 줄 추가:
```python
('key', 'dblp/stream', 'LABEL', range(start_year, 2026)),
```
그 후 step1 → step2 → step3 → HTML 생성 순서로 실행.
각 HTML 생성기에 venue 색/필터/카드 추가 필요 (ICRA/IROS/RA-L/T-RO/RSS가 어떻게 들어있는지 참고).
