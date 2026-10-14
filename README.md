# TreeViz

A standalone, dependency-free project tree visualizer. Python 3.9+, Git, and a browser.
Added paths are green, deleted paths red, modifications amber, type changes purple,
and uncertain/omitted paths gray with a question mark. Text badges accompany colors.
Unchanged files stay visible for context; deleted directories and files remain as ghosts.
Directories expand/collapse; search and Changes only retain ancestor context.

## GitDiffViz-compatible interface

```sh
python3 treeviz.py extract-diff --repo /path/to/project --base HEAD~1 --target HEAD --out diff.json
python3 treeviz.py build-scene --diff diff.json --out viewer/scene.json
python3 -m http.server 8090 --directory viewer
# Open http://localhost:8090
```

These are the same two operations, argument names, v1 diff envelope and v1 scene
envelope used by GitDiffViz. `build-scene` also accepts GitDiffViz-produced diffs;
the viewer accepts GitDiffViz scenes (repository/directory/file nodes).
The optional `treeviz.entries` extension in our diffs supplies unchanged paths and
directory metadata. Without it only paths supplied by the diff can be shown.
We compare blob IDs and modes, not source lines: line totals are zero placeholders
and `treeviz.lineCountsAvailable` is false. Renames from Git revisions appear as
delete/add; renamed entries supplied by GitDiffViz are supported.
This implements the existing diff/scene contract, not Labradour's proposed JSON-RPC SDK.

An embedded same-origin iframe announces `{type: "treeviz-ready"}` and accepts
`{type: "labradour-scene", scene: <v1 scene>}` from its parent. Send `scene: null`
to clear a previous session. The embedder owns selection, capture and refresh.

## Captured metadata input

`extract-diff --snapshots snapshots.json --out diff.json` reads no workspace.
The input contains `repoRoot`, `comparison: {base, target}`, `before` and `after`
maps keyed by repository-relative path. File values are `{kind: "file", mode,
oid}`; directories are `{kind: "directory"}`. Use `uncertain: true` for metadata
omissions. `issues` lists unreadable paths/subtrees (`.` means the entire tree).
An optional `notice` is displayed by the viewer. Unknown paths must not be
presented as observed deletions. Inputs are limited to 8 MiB / 20,000 tree paths.
Excluded paths are not discovered or fabricated. Symlinks are leaves, never followed.

In Labradour, Project tree compares the session baseline to the latest immutable
checkpoint, including empty captured directories. A file created and then deleted
within the session disappears from this net comparison; its events remain in Activity.
Saved review uses recorded metadata and Git objects, never current workspace files.

```sh
python3 -m unittest discover -s tests -v
```

This repository initially has no hosted remote. Its parent uses a local submodule URL;
publish this repository and update that URL before sharing a recursive clone.
