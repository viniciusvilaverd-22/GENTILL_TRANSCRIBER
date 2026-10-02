# Engineering notes

## Case study: a bug that existed only in the packaged executable

A useful failure during the Windows release process exposed a gap between source-level QA and artifact-level QA.

### Symptom

The desktop executable failed during transcription with:

```text
open() got an unexpected keyword argument 'metadata_errors'
```

Python source tests were passing.

### Root cause

The older packaged executable contained a PyAV build where `av.open()` did not expose the `metadata_errors` argument used by `faster-whisper 1.2.1`.

A newer runtime/build path used a compatible PyAV version, but the release validation at that point only proved that the GUI executable stayed open for a few seconds. It did not prove that media decoding worked inside the packaged application.

### Fix

The project changed the release strategy in three ways:

1. pin the runtime compatibility dependency used by packaging;
2. add a direct compatibility test that actually calls `av.open(..., metadata_errors="ignore")`;
3. add an executable self-test mode and run a real generated WAV through the packaged EXE.

### Result

A release candidate now has to produce TXT, JSON, SRT and VTT through the actual packaged executable before it can be promoted.

This case is why the project treats the final desktop artifact—not only source tests—as the release boundary.
