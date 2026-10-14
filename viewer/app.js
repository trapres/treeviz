'use strict';
const $ = id => document.getElementById(id);
let documentScene, collapsed = new Set(), comparisonKey;
const marks = {added: '+', deleted: '−', modified: '~', type_changed: '↔', unknown: '?', renamed: '→', copied: '+', unmerged: '!'};
// Filenames are data, never HTML. Escape controls visibly so one name cannot impersonate several rows.
const label = text => String(text).replace(/[\u0000-\u001f\u007f-\u009f]/g, c => JSON.stringify(c).slice(1, -1));
function render() {
  if (!documentScene) return;
  const nodes = documentScene.scene.nodes.filter(n => ['repository', 'directory', 'file'].includes(n.kind));
  const index = new Map(nodes.map(n => [n.id, n]));
  const children = new Map();
  for (const node of nodes) {
    const parent = index.has(node.parentId) ? node.parentId : null;
    if (!children.has(parent)) children.set(parent, []);
    children.get(parent).push(node);
  }
  for (const list of children.values()) list.sort((a, b) => (a.kind === 'file') - (b.kind === 'file') || a.name.localeCompare(b.name));
  const query = $('search').value.toLowerCase(), changes = $('changes').checked;
  const visible = new Set();
  for (const node of nodes) {
    if (query && !(node.path || node.name).toLowerCase().includes(query)) continue;
    if (changes && (!node.status || node.status === 'unchanged')) continue;
    let current = node;
    const visited = new Set();
    while (current && !visited.has(current.id)) { visible.add(current.id); visited.add(current.id); current = index.get(current.parentId); }
  }
  const visited = new Set();
  function branch(parent, depth = 0) {
    const list = document.createElement('ul');
    if (depth > 100) return list;
    for (const node of children.get(parent) || []) {
      if (!visible.has(node.id) || visited.has(node.id)) continue;
      visited.add(node.id);
      const li = document.createElement('li'), entry = document.createElement('button');
      const status = Object.hasOwn(marks, node.status) ? node.status : 'unchanged';
      entry.className = `entry ${status}`;
      const folder = node.kind !== 'file', open = !collapsed.has(node.id) || !!query || changes;
      const glyph = document.createElement('span'); glyph.className = 'glyph'; glyph.textContent = folder ? (open ? '▾' : '▸') : (marks[status] || '·');
      const name = document.createElement('span'); name.className = 'name'; name.textContent = label(node.name) + (folder ? '/' : '');
      const badge = document.createElement('span'); badge.className = 'badge'; badge.textContent = status === 'unchanged' ? '' : status.replace('_', ' ');
      entry.append(glyph, name, badge); entry.title = label(node.path || node.name) + ' · ' + status;
      if (folder) {
        entry.setAttribute('aria-expanded', String(open));
        entry.onclick = () => { collapsed.has(node.id) ? collapsed.delete(node.id) : collapsed.add(node.id); render();
          Array.from($('tree').querySelectorAll('button')).find(b => b.dataset.id === node.id)?.focus(); };
      }
      entry.dataset.id = node.id;
      li.append(entry);
      if (folder && open) li.append(branch(node.id, depth + 1));
      list.append(li);
    }
    return list;
  }
  const position = $('tree').scrollTop;
  $('tree').replaceChildren(branch(null));
  if (!visible.size) { const p = document.createElement('p'); p.className = 'empty'; p.textContent = 'No matching paths.'; $('tree').append(p); }
  $('tree').scrollTop = position;
  const files = nodes.filter(n => n.kind === 'file');
  const count = status => files.filter(n => n.status === status).length;
  $('summary').textContent = `${files.length} file paths · ${count('added')} added · ${count('deleted')} deleted · ${count('modified')} modified · ${count('unknown')} unknown`;
}
function applyDocument(value) {
  if (value === null) { documentScene = null; $('tree').replaceChildren(); $('summary').textContent = ''; $('notice').textContent = 'Waiting for captured project structure…'; return; }
  if (value?.version !== 1 || !Array.isArray(value?.scene?.nodes)) throw new Error('Expected a GitDiffViz version 1 scene');
  if (value.scene.nodes.length > 20001) throw new Error('Tree exceeds 20,000 paths');
  const key = value.repoRoot + ':' + value.comparison.base;
  if (key !== comparisonKey) collapsed.clear();
  comparisonKey = key; documentScene = value;
  $('notice').textContent = value.treeviz?.notice || 'GitDiffViz scene · supplied paths only';
  render();
}
window.addEventListener('message', event => {
  if (event.source !== parent || event.origin !== location.origin || event.data?.type !== 'labradour-scene') return;
  try { applyDocument(event.data.scene); } catch (error) { $('tree').replaceChildren(); $('notice').textContent = error.message; }
});
$('search').oninput = render; $('changes').onchange = render;
$('expand').onclick = () => { collapsed.clear(); render(); };
$('collapse').onclick = () => { collapsed = new Set((documentScene?.scene.nodes || []).filter(n => n.kind === 'directory').map(n => n.id)); render(); };
parent.postMessage({type: 'treeviz-ready'}, location.origin);
// Standalone viewer: serve this directory and place a scene.json beside index.html.
if (parent === window) fetch('scene.json').then(r => { if (!r.ok) throw new Error('Place scene.json beside the viewer to open a standalone tree.'); return r.json(); }).then(applyDocument).catch(e => { $('notice').textContent = e.message; });
