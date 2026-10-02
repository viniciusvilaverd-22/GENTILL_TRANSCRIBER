# Contributing

Gentill Transcriber is currently maintained as a portfolio/product project by Vinícius Vilaverde + Gentill Ops.

## Before opening a change

1. Keep transcription local by default.
2. Do not add implicit model downloads to the runtime transcription path.
3. Do not commit media files, model weights, virtual environments, build output or local receipts.
4. Keep `local_files_only=True` in the production model-loading path.
5. Add or update tests for compatibility and output-format changes.

## Local validation

On Windows:

```powershell
.venv\Scripts\python.exe -m unittest -v test_transcriber.py test_transcriber_e2e.py
```

For release changes, run the full Windows build pipeline and require:

- unit/E2E tests PASS;
- packaged executable startup PASS;
- packaged executable transcription PASS;
- PE icon validation PASS;
- release manifest PASS.

## Pull requests

Keep PRs focused. Explain:

- what changed;
- why it changed;
- how it was tested;
- whether it affects offline/privacy behavior;
- whether it affects packaging or release artifacts.
