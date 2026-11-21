import { adfToText } from './adf.js';

const stopwords = new Set('the and for with this that from into have has was were are not but can will should would could issue jira ticket task story epic please need needs update implement add fix support acceptance criteria given when then'.split(' '));
export function normalizeText(value) {
  return String(value ?? '').toLowerCase().replace(/[^\p{L}\p{N}\s]/gu, ' ').replace(/\s+/g, ' ').trim();
}
export function safePhrase(value) {
  return normalizeText(value).slice(0, 160);
}
export function extractKeywords(issue, limit = 6) {
  const fields = issue?.fields ?? issue ?? {};
  const weights = new Map();
  const add = (value, weight) => {
    for (const word of normalizeText(value).split(' ')) {
      if (word.length >= 3 && !stopwords.has(word)) weights.set(word, (weights.get(word) ?? 0) + weight);
    }
  };
  add(fields.summary, 3);
  add(adfToText(fields.description), 1);
  for (const label of fields.labels ?? []) add(label, 1);
  for (const component of fields.components ?? []) add(component.name, 1);
  return [...weights].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).slice(0, limit).map(([word]) => word);
}
