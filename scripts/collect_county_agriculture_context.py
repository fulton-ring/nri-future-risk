#!/usr/bin/env python3
"""Extract USDA 2022 county farm/crop facts for editorial research.
Download the source XLSX to /tmp/fri-county-research/agriculture.xlsx first; reads only, no workbook modifications.
"""
import zipfile,xml.etree.ElementTree as X,json,pathlib,re
P=pathlib.Path('/tmp/fri-county-research');z=zipfile.ZipFile(P/'agriculture.xlsx');N={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'};S=[''.join(i.itertext())for i in X.fromstring(z.read('xl/sharedStrings.xml'))];NS='{'+N['m']+'}'
def rows(sh):
 with z.open(f'xl/worksheets/sheet{sh}.xml')as f:
  for _,e in X.iterparse(f,events=['end']):
   if e.tag==NS+'row':
    vals={}
    for c in e:
     v=c.find(NS+'v');t=v.text if v is not None else '';vals[re.sub(r'\d+','',c.get('r'))]=S[int(t)]if c.get('t')=='s'else t
    yield vals;e.clear()
lookup={}
for i,r in enumerate(rows(3)):
 if i and r.get('A'):lookup[r['A']]={'label':r.get('D'),'unit':r.get('E')}
selected={'y22_M001','y22_M050','y22_M107','y22_M112','y22_M115','y22_M120','y22_M126','y22_M133','y22_M140','y22_M156','y22_M158','y22_M160','y22_M162','y22_M164','y22_M170'}
expected={c['id']for c in json.load(open('public/atlas/counties.json'))['counties']};out={}
for sh in [4,6]:
 head=None
 for r in rows(sh):
  if head is None:
   head={col:value for col,value in r.items()if value.endswith('_valueNumeric') and value.removesuffix('_valueNumeric')in selected};continue
  k=r.get('B','')
  if k not in expected or k.startswith(('02','51','72')):continue
  v=out.setdefault(k,{})
  for col,var in head.items():
   t=r.get(col,'');code=var.removesuffix('_valueNumeric')
   if t and re.fullmatch(r'-?\d+(?:\.\d+)?',t):
    num=float(t)
    if num>0 and (code=='y22_M001' or num>=5):v[code]={**lookup[code],'value':num}
root=P/'agriculture';root.mkdir(exist_ok=True)
url='https://www.nass.usda.gov/sites/default/files/publications/agcensus/2022/Online_Resources/Ag_Census_Web_Maps/Data_download/NASSAgCensusDownload2022_175maps_Links.xlsx'
for k,stats in out.items():
 if stats:(root/f'{k}.json').write_text(json.dumps({'year':2022,'source':{'title':'USDA 2022 Census of Agriculture county statistics','url':url},'statistics':stats,'interpretation':'Preserve each metric denominator and 2022 date. Percent of harvested cropland is NOT percent of all county land. Suppressed/missing data omitted; do not assume zero. NASS mapping not used for Alaska/Virginia/PuertoRico to avoid combined-geography ambiguity.'},ensure_ascii=False))
print('USDA evidence prepared for',len(list(root.glob('*.json'))),'counties')
