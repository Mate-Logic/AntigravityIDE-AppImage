# AntigravityIDE AppImage

[![Build and publish](https://github.com/Mate-Logic/AntigravityIDE-AppImage/actions/workflows/release.yml/badge.svg)](https://github.com/Mate-Logic/AntigravityIDE-AppImage/actions/workflows/release.yml)

An unofficial, community-maintained AppImage distribution of the Google
Antigravity IDE for Linux x86_64.

## Download

Download the [latest release](https://github.com/Mate-Logic/AntigravityIDE-AppImage/releases/latest).
Every release contains the AppImage, its zsync update file, and SHA-256, MD5,
and SHA-512 manifests. The release notes also contain a checksum table for each
published AppImage asset.

This project is not affiliated with Google. The application itself is always
downloaded from the official [Antigravity download page](https://antigravity.google/download).

## Run

```bash
chmod +x AntigravityIDE*.AppImage
./AntigravityIDE*.AppImage
```

AppImage update metadata is embedded in each image. Compatible AppImage
updaters can use the zsync asset from the latest GitHub release.

## Automation

The scheduled workflow runs every six hours and also supports manual runs. A
manual run can set `force` to rebuild the current source and repair or refresh
the latest release metadata. Each run also re-enables its own schedule, because
GitHub disables scheduled workflows after 60 days without repository activity.
The workflow:

1. Asks the official IDE update service (the one the Antigravity app uses) for the current Linux x86_64 archive, falling back to the official download page.
2. Downloads the archive and checks it against the SHA-256 published by the update service.
3. Compares that digest with the `SOURCE-SHA256` asset of the latest release.
4. Stops without publishing when the source bytes have not changed.
5. Passes the expected digest to [`appimage-python`](https://github.com/Mate-Logic/appimage-python), which verifies the archive it downloads before building.
6. Publishes the AppImage, zsync file, checksum manifests, and a release checksum table in a release tagged with the upstream version, such as `v2.5.5`.

The IDE update service publishes a SHA-256 for the archive, and a download that
does not match it fails the workflow. This is a vendor checksum, not a signed
attestation. A mismatch between the
workflow's preflight download and the builder's download fails the build rather
than packaging unverified bytes.

## Local development

The workflow is the supported reproducible build path because the official
download URL is dynamic. To inspect the resolver locally:

```bash
python3 scripts/resolve-release.py
```

The AppImage is built with the `Mate-Logic/appimage-python` GitHub Action. The
repository intentionally contains only the desktop integration files and the
workflow-specific resolver.

## License

This project is distributed under the MIT License. See [LICENSE](LICENSE).
