"""Readable text of a public news article, to check every claim against its source."""

from html.parser import HTMLParser
import re
import urllib.request

AGENT = "Mozilla/5.0 (compatible; EdgerunnersStudio/1.0; +https://edgerunners.fr/about)"
SKIP = {"script", "style", "noscript", "nav", "header", "footer", "aside", "form", "figure"}


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.inside = None
        self.title = ""
        self.in_title = False
        self.paragraphs = []
        self.current = []

    def handle_starttag(self, tag, attrs):
        if tag in SKIP:
            self.skip += 1
        elif tag == "title":
            self.in_title = True
        elif tag in {"p", "h2", "h3", "li", "blockquote"} and not self.skip:
            self.inside = tag
            self.current = []

    def handle_endtag(self, tag):
        if tag in SKIP and self.skip:
            self.skip -= 1
        elif tag == "title":
            self.in_title = False
        elif tag == self.inside:
            text = re.sub(r"\s+", " ", "".join(self.current)).strip()
            if len(text.split()) >= 6:
                self.paragraphs.append(text)
            self.inside = None

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        elif self.inside and not self.skip:
            self.current.append(data)


def extract(html):
    parser = _Text()
    parser.feed(html)
    seen, kept = set(), []
    for p in parser.paragraphs:
        if p not in seen and not re.search(r"(?i)cookie|subscribe|newsletter|sign up|all rights reserved", p):
            seen.add(p)
            kept.append(p)
    return re.sub(r"\s+", " ", parser.title).strip(), "\n".join(kept)


def fetch(url, *, limit=2_500_000, timeout=25):
    """Title and body text; the caller validates the public HTTPS address first."""
    req = urllib.request.Request(url, headers={"User-Agent": AGENT, "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        kind = r.headers.get("Content-Type", "")
        if "html" not in kind:
            raise ValueError("La source n’est pas une page d’article.")
        body = r.read(limit + 1)[:limit]
        charset = r.headers.get_content_charset() or "utf-8"
    title, text = extract(body.decode(charset, "replace"))
    return {"title": title[:300], "text": text[:20000], "words": len(text.split())}
