# Co-author Network 업데이트 가이드

`coauthor_network.html` 의 노드(저자) · 엣지(공저 관계) 는 매년 논문이 쌓이면서
새 노드가 등장하고 기존 노드의 연결이 확장됩니다. 이 문서를 Claude에게 주면
최신 데이터로 재계산해줍니다.

---

## 👉 Claude에게 줄 프롬프트

```
REFRESH_CONNECTIONS.md 보고 co-author network 업데이트 해줘.
```

---

## Claude가 할 일 (체크리스트)

### 1) 본체 데이터가 최신인지 확인
`all_enriched.json` 의 수정일이 오래됐으면 먼저 **[REFRESH.md](REFRESH.md)** 절차로 메인
파이프라인을 돌려야 합니다. (새 연도 / 인용수 갱신 / dedup)

`coauthor_network.json` 은 `all_enriched.json` 을 입력으로 쓰므로 그쪽이 먼저 최신이어야 합니다.

### 2) 네트워크 재생성 (두 단계)

```bash
python _make_coauthor_network.py   # 그래프 빌드
python _enrich_communities.py      # Leiden 커뮤니티 + TF-IDF 토픽 라벨 주입
```

> `_enrich_communities.py`는 네트워크 JSON을 **in-place로 수정**합니다. 반드시
> `_make_coauthor_network.py` 다음에 실행해야 커뮤니티 색/라벨이 복구됩니다.
> 필요 패키지: `networkx · leidenalg · igraph · scikit-learn`.

출력:
- `coauthor_network.json` — nodes / edges / meta + 각 노드 `community` id + `meta.communities` (id, size, top_authors, label_words, color)
- `coauthor_network.html` — d3-force 기반 인터랙티브 viz (runtime에 JSON fetch)

현재 기준 파라미터 (스크립트 상단에서 조정):
```python
MIN_AUTHOR_PAPERS = 3   # 저자당 최소 편수 — 3편 이상이면 검색 대상
MIN_EDGE_COLLABS  = 2   # 데이터에 포함되는 최소 공저 횟수 (슬라이더 하한)
DEFAULT_EDGE_VIEW = 5   # HTML 슬라이더 초기값 — 기본 뷰는 공저 5회 이상만
```

### 3) 데이터가 많이 늘면 임계치 튜닝

노드 개수가 너무 많아지면 브라우저가 버벅이므로 아래 가이드대로 올립니다:

| 전체 논문 수 | `MIN_AUTHOR_PAPERS` | `MIN_EDGE_COLLABS` | 실제 노드 수 |
|---|---:|---:|---:|
| ~82k (현재, 9 venues) | 3 | 2 | 24,017 |
| ~100k                 | 4 | 2 | ~25,000 |
| ~150k                 | 5 | 3 | ~22,000 |
| ~200k                 | 6 | 3 | ~20,000 |

브라우저 쾌적성: 기본 뷰(threshold 5)에서는 수천 노드라 쾌적. 슬라이더를 2로 내리면
전체 노드가 보여져 가장 무거워지는데, 이때 기준 25k 이하가 되도록 임계치 조절.

### 4) 결과 검증

`coauthor_network.html` 을 브라우저에서 열어 확인 (서버 띄워야 함 — `python -m http.server`):
- 좌측 패널 상단 meta: `nodes · edges` · Papers · Years · Built 날짜 정상
- **Communities 패널**: 토글하면 히스토그램 + 93개 동네 리스트. 각 항목 `visible / total` 두 숫자 표시 (문서 하단 설명 참조)
- 검색창에 아무 저자 이름(예: `Thrun`) 쳐서 중앙 이동 정상
- Top 100 hubs 토글 → 순위 변화
- 체크박스 "Show 2nd/3rd degree connections" → 색상 표시 정상
  - 1차 emerald `#34d399` / 2차 indigo `#818cf8` / 3차 amber `#f59e0b`
- Edge threshold · Layout spread 슬라이더 동작
- Color 라디오(community/year) 전환 정상
- 우하단 legend에 "How this works →" 링크 → methods 페이지 열림

### 5) 커밋·푸시

```bash
git add _make_coauthor_network.py _enrich_communities.py \
        coauthor_network.json coauthor_network.html
git commit -m "Refresh co-author network (<N> authors, <M> edges as of <date>)"
git push
```

---

## 기능 요약 (현재 구현된 것)

- **Force-directed canvas** (d3-force) + 줌/팬/드래그
- **줌아웃 적응 엣지 두께**: 배율 `k < 1` 일 때 선이 `1/k` 배 굵어져 화면 픽셀 두께 일정 유지
- **노드 호버**: 공저자 상위 10명 + 공저 횟수 툴팁
- **노드 클릭**: 중심 노드 표시 + 연결 엣지 색상 강조
- **검색 패널**: 저자명 부분 일치 25명 (Enter 시 첫 결과 이동)
- **Top 100 hubs**: 현재 뷰 기준 공저자 수 내림차순 (엣지 threshold 변경 시 자동 재계산)
- **2/3차 연결 토글** (기본 off): emerald → indigo → amber 3단계 시각화
- **Edge threshold 슬라이더**: 2~30 범위 (기본 5), 실시간으로 subgraph 축소/확장
- **Layout spread 슬라이더**: 1~10 범위 (기본 3.5), 레이아웃의 반발력·링크 거리 조정 (데이터 영향 없음)
- **Meta 표기**: 좌상단 패널에 대상 venue 목록 · 연도 범위 · 빌드일 표시

## 관련 파일
- [`_make_coauthor_network.py`](./_make_coauthor_network.py) — 이 네트워크 생성기
- [`REFRESH.md`](./REFRESH.md) — 메인 데이터(`all_enriched.json`) 업데이트 가이드
- [`REFRESH_INDEX.md`](./REFRESH_INDEX.md) — 네트워크 노드/엣지 수가 바뀌면 `index.html`·`README.md` 의 "24k+ / 70k+" 같은 카피도 같이 갱신
