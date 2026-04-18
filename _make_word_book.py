"""초록 단어장(word book) 생성

출력:
  - word_book.json : vocab + per-paper 상위 단어 인덱스 (HTML 내장용 + 외부 분석용)
  - word_book.csv  : word, global_count, num_papers (인간 가독용)

토큰화: 소문자 영문 단어만, 3자 이상, stop word 제외.
"""
import collections
import json
import os
import re
from datetime import date

INPUT = 'all_enriched.json'
OUT_JSON = 'word_book.json'
OUT_CSV  = 'word_book.csv'
MIN_FREQ = 10       # 전체 문서에서 10회 미만 출현하는 단어는 vocab에서 제외
TOP_PER_PAPER = 50  # 한 논문당 tf-상위 몇 개까지 저장

# 표준 영어 stop words + 흔한 학술 filler
STOP_WORDS = {
    # articles / pronouns / possessives
    'a','an','the','i','me','my','mine','myself','we','our','ours','ourselves',
    'you','your','yours','yourself','yourselves','he','him','his','himself',
    'she','her','hers','herself','it','its','itself','they','them','their',
    'theirs','themselves','this','that','these','those','what','which','who',
    'whom','whose',
    # be / have / do / modal verbs
    'am','is','are','was','were','be','been','being','have','has','had','having',
    'do','does','did','doing','done','will','would','shall','should','can',
    'could','may','might','must','ought',
    # negations / conjunctions
    'not','no','nor','none','never','and','but','if','or','because','as',
    'until','while','although','though','since','unless','however','therefore',
    'thus','hence','moreover','furthermore','also','additionally',
    # prepositions
    'of','at','by','for','with','about','against','between','into','through',
    'during','before','after','above','below','to','from','up','down','in','on',
    'out','off','over','under','again','further','then','once','within','without',
    # quantifiers / common adverbs
    'all','any','both','each','few','more','most','other','others','some','such',
    'several','many','much','every','either','neither','here','there','where',
    'when','why','how','now','only','own','same','so','than','too','very','just',
    'well','still','even','ever','yet','almost','very',
    # filler / academic filler
    'one','two','three','four','five','six','seven','eight','nine','ten',
    'first','second','third','new','old','via','per','among','across','along',
    'e.g','i.e','etc','et','al','due',
    # common academic prose
    'paper','papers','article','articles','study','studies','studied',
    'propose','proposed','proposes','proposal','present','presented','presents',
    'presentation','work','works','working','show','shows','shown','showing',
    'use','used','using','uses','method','methods','approach','approaches',
    'result','results','resulting','find','finds','found','finding','findings',
    'demonstrate','demonstrated','demonstrates','based','provide','provides',
    'provided','achieve','achieved','achieves','include','includes','included',
    'including','different','various','compared','compare','comparison',
    'consider','considered','considering','state','art','furthermore',
    'especially','particular','particularly','note','notably','previous',
    'previously','recent','recently','general','specific','specifically',
    'experiment','experiments','experimental','effective','effectively',
    'efficient','efficiency','performance','performances','perform','performs',
    'performed','performing','address','addresses','addressed','addressing',
    'able','allow','allows','allowing','need','needs','needed','required','require',
    'requires','requiring','given','gives','gave','make','makes','made','making',
    'set','sets','setting','let','lets','called','termed',
    'respectively','instead','though','whether','towards','toward',
    # short common chars leaked in
    'x','y','z','e',
    # XML / HTML / MathML noise from some OpenAlex abstracts
    'http','https','www','org','com','edu','doi','xmlns','xlink','dtd','mml',
    'xml','html','href','src','jats','ns','tag','inline','display','style',
    # figure / equation / section abbreviations
    'fig','figs','figure','figures','eq','eqs','equation','equations',
    'sec','secs','section','sections','ref','refs','reference','references',
    'table','tables','appendix','appendices',
    # common unit-ish leakages
    'abs','pos','neg','avg','std','min','max','mean','median','variance',
}

TOKEN_RE = re.compile(r"[a-z][a-z'-]*[a-z]")

def tokenize(text):
    text = text.lower()
    out = []
    for t in TOKEN_RE.findall(text):
        t = t.strip("-'")
        if len(t) < 3 or len(t) > 30: continue
        if t in STOP_WORDS: continue
        if t.isnumeric(): continue
        out.append(t)
    return out


def main():
    with open(INPUT, encoding='utf-8') as f:
        papers = json.load(f)

    global_counts = collections.Counter()
    papers_in_word = collections.Counter()  # how many papers contain the word
    paper_freq = {}  # doi -> Counter

    for p in papers:
        doi = (p.get('doi') or '').lower().strip()
        if doi.startswith('https://doi.org/'): doi = doi[len('https://doi.org/'):]
        if not doi: continue
        abs_text = p.get('abstract', '') or ''
        if not abs_text: continue
        tokens = tokenize(abs_text)
        if not tokens: continue
        global_counts.update(tokens)
        paper_freq[doi] = collections.Counter(tokens)
        for w in set(tokens):
            papers_in_word[w] += 1

    # Build vocab (freq-desc), trim by MIN_FREQ
    vocab_pairs = [(w, c) for w, c in global_counts.most_common() if c >= MIN_FREQ]
    vocab_words = [w for w, _ in vocab_pairs]
    global_counts_arr = [c for _, c in vocab_pairs]
    papers_count_arr = [papers_in_word[w] for w in vocab_words]
    word_to_idx = {w: i for i, w in enumerate(vocab_words)}

    # Per-paper: top-N words by tf
    papers_data = {}
    for doi, freq in paper_freq.items():
        in_vocab = [(word_to_idx[w], c) for w, c in freq.items() if w in word_to_idx]
        in_vocab.sort(key=lambda x: -x[1])
        papers_data[doi] = [i for i, _ in in_vocab[:TOP_PER_PAPER]]

    # JSON output
    output = {
        'vocab': vocab_words,
        'global_counts': global_counts_arr,
        'papers_count': papers_count_arr,
        'papers': papers_data,
        'meta': {
            'papers_with_abstract': len(paper_freq),
            'vocab_size': len(vocab_words),
            'min_freq_threshold': MIN_FREQ,
            'top_per_paper_cap': TOP_PER_PAPER,
            'generated_at': date.today().isoformat(),
        },
    }
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False)

    # CSV output (human-readable summary)
    with open(OUT_CSV, 'w', encoding='utf-8-sig') as f:
        f.write('word,total_count,num_papers\n')
        for w, tc, pc in zip(vocab_words, global_counts_arr, papers_count_arr):
            f.write(f'{w},{tc},{pc}\n')

    print(f"wrote {OUT_JSON} ({os.path.getsize(OUT_JSON)/1024/1024:.1f} MB)")
    print(f"wrote {OUT_CSV}  ({os.path.getsize(OUT_CSV)/1024/1024:.1f} MB)")
    print(f"  vocab size: {len(vocab_words):,}")
    print(f"  papers indexed: {len(papers_data):,}")
    print(f"  top 15 words: {vocab_words[:15]}")


if __name__ == '__main__':
    main()
