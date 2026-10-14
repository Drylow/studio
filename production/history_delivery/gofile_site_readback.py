#!/usr/bin/env python3
"""Observe GoFile's unmodified website with a copied authenticated profile.

No account creation, upload, or other HTTP mutation is permitted. Authentication
comes only from the existing browser profile; this helper never reads or replays
the owner token or creates website authorization headers. The optional expected
files JSON is an array containing the seven exact public delivery filenames.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import urlsplit



SHARE_PAGE = re.compile(r'https://gofile\.io/d/[A-Za-z0-9]+')
FOLDER_ID = re.compile(r'[A-Za-z0-9-]+')
READ_METHODS = frozenset(('GET', 'HEAD', 'OPTIONS'))


def save(path, value, private=False):
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + '.', dir=path.parent)
    try:
        os.fchmod(descriptor, 0o600 if private else 0o644)
        with os.fdopen(descriptor, 'w') as stream:
            json.dump(value, stream, indent=2)
            stream.write('\n')
        Path(temporary).replace(path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def official_api(parts):
    try:
        return (parts.scheme == 'https' and parts.hostname == 'api.gofile.io'
                and parts.port in (None, 443) and parts.username is None
                and parts.password is None)
    except ValueError:
        return False


def make_guard(blocked_mutations, blocked_authorization_requests):
    """Inspect header names without logging or persisting any header values."""
    def guard(route):
        request = route.request
        parts = urlsplit(request.url)
        safe_event = {'method': request.method, 'host': parts.hostname,
                      'path': parts.path}
        if request.method not in READ_METHODS:
            blocked_mutations.append(safe_event)
            route.abort()
            return
        try:
            authorization_present = any(
                name.lower() == 'authorization' for name in request.all_headers())
            allowed_authorization_host = official_api(parts)
        except Exception:
            blocked_authorization_requests.append({**safe_event, 'reason': 'headers-or-url-unavailable'})
            route.abort()
            return
        if authorization_present and not allowed_authorization_host:
            blocked_authorization_requests.append({**safe_event, 'reason': 'authorization-host-blocked'})
            route.abort()
            return
        route.continue_()
    return guard


def load_expected_names(path):
    if path is None:
        return None
    names = json.loads(path.read_text())
    if (not isinstance(names, list) or len(names) != 7
            or not all(isinstance(name, str) and name and name == Path(name).name
                       and '\n' not in name and '\r' not in name for name in names)
            or len(set(names)) != 7):
        raise ValueError('Expected files JSON must contain seven unique exact filenames')
    return names


def observed_listing(response, expected_folder):
    parts = urlsplit(response.url)
    if (not official_api(parts) or response.request.method != 'GET'
            or response.status != 200):
        return None
    # The normal website requests the public share code, while upload responses
    # identify the canonical folder UUID. Bind the response's actual folder id
    # below rather than rejecting this legitimate share-code alias in the URL.
    if not re.fullmatch(r'/contents/[A-Za-z0-9-]+', parts.path):
        return None
    try:
        body = response.json()
    except Exception:
        return None
    if not isinstance(body, dict) or body.get('status') != 'ok':
        return None
    data = body.get('data')
    if (not isinstance(data, dict) or data.get('type') != 'folder'
            or (expected_folder and data.get('id') != expected_folder)):
        return None
    children = data.get('children')
    if not isinstance(children, dict):
        return None
    metadata = body.get('metadata')
    if not isinstance(metadata, dict):
        metadata = {}
    return {'http_status': response.status, 'api_status': body['status'],
            'folder_id': data.get('id'), 'folder_type': data['type'],
            'folder_public': data.get('public'),
            'metadata': {key: metadata.get(key) for key in
                         ('totalCount', 'totalPages', 'page', 'pageSize', 'hasNextPage')},
            'files': [{key: entry.get(key) for key in ('id', 'type', 'name', 'size', 'md5')}
                      for entry in children.values() if isinstance(entry, dict)]}


def complete_for_names(listing, names):
    if not listing or listing.get('folder_public') is not True:
        return False
    if names is None:
        return True
    files = listing.get('files', [])
    metadata = listing.get('metadata', {})
    return (len(files) == len(names)
            and all(entry.get('type') == 'file' for entry in files)
            and all(isinstance(entry.get('name'), str) for entry in files)
            and sorted(entry.get('name', '') for entry in files) == sorted(names)
            and metadata.get('totalCount') == len(names)
            and metadata.get('totalPages') == 1 and metadata.get('page') == 1
            and isinstance(metadata.get('pageSize'), int)
            and metadata['pageSize'] >= len(names)
            and metadata.get('hasNextPage') is False)


def painted_names(page, names):
    if names is None:
        return []
    painted = []
    for name in names:
        locator = page.get_by_text(name, exact=True)
        if any(locator.nth(index).is_visible() for index in range(locator.count())):
            painted.append(name)
    return painted


def fresh_screenshot(page, screenshot):
    """Replace the final PNG only after a fresh successful capture."""
    descriptor, temporary = tempfile.mkstemp(
        prefix=screenshot.stem + '.capture.', suffix='.png', dir=screenshot.parent)
    os.close(descriptor)
    capture = Path(temporary)
    capture.unlink()
    try:
        page.screenshot(path=str(capture), full_page=True)
        if not capture.is_file() or not capture.read_bytes().startswith(b'\x89PNG\r\n\x1a\n'):
            return False
        capture.chmod(0o644)
        capture.replace(screenshot)
        return True
    except Exception:
        return False
    finally:
        capture.unlink(missing_ok=True)


def read_site(url, state, output, expected_folder=None, expected_names=None):
    from playwright.sync_api import sync_playwright
    if not SHARE_PAGE.fullmatch(url):
        raise ValueError('Use the exact HTTPS official GoFile share URL without query or fragment')
    if expected_folder is not None and not FOLDER_ID.fullmatch(expected_folder):
        raise ValueError('Expected folder ID has an invalid format')
    if output.suffix.lower() != '.json':
        raise ValueError('Proof output must be a JSON file')
    profile = state / 'browser-profile'
    owner_path = state / 'owner-private.json'
    if (not profile.is_dir() or profile.is_symlink() or not owner_path.is_file()
            or owner_path.is_symlink()):
        raise ValueError('An existing copied browser profile and private owner file are required')
    if owner_path.stat().st_mode & 0o777 != 0o600:
        raise ValueError('Private owner file must have mode 600')
    state.chmod(0o700)
    profile.chmod(0o700)
    output.parent.mkdir(parents=True, exist_ok=True)
    screenshot = output.with_suffix('.png')
    observed = []
    blocked_mutations = []
    blocked_authorization_requests = []
    blocked_websockets = []
    navigation_error = None
    screenshot_created_this_run = False
    painted = []
    proxy = os.environ.get('HTTPS_PROXY') or os.environ.get('HTTP_PROXY')
    with sync_playwright() as driver:
        browser = driver.chromium.launch_persistent_context(
            str(profile), executable_path=os.environ.get('HISTORY_CHROMIUM_PATH') or None, headless=True,
            proxy={'server': proxy} if proxy else None,
            args=['--no-sandbox'], viewport={'width': 1440, 'height': 1000},
            accept_downloads=False, service_workers='block')
        browser.route('**/*', make_guard(blocked_mutations, blocked_authorization_requests))
        def block_websocket(websocket):
            parts = urlsplit(websocket.url)
            blocked_websockets.append({'host': parts.hostname, 'path': parts.path})
            websocket.close(code=1000, reason='Readback permits no WebSocket traffic')
        browser.route_web_socket('**/*', block_websocket)
        page = browser.pages[0] if browser.pages else browser.new_page()
        def response_seen(response):
            listing = observed_listing(response, expected_folder)
            if listing is not None:
                observed.append(listing)
        page.on('response', response_seen)
        try:
            page.goto(url, wait_until='domcontentloaded', timeout=45000)
            for unused in range(40):
                painted = painted_names(page, expected_names)
                if (observed and complete_for_names(observed[-1], expected_names)
                        and (expected_names is None or len(painted) == len(expected_names))):
                    page.wait_for_timeout(750)
                    painted = painted_names(page, expected_names)
                    break
                page.wait_for_timeout(1000)
        except Exception as exc:
            navigation_error = type(exc).__name__
        screenshot_created_this_run = fresh_screenshot(page, screenshot)
        browser.close()
    listing = observed[-1] if observed else None
    complete_listing_observed = complete_for_names(listing, expected_names)
    all_expected_filenames_painted = (expected_names is None or len(painted) == len(expected_names))
    verified = (complete_listing_observed and all_expected_filenames_painted
                and screenshot_created_this_run and navigation_error is None
                and not blocked_authorization_requests)
    result = {
        'method': 'normal official website observed in Playwright; no synthesized/replayed auth',
        'public_url': url, 'listing_observed': bool(observed),
        'complete_listing_observed': complete_listing_observed, 'listing': listing,
        'expected_filenames': expected_names,
        'painted_expected_filenames': painted,
        'all_expected_filenames_painted': all_expected_filenames_painted,
        'owner_private_file_present': owner_path.is_file(),
        'normal_guest_creation_posts': 0, 'file_uploads': 0,
        'blocked_mutations': blocked_mutations,
        'blocked_authorization_requests': blocked_authorization_requests,
        'blocked_websockets': blocked_websockets,
        'navigation_error_type': navigation_error,
        'screenshot_created_this_run': screenshot_created_this_run,
        'screenshot': str(screenshot) if screenshot_created_this_run else None,
        'screenshot_sha256': hashlib.sha256(screenshot.read_bytes()).hexdigest()
                             if screenshot_created_this_run else None,
        'proof_verified': verified}
    save(output, result)
    print(json.dumps({'listing_observed': bool(observed), 'proof_verified': verified,
                      'owner_private_file_present': owner_path.is_file(),
                      'normal_guest_creation_posts': 0, 'file_uploads': 0,
                      'screenshot_created_this_run': screenshot_created_this_run,
                      'proof': str(output), 'navigation_error_type': navigation_error}), flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    parser.add_argument('--state-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--expected-folder')
    parser.add_argument('--expected-files-json', type=Path)
    args = parser.parse_args()
    try:
        expected_names = load_expected_names(args.expected_files_json)
        result = read_site(args.url, args.state_dir.resolve(), args.output.resolve(),
                           args.expected_folder, expected_names)
    except Exception as exc:
        # Browser/transport exceptions can contain private URLs or proxy values.
        raise SystemExit('Readback stopped: ' + type(exc).__name__) from None
    raise SystemExit(0 if result['proof_verified'] else 1)
