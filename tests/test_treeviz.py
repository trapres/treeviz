import unittest
from treeviz import compare, build_scene, parse_tree


def file(oid='a', **extra):
    return dict(kind='file', mode='100644', oid=oid, **extra)


class TreeTests(unittest.TestCase):
    def scene(self, before, after, **extra):
        return build_scene(compare(dict(repoRoot='/project', comparison={'base': 'a', 'target': 'b'},
                                        before=before, after=after, **extra)))

    def test_context_nested_add_delete_modify_and_empty_directories(self):
        scene = self.scene({'src/keep': file(), 'src/edit': file(), 'old/gone': file()},
                           {'src/keep': file(), 'src/edit': file('b'), 'new/deep/create': file(),
                            'empty': {'kind': 'directory'}})
        nodes = {n.get('path'): n for n in scene['scene']['nodes']}
        for path, status in [('src/keep', 'unchanged'), ('src/edit', 'modified'), ('old/gone', 'deleted'),
                             ('old', 'deleted'), ('new/deep', 'added'), ('empty', 'added'), ('src', 'modified')]:
            self.assertEqual(nodes[path]['status'], status)
        self.assertEqual(scene['metrics']['totalFiles'], 4)
        self.assertEqual(scene['metrics']['changedFiles'], 3)
        self.assertTrue(all(e['from'] in {n['id'] for n in nodes.values()} for e in scene['scene']['edges']))

    def test_omissions_and_failed_subtrees_are_not_deleted(self):
        scene = self.scene({'blocked/a': file(), 'large': file()},
                           {'large': {'kind': 'file', 'uncertain': True}}, issues=['blocked'])
        nodes = {n.get('path'): n for n in scene['scene']['nodes']}
        self.assertEqual(nodes['blocked/a']['status'], 'unknown')
        self.assertEqual(nodes['large']['status'], 'unknown')

    def test_gitdiffviz_diff_without_extension(self):
        scene = build_scene({'version': 1, 'repoRoot': '/project', 'comparison': {'base': 'a', 'target': 'b'},
                            'files': [{'path': 'src/new.py', 'oldPath': 'src/old.py', 'status': 'renamed',
                                       'additions': 2, 'deletions': 1, 'isBinary': False, 'hunks': []}],
                            'summary': {'changedFiles': 1, 'totalAdditions': 2, 'totalDeletions': 1}})
        nodes = {n.get('path'): n for n in scene['scene']['nodes']}
        self.assertEqual(nodes['src/old.py']['status'], 'deleted')
        self.assertEqual(nodes['src/new.py']['status'], 'renamed')
        self.assertIn('unchanged paths were not supplied', scene['treeviz']['notice'])

    def test_nul_framing_preserves_odd_filenames_and_rejects_escape(self):
        self.assertIn('a\tb\nc', parse_tree(b'100644 blob abc\ta\tb\nc\0'))
        with self.assertRaises(ValueError):
            self.scene({}, {'../escape': file()})


if __name__ == '__main__':
    unittest.main()
