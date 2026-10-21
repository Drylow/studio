"""Meter contracts; no network or media processing."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('meter', Path(__file__).with_name('image_quota.py'))
meter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(meter)


class QuotaTests(unittest.TestCase):
    def test_refusals_are_distinct_and_retry_is_preserved(self):
        a = meter.refusal(429, {'error': 'PUBLIC_ERROR_PER_MODEL_DAILY_QUOTA_REACHED'}, {'Retry-After': '60'}, 100)
        self.assertEqual((a['kind'], a['retry_at']), ('daily_model_quota', 160))
        self.assertEqual(meter.refusal(429, 'PUBLIC_ERROR_USER_REQUESTS_THROTTLED')['kind'], 'temporary_throttle')
        self.assertEqual(meter.refusal(429, 'PUBLIC_ERROR_UNUSUAL_ACTIVITY_TOO_MUCH_TRAFFIC')['kind'], 'captcha_quality')
        self.assertEqual(meter.refusal(429, {'error': 'unknown'})['kind'], 'unclassified')

    def test_counts_images_separately_and_reconciles_without_double_counting(self):
        base = dict(at=100, account='a', model='selected', endpoint='image')
        events = [dict(base, id='one', status=None), dict(base, id='one', status=200, images=2),
                  dict(base, id='two', status=429, kind='daily_model_quota'),
                  dict(base, id='upload', endpoint='upload', status=429, kind='temporary_throttle', images=99),
                  dict(base, id='unknown', status=None)]
        row = meter.report(events)['buckets'][0]
        self.assertEqual((row['generation_requests'], row['generated_images'], row['upload_requests']), (3, 2, 1))
        self.assertEqual((row['failed_requests'], row['unresolved_requests']), (1, 1))
        self.assertEqual(row['refusals'], {'daily_model_quota': 1})
        self.assertEqual(row['upload_refusals'], {'temporary_throttle': 1})

    def test_daily_model_and_account_buckets_do_not_mix(self):
        base = dict(endpoint='image', status=200, images=1)
        events = [dict(base, id='a', at=86399, account='x', model='a'),
                  dict(base, id='b', at=86400, account='x', model='a'),
                  dict(base, id='c', at=86400, account='x', model='b'),
                  dict(base, id='d', at=86400, account='y', model='a')]
        self.assertEqual(len(meter.report(events)['buckets']), 4)


if __name__ == '__main__':
    unittest.main()
