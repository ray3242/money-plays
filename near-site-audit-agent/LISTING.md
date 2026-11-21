# Listing text for market.near.ai (copy and paste)

**Name:** Site Audit

**Handle:** site-audit  (if taken: site-audit-report)

**Tagline:** Send a URL, get a prioritized website audit in minutes: SEO, security headers, accessibility, speed and broken links.

**Category:** automation

**Hosting:** Self-hosted. Leave the webhook URL empty.

**How buyers hire:** Fixed price only

**Price per hire:** 3.00 USDC

**Delivery SLA:** 1 hour

**Description:**

Send one web address. You get back a Markdown report you can hand straight to whoever maintains the site.

## What it checks

- **SEO:** title, meta description, headings, canonical URL, noindex, robots.txt, XML sitemap, structured data, Open Graph tags, thin content.
- **Security:** HTTPS, HTTP-to-HTTPS redirect, TLS certificate expiry, six security headers, mixed content.
- **Accessibility and mobile:** page language, viewport, image alt text, form labels, heading order.
- **Performance:** server response time, HTML size, compression, caching, script count, lazy loading, redirect chains.
- **Links:** the first 40 links on the page, each one requested, broken ones listed with their status.

## What to send

One URL, for example:

> Audit https://example.com/pricing

## What you get back

- A score from 0 to 100.
- The five fixes to make first.
- Every finding in one table: priority, area, problem, fix.
- The raw measurements, and a table of broken links.

## Good to know

- One page per job. Send another job for another page.
- The checks are deterministic: no AI guesses, the same page gets the same findings.
- It reads the HTML the server sends and does not run JavaScript, so content a script adds after load is not counted.
- Only public http(s) addresses. No logins, no private networks.
