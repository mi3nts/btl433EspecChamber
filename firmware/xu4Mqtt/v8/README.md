<!-- ADDED BY CLAUDE (v8 routine update, 2026-10-20) -->
# v8 schedule copy

`schedule.tsv` is a **verbatim, byte-for-byte** copy of the MINTS-AI calibration programme v8 that
`../runRoutineV8.py` runs. Do not edit it here: change it in the Calibration repository and copy it again.

| | |
|---|---|
| Source | `mi3nts/Calibration`, `Docs/protocol/schedule.tsv` |
| Last changed in Calibration commit | `3ca7f8509ce0b93f01d3c93c0651c9e6a988bf92` (2026-10-23, "Chamber protocol: keep the unheated Frog line dry (temporary stop-gap)") |
| Calibration HEAD when copied | `0e4a54913b5b6670791343611bc975dbbd2811b9` (2026-10-26; the file is unchanged since `3ca7f85`) |
| sha256 of the file bytes | `92ee4e0873b00c0ef3b4eef3e2637539592102e19d46cdd4aca55de28ff5cfa1` |
| Copied | 2026-10-26, with `git show 3ca7f85:Docs/protocol/schedule.tsv` (replaces the 2026-10-20 copy of `d809739`, sha256 `9f59b5fb…`) |

What changed in `3ca7f85`: until heated sample lines exist the chamber dew point is capped at the Frog line temperature
minus 3 C, so the cap is 19 C (was 23 C) and the dew-point ABORT is cap + 2 C for 2 min (was cap + 3 C for 5 min). The
warm humid points 16-21 (35/45 ... 20/90, dew points 21.3-22.7 C) are replaced by a 20 C ladder (45/60/70/80/90 %);
the profile is now points 1-28 (was 1-30). The 19 C cap assumes a 22 C Frog line; this routine reads it from the
`excursion` row and has no line-temperature check of its own (Calibration's gate G0.7, `--frog-line-T`).

The file has CRLF line ends, as committed in Calibration. `.gitattributes` in this folder marks it `-text` so git never
rewrites them; otherwise its sha256 would change on checkout. `runRoutineV8.py` prints this sha256 at start and writes
it to every `BTL433ESC001RTNV8` record (`scheduleSha`).

Calibration's own runner hashes the text after newline translation, so its `--plan` prints `3f0b1239ecc5…` for the
same file (`3f0b1239ecc5e8801de718f0e760313136e53975c16e59d0f7167bdabd5f3ec1`). Both identify the same content.

Check a copy:

```bash
sha256sum v8/schedule.tsv
```
<!-- END ADDED BY CLAUDE -->
