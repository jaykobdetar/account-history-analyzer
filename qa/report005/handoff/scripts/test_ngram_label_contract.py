"""Known remaining presentation regression; expected to FAIL in unmodified 1.0.2.

AHAS_SOURCE_ROOT must point at the extracted project. This runs the full renderer
on the bundled style fixture; it does not test a proposed replacement helper.
"""
import os
from probe_ngram_labels import load_and_render

def test_distinct_four_character_features_have_distinct_display_labels():
 _,tables,_=load_and_render(os.environ['AHAS_SOURCE_ROOT'])
 table=next(t for t in tables if t['context'].startswith('cosine_distance_v1, retained_prose, n=4:'))
 labels=[row[0] for row in table['rows']]
 assert len(set(labels))==len(labels), f'Distinct exported feature strings collapsed in HTML: {labels!r}'
