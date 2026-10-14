#!/usr/bin/env python3
"""TreeViz: dependency-free GitDiffViz v1 diff/scene producer."""
import argparse
import json
import os
from pathlib import Path
import subprocess

LIMIT = 20000
COLORS = {'added': '#72df9a', 'deleted': '#ff8c94', 'modified': '#f2c879',
          'type_changed': '#c8a4ff', 'unknown': '#aebbd0', 'unchanged': '#9aaabd',
          'renamed': '#82cfff', 'copied': '#72df9a', 'unmerged': '#ff8c94'}


def valid_path(path):
    if not isinstance(path, str) or not path or path.startswith('/') or any(
            part in ('', '.', '..', '.git') for part in path.split('/')) or '\0' in path:
        raise ValueError('Invalid repository-relative path')
    return path


def git_tree(repo, revision):
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull, GIT_NO_REPLACE_OBJECTS='1')
    commit = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', '--verify',
                                     '--end-of-options', revision + '^{commit}'], env=env, timeout=10).strip()
    raw = subprocess.check_output(['git', '-C', str(repo), 'ls-tree', '-rz', commit.decode()], env=env, timeout=10)
    return parse_tree(raw)


def parse_tree(raw):
    result = {}
    for entry in raw.split(b'\0'):
        if not entry:
            continue
        head, name = entry.split(b'\t', 1)
        mode, kind, oid = head.decode().split()
        path = valid_path(os.fsdecode(name))
        result[path] = {'kind': 'file', 'mode': mode, 'oid': oid}
        if len(result) > LIMIT:
            raise ValueError('Tree exceeds 20,000 paths')
    return result


def with_directories(entries):
    result = dict(entries)
    for path in list(result):
        valid_path(path)
        parts = path.split('/')
        for i in range(1, len(parts)):
            result.setdefault('/'.join(parts[:i]), {'kind': 'directory'})
    if len(result) > LIMIT:
        raise ValueError('Tree exceeds 20,000 paths')
    return result


def compare(document):
    before, after = (with_directories(document[key]) for key in ('before', 'after'))
    entries = []
    issues = document.get('issues', [])
    for path in sorted(before.keys() | after.keys()):
        old, new = before.get(path), after.get(path)
        uncertain = any(p == '.' or path == p or path.startswith(p + '/') for p in issues)
        uncertain |= bool((old or {}).get('uncertain') or (new or {}).get('uncertain'))
        status = ('unknown' if uncertain else 'added' if old is None else 'deleted' if new is None else
                  'type_changed' if old.get('mode', old['kind']) != new.get('mode', new['kind']) else
                  'modified' if old != new else 'unchanged')
        entries.append({'path': path, 'kind': (new or old)['kind'], 'status': status,
                        'additions': 0, 'deletions': 0, 'isBinary': False, 'hunks': []})
    files = [item for item in entries if item['kind'] == 'file' and item['status'] != 'unchanged']
    return {'version': 1, 'repoRoot': document['repoRoot'], 'comparison': document['comparison'],
            'files': files, 'summary': {'changedFiles': len(files), 'totalAdditions': 0, 'totalDeletions': 0},
            'treeviz': {'entries': entries, 'lineCountsAvailable': False,
                        'notice': document.get('notice', 'Committed tree comparison; line counts not collected')}}


def build_scene(diff):
    if diff.get('version') != 1:
        raise ValueError('Expected GitDiffViz diff version 1')
    extension = diff.get('treeviz', {})
    entries = extension.get('entries', diff['files'])
    if len(entries) > LIMIT:
        raise ValueError('Tree exceeds 20,000 paths')
    by_path = {}
    for entry in entries:
        path = valid_path(entry['path'])
        by_path[path] = dict(entry, kind=entry.get('kind', 'file'))
        # A renamed file remains visible at its previous location as a deleted ghost.
        if entry.get('oldPath') and entry.get('status') == 'renamed':
            old = valid_path(entry['oldPath'])
            by_path.setdefault(old, dict(entry, path=old, status='deleted', kind='file'))
    by_path = with_directories(by_path)
    nodes = [{'id': 'root', 'kind': 'repository', 'name': Path(diff['repoRoot']).name or 'Project',
              'status': 'unchanged'}]
    for path, entry in sorted(by_path.items()):
        status = entry.get('status', 'unchanged')
        if status not in COLORS:
            status = 'unknown'
        parent = path.rpartition('/')[0]
        nodes.append({'id': 'path:' + path, 'kind': entry['kind'], 'path': path,
                      'name': path.rsplit('/', 1)[-1], 'parentId': 'path:' + parent if parent else 'root',
                      'status': status, 'render': {'baseColor': COLORS[status]}})
    # Existing directories show that their descendants changed, without claiming creation/deletion.
    indexed = {node['id']: node for node in nodes}
    for node in reversed(nodes[1:]):
        parent = indexed.get(node['parentId'])
        if parent and node['status'] != 'unchanged' and parent['status'] == 'unchanged':
            parent['status'] = 'modified'
    return {'version': 1, 'repoRoot': diff['repoRoot'], 'comparison': diff['comparison'],
            'scene': {'nodes': nodes, 'edges': [{'id': 'edge:' + n['id'], 'kind': 'contains',
                       'from': n['parentId'], 'to': n['id']} for n in nodes[1:]], 'assets': [],
                      'legend': [{'key': k, 'label': k.replace('_', ' '), 'color': v} for k, v in COLORS.items()]},
            'metrics': {'totalFiles': sum(n['kind'] == 'file' for n in nodes),
                        'changedFiles': diff['summary']['changedFiles'],
                        'totalAddedLines': diff['summary']['totalAdditions'],
                        'totalRemovedLines': diff['summary']['totalDeletions']},
            'treeviz': {'notice': extension.get('notice', 'Diff-only tree: unchanged paths were not supplied'),
                        'lineCountsAvailable': extension.get('lineCountsAvailable', True)}}


def read_json(path):
    if Path(path).stat().st_size > 8 * 1024 * 1024:
        raise ValueError('Input exceeds 8 MiB')
    return json.loads(Path(path).read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    extract = commands.add_parser('extract-diff')
    extract.add_argument('--repo')
    extract.add_argument('--base')
    extract.add_argument('--target')
    extract.add_argument('--snapshots', help='Optional captured before/after metadata, without reading a workspace')
    extract.add_argument('--out', required=True)
    build = commands.add_parser('build-scene')
    build.add_argument('--diff', required=True)
    build.add_argument('--out', required=True)
    args = parser.parse_args()
    if args.command == 'build-scene':
        result = build_scene(read_json(args.diff))
    elif args.snapshots:
        result = compare(read_json(args.snapshots))
    else:
        if not all((args.repo, args.base, args.target)):
            parser.error('extract-diff requires --repo, --base and --target, or --snapshots')
        result = compare({'repoRoot': str(Path(args.repo).resolve()),
                          'comparison': {'base': args.base, 'target': args.target},
                          'before': git_tree(args.repo, args.base), 'after': git_tree(args.repo, args.target)})
    Path(args.out).write_text(json.dumps(result, ensure_ascii=True) + '\n')


if __name__ == '__main__':
    main()
