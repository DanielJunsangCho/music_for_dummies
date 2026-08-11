# Symbolic harmony fixtures

Small public excerpts used to validate the harmony engine with **known pitches**.

## When-in-Rome (RomanText)

| Fixture | Piece |
|---|---|
| `when_in_rome/das_wandern` | Schubert, *Das Wandern* |
| `when_in_rome/die_sterne` | Schubert, *Die Sterne* |
| `when_in_rome/wohin` | Schubert, *Wohin?* |
| `when_in_rome/schwanenlied` | Hensel, *Schwanenlied* |
| `when_in_rome/le_colibri` | Chausson, *Le Colibri* |
| `when_in_rome/berceuse` | Chaminade, *Berceuse* |

Source: [When-in-Rome](https://github.com/MarkGotham/When-in-Rome) / OpenScore Lieder Corpus.

## Hooktheory (TheoryTab chord symbols)

| Fixture |
|---|
| `hooktheory/unsteady_intro.xml` |
| `hooktheory/orlando_intro.xml` |
| `hooktheory/revenge_intro.xml` |
| `hooktheory/freedom_dive_intro.xml` |

Source: [lead-sheet-dataset](https://github.com/wayne391/lead-sheet-dataset). Chord tones are synthesised from the annotated symbols.

## Run

```bash
cd backend
source .venv/bin/activate
python -m unittest tests.test_symbolic_harmony -v
```

These fixtures do **not** test scan CV. For Jobim phone photos see `tests/test_corpus.py` with `MUSIC_TEST_CORPUS_DIR`.
