# Website audit: ray3242.github.io

Audited `https://ray3242.github.io` on 2026-11-21 19:24 UTC.

**Score: 83/100.** 0 high, 3 medium and 8 low priority findings.

## Fix these first

1. **The `content-security-policy` response header is missing.** Send it to limit where scripts and other resources may load from.
2. **The `x-content-type-options` response header is missing.** Send `nosniff` so browsers do not guess content types.
3. **No XML sitemap was found (robots.txt or /sitemap.xml).** Publish a sitemap so search engines find every page.
4. **The `x-frame-options` response header is missing.** Send `DENY` or `SAMEORIGIN` (or CSP `frame-ancestors`) to block clickjacking.
5. **The `referrer-policy` response header is missing.** Send it to control how much of the URL other sites receive.

## All findings

| Priority | Area | Problem | Fix |
| --- | --- | --- | --- |
| Medium | Security | The `content-security-policy` response header is missing. | Send it to limit where scripts and other resources may load from. |
| Medium | Security | The `x-content-type-options` response header is missing. | Send `nosniff` so browsers do not guess content types. |
| Medium | SEO | No XML sitemap was found (robots.txt or /sitemap.xml). | Publish a sitemap so search engines find every page. |
| Low | Security | The `x-frame-options` response header is missing. | Send `DENY` or `SAMEORIGIN` (or CSP `frame-ancestors`) to block clickjacking. |
| Low | Security | The `referrer-policy` response header is missing. | Send it to control how much of the URL other sites receive. |
| Low | Security | The `permissions-policy` response header is missing. | Send it to switch off browser features the site does not use. |
| Low | SEO | The page has 2 `<h1>` headings. | Keep one `<h1>` and demote the others to `<h2>`. |
| Low | Sharing | Open Graph tags are missing: og:image. | Add them so links shared on social apps show a title, text and image. |
| Low | SEO | The page has about 19 words of visible text. | Thin pages rank poorly; add content that answers what visitors search for. |
| Low | SEO | There is no robots.txt. | Add one, and list the sitemap in it. |
| Low | Polish | No favicon is declared in the page. | Add `<link rel="icon">`. |

## What was measured

| Check | Result |
| --- | --- |
| HTTP status | 200 |
| Redirects | 0 |
| HTTPS | yes |
| HTTP redirects to HTTPS | yes |
| TLS certificate days left | 38 |
| Server response time | 0.03 s |
| HTML size | 2 KB |
| Compression | none |
| Title | ray3242.github.io \| Rayhan Robin (32 chars) |
| Meta description | 79 chars |
| Headings | 2 h1, 2 total |
| Images | 0 (0 without alt) |
| External scripts / stylesheets | 1 / 1 |
| Visible words | 19 |
| robots.txt | no |
| XML sitemap | no |
| Structured data blocks | 1 |
| Links found / checked | 1 / 1 |

## Scope

This audit covers the one page above: its HTML, response headers, robots.txt, sitemap, and the first 40 links on it. It does not run JavaScript, so content a script adds after load is not counted. Send another URL to audit another page.

