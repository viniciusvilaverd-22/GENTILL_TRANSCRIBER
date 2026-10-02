# Release process

## Windows

The local Windows release pipeline is implemented by `build_windows.cmd`.

### Gates

1. Generate the deterministic `.ico`.
2. Install runtime/build dependencies.
3. Run unit and E2E tests.
4. Build the PyInstaller RC into `dist-rc`.
5. Validate model files and expected model SHA-256.
6. Launch the packaged executable.
7. Execute a generated WAV through the packaged executable.
8. Require TXT/JSON/SRT/VTT output.
9. Require `offline_policy=local_files_only`.
10. Validate PE `RT_ICON` and `RT_GROUP_ICON` resources.
11. Generate `RELEASE_MANIFEST_windows.json`.
12. Promote the RC to `dist` with backup/rollback.

## GitHub CI

`windows-ci.yml` intentionally avoids downloading the large Whisper model. It checks fast unit/compatibility gates on each push/PR.

## GitHub Release automation

`release-windows.yml` runs only for `v*` tags. It provisions the model in the GitHub runner, builds and verifies the Windows bundle, creates a ZIP and publishes it through GitHub Releases using the repository token.

## macOS

The macOS build is prepared but should be treated as unvalidated until it is executed on a supported Mac and the resulting `.app` passes the same runtime/media expectations.
