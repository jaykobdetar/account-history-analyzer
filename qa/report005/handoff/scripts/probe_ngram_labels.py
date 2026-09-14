from pathlib import Path
from html.parser import HTMLParser
import sys,json,os
from account_history_analyzer.artifact_io import load_artifact_json,iter_artifact_jsonl
from account_history_analyzer.reporting import render_html

class Tables(HTMLParser):
 def __init__(self):
  super().__init__(convert_charrefs=True);self.tables=[];self.paragraph=None;self.last_p='';self.summary=None;self.last_summary='';self.row=None;self.cell=None;self.table=None
 def handle_starttag(self,tag,attrs):
  if tag=='p':self.paragraph=[]
  if tag=='summary':self.summary=[]
  if tag=='table':self.table={'context':self.last_p,'summary':self.last_summary,'rows':[]}
  if tag=='tr':self.row=[]
  if tag=='td':self.cell=[]
 def handle_data(self,data):
  if self.paragraph is not None:self.paragraph.append(data)
  if self.summary is not None:self.summary.append(data)
  if self.cell is not None:self.cell.append(data)
 def handle_endtag(self,tag):
  if tag=='p' and self.paragraph is not None:self.last_p=''.join(self.paragraph);self.paragraph=None
  if tag=='summary' and self.summary is not None:self.last_summary=''.join(self.summary);self.summary=None
  if tag=='td' and self.cell is not None:
   if self.row is not None:self.row.append(''.join(self.cell))
   self.cell=None
  if tag=='tr' and self.row is not None:
   if self.table is not None and self.row:self.table['rows'].append(self.row)
   self.row=None
  if tag=='table' and self.table is not None:self.tables.append(self.table);self.table=None

def load_and_render(root):
 p=Path(root)/'output/audit-repair/constructed_style_shift'
 r=load_artifact_json(p/'results.json');e=list(iter_artifact_jsonl(p/'evidence.jsonl'));w=list(iter_artifact_jsonl(p/'windows.jsonl'))
 generated=render_html(r,e,windows=w);parser=Tables();parser.feed(generated)
 return r,parser.tables,generated==(p/'report.html').read_text()

def probe(root):
 r,tables,equal=load_and_render(root)
 comps=r['modules']['style']['payload']['comparisons']
 count=bad=0
 for c in comps:
  for d in c['distances']:
   if d['method_id']=='cosine_distance_v1':
    for item in d['contributions']:
     count+=1;bad+=len(item['feature_id'])!=d['n']
 samples=[]
 for n in (3,4,5):
  table=next(t for t in tables if t['context'].startswith(f'cosine_distance_v1, retained_prose, n={n}:'))
  # The first displayed comparison is the candidate-adjacent comparison, as in
  # the production preview rule. Match its first feature rates to its stored data.
  c=next(c for c in comps if c['comparison_id']=='cmp-468edd07663f8b6816713521')
  d=next(d for d in c['distances'] if d['method_id']=='cosine_distance_v1' and d['view']=='retained_prose' and d['n']==n)
  samples.append({'n':n,'rows':[{'stored_feature':i['feature_id'],'stored_codepoints':len(i['feature_id']),'displayed_feature':row[0]} for i,row in zip(d['contributions'][:10],table['rows'],strict=True)],'distinct_displayed_labels':len(set(row[0] for row in table['rows']))})
 return {'scope':'Actual rendering and supplied JSON inspected; calculations not rerun here.','regenerated_html_matches_supplied':equal,'checked_exported_ngram_coordinates':count,'wrong_length_in_json':bad,'examples':samples,'source_location':'reporting.py:304 passes md_text(feature_id) to _table; Markdown table parser trims structural whitespace.'}

if __name__=='__main__':
 result=probe(sys.argv[1]);Path(sys.argv[2]).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False,indent=2))
