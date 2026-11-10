"""Local synthetic fixtures only: these tests never call the paid API."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / 'tools' / 'generate_monthly.py'
if MODULE.exists():
    spec = importlib.util.spec_from_file_location('monthly', MODULE)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
else:
    m = None


def lesson(level='A1', number=1, month='2026-12'):
    return dict(id=f'monthly-{month}-{level.lower()}-{number:03}', category='fiction', level=level,
                french=f'Exemple original {level} {number}. ' + 'Une réflexion imaginaire sur nos habitudes quotidiennes. ' * 15,
                japanese=f'架空の練習文 {level} {number}。日常の習慣について考えます。',
                vocabulary='habitude : 習慣 ; réflexion : 考察', grammar='名詞と形容詞の一致を確認します。')


class MonthlyTests(unittest.TestCase):
    def test_schema_levels_strings_and_advanced_lengths(self):
        self.assertTrue(callable(getattr(m, 'validate_lessons', None)), 'lesson validator missing')
        m.validate_lessons([lesson()])
        for field, value in [('level','D1'), ('grammar',' '), ('japanese',[]), ('extra','bad'), ('vocabulary','x'*10001)]:
            row = lesson(); row[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                m.validate_lessons([row])
        row = lesson('C2'); row['french'] = 'Trop court.'
        with self.assertRaises(ValueError):
            m.validate_lessons([row])

    def test_duplicate_ids_and_french_against_history(self):
        self.assertTrue(callable(getattr(m, 'reject_history', None)), 'history duplicate guard missing')
        for old in [lesson(), dict(lesson(), id='old-base-id')]:
            with self.assertRaises(ValueError):
                m.reject_history([lesson()], [old])
        m.reject_history([lesson(number=2)], [lesson()])
        with self.assertRaises(ValueError):
            m.validate_lessons([lesson(), lesson()])
    def test_responses_parser_rejects_incomplete_refusal_and_bad_json(self):
        self.assertTrue(callable(getattr(m, 'parse_response', None)), 'Responses parser missing')
        good = {'status':'completed', 'output':[{'type':'message', 'content':[{'type':'output_text','text':json.dumps({'lessons':[lesson()]})}]}]}
        self.assertEqual(m.parse_response(good), [lesson()])
        for bad in [dict(good, status='incomplete'), dict(good, output=[]),
                    dict(good, output=[{'type':'message','content':[{'type':'refusal','refusal':'no'}]}]),
                    dict(good, output=[{'type':'message','content':[{'type':'output_text','text':'not JSON'}]}])]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                m.parse_response(bad)

    def test_budget_preflight_and_bounded_level_requests_local_fake(self):
        self.assertTrue(callable(getattr(m, 'generate_level', None)), 'bounded generator missing')
        env = dict(OPENAI_API_KEY='LOCAL-FAKE-NOT-A-KEY', OPENAI_MODEL='local-fixture-model',
                   MONTHLY_BUDGET_USD='10', INPUT_PRICE_USD_PER_M='1', OUTPUT_PRICE_USD_PER_M='1')
        calls = []
        def fake_http(payload, key, timeout):
            calls.append(payload)
            return {'status':'completed', 'usage':{'input_tokens':100, 'output_tokens':200},
                    'output':[{'type':'message','content':[{'type':'output_text', 'text':json.dumps({'lessons':[lesson(number=n) for n in range(1,11)]})}]}]}
        for missing in env:
            bad = dict(env); del bad[missing]
            with self.subTest(missing=missing), self.assertRaises(ValueError):
                m.generate_level('2026-12', 'A1', [], m.Budget(bad), fake_http)
        for value in ['0', '-1', 'NaN', 'Infinity']:
            with self.assertRaises(ValueError):
                m.Budget(dict(env, MONTHLY_BUDGET_USD=value))
        self.assertEqual(calls, [])
        rows = m.generate_level('2026-12','A1',[lesson(number=99)],m.Budget(env),fake_http)
        self.assertEqual(len(rows),10)
        request = calls[0]
        self.assertIn(lesson(number=99)['french'],request['input'])
        self.assertFalse(request['store'])
        self.assertEqual({'effort':'low'},request.get('reasoning'))
        self.assertEqual(request['max_output_tokens'],9000)
        self.assertTrue(request['text']['format']['strict'])
        self.assertEqual(request['text']['format']['type'],'json_schema')
        tiny = dict(env, MONTHLY_BUDGET_USD='0.00000001')
        with self.assertRaises(ValueError):
            m.generate_level('2026-12','A1',[],m.Budget(tiny),fake_http)
        self.assertEqual(len(calls),1)
        def bad_http(*args):
            calls.append(None)
            return {'status':'incomplete'}
        with self.assertRaises(ValueError):
            m.generate_level('2026-12','A1',[],m.Budget(env),bad_http)
        self.assertEqual(len(calls),3)

    def test_month_publication_atomic_sha_and_idempotency_local_fake(self):
        self.assertTrue(callable(getattr(m, 'run', None)), 'month publisher missing')
        env = dict(OPENAI_API_KEY='LOCAL-FAKE-NOT-A-KEY', OPENAI_MODEL='local-fixture-model',
                   MONTHLY_BUDGET_USD='10', INPUT_PRICE_USD_PER_M='1', OUTPUT_PRICE_USD_PER_M='1')
        calls = []
        def fake_http(payload, key, timeout):
            level = m.LEVELS[len(calls)]; calls.append(payload)
            return {'status':'completed','usage':{'input_tokens':10,'output_tokens':20},
                    'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps({'lessons':[lesson(level,n) for n in range(1,11)]})}]}]}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root/'catalog').mkdir()
            (root/'catalog/catalog.json').write_text(json.dumps({'schema':1,'lessons':[dict(lesson(number=99),id='base-99')]}),encoding='utf-8')
            result = m.run(root,'2026-12',env,fake_http)
            self.assertEqual(result['status'],'published')
            self.assertEqual(len(calls),6)
            pack_path = root/'packs/2026-12.json'; before = pack_path.read_bytes()
            pack = json.loads(before)
            self.assertEqual(len(pack['lessons']),60)
            self.assertEqual(pack['lessons'][0]['id'],'monthly-2026-12-a1-001')
            import hashlib
            feed = json.loads((root/'feed.json').read_bytes())
            self.assertEqual(feed, {'schema':1,'packs':[{'id':'2026-12','month':'2026-12','url':'packs/2026-12.json','sha256':hashlib.sha256(before).hexdigest(),'count':60}]})
            self.assertEqual(m.run(root,'2026-12',{},fake_http)['status'],'skipped')
            self.assertEqual(len(calls),6)
            self.assertEqual(pack_path.read_bytes(),before)
            self.assertEqual(list(root.rglob('*.tmp')),[])
            # Failed atomic feed replacement leaves old valid feed and no partial JSON.
            feed_before = (root/'feed.json').read_bytes()
            with patch.object(m.os,'replace',side_effect=OSError('local injected failure')):
                with self.assertRaises(OSError):
                    m.atomic_json(root/'feed.json',{'broken':True})
            self.assertEqual((root/'feed.json').read_bytes(),feed_before)
            self.assertEqual(list(root.rglob('*.tmp')),[])

    def test_failed_generation_never_creates_public_files(self):
        env = dict(OPENAI_API_KEY='LOCAL-FAKE-NOT-A-KEY', OPENAI_MODEL='local-fixture-model',
                   MONTHLY_BUDGET_USD='10', INPUT_PRICE_USD_PER_M='1', OUTPUT_PRICE_USD_PER_M='1')
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); (root/'catalog').mkdir()
            (root/'catalog/catalog.json').write_text(json.dumps({'schema':1,'lessons':[dict(lesson(number=99),id='base-99')]}),encoding='utf-8')
            for response in [{'status':'incomplete'}, {'status':'completed','output':[]}]:
                calls=[]
                def fake(*args):
                    calls.append(1); return response
                with self.assertRaises(ValueError):
                    m.run(root,'2026-12',env,fake)
                self.assertEqual(len(calls),2)
                self.assertFalse((root/'feed.json').exists())
                self.assertFalse((root/'packs/2026-12.json').exists())
            for month in ['2026-00','2026-13','../x','2026-1','0000-01']:
                with self.assertRaises(ValueError):
                    m.run(root,month,env,fake)

    def test_empty_catalog_is_rejected_before_transport(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); (root/'catalog').mkdir()
            (root/'catalog/catalog.json').write_text('{"schema":1,"lessons":[]}',encoding='utf-8')
            def fake(*args):
                self.fail('network must not be reached')
            with self.assertRaises(ValueError):
                m.run(root,'2026-12',{},fake)

    def test_published_pack_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); (root/'catalog').mkdir(); (root/'packs').mkdir()
            (root/'catalog/catalog.json').write_text(json.dumps({'schema':1,'lessons':[dict(lesson(number=99),id='base-99')]}),encoding='utf-8')
            pack={'schema':1,'month':'2026-12','lessons':[lesson(level,n) for level in m.LEVELS for n in range(1,11)]}
            m.atomic_json(root/'packs/2026-12.json',pack)
            _, entries=m.inventory(root)
            m.atomic_json(root/'feed.json',{'schema':1,'packs':entries})
            pack['lessons'][0]['grammar']='改変された説明'
            m.atomic_json(root/'packs/2026-12.json',pack)
            with self.assertRaises(ValueError):
                m.run(root,'2026-12',{})

    def test_twelve_call_cap_and_usage_are_retained(self):
        env = dict(OPENAI_API_KEY='LOCAL-FAKE-NOT-A-KEY', OPENAI_MODEL='local-fixture-model',
                   MONTHLY_BUDGET_USD='10', INPUT_PRICE_USD_PER_M='1', OUTPUT_PRICE_USD_PER_M='1')
        budget=m.Budget(env)
        for _ in range(12):
            budget.reserve({'input':'local synthetic test'})
        with self.assertRaises(ValueError):
            budget.reserve({'input':'local synthetic test'})
        self.assertEqual(budget.calls,12)

    def test_generator_cli_no_configuration_fails_without_network(self):
        self.assertTrue(callable(getattr(m, 'main', None)))
        with patch.dict(os.environ,{},clear=True), patch('sys.argv',['generate_monthly.py','--month','2026-12']):
            with patch.object(m,'run',side_effect=ValueError('LOCAL TEST ERROR')), patch('sys.stderr'):
                self.assertEqual(m.main(),1)

    def test_missing_usage_is_not_silently_treated_as_verified(self):
        self.assertTrue(callable(getattr(m, 'validated_usage', None)), 'usage validation missing')
        self.assertEqual(m.validated_usage({'input_tokens':3,'output_tokens':4}),{'input_tokens':3,'output_tokens':4})
        for bad in [{}, {'input_tokens':-1,'output_tokens':1}, {'input_tokens':True,'output_tokens':1}]:
            with self.assertRaises(ValueError):
                m.validated_usage(bad)

    def test_real_http_adapter_with_local_monkeypatch_only(self):
        import io
        fixture={'status':'completed','usage':{'input_tokens':1,'output_tokens':2},'output':[]}
        with patch.object(m,'urlopen',return_value=io.BytesIO(json.dumps(fixture).encode())) as local_urlopen:
            self.assertEqual(m.http_response({'store':False},'LOCAL-FAKE-NOT-A-KEY',17),fixture)
        request=local_urlopen.call_args.args[0]
        self.assertEqual(request.full_url,'https://api.openai.com/v1/responses')
        self.assertEqual(request.get_method(),'POST')
        self.assertEqual(request.get_header('Authorization'),'Bearer LOCAL-FAKE-NOT-A-KEY')
        self.assertEqual(local_urlopen.call_args.kwargs['timeout'],17)
        self.assertFalse(json.loads(request.data)['store'])

    def test_run_missing_config_and_zero_budget_never_calls_transport(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); (root/'catalog').mkdir()
            (root/'catalog/catalog.json').write_text(json.dumps({'schema':1,'lessons':[dict(lesson(number=99),id='base-99')]}),encoding='utf-8')
            def forbidden(*args):
                self.fail('No paid request may occur')
            for env in [{}, dict(OPENAI_API_KEY='LOCAL-FAKE',OPENAI_MODEL='local-fixture',MONTHLY_BUDGET_USD='0',INPUT_PRICE_USD_PER_M='1',OUTPUT_PRICE_USD_PER_M='1')]:
                with self.assertRaises(ValueError):
                    m.run(root,'2026-12',env,forbidden)
            self.assertFalse((root/'packs').exists())
            self.assertFalse((root/'feed.json').exists())

    def test_base_duplicate_blocks_month_before_any_public_write(self):
        env=dict(OPENAI_API_KEY='LOCAL-FAKE',OPENAI_MODEL='local-fixture',MONTHLY_BUDGET_USD='10',INPUT_PRICE_USD_PER_M='1',OUTPUT_PRICE_USD_PER_M='1')
        calls=[]
        def duplicate_fixture(*args):
            calls.append(1)
            return {'status':'completed','usage':{'input_tokens':1,'output_tokens':1},'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps({'lessons':[lesson(number=n) for n in range(1,11)]})}]}]}
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); (root/'catalog').mkdir()
            (root/'catalog/catalog.json').write_text(json.dumps({'schema':1,'lessons':[dict(lesson(),id='base-1')]}),encoding='utf-8')
            with self.assertRaises(ValueError):
                m.run(root,'2026-12',env,duplicate_fixture)
            self.assertEqual(len(calls),2)
            self.assertFalse((root/'packs').exists())
            self.assertFalse((root/'feed.json').exists())

    def test_complete_orphan_pack_recovers_feed_without_credentials(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); (root/'catalog').mkdir()
            (root/'catalog/catalog.json').write_text(json.dumps({'schema':1,'lessons':[dict(lesson(number=99),id='base-99')]}),encoding='utf-8')
            pack={'schema':1,'month':'2026-12','lessons':[lesson(level,n) for level in m.LEVELS for n in range(1,11)]}
            m.atomic_json(root/'packs/2026-12.json',pack)
            result=m.run(root,'2026-12',{},lambda *args:self.fail('orphan must not be regenerated'))
            self.assertEqual(result['status'],'skipped')
            self.assertEqual(len(json.loads((root/'feed.json').read_bytes())['packs']),1)


if __name__ == '__main__':
    unittest.main()
