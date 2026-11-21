# Custom UI

Two React 18 entrypoints share a token-based interface and resolver client.

```sh
npm ci
npm run build
npm test
npm run validate:manifest
```

Build before Forge lint/deploy: Vite writes both manifest resource directories,
`static/panel/dist` and `static/ledger/dist`. The app still needs registration and
an authenticated Atlassian environment; see BACKEND.md.

## Standalone demo

Run `npm run preview:panel` (port 4173) and `npm run preview:ledger` (port 4174).
Outside the Forge iframe these development servers use realistic payments-team
fixtures. Add `?theme=dark`, `?state=empty` or `?state=error` to inspect states.
Demo mutations persist in localStorage; clear `precedent-demo-decisions` to reset.
Fixture links deliberately do not navigate to a fictional Atlassian site.

Production builds eliminate fixture data and the mock theme loader. Inside Forge,
the bridge enables the host theme and invokes the existing backend resolvers.
Supersede controls are author-only; the backend also enforces authorization.

## Browser verification

With both development servers running:

```sh
npx playwright install chromium
node scripts/verify-ui.mjs
```

Set `CHROME_PATH` to use an existing Chrome executable instead. The script checks
record/supersede interactions, filters, empty/error states and horizontal overflow,
and captures evidence under `docs/screenshots` at 700px panel / 1280px page widths.
It uses fresh browser storage and does not contact Atlassian services.
