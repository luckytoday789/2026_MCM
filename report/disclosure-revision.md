# User-requested AI disclosure revision

The current delivery applies `ai-disclosure-revised.txt` to the final paragraph
of the illustrated manuscript. It uses the team as the subject, retains tool
names and discloses assistance with ideas, code, checks, figures and writing.
The historical independently reviewed manuscript remains unchanged in its
source file; the editorial replacement is explicit in build provenance.

Reproduce after restoring the offline evidence repository:

```text
python -B report/build_illustrated_submission.py --public --revised-disclosure --output-dir .runtime/reproduced-disclosure
```

For the private named copy, replace `--public` with `--team-file` pointing to
the ignored local team-display JSON. Do not publish that file or the named PDF.

The revision changes only the final AI-use paragraph. The private PDF retains
nine A4 pages, three figures on pages 6-8, and a minimum 11-point text size.
Pages 1-8 have byte-identical PDF content streams to the previously delivered
illustrated PDF. Extracted page 9 text differs only by the exact paragraph
replacement. The rendered final page was visually inspected without defects.
The original numerical and manuscript reviews apply to their historical
versions; this wording change was checked by the coordinator.
