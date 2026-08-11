import hashlib
import json
import os
import unittest
from pathlib import Path

import fitz

from app.services import score_vision


MANIFEST_PATH = Path(__file__).parent / 'corpus' / 'manifest.json'


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


class ScoreCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(MANIFEST_PATH.read_text())
        root_env = cls.manifest['rootEnv']
        root = os.environ.get(root_env)
        if not root:
            raise unittest.SkipTest(f'{root_env} is not set')
        cls.corpus_root = Path(root)

    def test_score_vision_corpus(self):
        for case in self.manifest['cases']:
            with self.subTest(case=case['id']):
                path = self.corpus_root / case['filename']
                self.assertTrue(path.is_file(), f'missing fixture: {path}')
                self.assertEqual(file_digest(path), case['sha256'])

                doc = fitz.open(path)
                try:
                    self.assertEqual(len(doc), case['pages'])
                    geometries = [score_vision.read_page(page)[0] for page in doc]
                finally:
                    doc.close()

                systems = sum(len(geometry.systems) for geometry in geometries)
                measures = sum(len(geometry.measures) for geometry in geometries)
                notes = sum(len(geometry.noteheads) for geometry in geometries)
                sources = {geometry.source for geometry in geometries}
                expected = case['expected']

                failures = []
                if sources != {expected['source']}:
                    failures.append(f'source {sorted(sources)} != {expected["source"]}')
                if systems < expected['minSystems']:
                    failures.append(f'systems {systems} < {expected["minSystems"]}')
                if measures < expected['minMeasures']:
                    failures.append(f'measures {measures} < {expected["minMeasures"]}')
                if notes < expected['minNotes']:
                    failures.append(f'notes {notes} < {expected["minNotes"]}')

                self.assertFalse(failures, '; '.join(failures))


if __name__ == '__main__':
    unittest.main()
