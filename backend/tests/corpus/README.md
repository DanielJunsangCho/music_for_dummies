# Score corpus

The manifest identifies large, local integration fixtures by filename and SHA-256 hash. The PDF binaries are intentionally not committed because these three files alone add about 17.6 MB to Git.

Set the corpus directory and run the integration test:

```bash
cd backend
source .venv/bin/activate
MUSIC_TEST_CORPUS_DIR=/Users/juncho/Downloads/compressed \
  python -m unittest tests.test_corpus -v
```

Without `MUSIC_TEST_CORPUS_DIR`, normal unit-test discovery skips the corpus cleanly.

Thresholds describe the visible score, not the current detector output. A fixture remains failing until the vision engine recovers the expected minimum number of systems, measures, and notes.
