export const isMock = import.meta.env.DEV && !window.__bridge && window.parent === window;
const client = isMock ? import('./mock.js') : import('@forge/bridge');

export async function initialize() {
  if (isMock) {
    const { setGlobalTheme } = await import('@atlaskit/tokens/set-global-theme');
    const colorMode = new URLSearchParams(window.location.search).get('theme') === 'dark' ? 'dark' : 'light';
    await setGlobalTheme({ colorMode });
    return { accountId: 'ada', extension: { project: { key: 'PAY' }, issue: { key: 'PAY-412' } } };
  }
  const { view } = await client;
  await view.theme.enable();
  return view.getContext();
}
export async function invoke(name, payload) { return (await client).invoke(name, payload); }
export async function openLink(event, url) {
  event.preventDefault();
  if (!url || !/^(\/[^/]|https:\/\/)/.test(url)) return;
  if (isMock) return; // Fixture links refer to a fictional Atlassian site.
  await (await client).router.open(url);
}
