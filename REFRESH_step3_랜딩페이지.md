# Step 3 — Landing 페이지 (index.html · README.md) 업데이트 가이드

전체 리프레시 3단계 중 마지막 단계 (수기 관리 파일의 통계를 새 데이터로 동기화).

`explorer.html` · `by_year.html` · `coauthor_network.html` 은 `_make_*.py`가 자동 생성하지만,
**`index.html` 과 `README.md` 는 수기 관리** 파일입니다. 데이터 파이프라인
([REFRESH_step1_데이터업데이트.md](REFRESH_step1_데이터업데이트.md) /
[REFRESH_step2_공저자네트워크.md](REFRESH_step2_공저자네트워크.md))을 돌린 후, 화면에 표시되는 통계가
stale 해지므로 별도 갱신 필요.

> 데이터/네트워크/랜딩까지 한 큐로 가려면 **[REFRESH.md](REFRESH.md)** 한 줄로 시작.

---

## 👉 Claude에게 줄 프롬프트

```
REFRESH_step3_랜딩페이지.md 보고 landing/README 통계 업데이트 해줘.
```

전제: Step 1·2 가 이미 실행되어 산출물이 최신이어야 합니다.

---

## Claude가 할 일 (체크리스트)

### 1) 현재 수치 추출

```bash
# 1) 총 편수 + 연도 범위 + venue별 편수
python3 - <<'PY'
import json
with open('all_enriched.json') as f:
    papers = json.load(f)
print('total raw:', len(papers))
years = sorted({p['year'] for p in papers if p.get('year')})
print('year range:', years[0], '~', years[-1])
PY

# 2) 정확한 dedup 후 수치 — step3_excel.py 마지막 출력의
#    "Total rows:" / "Venue counts:" 그대로 사용

# 3) Abstract coverage — _make_word_book.py 출력의 "papers indexed"
#    coverage = papers_indexed / total_rows

# 4) xlsx 파일 크기
ls -lh robopaper_atlas_all.xlsx | awk '{print $5}'

# 5) Co-author network 통계
python3 -c "
import json
m = json.load(open('coauthor_network.json'))['meta']
print('nodes:', m['nodes'], 'edges:', m['edges'], 'built:', m['built_at'])
"
```

### 2) `index.html` 갱신 (검색 + Edit)

| 위치 (검색 키워드) | 갱신할 항목 |
|---|---|
| `<meta name="description"` | 총 편수 (반올림, "82,000+") · 연도 범위 |
| 페이지 상단 `.tagline` | 총 편수 (반올림) |
| `.stats` 블록 (4개 카드) | Papers (정확) · Venues · Years · Abstract coverage |
| `Co-author Network` 카드 `.desc` | 저자 수 / 엣지 수 (반올림, "24k+ / 70k+") |
| `📊 Excel (.xlsx)` 다운로드 라인 | 파일 크기 · 정확한 편수 |

> 반올림 가이드: "총 편수"·"네트워크 저자/엣지" 같은 마케팅 카피는 천 단위 반올림(82,000+ / 24k+),
> stat 카드의 정확한 숫자는 천단위 콤마 그대로 (82,795).

### 3) `README.md` 갱신

| 위치 | 갱신할 항목 |
|---|---|
| 상단 한 줄 소개 | 총 편수 (반올림) |
| 「수집 범위」 표 | venue별 편수 (백 단위 반올림) · 합계 행의 연도 범위 + 총합 |
| 「Full Explorer」 섹션 헤더 | 총 편수 (반올림) |
| 「Co-author Network」 섹션 | 저자 / 엣지 수 (반올림) |
| 「새 venue 추가하려면」 코드 예시 | `range(..., 2026)` → `range(..., 2027)` 등 현재 수집년도 +1 로 통일 |

### 4) 검증

브라우저에서 `index.html` 열어 시각 확인:
- stat 카드 4개 숫자 / 배지 / 다운로드 라벨 / 카드 desc 줄이 모두 새 데이터와 일치
- README.md 는 GitHub 렌더링으로 확인 (또는 로컬 markdown viewer)

`step1_dblp.py` / `step1_extra_openalex.py`의 `range(start, END)` 의 END 값도
새로 수집한 마지막 연도 +1 로 일관되게 맞춰져 있는지 한 번 더 점검 (예: 2026까지 수집했으면 END=2027).

### 5) 커밋·푸시

```bash
git add index.html README.md \
        step1_dblp.py step1_extra_openalex.py
git commit -m "Refresh landing & README stats (<N> papers, <Y> range)"
git push
```

---

## 어떤 파일이 수기인지 정리

| 파일 | 자동/수기 | 트리거 |
|---|---|---|
| `explorer.html` | 자동 | `_make_all_html.py` |
| `by_year.html` | 자동 | `_make_by_year_html.py` |
| `coauthor_network.html` | 자동 | `_make_coauthor_network.py` |
| `dataset_preview.html` | 자동 | `_make_xlsx_preview.py` |
| `coauthor_network_methods.html` | 수기 | 수동 편집 |
| **`index.html`** | **수기** | **본 문서** |
| **`README.md`** | **수기** | **본 문서** |

## 관련 파일
- [`REFRESH.md`](./REFRESH.md) — 3단계 전체 흐름을 관장하는 top 문서
- [`REFRESH_step1_데이터업데이트.md`](./REFRESH_step1_데이터업데이트.md) — 메인 데이터 파이프라인 (raw → enriched → xlsx + 자동 HTML)
- [`REFRESH_step2_공저자네트워크.md`](./REFRESH_step2_공저자네트워크.md) — 공저자 네트워크 재계산
- 본 문서 — 위 두 단계 후 landing 페이지·README 의 수기 통계 동기화
