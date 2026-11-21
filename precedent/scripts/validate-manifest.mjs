import { readFileSync, existsSync } from 'node:fs';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { resolve, dirname } from 'node:path';
import Ajv from 'ajv';
import addFormats from 'ajv-formats';
import { parseDocument } from 'yaml';

const require = createRequire(import.meta.url);
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const document = parseDocument(readFileSync(resolve(root, 'manifest.yml'), 'utf8'), { uniqueKeys: true });
if (document.errors.length) throw new Error(document.errors.map(error => error.message).join('\n'));
const manifest = document.toJS();
const schemaPath = resolve(dirname(require.resolve('@forge/manifest')), 'schema/manifest-schema.json');
const schema = JSON.parse(readFileSync(schemaPath, 'utf8'));
const ajv = new Ajv({ strict: false, allErrors: true });
addFormats(ajv);
const validate = ajv.compile(schema);
if (!validate(manifest)) {
  console.error(ajv.errorsText(validate.errors, { separator: '\n' }));
  process.exit(1);
}
const functions = new Set(manifest.modules.function.map(fn => fn.key));
const resources = new Map(manifest.resources.map(resource => [resource.key, resource.path]));
const actions = new Set(manifest.modules.action.map(action => action.key));
for (const [type, modules] of Object.entries(manifest.modules)) {
  for (const module of modules) {
    if (module.function && !functions.has(module.function)) throw new Error(`Missing function: ${module.function}`);
    if (module.resolver?.function && !functions.has(module.resolver.function)) throw new Error('Missing resolver function');
    if (module.resource && !resources.has(module.resource)) throw new Error('Missing resource');
    for (const action of [...(module.actions ?? []), ...(module.tools ?? [])]) if (!actions.has(action)) throw new Error(`Missing action: ${action}`);
    if (type === 'function') {
      const [file, handler] = module.handler.split('.');
      const source = readFileSync(resolve(root, `src/${file}.js`), 'utf8');
      if (!new RegExp(`export (?:async )?(?:function|const) ${handler}\\b`).test(source)) throw new Error(`Missing handler: ${module.handler}`);
    }
  }
}
for (const path of resources.values()) if (!existsSync(resolve(root, path, 'index.html'))) throw new Error(`Missing resource index: ${path}`);
console.log('Manifest valid against @forge/manifest JSON schema (13.9.0).');
console.log('Function/action/resource references and placeholder HTML entry points verified.');
console.log('Offline validation only: replace placeholder app.id with forge register before deployment.');
