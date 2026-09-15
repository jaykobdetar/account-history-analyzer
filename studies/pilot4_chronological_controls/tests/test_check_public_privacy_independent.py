"""Planted synthetic leaks verify the bounded publication checker."""
from pathlib import Path
import json
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from check_public_privacy_independent import review


class PrivacyCheck(unittest.TestCase):
    def fixture(self,root):
        public=root/'public';public.mkdir()
        prose=' '.join('fixtureword'+str(i) for i in range(25))
        pool=root/'pool';pool.write_text(json.dumps({'record':{
            'id':'private_record_123','thread_id':'private_thread_123',
            'parent_id':'private_parent_123','account_id':'private_account_123','text':prose}})+'\n')
        audit=root/'audit';audit.write_text(json.dumps({'record_provenance':{'n':{
            'account_key':'private_account_123','source_record_id':'private_record_123',
            'thread_id':'private_thread_123'}}}))
        flags=root/'flags';flags.write_text(json.dumps({'accounts':[{'account_key':'excluded_account_456'}]}))
        return public,pool,audit,flags,prose

    def test_positive_leaks_detected_without_excerpts_or_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            public,pool,audit,flags,prose=self.fixture(Path(tmp))
            (public/'leak.json').write_text(json.dumps({'author':'private_account_123','text':prose}))
            result=review(public,pool,audit,flags)
            self.assertEqual(result['status'],'potential_matches_require_review')
            self.assertTrue(result['identity_token_findings'])
            self.assertTrue(result['exact_json_identity_findings'])
            self.assertTrue(result['candidate_phrase_findings'])
            serialized=json.dumps(result)
            self.assertNotIn('private_account_123',serialized)
            self.assertNotIn('fixtureword',serialized)

    def test_hashes_and_aggregate_prose_allowed_cache_omitted(self):
        with tempfile.TemporaryDirectory() as tmp:
            public,pool,audit,flags,_=self.fixture(Path(tmp))
            (public/'report.json').write_text(json.dumps({'accounts':1,'source_sha256':'0'*64}))
            cache=public/'__pycache__';cache.mkdir()
            (cache/'sample.pyc').write_bytes(b'private_account_123')
            result=review(public,pool,audit,flags)
            self.assertEqual(result['status'],'no_matches')
            self.assertEqual(result['files_checked'],1)


if __name__=='__main__':unittest.main()
