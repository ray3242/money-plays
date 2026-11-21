export function adfToText(node, maxLength = 12000) {
  let text = '';
  const append = value => { text += String(value ?? '').slice(0, Math.max(0, maxLength - text.length)); };
  function visit(value) {
    if (!value || text.length >= maxLength) return;
    if (typeof value === 'string') return append(value);
    if (Array.isArray(value)) return value.forEach(visit);
    if (value.type === 'text') append(value.text);
    else if (value.type === 'hardBreak') append('\n');
    else if (value.type === 'mention') append(value.attrs?.text ?? value.attrs?.id);
    else if (value.type === 'inlineCard') append(value.attrs?.url);
    else {
      if (value.type === 'taskItem') append(value.attrs?.state === 'DONE' ? '[x] ' : '[ ] ');
      visit(value.content);
      if (['paragraph', 'heading', 'listItem', 'taskItem'].includes(value.type)) append('\n');
    }
  }
  visit(node);
  return text.trim();
}
