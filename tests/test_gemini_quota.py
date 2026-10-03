import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
import openai
from src.tools import gemini_quota as g


class QuotaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.now = 1791040000.0
        self.clock = patch.object(g.time, 'time', side_effect=lambda: self.now)
        self.sleeper = patch.object(g.time, 'sleep', side_effect=self.advance)
        self.clock.start(); self.sleeper.start()
        self.addCleanup(self.clock.stop); self.addCleanup(self.sleeper.stop)
        self.limits = {'m': {'rpm': 10, 'tpm': 250000, 'rpd': 1500}}
        self.q = g.GeminiQuota(Path(self.tmp.name) / 'quota.sqlite3', self.limits)

    def advance(self, seconds):
        self.now += seconds

    def error(self, body, status=429, headers=None):
        response = httpx.Response(status, headers=headers, request=httpx.Request('POST', 'https://example.test'))
        cls = openai.RateLimitError if status == 429 else openai.InternalServerError
        return cls('test', response=response, body=body)

    def client(self, effects):
        create = Mock(side_effect=effects)
        return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))), create

    def test_rpm_survives_restart(self):
        start = self.now
        self.q.reserve('m', 100)
        g.GeminiQuota(self.q.path, self.limits).reserve('m', 100)
        self.assertGreaterEqual(self.now - start, 6)

    def test_rolling_rpm(self):
        start = self.now
        for _ in range(11): self.q.reserve('m', 1)
        self.assertGreaterEqual(self.now - start, 60)

    def test_models_have_separate_budgets(self):
        self.limits['m']['rpd'] = 1
        self.limits['lite'] = {'rpm': 15, 'tpm': None, 'rpd': 1000}
        self.q.reserve('m', 1)
        self.q.reserve('lite', 1)

    def test_llm_integration_and_sdk_retry_disabled(self):
        from src.tools import llm
        reply = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{}'))],
                                usage=SimpleNamespace(prompt_tokens=10, completion_tokens=3))
        client, create = self.client([reply])
        profile = {'provider': 'openai', 'base_url': 'https://example.test', 'api_key_env': 'GEMINI_API_KEY'}
        with patch.object(llm, '_quota', self.q), patch.object(llm, '_get_client', return_value=client):
            text, usage = llm.chat('system', 'user', 'm', max_tokens=123, profile=profile)
        self.assertEqual((text, usage.input_tokens, usage.output_tokens), ('{}', 10, 3))
        self.assertEqual(create.call_args.kwargs['max_tokens'], 123)
        with patch.object(llm, '_clients', {}), \
             patch.object(llm, 'secret', return_value=None), \
             patch.object(openai, 'OpenAI') as constructor:
            llm._get_client(profile)
            self.assertEqual(constructor.call_args.kwargs['max_retries'], 0)

    def test_tpm_waits_for_window(self):
        self.q.reserve('m', 200000)
        start = self.now
        self.q.reserve('m', 100000)
        self.assertGreaterEqual(self.now - start, 60)

    def test_large_input_fails_before_request(self):
        with self.assertRaises(ValueError): self.q.reserve('m', 250001)

    def test_daily_persistent_and_resets(self):
        self.limits['m']['rpd'] = 1
        self.q.reserve('m', 100)
        with self.assertRaises(g.QuotaExhausted):
            g.GeminiQuota(self.q.path, self.limits).reserve('m', 100)
        self.now += 86400
        self.q.reserve('m', 100)

    def test_pacific_dst(self):
        for stamp in ['2026-01-02T07:59:00+00:00', '2026-07-02T06:59:00+00:00']:
            self.assertTrue(self.q.day(datetime.fromisoformat(stamp).timestamp()).endswith('-01'))

    def test_unknown_model_and_bad_limits(self):
        with self.assertRaises(ValueError): self.q.reserve('other', 1)
        self.limits['m']['rpm'] = 0
        with self.assertRaises(ValueError): self.q.reserve('m', 1)

    def test_lite_pacing(self):
        self.limits['m'] = {'rpm': 15, 'tpm': None, 'rpd': 1000}
        start = self.now
        self.q.reserve('m', 300000); self.q.reserve('m', 300000)
        self.assertGreaterEqual(self.now - start, 4)

    def test_every_retry_reserved_and_output_cap(self):
        client, create = self.client([self.error({}, headers={'retry-after': '8'}), 'ok'])
        start = self.now
        self.assertEqual(g.call(client, 'm', 'system', 'user', {'max_tokens': 123}, self.q, 2), 'ok')
        self.assertGreaterEqual(self.now - start, 9)
        self.assertEqual(create.call_args.kwargs['max_tokens'], 123)
        self.limits['m']['rpd'] = 2
        with self.assertRaises(g.QuotaExhausted): self.q.reserve('m', 1)

    def test_provider_daily_stops_and_blocks_restart(self):
        client, create = self.client([self.error({'quotaId': 'GenerateRequestsPerDayPerProjectPerModel-FreeTier'})])
        with self.assertRaises(g.QuotaExhausted): g.call(client, 'm', '', '', {}, self.q, 6)
        self.assertEqual(create.call_count, 1)
        with self.assertRaises(g.QuotaExhausted): self.q.reserve('m', 1)

    def test_retry_exhaustion_is_terminal(self):
        client, create = self.client([self.error({}), self.error({})])
        with self.assertRaises(g.GeminiRequestStopped): g.call(client, 'm', '', '', {}, self.q, 1)
        self.assertEqual(create.call_count, 2)

    def test_5xx_retries(self):
        client, create = self.client([self.error({}, status=503), 'ok'])
        self.assertEqual(g.call(client, 'm', '', '', {}, self.q, 1), 'ok')

    def test_retry_hints(self):
        self.assertEqual(g.retry_delay(self.error({'retryDelay': '12.5s'}), 0), 13.5)
        self.assertEqual(g.retry_delay(self.error({}), 3), 8)

    def test_400_not_retried(self):
        error = openai.BadRequestError('test', response=httpx.Response(400, request=httpx.Request('POST', 'https://example.test')), body={})
        client, create = self.client([error])
        with self.assertRaises(openai.BadRequestError): g.call(client, 'm', '', '', {}, self.q, 6)
        self.assertEqual(create.call_count, 1)


if __name__ == '__main__': unittest.main()
