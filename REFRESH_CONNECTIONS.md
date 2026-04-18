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

### 2) 네트워크 재생성

```bash
python _make_coauthor_network.py
```

출력:
- `coauthor_network.json` — nodes / edges / meta
- `coauthor_network.html` — d3-force 기반 인터랙티브 viz (데이터 임베드)

현재 기준 파라미터 (스크립트 상단에서 조정):
```python
MIN_AUTHOR_PAPERS = 5   # 저자당 최소 편수
MIN_EDGE_COLLABS  = 5   # 두 저자 공저 최소 횟수
```

### 3) 데이터가 많이 늘면 임계치 튜닝

노드 개수가 너무 많아지면 브라우저가 버벅이므로 아래 가이드대로 올립니다:

| 전체 논문 수 | `MIN_AUTHOR_PAPERS` | `MIN_EDGE_COLLABS` | 예상 노드 수 |
|---|---:|---:|---:|
| ~75k (현재) | 5 | 5 | ~8,000 |
| ~100k       | 6 | 6 | ~8,500 |
| ~150k       | 8 | 8 | ~9,000 |
| ~200k       | 10 | 8 | ~9,500 |

브라우저 쾌적성 기준: 노드 ≤ 10k, 엣지 ≤ 20k.

### 4) 결과 검증

`coauthor_network.html` 을 브라우저에서 열어 확인:
- 좌측 패널 하단의 meta: `nodes · edges` 수 증가 확인
- 검색창에 아무 저자 이름(예: `Thrun`) 쳐서 중앙 이동 정상
- Top 100 hubs 토글 → 순위 변화
- 체크박스 "Show 2nd/3rd degree connections" → 색상 표시 정상
  - 1차 emerald `#34d399` / 2차 indigo `#818cf8` / 3차 amber `#f59e0b`
- Edge threshold 슬라이더 동작

### 5) 커밋·푸시

```bash
git add _make_coauthor_network.py coauthor_network.json coauthor_network.html
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
- **Edge threshold 슬라이더**: 5~30 범위, 실시간으로 subgraph 축소/확장

## 관련 파일
- [`_make_coauthor_network.py`](./_make_coauthor_network.py) — 이 네트워크 생성기
- [`REFRESH.md`](./REFRESH.md) — 메인 데이터(`all_enriched.json`) 업데이트 가이드
