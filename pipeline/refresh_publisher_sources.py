"""Supplement recent DBLP records from publisher metadata when DBLP is unavailable.

Keeps existing DBLP records and identifiers. Caches use their real source names.
Run from pipeline: python refresh_publisher_sources.py journals|conferences|rss|corl|merge
"""
import argparse
import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from step1_extra_openalex import fetch_venue_year
from step1c_crossref_conferences import _to_record

YEARS = (2025, 2026)
OUT = Path('publisher_raw')
OUT.mkdir(exist_ok=True)

def get(url, **kwargs):
    for attempt in range(5):
        r = requests.get(url, timeout=90, **kwargs)
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(10 * (attempt + 1))
            continue
        r.raise_for_status()
        return r
    r.raise_for_status()

def save(key, year, records):
    path = OUT / f'{key}_{year}.json'
    path.write_text(json.dumps(records, ensure_ascii=False), encoding='utf-8')
    print(f'{key} {year}: {len(records)} records', flush=True)

def html_page(url):
    # text/html without an HTTP charset makes requests.text default to Latin-1.
    # Parse the original bytes so the document's UTF-8 declaration is respected.
    return BeautifulSoup(get(url).content, 'html.parser')

def journals():
    sources = [
        ('ral','RA-L','IEEE Robotics and Automation Letters'),
        ('tro','T-RO','IEEE Transactions on Robotics'),
        ('ijrr','IJRR','The International Journal of Robotics Research'),
        ('ram','RAM','IEEE Robotics & Automation Magazine'),
        ('scirob','Sci-Rob','Science Robotics'),
    ]
    for key,label,name in sources:
        results=get('https://api.openalex.org/sources',params={'search':name,'per-page':5}).json()['results']
        norm=lambda s: re.sub(r'[^a-z0-9]','',s.lower().replace('and','').replace('the',''))
        matches=[s for s in results if norm(s['display_name'])==norm(name)]
        if len(matches)!=1: raise RuntimeError(f'Ambiguous journal: {name}')
        source=matches[0]
        print(f'{label}: {source["display_name"]}, ISSN {source["issn_l"]}',flush=True)
        for year in YEARS:
            rows=fetch_venue_year(source['issn_l'],label,year)
            if rows is None: raise RuntimeError(f'Failed {label} {year}')
            for row in rows: row['metadata_source']='OpenAlex'
            save(key,year,rows)

def conferences():
    for key,label in [('icra','ICRA'),('iros','IROS'),('ssrr','SSRR'),('isparo','iSpaRo')]:
        for year in YEARS:
            records={}
            # Bibliographic acronym query ranks the exact DOI stem first;
            # continue past 1000 rows until a whole page has no exact matches.
            for offset in range(0,10000,1000):
                data=get('https://api.crossref.org/works',params={
                    'query.bibliographic':f'{label} {year}',
                    'filter':f'prefix:10.1109,from-pub-date:{year}-01-01,until-pub-date:{year}-12-31',
                    'rows':1000,'offset':offset,'mailto':'gisbi.kim@gmail.com',
                    'select':'DOI,title,container-title,page,author,published-print,published-online,published',
                }).json()['message']
                pattern=re.compile(rf'^10\.1109/{key}\d*\.{year}\.')
                matched=[x for x in data['items'] if pattern.match(x.get('DOI','').lower())]
                for item in matched:
                    row=_to_record(item,label,year)
                    row['metadata_source']='Crossref'
                    if row['authors']: records[row['doi']]=row
                print(f'{label} {year} offset {offset}: {len(matched)} exact matches',flush=True)
                if not matched or len(data['items'])<1000: break
                time.sleep(1)
            else: raise RuntimeError(f'Pagination cap reached for {label} {year}')
            save(key,year,list(records.values()))
            time.sleep(1)

def rss():
    for year in YEARS:
        base=f'https://www.roboticsproceedings.org/rss{year-2004:02d}/'
        soup=html_page(base)
        links=sorted({urljoin(base,a['href']) for a in soup.find_all('a',href=re.compile(r'^p\d+\.html$'))})
        if not links: raise RuntimeError(f'No RSS papers at {base}')
        records=[]
        for i,url in enumerate(links):
            page=html_page(url)
            def meta(name):
                return [x.get('content','') for x in page.find_all('meta',attrs={'name':name})]
            doi=re.search(r'DOI\s*=\s*\{([^}]+)\}',page.get_text())
            if not doi: raise RuntimeError(f'Missing DOI: {url}')
            abstract=page.select_one('p[style*="text-align"]')
            records.append({'venue':'RSS','year':str(year),'title':meta('citation_title')[0],
                'authors':'; '.join(meta('citation_author')),'doi':doi.group(1).lower(),
                'ee':url,'pages':'','dblp_key':'','metadata_source':'RSS proceedings',
                'publisher_abstract':abstract.get_text(' ',strip=True) if abstract else ''})
            if (i+1)%25==0: print(f'RSS {year}: {i+1}/{len(links)}',flush=True)
            time.sleep(0.1)
        save('rss',year,records)

def corl():
    base='https://proceedings.mlr.press/'
    index=html_page(base)
    volumes=[]
    for li in index.select('.proceedings-list li'):
        match=re.search(r'CoRL (20\d\d)',li.get_text())
        if match and int(match.group(1)) in YEARS:
            volumes.append((int(match.group(1)),urljoin(base,li.a['href'])+'/'))
    for year,url in volumes:
        page=html_page(url)
        records=[]
        for paper in page.select('.paper'):
            link=paper.find('a',string='abs')['href']
            pages=re.search(r'PMLR \d+:([\d-]+)',paper.get_text())
            records.append({'venue':'CoRL','year':str(year),
                'title':paper.select_one('.title').get_text(' ',strip=True),
                'authors':'; '.join(a.strip() for a in paper.select_one('.authors').get_text().split(',')),
                'doi':'','ee':link,'pages':pages.group(1) if pages else '',
                'dblp_key':'','metadata_source':'PMLR'})
        if not records: raise RuntimeError(f'No papers at {url}')
        save('corl',year,records)
    print('CoRL published recent volumes:',volumes,flush=True)

def merge():
    path=Path('all_dblp.json')
    papers=json.loads(path.read_text(encoding='utf-8'))
    # Venue-specific keys retain cross-listed journal/conference records.
    def identity(p):
        return (p['venue'],p.get('doi','').lower().strip() or p.get('ee','').rstrip('/'))
    by_id={identity(p):p for p in papers}
    before=len(papers)
    files=sorted(OUT.glob('*.json'))+sorted(Path('openalex_raw').glob('*_202[56].json'))
    for file in files:
        added=0
        for row in json.loads(file.read_text(encoding='utf-8')):
            key=identity(row)
            if key in by_id:
                old=by_id[key]
                # Preserve DBLP year/identity; fill missing publisher information.
                for field,value in row.items():
                    own_publisher_text = (
                        old.get('metadata_source') == row.get('metadata_source') == 'RSS proceedings'
                        and field in ('title', 'authors', 'publisher_abstract')
                    )
                    if value and (not old.get(field) or own_publisher_text): old[field]=value
            else:
                papers.append(row); by_id[key]=row;added+=1
        print(f'{file}: +{added}',flush=True)
    path.write_text(json.dumps(papers,ensure_ascii=False),encoding='utf-8')
    print(f'Merged {before} -> {len(papers)} records',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('source',choices=['journals','conferences','rss','corl','merge'])
    args=parser.parse_args()
    globals()[args.source]()
