# Changelog

All notable changes to Gentill Transcriber are documented here.

## [0.3.0-rc1] - 2026-10-01

### Added
- branded Tkinter/ttk desktop interface;
- local/offline faster-whisper transcription;
- TXT, JSON, SRT and VTT exporters;
- elapsed-time and waveform processing feedback;
- About screen with author, Gentill Ops, GitHub and optional Pix contribution shortcut;
- deterministic multi-size Windows icon generation;
- PyInstaller Windows packaging;
- packaged executable startup smoke;
- packaged executable real-media E2E transcription;
- Windows PE icon resource validation;
- SHA-256 release manifest;
- RC-to-release promotion with backup and rollback;
- lightweight Windows CI and tag-driven release workflow.

### Fixed
- compatibility failure caused by a packaged PyAV build whose `av.open()` did not accept the `metadata_errors` argument used by faster-whisper;
- release validation now tests the final executable instead of only the Python source/runtime.

### Validated
- Windows executable SHA-256: `64cba27e2535457962aa4f3da1b0ed86ae66c8944570e22e2790aeafc9d85243`;
- packaged transcription: PASS;
- offline policy: `local_files_only`;
- PE icon resources: PASS.
