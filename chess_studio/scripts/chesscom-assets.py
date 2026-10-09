"""Fetch actual Game Review SVG markup from the public Chess.com client.
No imitation icons, no account, no arbitrary guessed asset URLs.
"""
import datetime, hashlib, json, pathlib, re, urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1] / 'public' / 'chesscom'
ROOT.mkdir(parents=True, exist_ok=True)
REFERER = 'https://www.chess.com/analysis'

def fetch(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0', 'Referer': REFERER}), timeout=30).read()

page = fetch(REFERER).decode()
client = re.search(r'src="([^"]+/analysis\.js)"', page).group(1)
client_url = 'https://www.chess.com' + client
script = fetch(client_url).decode()
shared = re.search(r'from["\'](\./shared\.eager\.[^"\']+\.js)["\']', script).group(1)
source = urllib.request.urljoin(client_url, shared)
bundle = fetch(source).decode()
groups = re.findall(r'`(<g id="([^"]+)"[^`]+)`', bundle)
mapping = {'brilliant': 'Brilliant', 'great': 'great_find', 'best': 'best',
           'excellent': 'excellent', 'good': 'good', 'book': 'book',
           'inaccuracy': 'inaccuracy', 'mistake': 'mistake', 'miss': 'missed_win', 'blunder': 'blunder'}
assets = []
for name, group_id in mapping.items():
    markup = next(g for g, ident in groups if ident == group_id and 'ClassNames.Background' in g)
    markup = re.sub(r'\$\{[^}]+\}', 'chesscom-component', markup)
    data = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 18 19" width="180" height="190">' + markup + '</svg>').encode()
    (ROOT / (name + '.svg')).write_bytes(data)
    assets.append({'file': name + '.svg', 'source': source, 'sha256': hashlib.sha256(data).hexdigest(),
                   'processing': 'SVG group extracted; template class names flattened; vector geometry and fills unchanged'})
manifest = {'retrieved_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'publisher': 'Chess.com', 'reference_page': REFERER,
            'license': 'Proprietary Chess.com assets; no open redistribution license asserted.', 'assets': assets}
(ROOT / 'sources.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print('Downloaded', len(assets), 'original vector classification icons.')
