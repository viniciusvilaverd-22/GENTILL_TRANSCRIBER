# Privacy and offline behavior

Gentill Transcriber is designed around local processing.

## Runtime guarantees

- No transcription API key is required.
- Input audio/video is passed to the local faster-whisper runtime.
- The Whisper model is loaded from disk.
- Runtime model loading uses `local_files_only=True`.
- Generated TXT/JSON/SRT/VTT files are written to the user's local output directory.

## What may use the network

Development/provisioning can use the network to install Python packages and obtain the Whisper model before offline use. The macOS build script can also provision the model when it is missing.

That is separate from the normal transcription path.

## Repository hygiene

The public repository excludes:

- model weights;
- virtual environments;
- user media;
- generated transcriptions;
- build directories;
- release bundles;
- local audit/log/receipt files.

## Threat model

This project currently focuses on preventing accidental cloud transcription and implicit model downloads. It is not presented as a hardened sandbox against malicious local files or a replacement for endpoint security.
