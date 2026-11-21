"""Deterministic website audit: fetch one page, inspect it, return a Markdown report."""
import http.client
import ipaddress
import re
import socket
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser

UA = "SiteAuditAgent/1.0 (+https://market.near.ai)"
MAX_BYTES = 3_000_000
MAX_LINKS = 40
TIMEOUT = 15
FETCH_DEADLINE = 40  # whole request, so a slow-dripping server cannot hold the worker
URL_RE = re.compile(r"https?://[^\s<>\"'\]]+", re.I)
BARE_RE = re.compile(r"(?<![\w@.-])((?:[a-z0-9-]+\.)+[a-z]{2,})(?![\w@-])(:\d+)?([/?#][^\s<>\"'\]]*)?", re.I)

SECURITY_HEADERS = {
    "strict-transport-security": "Send it so browsers use HTTPS on every return visit.",
    "content-security-policy": "Send it to limit where scripts and other resources may load from.",
    "x-content-type-options": "Send `nosniff` so browsers do not guess content types.",
    "x-frame-options": "Send `DENY` or `SAMEORIGIN` (or CSP `frame-ancestors`) to block clickjacking.",
    "referrer-policy": "Send it to control how much of the URL other sites receive.",
    "permissions-policy": "Send it to switch off browser features the site does not use.",
}


class UnsafeUrl(ValueError):
    pass


def extract_url(text):
    """First URL in a brief; falls back to a bare domain such as example.com/page."""
    if not text:
        return None
    m = URL_RE.search(text)
    if m:
        return _trim(m.group(0))
    m = BARE_RE.search(text)
    if m:
        return "https://" + _trim(m.group(0))
    return None


def _trim(u):
    """Drop sentence punctuation and any closing bracket the URL itself never opened."""
    while u and (u[-1] in ".,;:!?" or (u[-1] == ")" and u.count(")") > u.count("("))):
        u = u[:-1]
    return u


def check_public(url, allow_private=False):
    """Refuse non-HTTP schemes and hosts that resolve to private or local addresses."""
    p = urllib.parse.urlsplit(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise UnsafeUrl("only http and https URLs can be audited")
    if allow_private:
        return
    try:
        infos = socket.getaddrinfo(p.hostname, p.port or (443 if p.scheme == "https" else 80))
    except socket.gaierror as e:
        raise UnsafeUrl(f"the host {p.hostname} does not resolve ({e})")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise UnsafeUrl(f"{p.hostname} resolves to a non-public address")


def _connect(host, port, timeout, allow_private):
    """Resolve once, vet every address, and connect to a vetted address (no second DNS lookup)."""
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    if not allow_private:
        for info in infos:
            if not ipaddress.ip_address(info[4][0]).is_global:
                raise UnsafeUrl(f"{host} resolves to a non-public address")
    err = None
    for info in infos:
        try:
            return socket.create_connection(info[4][:2], timeout)
        except OSError as e:
            err = e
    raise err or OSError(f"could not connect to {host}")


class _Http(http.client.HTTPConnection):
    allow_private = False

    def connect(self):
        self.sock = _connect(self.host, self.port, self.timeout, self.allow_private)


class _Https(http.client.HTTPSConnection):
    allow_private = False

    def connect(self):
        sock = _connect(self.host, self.port, self.timeout, self.allow_private)
        self.sock = ssl.create_default_context().wrap_socket(sock, server_hostname=self.host)


def _handlers(allow_private):
    http_cls = type("C", (_Http,), {"allow_private": allow_private})
    https_cls = type("S", (_Https,), {"allow_private": allow_private})

    class H(urllib.request.HTTPHandler):
        def http_open(self, req):
            return self.do_open(http_cls, req)

    class S(urllib.request.HTTPSHandler):
        def https_open(self, req):
            return self.do_open(https_cls, req)

    return [urllib.request.ProxyHandler({}), H(), S()]


class _Redirects(urllib.request.HTTPRedirectHandler):
    def __init__(self, allow_private):
        self.allow_private = allow_private
        self.chain = []

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_public(newurl, self.allow_private)
        self.chain.append((code, newurl))
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url, allow_private=False, method="GET", limit=MAX_BYTES):
    """_fetch with a hard wall-clock limit; the worker thread is abandoned if the server stalls."""
    box = {}

    def work():
        try:
            box["ok"] = _fetch(url, allow_private, method, limit)
        except BaseException as e:
            box["err"] = e

    t = threading.Thread(target=work, daemon=True)
    t.start()
    t.join(FETCH_DEADLINE)
    if "err" in box:
        raise box["err"]
    if "ok" not in box:
        raise TimeoutError(f"no complete response within {FETCH_DEADLINE} s")
    return box["ok"]


def _fetch(url, allow_private, method, limit):
    check_public(url, allow_private)
    red = _Redirects(allow_private)
    opener = urllib.request.build_opener(red, *_handlers(allow_private))
    req = urllib.request.Request(url, method=method, headers={"User-Agent": UA, "Accept": "*/*",
                                                              "Accept-Encoding": "gzip, deflate"})
    t0 = time.time()
    try:
        with opener.open(req, timeout=TIMEOUT) as r:
            enc = (r.headers.get("Content-Encoding") or "").strip().lower()
            dec = _decoder(enc)
            body, wire = b"", 0
            while method == "GET" and len(body) <= limit and time.time() - t0 < FETCH_DEADLINE:
                chunk = r.read1(65536)
                if not chunk:
                    break
                wire += len(chunk)
                body += _inflate(dec, chunk, limit + 1 - len(body)) if dec else chunk
            return {"status": r.status, "url": r.geturl(), "headers": {k.lower(): v for k, v in r.headers.items()},
                    "body": body[:limit], "truncated": len(body) > limit, "seconds": time.time() - t0,
                    "redirects": red.chain, "wire_bytes": wire}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "url": url, "headers": {k.lower(): v for k, v in e.headers.items()},
                "body": b"", "truncated": False, "seconds": time.time() - t0, "redirects": red.chain, "wire_bytes": 0}


def _decoder(enc):
    if enc in ("gzip", "x-gzip"):
        return zlib.decompressobj(16 + zlib.MAX_WBITS)
    if enc == "deflate":
        return zlib.decompressobj()
    return None


def _inflate(dec, chunk, room):
    """Decompress at most room bytes, so a compression bomb cannot exhaust memory."""
    try:
        return dec.decompress(chunk, max(room, 1))
    except zlib.error:  # corrupt or mislabelled body: keep what was decoded so far
        return b""


def parse_robots(text):
    """Group robots.txt into [(agents, [(field, value)])] following RFC 9309 grouping."""
    groups, cur, in_agents = [], None, False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        field, value = (x.strip() for x in line.split(":", 1))
        field = field.lower()
        if field == "user-agent":
            if not in_agents:
                cur = ([], [])
                groups.append(cur)
                in_agents = True
            cur[0].append(value.lower())
        elif field in ("allow", "disallow"):
            if cur is not None:
                cur[1].append((field, value))
            in_agents = False
    return groups


def blocks_everything(text):
    """True when the rules for generic crawlers (the `*` group) disallow the root path."""
    rules = [r for agents, rs in parse_robots(text) if "*" in agents for r in rs]
    disallow_root = any(f == "disallow" and v == "/" for f, v in rules)
    allow_root = any(f == "allow" and v in ("/", "/$") for f, v in rules)
    return disallow_root and not allow_root


class _Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.meta = {}
        self.links = []
        self.images = []
        self.headings = []
        self.canonical = None
        self.lang = None
        self.scripts = 0
        self.stylesheets = 0
        self.jsonld = 0
        self.inputs_unlabelled = 0
        self.labels_for = set()
        self.input_ids = []
        self.mixed = []
        self.words = 0
        self.base = None
        self._labels = 0
        self._stack = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag in ("script", "style", "noscript"):
            self._skip += 1
        if tag == "html":
            self.lang = a.get("lang") or None
        elif tag == "title":
            self._stack.append("title")
        elif tag == "meta":
            key = (a.get("name") or a.get("property") or a.get("http-equiv") or "").lower()
            if key:
                self.meta[key] = a.get("content", "")
            if "charset" in a:
                self.meta["charset"] = a["charset"]
        elif tag == "link":
            rel = a.get("rel", "").lower()
            if "canonical" in rel:
                self.canonical = a.get("href")
            if "stylesheet" in rel:
                self.stylesheets += 1
                self._res(a.get("href"))
            if "icon" in rel:
                self.meta["icon"] = a.get("href", "")
        elif tag == "a" and a.get("href"):
            self.links.append(a["href"])
        elif tag == "img":
            self.images.append(a)
            self._res(a.get("src"))
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.headings.append([int(tag[1]), ""])
            self._stack.append("h")
        elif tag == "script":
            if a.get("src"):
                self.scripts += 1
                self._res(a["src"])
            if a.get("type", "").lower() == "application/ld+json":
                self.jsonld += 1
        elif tag == "base" and a.get("href") and self.base is None:
            self.base = a["href"].strip()
        elif tag == "label":
            self._labels += 1
            if a.get("for"):
                self.labels_for.add(a["for"])
        elif tag in ("input", "select", "textarea"):
            if a.get("type", "").lower() not in ("hidden", "submit", "button", "image", "reset"):
                named = bool(self._labels or a.get("aria-label") or a.get("aria-labelledby") or a.get("title"))
                self.input_ids.append((a.get("id"), named))

    def _res(self, src):
        if src and src.lower().startswith("http://"):
            self.mixed.append(src)

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self._skip:
            self._skip -= 1
        if tag == "title" and "title" in self._stack:
            self._stack.remove("title")
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6") and "h" in self._stack:
            self._stack.remove("h")
        if tag == "label" and self._labels:
            self._labels -= 1

    def handle_data(self, data):
        if "title" in self._stack:
            self.title += data
        if "h" in self._stack and self.headings:
            self.headings[-1][1] += data
        if not self._skip:
            self.words += len(data.split())


def _check_link(args):
    url, allow_private = args
    try:
        r = fetch(url, allow_private, method="HEAD", limit=0)
        if r["status"] in (403, 405, 501):
            r = fetch(url, allow_private, method="GET", limit=2000)
        return url, r["status"], None
    except UnsafeUrl as e:
        return url, None, str(e)
    except Exception as e:  # network errors are findings, not crashes
        return url, None, f"{type(e).__name__}: {getattr(e, 'reason', e)}"


def _cert_days(host, port, allow_private=False):
    try:
        ctx = ssl.create_default_context()
        with _connect(host, port, TIMEOUT, allow_private) as s:
            with ctx.wrap_socket(s, server_hostname=host) as t:
                exp = ssl.cert_time_to_seconds(t.getpeercert()["notAfter"])
                return int((exp - time.time()) // 86400)
    except Exception:
        return None


def audit(url, allow_private=False):
    """Return (markdown, summary). Raises UnsafeUrl when the URL cannot be audited."""
    findings = []  # (severity, area, problem, fix)

    def add(sev, area, problem, fix):
        findings.append((sev, area, problem, fix))

    page = fetch(url, allow_private)
    final = page["url"]
    fp = urllib.parse.urlsplit(final)
    origin = f"{fp.scheme}://{fp.netloc}"
    h = page["headers"]
    ctype = h.get("content-type", "")
    html = page["body"].decode("utf-8", "replace")
    doc = _Page()
    if "html" in ctype or "<html" in html[:2000].lower():
        try:
            doc.feed(html)
        except Exception:
            pass

    # --- availability and transport
    if page["status"] >= 400:
        add("High", "Availability", f"The page answers with HTTP {page['status']}.", "Restore the page or redirect it to a working URL.")
    if fp.scheme != "https":
        add("High", "Security", "The page is served over plain HTTP.", "Serve the site over HTTPS and redirect HTTP to it.")
    cert_days = _cert_days(fp.hostname, fp.port or 443, allow_private) if fp.scheme == "https" else None
    if cert_days is not None and cert_days < 21:
        add("High", "Security", f"The TLS certificate expires in {cert_days} days.", "Renew the certificate or fix automatic renewal.")
    http_upgrade = None
    if fp.scheme == "https" and not allow_private:
        try:
            r = fetch(f"http://{fp.netloc}/", allow_private, limit=1000)
            http_upgrade = r["url"].startswith("https://")
            if not http_upgrade:
                add("High", "Security", "The HTTP version of the site does not redirect to HTTPS.", "Add a permanent redirect from http:// to https://.")
        except Exception:
            pass
    if len(page["redirects"]) > 1:
        add("Low", "Performance", f"The URL goes through {len(page['redirects'])} redirects before it loads.", "Link straight to the final URL and collapse the chain to one redirect.")

    # --- security headers
    missing = [k for k in SECURITY_HEADERS if k not in h]
    if fp.scheme != "https" and "strict-transport-security" in missing:
        missing.remove("strict-transport-security")
    for k in missing:
        sev = "Medium" if k in ("strict-transport-security", "content-security-policy", "x-content-type-options") else "Low"
        if k == "x-frame-options" and "frame-ancestors" in h.get("content-security-policy", ""):
            continue
        add(sev, "Security", f"The `{k}` response header is missing.", SECURITY_HEADERS[k])
    if doc.mixed:
        add("High", "Security", f"{len(doc.mixed)} resource(s) load over http:// on the page (first: `{doc.mixed[0]}`).", "Load every script, style and image over https://.")

    # --- SEO
    title = " ".join(doc.title.split())
    desc = " ".join(doc.meta.get("description", "").split())
    if not title:
        add("High", "SEO", "The page has no `<title>`.", "Add a unique title of 30 to 60 characters.")
    elif not 15 <= len(title) <= 65:
        add("Low", "SEO", f"The title is {len(title)} characters long.", "Aim for 30 to 60 characters so search results show it in full.")
    if not desc:
        add("Medium", "SEO", "The page has no meta description.", "Add a description of 70 to 160 characters that says what the page offers.")
    elif not 50 <= len(desc) <= 170:
        add("Low", "SEO", f"The meta description is {len(desc)} characters long.", "Aim for 70 to 160 characters.")
    h1 = [t for lvl, t in doc.headings if lvl == 1]
    if not h1:
        add("Medium", "SEO", "The page has no `<h1>` heading.", "Add one `<h1>` that states the page's topic.")
    elif len(h1) > 1:
        add("Low", "SEO", f"The page has {len(h1)} `<h1>` headings.", "Keep one `<h1>` and demote the others to `<h2>`.")
    if not doc.canonical:
        add("Low", "SEO", "No canonical URL is declared.", "Add `<link rel=\"canonical\">` pointing at the preferred URL.")
    robots_meta = doc.meta.get("robots", "").lower() + " " + h.get("x-robots-tag", "").lower()
    if "noindex" in robots_meta:
        add("High", "SEO", "The page tells search engines not to index it (`noindex`).", "Remove `noindex` if the page should appear in search.")
    og_missing = [k for k in ("og:title", "og:description", "og:image") if not doc.meta.get(k)]
    if og_missing:
        add("Low", "Sharing", f"Open Graph tags are missing: {', '.join(og_missing)}.", "Add them so links shared on social apps show a title, text and image.")
    if not doc.jsonld:
        add("Low", "SEO", "No JSON-LD structured data was found.", "Add schema.org markup (Organization, Product, Article...) to qualify for rich results.")
    if doc.words and doc.words < 150:
        add("Low", "SEO", f"The page has about {doc.words} words of visible text.", "Thin pages rank poorly; add content that answers what visitors search for.")

    robots = sitemap = None
    try:
        r = fetch(origin + "/robots.txt", allow_private, limit=200_000)
        robots = r["status"] == 200 and b"<html" not in r["body"][:500].lower()
        rtxt = r["body"].decode("utf-8", "replace") if robots else ""
        if robots and blocks_everything(rtxt):
            add("High", "SEO", "robots.txt blocks all crawlers from the whole site (`Disallow: /`).", "Remove the rule unless the site is meant to stay out of search.")
        sm = re.findall(r"(?im)^sitemap:\s*(\S+)", rtxt)
        r2 = fetch(sm[0] if sm else origin + "/sitemap.xml", allow_private, limit=200_000)
        sitemap = r2["status"] == 200 and (b"<urlset" in r2["body"] or b"<sitemapindex" in r2["body"])
    except Exception:
        pass
    if robots is False:
        add("Low", "SEO", "There is no robots.txt.", "Add one, and list the sitemap in it.")
    if sitemap is False:
        add("Medium", "SEO", "No XML sitemap was found (robots.txt or /sitemap.xml).", "Publish a sitemap so search engines find every page.")

    # --- accessibility and mobile
    if not doc.lang:
        add("Medium", "Accessibility", "The `<html>` tag has no `lang` attribute.", "Add `lang=\"en\"` (or the page's language) for screen readers and translation.")
    if "viewport" not in doc.meta:
        add("High", "Mobile", "There is no viewport meta tag.", "Add `<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">`.")
    no_alt = [i for i in doc.images if "alt" not in i]
    if no_alt:
        add("Medium", "Accessibility", f"{len(no_alt)} of {len(doc.images)} images have no `alt` attribute (first: `{(no_alt[0].get('src') or '')[:80]}`).", "Describe each image in `alt`; use `alt=\"\"` for decoration.")
    unlabelled = [i for i, has in doc.input_ids if not has and (not i or i not in doc.labels_for)]
    if unlabelled:
        add("Medium", "Accessibility", f"{len(unlabelled)} form field(s) have no label.", "Give each field a `<label for>` or an `aria-label`.")
    levels = [lvl for lvl, _ in doc.headings]
    if any(b - a > 1 for a, b in zip(levels, levels[1:])):
        add("Low", "Accessibility", "Heading levels skip (for example `<h2>` straight to `<h4>`).", "Keep headings in order so the outline reads correctly.")
    if "icon" not in doc.meta:
        add("Low", "Polish", "No favicon is declared in the page.", "Add `<link rel=\"icon\">`.")

    # --- performance
    size = len(page["body"])
    enc = h.get("content-encoding", "")
    wire = page.get("wire_bytes", size)
    if size > 500_000:
        add("Medium", "Performance", f"The HTML alone is {size // 1024} KB.", "Trim inline scripts, styles and data; lazy-load what is below the fold.")
    if not enc and size > 20_000:
        add("Medium", "Performance", "The HTML is sent uncompressed.", "Turn on gzip or Brotli compression on the server.")
    if page["seconds"] > 2.0:
        add("Medium", "Performance", f"The server took {page['seconds']:.1f} s to deliver the HTML.", "Add caching or a CDN; look for slow back-end work on this route.")
    if doc.scripts > 20:
        add("Low", "Performance", f"The page loads {doc.scripts} external scripts.", "Remove unused scripts and defer the rest.")
    lazy = sum(1 for i in doc.images if i.get("loading", "").lower() == "lazy")
    if len(doc.images) > 10 and lazy == 0:
        add("Low", "Performance", f"None of the {len(doc.images)} images is lazy-loaded.", "Add `loading=\"lazy\"` to images below the fold.")
    if "cache-control" not in h:
        add("Low", "Performance", "The page sends no `Cache-Control` header.", "Set a caching policy, even a short one.")

    # --- links
    seen, targets = set(), []
    try:
        base = urllib.parse.urljoin(final, doc.base) if doc.base else final
    except ValueError:
        base = final
    for href in doc.links:
        try:
            u = urllib.parse.urljoin(base, href.strip()).split("#")[0]
        except ValueError:  # malformed href such as http://[bad
            continue
        if u.startswith(("http://", "https://")) and u not in seen and u != final:
            seen.add(u)
            targets.append(u)
    checked = targets[:MAX_LINKS]
    with ThreadPoolExecutor(8) as ex:
        results = list(ex.map(_check_link, [(u, allow_private) for u in checked]))
    broken = [(u, s, e) for u, s, e in results if (s is not None and s >= 400 and s not in (401, 403, 429, 999)) or (s is None)]
    if broken:
        add("High" if len(broken) > 2 else "Medium", "Links", f"{len(broken)} of {len(checked)} checked links are broken.", "Fix or remove them; the table below lists each one.")

    # --- report
    order = {"High": 0, "Medium": 1, "Low": 2}
    findings.sort(key=lambda f: order[f[0]])
    counts = {s: sum(1 for f in findings if f[0] == s) for s in order}
    score = max(0, 100 - 8 * counts["High"] - 3 * counts["Medium"] - counts["Low"])
    cell = lambda s: str(s).replace("|", "\\|").replace("\n", " ")
    yn = lambda v: "n/a" if v is None else ("yes" if v else "no")
    out = [f"# Website audit: {fp.netloc}", "",
           f"Audited `{final}` on {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}.", "",
           f"**Score: {score}/100.** {counts['High']} high, {counts['Medium']} medium and {counts['Low']} low priority findings.", ""]
    if findings:
        out += ["## Fix these first", ""]
        out += [f"{i}. **{f[2]}** {f[3]}" for i, f in enumerate(findings[:5], 1)]
        out += ["", "## All findings", "", "| Priority | Area | Problem | Fix |", "| --- | --- | --- | --- |"]
        out += [f"| {cell(f[0])} | {cell(f[1])} | {cell(f[2])} | {cell(f[3])} |" for f in findings]
    else:
        out += ["No problems were found by any check."]
    out += ["", "## What was measured", "", "| Check | Result |", "| --- | --- |",
            f"| HTTP status | {page['status']} |",
            f"| Redirects | {len(page['redirects'])} |",
            f"| HTTPS | {yn(fp.scheme == 'https')} |",
            f"| HTTP redirects to HTTPS | {yn(http_upgrade)} |",
            f"| TLS certificate days left | {cert_days if cert_days is not None else 'n/a'} |",
            f"| Server response time | {page['seconds']:.2f} s |",
            f"| HTML size | {size / 1024:.0f} KB{' (cut at 3 MB)' if page['truncated'] else ''} |",
            f"| Compression | {enc + f' ({wire / 1024:.0f} KB sent)' if enc else 'none'} |",
            f"| Title | {cell(title) or 'none'} ({len(title)} chars) |",
            f"| Meta description | {len(desc)} chars |",
            f"| Headings | {len(h1)} h1, {len(doc.headings)} total |",
            f"| Images | {len(doc.images)} ({len(no_alt)} without alt) |",
            f"| External scripts / stylesheets | {doc.scripts} / {doc.stylesheets} |",
            f"| Visible words | {doc.words} |",
            f"| robots.txt | {yn(robots)} |",
            f"| XML sitemap | {yn(sitemap)} |",
            f"| Structured data blocks | {doc.jsonld} |",
            f"| Links found / checked | {len(targets)} / {len(checked)} |"]
    if broken:
        out += ["", "## Broken links", "", "| Link | Result |", "| --- | --- |"]
        out += [f"| {cell(u)} | {cell('HTTP ' + str(s) if s else e)} |" for u, s, e in broken]
    out += ["", "## Scope", "",
            f"This audit covers the one page above: its HTML, response headers, robots.txt, sitemap, and the first {MAX_LINKS} links on it. "
            "It does not run JavaScript, so content a script adds after load is not counted. "
            "Send another URL to audit another page."]
    summary = f"{fp.netloc}: score {score}/100, {counts['High']} high, {counts['Medium']} medium, {counts['Low']} low priority findings."
    return "\n".join(out) + "\n", summary


if __name__ == "__main__":
    import sys
    print(audit(sys.argv[1])[0])
