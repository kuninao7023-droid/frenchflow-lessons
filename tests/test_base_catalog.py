"""Regression against the actual public seed, not synthesized model output."""
import json
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import generate_monthly as g

class ActualBaseCatalogTests(unittest.TestCase):
    def test_actual_420_seed_is_accepted_without_regrading_legacy_texts(self):
        seed=json.loads((ROOT/'catalog/catalog.json').read_text(encoding='utf-8'))['lessons']
        self.assertEqual(420,len(seed))
        history,entries=g.inventory(ROOT)
        self.assertEqual(seed,history[:420])
        self.assertEqual({x['level'] for x in seed},set(g.LEVELS))

if __name__=='__main__':unittest.main(verbosity=2)
