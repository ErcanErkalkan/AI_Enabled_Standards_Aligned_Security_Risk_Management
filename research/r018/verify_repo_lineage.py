#!/usr/bin/env python3
"""R018 version-boundary check. Run from any cwd inside GitHub checkout.
Checks identity and reciprocity, not human-reviewed semantic soundness.
"""
import csv
from pathlib import Path
import hashlib
import json
import sys

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
ORIGINAL=REPO/'software/data/mapping_iso_csf_gqm.csv'
DERIVED=HERE/'data/IST_R016_COORDINATOR_RATIFIED_199_ROW_DERIVED_CROSSWALK_20261029.csv'
XMI=REPO/'software/data/uml_schema.xmi'
SUMMARY=HERE/'data/R018_PUBLIC_AGGREGATE.csv'
HASHES={
 'software_baseline':'3f614840f33cc4be3d3d457ea9deee277486538ee23e3f3e0a594624919bacba',
 'ratified_copy':'ab431119507295678e3bed3ca8d48269733409302a8def255737160d5a3002ef',
 'canonical_xmi':'d1da069ab8b5ed543f4118679d01fa9c78c50de8d67debdb3c8c6dd365e01fac'
}
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def rows(path):
 with path.open('r',encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def links(data):
 d={r['id']:r for r in data};arcs=set()
 for r in data:
  for t in r['linked_ids'].split(';'):
   t=t.strip()
   if t:arcs.add((r['id'],t))
 if any(t not in d or (t,s) not in arcs for s,t in arcs):raise ValueError('Dangling or asymmetric link')
 return arcs,{tuple(sorted(x)) for x in arcs}
def main():
 try:
  a,b=rows(ORIGINAL),rows(DERIVED)
  for name,path,h in [('baseline',ORIGINAL,HASHES['software_baseline']),('ratified',DERIVED,HASHES['ratified_copy']),('schema',XMI,HASHES['canonical_xmi'])]:
   if sha(path)!=h:raise ValueError(f'{name} source mismatch {sha(path)}')
  if len(a)!=199 or len(b)!=199 or {r['id'] for r in a}!={r['id'] for r in b}:raise ValueError('row identity mismatch')
  aa,pa=links(a);ab,pb=links(b)
  if (len(aa),len(pa),len(ab),len(pb))!=(422,211,424,212):raise ValueError('arc/pair counts mismatch')
  removed=pa-pb;added=pb-pa
  if removed!={('A.8.16','ID.RA-03')} or added!={('A.7.14','PR.PS-03'),('A.5.36','ID.IM-03')}:raise ValueError('pair changes mismatch')
  if b[0]['framework']!='ISO27001:2022':raise ValueError('unexpected format')
  rated=rows(SUMMARY)[0]
  if int(rated.get('rated_presentations',-1))!=60 or int(rated.get('empty_presentations',-1))!=0 or int(rated.get('tasks',-1))!=15 or int(rated.get('v1_overreach_Y',-1))!=29 or int(rated.get('v2_overreach_Y',-1))!=0:raise ValueError('R018 ratings aggregate mismatch')
  result={'status':'PASS','baseline_pairs':211,'ratified_pairs':212,'ratified_directed_edges':424,'xmi_schema_same':True,'r018_rated_presentations':60,'interpretation':'version consistency only; not full-population semantic validation'}
  print(json.dumps(result,indent=2));return 0
 except Exception as e:
  print(json.dumps({'status':'FAIL','reason':str(e)},indent=2));return 1
if __name__=='__main__':sys.exit(main())
