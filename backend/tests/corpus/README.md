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

Thresholds are regression floors for the phone-photo CV path (wrinkled Jobim/
Bonfá plates). They are below a perfect reading of the page — especially
`IMG_4264`, which is still short on systems/notes — but they fail hard if
detection collapses back to zero notes.
