# 전체 리프레시 가이드 (top entry)

데이터 → 네트워크 → 랜딩까지 **3단계**를 순서대로 돌리는 오케스트레이터 문서.

각 단계는 별도 가이드(`REFRESH_step{N}_*.md`)로 분리되어 있으며 단독 실행도 가능하지만,
보통은 본 문서 한 줄 프롬프트로 시작해서 Claude가 셋을 차례로 진행합니다.

---

## 👉 Claude에게 줄 프롬프트 (아래 전체 복사)

```
REFRESH.md 보고 전체 리프레시 (데이터 → 네트워크 → 랜딩) 순서대로 진행해줘.
```

---

## Claude가 할 일 (체크리스트)

### Step 1 · 데이터 업데이트 — [REFRESH_step1_데이터업데이트.md](REFRESH_step1_데이터업데이트.md)

DBLP 새 연도 수집 + Semantic Scholar 인용수 갱신 + xlsx / explorer / by_year / dataset_preview / word_book 재생성.

⚠️ **반드시 사용자에게 물어볼 것**: "새 연도 추가할지" + "인용수 refresh 범위 (건너뛰기 / 최근 7년 / 전체)".
풀 refresh는 Semantic Scholar 호출 비용이 큼 — 기본 정책은 **3개월에 한 번**, 평소엔 신규 DOI와
신규 DOI-less PMLR 논문만 캐시 기반으로 fetch. 사용자 응답을 받기 전엔 절대 풀 refresh를 임의 실행하지 말 것.

자세한 분기와 데이터 cleanup invariant(front-matter / CJK 번역본 / DOI-less / 저널-학회 dedup
경계 / 페이지 cap)는 step1 문서 참조. 새 venue를 추가해도 모든 invariant가 자동으로 적용됨.

산출물 변화:
- `all_dblp.json`, `all_enriched.json`, `enriched_checkpoint_*.json`, `enriched_doi_less_checkpoint.json`
- `robopaper_atlas_all.xlsx`, `by_venue/*.xlsx`
- `explorer.html`, `by_year.html`, `dataset_preview.html`
- `word_book.{json,csv}`

### Step 2 · 공저자 네트워크 — [REFRESH_step2_공저자네트워크.md](REFRESH_step2_공저자네트워크.md)

`_make_coauthor_network.py` → `_enrich_communities.py` 순서로 실행.
Step 1 의 `all_enriched.json` 이 입력이므로 **반드시 Step 1 다음에**.

산출물 변화:
- `coauthor_network.json` (HTML은 정적 템플릿이라 보통 unchanged)

### Step 3 · 랜딩 페이지·README 동기화 — [REFRESH_step3_랜딩페이지.md](REFRESH_step3_랜딩페이지.md)

`index.html` 과 `README.md` 의 수기 통계(편수 / 연도 범위 / coverage / 네트워크 노드·엣지 수
/ xlsx 크기 등)를 새 산출물의 실제 값과 맞춤. Step 1·2 가 끝난 후에 진행.

산출물 변화:
- `index.html`, `README.md`

### 마무리 · 커밋·푸시 (한 큐로 묶어도 됨)

각 step 가이드마다 별도 커밋 예시가 있지만, 한 번에 푸시할 거면 마지막에 일괄로:

```bash
git add -u && git add pipeline/dblp_raw/ pipeline/openalex_raw/ REFRESH*.md
git commit -m "Refresh: data → network → landing (<오늘 날짜>)"
git push
```

> `git add -u` 는 추적 중인 변경만 잡으니 새 raw 캐시(`pipeline/dblp_raw/*_YYYY.json` 등)와 신규 문서는
> 명시적으로 추가. 민감 파일(.env, credentials) 없는 디렉터리만 골라 추가하세요.

---

## 단계 간 의존성

```
Step 1 (데이터)  →  Step 2 (네트워크)
       ↘                  ↘
        →→→→→→→→→→  Step 3 (랜딩)
```

- Step 2 는 Step 1 의 `all_enriched.json` 을 입력
- Step 3 는 Step 1 의 `step3_excel.py` 출력 + Step 2 의 `coauthor_network.json` 메타를 모두 참조
- 부분 실행도 가능: 네트워크만 다시 빌드하면 Step 2 → Step 3 (편수는 그대로지만 노드/엣지 카피 갱신)

## 관련 파일
- [`REFRESH_step1_데이터업데이트.md`](./REFRESH_step1_데이터업데이트.md)
- [`REFRESH_step2_공저자네트워크.md`](./REFRESH_step2_공저자네트워크.md)
- [`REFRESH_step3_랜딩페이지.md`](./REFRESH_step3_랜딩페이지.md)
