"""Pinned pre-repair link-label probe; intentionally reads the installed1.0.1."""
import importlib.metadata
import json
from pathlib import Path
import sys
import account_history_analyzer
from account_history_analyzer.config import AnalysisConfig
from account_history_analyzer.io import thaw
from account_history_analyzer.text import preprocess

assert Path(account_history_analyzer.__file__).is_relative_to('/tmp/ahas-pr383-install/lib/python3.12/site-packages')
assert account_history_analyzer.__version__ == '1.0.1'
config=AnalysisConfig.from_mapping()
rows=[]
for name,source in [
 ('mixed_same_host','[Read https://example.org for details](https://example.org)'),
 ('mixed_different_host','[Read https://label.test for details](https://destination.test)'),
 ('formatted_label','[**Read** https://example.org for _details_](https://example.org)'),
 ('code_label','[Read `https://label.test` for details](https://destination.test)'),
 ('quote_label','> [Read https://example.org for details](https://example.org)'),
 ('independent_links','[One https://example.org label](https://example.org) [Two https://example.org labels](https://example.org)'),
]:
 record={'id':'r','kind':'comment','status':'present','text':source,'language':'en','created_utc':None,
         'subreddit':None,'edit_state':'unknown','title':None}
 result=preprocess(record,{'text_format':'markdown','default_language':'en'},config)
 rows.append({'name':name,'source':source,'segments':thaw(result['segments']),
              'links':thaw(result['links']),'structure':thaw(result['structure'])})
print(json.dumps({'package_version':account_history_analyzer.__version__,'module_file':account_history_analyzer.__file__,
 'python':sys.version,'markdown_it_py':importlib.metadata.version('markdown-it-py'),'cases':rows},sort_keys=True,indent=2))
