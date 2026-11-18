"""Bounded deterministic catalog relevance search for a small local demo.

Design: weighted fields + transliterated synonyms + phrase/prefix matching
+ conservative fuzzy fallback. For large catalogs replace scan with indexed
PostgreSQL FTS and pg_trgm; never treat fuzzy matching as clinical inference.
"""
import re
import unicodedata
from difflib import SequenceMatcher

CATEGORIES = {
    'Tulsi':'Aromatic herbs', 'Neem':'Trees & saplings', 'Aloe vera':'Succulents',
    'Ashwagandha':'Shrubs & roots', 'Brahmi':'Wetland plants', 'Amla':'Trees & saplings',
    'Lemongrass':'Aromatic herbs', 'Mint':'Aromatic herbs'
}
ALIASES = {
    'holy basil':'tulsi', 'tulasi':'tulsi', 'tulas':'tulsi',
    'neem tree':'neem', 'vepa':'neem',
    'aloe':'aloe vera', 'kalabanda':'aloe vera', 'ghritkumari':'aloe vera',
    'indian ginseng':'ashwagandha', 'aswagandha':'ashwagandha',
    'water hyssop':'brahmi', 'bacopa':'brahmi',
    'indian gooseberry':'amla', 'gooseberry':'amla', 'usiri':'amla', 'amla fruit':'amla',
    'lemon grass':'lemongrass', 'pudina':'mint', 'pudhina':'mint',
}
WEIGHTS = (('common_name',110),('scientific_name',85),('vernacular',70),
           ('family',40),('category',35),('growth',20),('habitat',12),('origin',8))

def norm(value: str) -> str:
    value=unicodedata.normalize('NFKC',str(value or '')).casefold().strip()
    return ' '.join(re.findall(r'[^\W_]+',value,flags=re.UNICODE))

def category(name:str) -> str:
    return CATEGORIES.get(name,'Medicinal plants')

def relevance(product,query: str) -> float:
    q=norm(query)[:90]
    if not q:return 1.0
    alias_points=0.0
    # Name aliases also participate in autocomplete, even when the user
    # types only a portion of a common two-word alias (e.g. 'hol bas').
    common=norm(product.get('common_name',''))
    for alias,target in ALIASES.items():
        if norm(target)!=common:continue
        alias=norm(alias)
        fragments=q.split()
        atokens=alias.split()
        if q==alias:alias_points=max(alias_points,260)
        elif len(q)>=3 and alias.startswith(q):alias_points=max(alias_points,160)
        elif len(fragments)>=2 and len(fragments)<=len(atokens) and all(a.startswith(f) for f,a in zip(fragments,atokens)):
            alias_points=max(alias_points,150)
        elif len(q)>=5 and SequenceMatcher(None,q,alias).ratio()>=0.82:
            alias_points=max(alias_points,105)
    q=ALIASES.get(q,q)
    fields={key:norm(product.get(key,'')) for key,_ in WEIGHTS}
    words=q.split()
    best=0.0
    for key,weight in WEIGHTS:
        text=fields[key]
        if not text:continue
        if q==text:score=weight*2.4
        elif text.startswith(q):score=weight*1.45
        elif q in text:score=weight*1.04
        else:
            tokens=text.split()
            match_count=sum(any(t==word or t.startswith(word) for t in tokens) for word in words)
            score=weight*0.60*match_count/len(words) if match_count==len(words) else 0
            if key in ('common_name','scientific_name','vernacular') and len(q)>=4:
                # Conservative fallback: avoid unrelated results for short user queries.
                similarities=[SequenceMatcher(None,q,t).ratio() for t in (text,*tokens) if len(t)>=3]
                sim=max(similarities,default=0)
                if sim>=0.72:score=max(score,weight*sim*0.80)
        best=max(best,score)
    return round(max(best,alias_points),3)

def suggestions(products,query:str,limit:int=6):
    q=norm(query)
    if not q:return []
    ranked=[]
    for p in products:
        score=relevance(p,q)
        if score>0: ranked.append((score,p['common_name'],p['scientific_name']))
    return [{'name':name,'scientific_name':scientific,'score':score}
            for score,name,scientific in sorted(ranked,key=lambda x:(-x[0],x[1]))[:limit]]
