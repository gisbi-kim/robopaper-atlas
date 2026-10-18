// Rebuild the coauthor network from the same records and overlays as explorer.html.
// Run from any directory: node pipeline/refresh_coauthor_network.mjs
// Python dependencies: networkx, igraph, leidenalg, scikit-learn.
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const work = await fs.mkdtemp(path.join(os.tmpdir(), 'atlas-coauthors-'));
const pipeline = path.join(work, 'pipeline');
await fs.mkdir(pipeline);
const html = await fs.readFile(path.join(root, 'explorer.html'), 'utf8');
const scripts = [...html.matchAll(/src="(explorer_data\/(?:all-|rss-citations-|trio-citations-|corl2026-metadata-)[^"]+)"/g)].map(m => m[1]);
if (!scripts.some(s => s.includes('corl2026-metadata-'))) throw new Error('Missing CoRL metadata overlay');
const context = vm.createContext({ URL });
for (const script of scripts) vm.runInContext(await fs.readFile(path.join(root, script), 'utf8'), context);
const records = vm.runInContext('ALL', context);
const input = records.map(r => ({ venue:r[0], year:r[1], title:r[2], authors:r[3], cited_by_count:r[4], doi:r[5], url:r[8] || '', atlas_verified:true }));
await fs.writeFile(path.join(pipeline, 'all_enriched.json'), JSON.stringify(input));
for (const name of ['_make_coauthor_network.py', '_enrich_communities.py', '_clean.py']) {
  await fs.copyFile(path.join(root, 'pipeline', name), path.join(pipeline, name));
}
const env = {...process.env, PYTHONIOENCODING:'utf-8', MPLCONFIGDIR:path.join(work, 'mpl'), COAUTHOR_SKIP_HTML:'1'};
for (const script of ['_make_coauthor_network.py', '_enrich_communities.py']) {
  execFileSync(process.env.PYTHON || 'python', [script], {cwd:pipeline, env, stdio:'inherit'});
}
const data = JSON.parse(await fs.readFile(path.join(work, 'coauthor_network.json'), 'utf8'));
if (data.meta.papers_used !== input.length || !data.meta.venues.includes('CoRL')) throw new Error('Incomplete paper coverage');
if (data.nodes.some(n => n.papers < 3) || data.edges.some(e => e.source === e.target || e.weight < 2)) throw new Error('Invalid graph');
const edgesFile = 'coauthor_network_edges-' + data.meta.built_at + '.json';
await fs.writeFile(path.join(root, edgesFile), JSON.stringify(data.edges));
await fs.writeFile(path.join(root, 'coauthor_network.json'), JSON.stringify({...data, edges:[], edges_file:edgesFile}));
console.log(JSON.stringify({papers:data.meta.papers_used, nodes:data.nodes.length, edges:data.edges.length, built_at:data.meta.built_at}));
