"""Small append-only image usage ledger; observation is not a published quota."""
from collections import defaultdict
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
import json
import os
from pathlib import Path
import re


def account_key(value):
    return hashlib.sha256(value.lower().encode()).hexdigest()[:12]


def refusal(status, body, headers=None, now=None):
    """Extract only known error codes and retry time, never credentials/body text."""
    now = now if now is not None else datetime.now(timezone.utc).timestamp()
    text = json.dumps(body) if isinstance(body, (dict, list)) else str(body)
    codes = re.findall(r'(?:PUBLIC_ERROR_)?(?:PER_MODEL_DAILY_QUOTA_REACHED|USER_QUOTA_REACHED|USER_REQUESTS_THROTTLED|UNUSUAL_ACTIVITY_TOO_MUCH_TRAFFIC|MODEL_ACCESS_DENIED)|ZERO_BALANCE|no_eligible_account', text)
    reason = codes[0].removeprefix('PUBLIC_ERROR_') if codes else 'HTTP_' + str(status)
    kind = {'PER_MODEL_DAILY_QUOTA_REACHED': 'daily_model_quota',
            'USER_QUOTA_REACHED': 'account_quota',
            'USER_REQUESTS_THROTTLED': 'temporary_throttle',
            'UNUSUAL_ACTIVITY_TOO_MUCH_TRAFFIC': 'captcha_quality',
            'MODEL_ACCESS_DENIED': 'model_access',
            'ZERO_BALANCE': 'captcha_balance',
            'no_eligible_account': 'no_eligible_account'}.get(reason, 'unclassified')
    retry = None
    value = next((v for k, v in (headers or {}).items() if k.lower() == 'retry-after'), None)
    if value is not None:
        try:
            retry = now + max(0, int(value))
        except (ValueError, TypeError):
            try:
                retry = parsedate_to_datetime(value).timestamp()
            except (ValueError, TypeError, OverflowError):
                pass
    if retry is None and isinstance(body, dict) and body.get('retryAfter'):
        try:
            retry = datetime.fromisoformat(body['retryAfter'].replace('Z', '+00:00')).timestamp()
        except (ValueError, TypeError):
            pass
    return {'reason': reason, 'kind': kind, 'retry_at': retry}


def append(path, event):
    """One small append per event; the caller provides a stable unique event id."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(event, separators=(',', ':')) + '\n').encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        if os.name == 'posix':
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX)
        assert os.write(fd, raw) == len(raw)
        os.fsync(fd)
    finally:
        os.close(fd)


def report(events):
    """Per-account, per-model UTC buckets, with uploads separate from generations."""
    groups = defaultdict(lambda: {'generation_requests': 0, 'successful_requests': 0,
                                  'generated_images': 0, 'failed_requests': 0,
                                  'upload_requests': 0, 'unresolved_requests': 0,
                                  'upload_refusals': defaultdict(int),
                                  'refusals': defaultdict(int), 'first_event': None,
                                  'last_event': None, 'last_retry_at': None})
    by_id = {}
    for event in events:
        # Reconciliation replaces the earlier unresolved event with the same id.
        by_id[event['id']] = event
    for event in by_id.values():
        day = datetime.fromtimestamp(event['at'], timezone.utc).date().isoformat()
        key = (event.get('account', 'unassigned'), event.get('model', 'unknown'), day)
        row = groups[key]
        row['first_event'] = min(row['first_event'] or event['at'], event['at'])
        row['last_event'] = max(row['last_event'] or event['at'], event['at'])
        if event.get('retry_at'):
            row['last_retry_at'] = event['retry_at']
        if event['endpoint'] == 'upload':
            row['upload_requests'] += 1
            if event.get('status') is not None and event['status'] >= 400:
                row['upload_refusals'][event.get('kind', 'unclassified')] += 1
            continue
        if event['endpoint'] != 'image':
            continue
        row['generation_requests'] += 1
        if event.get('status') is None:
            row['unresolved_requests'] += 1
        elif 200 <= event['status'] < 300:
            row['successful_requests'] += 1
            row['generated_images'] += event.get('images', 0)
        else:
            row['failed_requests'] += 1
            row['refusals'][event.get('kind', 'unclassified')] += 1
    return {'interpretation': 'observed_lower_bound_not_published_quota',
            'buckets': [dict(account=a, model=m, day_utc=d, **dict(v, refusals=dict(v['refusals']), upload_refusals=dict(v['upload_refusals'])))
                        for (a, m, d), v in sorted(groups.items())]}
