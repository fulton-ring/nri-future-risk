#!/usr/bin/env python3
"""Prepare per-county public-source and actual-risk dossiers for the writing agents. Run from the repository root after collecting source evidence."""
import json,math,pathlib,bisect,hashlib
P=pathlib.Path('/tmp/fri-county-research');P.mkdir(parents=True,exist_ok=True);R=pathlib.Path.cwd();W=json.load(open('/tmp/fri-county-context/sources.json')); C=json.load(open('public/context/counties.json')); B=json.load(open('public/atlas/counties.json')); A=json.load(open('public/preview/counties.json')) if pathlib.Path('public/preview/counties.json').exists() else None; E=json.load(open('/tmp/fri-county-economy/bea-facts.json'))['counties']; O=json.load(open('scripts/county-economy-overrides.json'));COL=B['columns'];ac=A['columns'] if A else COL;D={v['id']:{**v,'v':dict(zip(COL,v['values']))}for v in B['counties']};ad={v['id']:dict(zip(ac,v['values']))for v in A['counties']} if A else {};HS=['DRGT','WFIR','EXHT','CFLD','HRCN'];pop={k:e['population']['value']for k,e in C['counties'].items()};ps=sorted(pop.values());byState={}
for k,c in D.items():byState.setdefault(c['state'],[]).append(k)
losses={h:sorted(c['v'][h+'_EALT'] for c in D.values() if isinstance(c['v'].get(h+'_EALT'),(int,float)))for h in HS}
for k,c in D.items():
 if k not in ad:continue
 for h in HS:
  for field in ['EALT','RISKV','RISKS','RISKR']:
   assert c['v'][h+'_'+field]==ad[k][h+'_'+field],(k,h,field)

def pct(n,a):return round(100*(bisect.bisect_left(a,n)+bisect.bisect_right(a,n))/(2*len(a)),1)

def risk(k):
 v=D[k]['v'];out={}
 for h in HS:
  loss=v.get(h+'_EALT');r=v.get(h+'_RISKR');valid=isinstance(r,str)and r not in ['No Rating','Not Applicable','Insufficient Data']
  out[h]={'annualLoss':loss,'lossRating':v.get(h+'_EALR'),'riskRating':r,'nationalRiskScore':v.get(h+'_RISKS')if valid else None,'lossPercentileAmongMapped3218':pct(loss,losses[h])if isinstance(loss,(int,float))else None}
 return out
baseline={k:risk(k)for k in D}
(P/'dossiers').mkdir(exist_ok=True)
for k,c in D.items():
 entry=C['counties'][k];w=W[k];p=pop[k];peer=min((x for x in byState[c['state']]if x!=k),key=lambda x:abs(math.log(pop[x]/p)),default=None);inc=E.get(k,{}).get('income');top=[]
 if inc:
  rows=inc['industryEarnings'];total=inc['earningsByPlaceOfWorkThousandDollars'];top=[{'sector':r['name'],'shareOfLocalEarningsPct':round(r['thousandDollars']/total*100,1)if total and total>0 else None}for r in sorted((r for r in rows if r['thousandDollars']is not None and r['thousandDollars']>0),key=lambda r:r['thousandDollars'],reverse=True)[:5]]
 x={'id':k,'place':w['title'],'name':c['name'],'state':c['state'],'population':{'value':p,'year':entry['population']['year'],'percentileAmongMappedCounties':pct(p,ps)},'economy':{'year':inc['year']if inc else None,'publishedEarningSectors':top,'otherSectorsSuppressed':any(r['thousandDollars']is None for r in inc['industryEarnings'])if inc else None,'localDescription':O.get(k,{}).get('description'),'sourceEvidence':O.get(k,{}).get('evidence',[])},'wiki':{'intro':w['intro'][:600],'geography':w['geography'][:950],'economy':w['economy'][:950]},'baselineNRIv119':baseline[k],'similarPopulationPeerSameState':{'id':peer,'place':W[peer]['title'],'population':pop[peer],'baseline':baseline[peer]}if peer else None,'futureAnalysisReviewOnly':{h:{key.replace(h+'_',''):value for key,value in ad.get(k,{}).items()if key.startswith(h+'_')and key.endswith('_HM')and ('MID_LOWER'in key or'LATE_HIGHER'in key)and ('L95'in key if h=='EXHT'else True)}for h in HS},'sources':entry['sources']+[{'title':'Wikipedia: '+w['title'],'url':'https://en.wikipedia.org/w/index.php?title='+w['title'].replace(' ','_')+'&oldid='+str(w['revisionId']),'revisionId':w['revisionId']}]}
 (P/'dossiers'/f'{k}.json').write_text(json.dumps(x,ensure_ascii=False,separators=(',',':')))
ids=sorted(D)
for i in range(8):
 a=ids[i::8];(P/f'assignment-{i}.json').write_text(json.dumps(a));print(i,len(a))
(P/'basis.json').write_text(json.dumps({'baselineFile':'public/atlas/counties.json','baselineSha256':hashlib.sha256((R/'public/atlas/counties.json').read_bytes()).hexdigest(),'comparisonUniverseMappedCounties':len(D),'riskScoreUniverse':'FEMA published national percentiles; do not confuse with computed annual-loss percentiles','riskSourceUrl':'https://github.com/fulton-ring/nri-future-risk/blob/ec09931b18cee40c651fcd1054fade6edc9d5cd7/public/NRI_Future_Risk_Master_Datasheet_12052024.xlsx','publicationRule':'Shared across versions and filters. All risk comparisons MUST explicitly say baseline, never assert fixed future rankings from a single scenario.'},indent=2))
print('Prepared',len(D),'fact dossiers; baseline equality verified across archive and analysis')
