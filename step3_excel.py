"""
Step 3: 최종 엑셀 파일 생성

실행: python step3_excel.py

참고:
- 5만~7만 행이면 .xlsx 한 파일에도 들어감 (엑셀 제한: 1,048,576 행)
- 다만 초록까지 포함하면 파일이 무거워질 수 있음
- 빠른 필터링을 원하면 Parquet 파일도 같이 만들면 좋음 (pandas로 바로 읽힘)
"""
import json
import html
import os
import re
from datetime import datetime
import pandas as pd

from _clean import is_front_matter, is_translated_dup

INPUT = "all_enriched.json"

# 인용수 기준일: all_enriched.json의 최종 수정일 (step2가 마지막으로 돈 시점)
try:
    AS_OF = datetime.fromtimestamp(os.path.getmtime(INPUT)).date().isoformat()
except OSError:
    AS_OF = datetime.now().date().isoformat()
print(f"Citations as of: {AS_OF}")
OUT_XLSX = "robopaper_atlas_all.xlsx"

# DOI 중복 시 어느 venue를 남길지 우선순위 (저널/선택도 높은 conf 우선).
# 순서 = summary 시트 표시 순서. 데이터에 등장하는데 여기 없는 venue는 default priority 99.
VENUE_LABELS = ['T-RO', 'IJRR', 'Sci-Rob', 'T-FR', 'SoRo', 'T-Mech', 'T-ASE', 'RAM', 'RA-L', 'RA-P', 'RSS', 'ICRA', 'IROS', 'CoRL']
VENUE_PRIORITY = {v: i for i, v in enumerate(VENUE_LABELS)}

with open(INPUT, encoding='utf-8') as f:
    papers = json.load(f)

df = pd.DataFrame(papers)

# 컬럼 순서 정리
cols = ['venue', 'year', 'title', 'authors', 'abstract', 'cited_by_count',
        'concepts', 'doi', 'ee', 'pages', 'dblp_key', 'openalex_id']
df = df[[c for c in cols if c in df.columns]]

# --- 정제 ---
# 1) HTML 엔티티 디코딩 (&quot; &apos; &amp; 등)
for col in ['title', 'authors']:
    df[col] = df[col].fillna('').astype(str).map(html.unescape)

# 1b) 저자 이름 끝의 DBLP 동명이인 식별자(예: "Tong Qin 0001") 제거
_dblp_suffix = re.compile(r'\s+\d{4}$')
def _clean_authors(s):
    return '; '.join(_dblp_suffix.sub('', a.strip()) for a in str(s).split(';') if a.strip())
df['authors'] = df['authors'].map(_clean_authors)

# 1c) 제목 끝 온점 제거 (DBLP 관습)
df['title'] = df['title'].str.rstrip('.').str.strip()

# 2) 학회 전체 proceedings 표제 행 제거 (저자 없는 것들)
before = len(df)
df = df[df['authors'].str.strip() != ''].reset_index(drop=True)
print(f"제외된 proceedings 표제 행: {before - len(df)}개")

# 2b) 저널 front-matter 제거 (Editorial, Table of Contents, Publication Info 등).
# OpenAlex가 이런 엔트리를 편집자 이름으로 귀속시켜 허브 저자를 부풀림.
before = len(df)
df = df[~df['title'].map(is_front_matter)].reset_index(drop=True)
print(f"제외된 front-matter 행: {before - len(df)}개")

# 2c) 비영어 번역본 중복 제거 (OpenAlex가 같은 논문의 일본어 번역 레코드를 별개 work로
#     기록 — DOI 비어있고 제목에 CJK 문자나 '【Powered by NICT】' 포함. T-Mech / T-ASE
#     ISSN 필터에 같이 잡혀들어옴).
before = len(df)
df = df[~df['title'].map(is_translated_dup)].reset_index(drop=True)
print(f"제외된 비영어 번역본 행: {before - len(df)}개")

# 2d) DOI 없는 행 제거 — 거의 다 학회 proceedings volume 표제
#     ("Robotics: Science and Systems XX, Delft, The Netherlands, ...") 같은
#     비논문 엔트리. 모던 robotics venue에서 정상 논문은 100% DOI 있음.
#     예외: PMLR 기반 학회 (CoRL 등) — ee URL로 정식 논문 확인됨 (DOI는 별도 resolve 필요).
before = len(df)
df['doi'] = df['doi'].fillna('').astype(str).str.strip()
is_pmlr = df['ee'].fillna('').str.startswith('https://proceedings.mlr.press/')
df = df[(df['doi'] != '') | is_pmlr].reset_index(drop=True)
print(f"제외된 DOI-less 행: {before - len(df)}개")

# 3) DOI 기반 중복 제거 (같은 DOI가 RA-L·ICRA·IROS에 중복 등장하면 RA-L 우선으로 남김)
df['doi'] = df['doi'].fillna('').astype(str).str.strip().str.lower()
# DOI 프리픽스 정규화
df['doi'] = df['doi'].str.replace(r'^https?://doi\.org/', '', regex=True)
before = len(df)
with_doi = df[df['doi'] != ''].copy()
without_doi = df[df['doi'] == ''].copy()
# venue 우선순위 기반 정렬 후 중복 DOI 첫 행만 남기고, 등장한 venue 목록도 기록
with_doi['_priority'] = with_doi['venue'].map(VENUE_PRIORITY).fillna(99).astype(int)
with_doi = with_doi.sort_values(['doi', '_priority'])
venues_per_doi = with_doi.groupby('doi')['venue'].apply(lambda s: '; '.join(sorted(set(s), key=lambda v: VENUE_PRIORITY.get(v, 99))))
with_doi = with_doi.drop_duplicates(subset=['doi'], keep='first').drop(columns=['_priority'])
with_doi['venues_all'] = with_doi['doi'].map(venues_per_doi)
without_doi['venues_all'] = without_doi['venue']
df = pd.concat([with_doi, without_doi], ignore_index=True)
print(f"DOI 중복 제거: {before} → {len(df)} ({before - len(df)}건 병합)")

# 4) 제목+연도 기반 추가 dedup (DOI 다르지만 같은 논문 — 주로 RA-L과 IROS/ICRA 교차 게재)
def _norm_title(s):
    return re.sub(r'[^a-z0-9]', '', str(s).lower())

# 제목 너무 짧은 것(예: "Editorial")은 dedup 대상에서 제외
before = len(df)
df['_tn'] = df['title'].map(_norm_title)
short_mask = df['_tn'].str.len() < 20
dedup_pool = df[~short_mask].copy()
keep_asis = df[short_mask].copy()

# Within-venue only: 같은 venue 안에서 DOI만 다른 중복 인덱스만 합침. 다른 venue 간(저널 ↔ 학회)에
# 같은-제목·같은-연도가 있어도 보통 저널 확장본/학회 원본으로 별개 publication이라 절대 합치지 않음.
dedup_pool['_priority'] = dedup_pool['venue'].map(VENUE_PRIORITY).fillna(99).astype(int)
dedup_pool = dedup_pool.sort_values(['_tn', 'year', 'venue', '_priority'])
dedup_pool = dedup_pool.drop_duplicates(subset=['_tn', 'year', 'venue'], keep='first').drop(columns=['_priority'])
df = pd.concat([dedup_pool, keep_asis], ignore_index=True).drop(columns=['_tn'])
print(f"제목+연도 dedup (within-venue): {before} → {len(df)} ({before - len(df)}건 병합)")

# 연도 내림차순, venue 정렬
df['year'] = pd.to_numeric(df['year'], errors='coerce').fillna(0).astype(int)
df = df.sort_values(['year', 'venue', 'title'], ascending=[False, True, True])

print(f"Total rows: {len(df)}")
print(f"Columns: {list(df.columns)}")
print(f"\nVenue counts:")
print(df['venue'].value_counts())
print(f"\nYear range: {df['year'].min()} ~ {df['year'].max()}")

# --- 통계 시트들 ---
# 1) by_year: 연도 × venue 논문 편수 (+ 커버리지)
cited_num = pd.to_numeric(df['cited_by_count'], errors='coerce')
stats_df = df.assign(
    _has_doi=df['doi'].astype(bool),
    _has_abs=df['abstract'].astype(str).str.len() > 0,
    _cited=cited_num,
)
by_year = stats_df.groupby(['year', 'venue']).agg(
    papers=('title', 'count'),
    with_doi=('_has_doi', 'sum'),
    with_abstract=('_has_abs', 'sum'),
    total_citations=('_cited', 'sum'),
    mean_citations=('_cited', 'mean'),
).reset_index()
by_year['abstract_coverage_%'] = (100 * by_year['with_abstract'] / by_year['papers']).round(1)
by_year['mean_citations'] = by_year['mean_citations'].round(1)
by_year = by_year.sort_values(['year', 'venue'], ascending=[False, True])

# 2) pivot: 연도 행, venue 열 (한 눈에 보기 좋게)
pivot = stats_df.pivot_table(index='year', columns='venue', values='title',
                              aggfunc='count', fill_value=0)
pivot['total'] = pivot.sum(axis=1)
pivot = pivot.sort_index(ascending=False).reset_index()

# 3) summary: 전체 요약
total = len(df)
summary_rows = [
    ('Citations as of', AS_OF),
    ('Total papers', total),
]
# 알려진 venue는 VENUE_LABELS 순서로, 그 외 데이터에만 있는 venue는 뒤에 덧붙임
seen_venues = set(df['venue'].astype(str).unique())
ordered = [v for v in VENUE_LABELS if v in seen_venues]
extras  = sorted(v for v in seen_venues if v and v not in VENUE_PRIORITY)
for v in ordered + extras:
    summary_rows.append((v, int((df['venue'] == v).sum())))
summary_rows += [
    ('Year range', f"{df['year'].min()} ~ {df['year'].max()}"),
    ('With DOI', f"{int(df['doi'].astype(bool).sum())} ({100*df['doi'].astype(bool).mean():.1f}%)"),
    ('With abstract', f"{int((df['abstract'].astype(str).str.len() > 0).sum())} ({100*(df['abstract'].astype(str).str.len() > 0).mean():.1f}%)"),
    ('With citation count', f"{int(cited_num.notna().sum())} ({100*cited_num.notna().mean():.1f}%)"),
    ('Total citations', int(cited_num.fillna(0).sum())),
    ('Mean citations', round(cited_num.mean(), 1)),
    ('Median citations', int(cited_num.median()) if cited_num.notna().any() else 0),
]
summary_df = pd.DataFrame(summary_rows, columns=['Field', 'Value'])

# 4) top_cited: 인용 많은 top 100
top_cited = df.copy()
top_cited['cited_num'] = cited_num
top_cited = top_cited.dropna(subset=['cited_num']).nlargest(100, 'cited_num')
top_cited = top_cited[['venue', 'year', 'title', 'authors', 'cited_num', 'doi']].rename(
    columns={'cited_num': 'cited_by_count'})

# XLSX (openpyxl 필요) — 멀티시트
try:
    # 초록이 긴 경우 엑셀 셀 한도(32,767자) 초과 방지
    for col in ['abstract', 'title', 'authors']:
        if col in df.columns:
            df[col] = df[col].astype(str).str[:32000]
    top_cited['title'] = top_cited['title'].astype(str).str[:32000]
    top_cited['authors'] = top_cited['authors'].astype(str).str[:32000]

    with pd.ExcelWriter(OUT_XLSX, engine='openpyxl') as writer:
        summary_df.to_excel(writer, sheet_name='summary', index=False)
        pivot.to_excel(writer, sheet_name='by_year_pivot', index=False)
        by_year.to_excel(writer, sheet_name='by_year_detail', index=False)
        top_cited.to_excel(writer, sheet_name='top_cited_100', index=False)
        df.to_excel(writer, sheet_name='papers', index=False)
    print(f"XLSX saved: {OUT_XLSX}")
    print(f"  sheets: summary, by_year_pivot, by_year_detail, top_cited_100, papers")
except Exception as e:
    print(f"XLSX 생성 실패: {e}")
    print("해결: pip install openpyxl")
