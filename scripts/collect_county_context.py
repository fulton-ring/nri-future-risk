#!/usr/bin/env python3
"""Collect brief Wikipedia county context with revision provenance for FRI counties."""
import concurrent.futures, hashlib, html, json, os, re, time, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get('FRI_COUNTY_CONTEXT_WORKDIR', '/tmp/fri-county-context'))
OUT.mkdir(parents=True, exist_ok=True)
CACHE = OUT / "cache"
CACHE.mkdir(exist_ok=True)
FILES = ["public/atlas/counties.json"]
STATES = dict(zip("AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC|PR".split("|"),
"Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|Florida|Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|Nebraska|Nevada|New Hampshire|New Jersey|New Mexico|New York|North Carolina|North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|Rhode Island|South Carolina|South Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|West Virginia|Wisconsin|Wyoming|District of Columbia|Puerto Rico".split("|")))

def records():
    allr = {}
    for f in FILES:
        if not (ROOT/f).exists(): continue
        for source in json.load(open(ROOT/f))["counties"]:
            c = dict(source)
            try: c["name"] = c["name"].encode("latin1").decode("utf8")
            except (UnicodeEncodeError, UnicodeDecodeError): pass
            allr[c["id"]] = c
    return allr

def title_for(c):
    fips, name, st = c["id"], c["name"], c["state"]
    if st == "DC": return "Washington, D.C."
    state = STATES.get(st, st)
    # Census labels normally omit the legal suffix.
    if st == "LA": return f"{name} Parish, Louisiana"
    if st == "PR": return f"{name}, Puerto Rico"
    if st == "VA":
        n = int(fips)
        if n >= 51510: return f"{name}, Virginia"
        return f"{name} County, Virginia"
    # Independent city equivalents.
    if fips in ("24510", "29510", "32510"): return {"24510":"Baltimore, Maryland","29510":"St. Louis, Missouri","32510":"Carson City, Nevada"}[fips]
    # Census county equivalent naming conventions.
    if st == "AK":
        if name in {'Anchorage', 'Juneau', 'Sitka', 'Skagway', 'Wrangell', 'Yakutat'}:
            return f'{name}, Alaska'
        if name in {'Southeast Fairbanks', 'Yukon-Koyukuk'}:
            return f'{name} Census Area, Alaska'
        census = {"Aleutians West":"Aleutians West Census Area","Bethel":"Bethel Census Area","Dillingham":"Dillingham Census Area","Hoonah-Angoon":"Hoonah-Angoon Census Area","Kusilvak":"Kusilvak Census Area","Nome":"Nome Census Area","Petersburg":"Petersburg Borough","Prince of Wales-Hyder":"Prince of Wales-Hyder Census Area","Yakutat":"Yakutat City and Borough"}
        if name in census: return f"{census[name]}, Alaska"
        suffix = "Borough" if name.endswith("Borough") else ("Census Area" if name.endswith("Census Area") else ("Municipality" if name.endswith("Municipality") else "Borough"))
        base = name if name.endswith(("Borough","Census Area","Municipality")) else f"{name} {suffix}"
        return f"{base}, Alaska"
    if st == "CT": return f"{name} County, Connecticut"
    return f"{name} County, {state}"

def clean_wikitext(raw):
    raw = re.sub(r"<!--.*?-->", " ", raw, flags=re.S)
    raw = re.sub(r"<ref\b[^>]*>.*?</ref\s*>|<ref\b[^>]*/\s*>", " ", raw, flags=re.I|re.S)
    raw = re.sub(r"\{\{[^{}]*\}\}", " ", raw)
    raw = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]+)\]\]", r"\1", raw)
    raw = re.sub(r"\[(?:https?://\S+\s*)?([^\]]*)\]", r"\1", raw)
    raw = re.sub(r"'{2,5}", "", raw)
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = html.unescape(raw)
    paras=[]
    for p in re.split(r"\n\s*\n", raw):
        p = re.sub(r"^\s*=+.*?=+\s*$", "", p, flags=re.M)
        p = re.sub(r"\[\[File:[^\]]+\]\]", "", p, flags=re.I)
        p = re.sub(r"\s+", " ", p).strip(" =\t")
        if len(p) > 50 and not p.startswith(("*", "#", "|", "!")): paras.append(p)
    return paras

def sections(text):
    bits = re.split(r"(?m)^==+\s*(.*?)\s*==+\s*$", text)
    lead = clean_wikitext(bits[0]) if bits else []
    wanted = {"geography":[], "economy":[]}
    for i in range(1,len(bits)-1,2):
        h=bits[i].lower()
        key = "geography" if any(x in h for x in ("geography","physical features","geology","climate")) else ("economy" if any(x in h for x in ("economy","agriculture","industry","economic")) else None)
        if key:
            wanted[key].extend(clean_wikitext(bits[i+1]))
    return lead, wanted

def fetch(titles, batchno):
    cache = CACHE / (hashlib.sha256('|'.join(titles).encode()).hexdigest() + '.json')
    if cache.exists(): return json.loads(cache.read_text())
    params = {"action":"query","format":"json","formatversion":"2","redirects":"1",
      "maxlag":"5","prop":"extracts|revisions|info","exintro":"1","explaintext":"1","exlimit":"max",
      "rvprop":"ids|content","rvslots":"main","inprop":"url","titles":"|".join(titles)}
    url="https://en.wikipedia.org/w/api.php?"+urllib.parse.urlencode(params)
    for attempt in range(7):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"FutureRiskIndex/1.0 (https://github.com/fulton-ring/nri-future-risk; county context research)"})
            with urllib.request.urlopen(req,timeout=45) as r: data=json.load(r)
            if data.get('error'): raise RuntimeError(data['error'].get('info', 'Wikipedia API error'))
            cache.write_text(json.dumps(data,ensure_ascii=False))
            return data
        except Exception as e:
            if attempt==6: print("FAILED batch",batchno,str(e),flush=True); return {"query":{"pages":[]}}
            time.sleep(min(30,2**attempt))

def main():
    cs=records(); items=sorted(cs.items())
    entries={}
    batches=[items[i:i+20] for i in range(0,len(items),20)]
    # Create one title per record, then request batches. Handles standard redirects.
    def run(job):
        bi, chunk=job
        ts=[title_for(c) for _,c in chunk]
        return bi,chunk,fetch(ts,bi)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for bi,chunk,data in pool.map(run, enumerate(batches)):
            pages=data.get("query",{}).get("pages",[])
            bytitle={p.get("title","").casefold():p for p in pages}
            aliases={}
            for group in ("normalized","redirects"):
                for pair in data.get("query",{}).get(group,[]):
                    aliases[pair.get("from","").casefold()]=pair.get("to","")
            for fips,c in chunk:
                expected=title_for(c)
                target=expected
                seen=set()
                while target.casefold() in aliases and target.casefold() not in seen:
                    seen.add(target.casefold())
                    target=aliases[target.casefold()]
                p=bytitle.get(target.casefold())
                # redirected title may vary only by capitalization
                if not p:
                    p=next((x for x in pages if x.get("title","").casefold()==expected.casefold()),None)
                if not p or p.get("missing") is not None or p.get("pageid") is None:
                    entries[fips]={"id":fips,"name":c["name"],"state":c["state"],"title":expected,"url":None,"revisionId":None,"intro":"","geography":"","economy":"","missing":True}
                    continue
                rv=(p.get("revisions") or [{}])[0]
                text=rv.get("slots",{}).get("main",{}).get("content","")
                lead, sec=sections(text)
                intro=" ".join(lead)
                intro=p.get("extract",intro) or intro
                entries[fips]={"id":fips,"name":c["name"],"state":c["state"],"title":p.get("title",expected),
                  "url":p.get("fullurl"),"revisionId":rv.get("revid"),"intro":intro[:1500],
                  "geography":" ".join(sec["geography"])[:1500],"economy":" ".join(sec["economy"])[:1500]}
            print(f"processed batch {bi+1}/{len(batches)}; sourced {sum(not v.get('missing') for v in entries.values())}/{len(entries)}",flush=True)
            tmp=OUT/"sources.json.tmp"
            tmp.write_text(json.dumps(entries,ensure_ascii=False,indent=2))
            tmp.replace(OUT/"sources.json")
    tmp=OUT/"sources.json.tmp"
    tmp.write_text(json.dumps(entries,ensure_ascii=False,indent=2))
    tmp.replace(OUT/"sources.json")
    missing=[{"id":k,"name":v["name"],"state":v["state"],"title":v["title"]} for k,v in entries.items() if v.get("missing")]
    (OUT/"missing.json").write_text(json.dumps(missing,indent=2))
    print(f"DONE: {len(entries)} total, {len(missing)} missing; {OUT/'sources.json'}",flush=True)

if __name__=="__main__": main()
