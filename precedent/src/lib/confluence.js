import api, { route } from '@forge/api';

export async function searchCql(cql, limit = 6) {
  const response = await api.asUser().requestConfluence(route`/wiki/rest/api/search?cql=${cql}&limit=${Math.min(25, Math.max(1, limit))}`);
  if (!response.ok) throw new Error(`Confluence search unavailable (${response.status})`);
  const data = await response.json();
  return (data.results ?? []).map(result => ({
    id: result.content?.id ?? result.id, title: result.title ?? result.content?.title,
    url: result.url?.startsWith('https://') ? result.url : `${data._links?.base ?? '/wiki'}${result.url ?? result.content?._links?.webui ?? ''}`,
    excerpt: String(result.excerpt ?? '').replace(/<[^>]*>/g, ''), lastModified: result.lastModified,
    labels: result.content?.metadata?.labels?.results?.map(label => label.name) ?? []
  }));
}
