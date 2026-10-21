<!-- ADDED BY CLAUDE (v8 routine update, 2026-10-20) -->
# v8 schedule copy

`schedule.tsv` is a **verbatim, byte-for-byte** copy of the MINTS-AI calibration programme v8 that
`../runRoutineV8.py` runs. Do not edit it here: change it in the Calibration repository and copy it again.

| | |
|---|---|
| Source | `mi3nts/Calibration`, `Docs/protocol/schedule.tsv` |
| Last changed in Calibration commit | `d8097393c4caf0bc68ca629f32c29ac4790a889b` (2026-10-15, "7.3.0 … v8 chained schedule …") |
| Calibration HEAD when copied | `d4db4740d91b977757befabad4b790f24df910ac` (2026-10-20; the file is unchanged since `d809739`) |
| sha256 of the file bytes | `9f59b5fbbedd238b72cbbe9267d7a67d4242f2dc70aed4bbb9377387e12d5157` |
| Copied | 2026-10-20, with `git show d809739:Docs/protocol/schedule.tsv` |

The file has CRLF line ends, as committed in Calibration. `.gitattributes` in this folder marks it `-text` so git never
rewrites them; otherwise its sha256 would change on checkout. `runRoutineV8.py` prints this sha256 at start and writes
it to every `BTL433ESC001RTNV8` record (`scheduleSha`).

Calibration's own runner hashes the text after newline translation, so its `--plan` prints `710c528b4fbd…` for the
same file (`710c528b4fbdc72b427c7f689a0215a953d3341450c596a3bef556340ff837f2`). Both identify the same content.

Check a copy:

```bash
sha256sum v8/schedule.tsv
```
<!-- END ADDED BY CLAUDE -->
