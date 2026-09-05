# Offline package assembly

Run from the repository with Python 3:

```sh
python3 portable/packaging.py build . /path/outside/repository/AegisArchive --assets /path/assets.json
python3 portable/packaging.py verify /path/outside/repository/AegisArchive
```

Assembly creates `app/`, mutable `data/`, `runtime/`, `licenses/`, and
`manifest.json`. The output must not already exist. Run the platform launcher
inside `app/`; the launcher still requires a compatible Python interpreter.
Assembly does not download or claim to supply Python, Git, a console, engines,
or models. Supply independently vetted runtime archives explicitly.

`assets.json` is a JSON list. Each entry has this shape (substitute the real
independently verified checksum and source; the placeholder is not usable):

```json
[
  {
    "id": "llama",
    "platform": "darwin-arm64",
    "archive": "/path/to/vetted-release.tar.gz",
    "sha256": "REPLACE_WITH_RELEASE_SHA256",
    "source_url": "https://github.com/ggml-org/llama.cpp/releases",
    "license": "MIT",
    "license_file": "LICENSE",
    "entrypoint": "bin/llama-cli"
  }
]
```

The licence file and entrypoint must exist within the archive. Preserve upstream
licence and attribution requirements; the licence field is a record of the
operator's review, not automatic legal verification. Use separate IDs for each
engine/model asset. Local intelligence adapters recognize `llama`, `scout`,
`general`, `deep`, `whisper`, `whisper_model`, `piper`, `piper_model`, and
`piper_config`. The manifest records source archive digests and individual
extracted file digests. Engines are resolved to `runtime/ID/ENTRYPOINT`.

Only ordinary files and directories are extracted. Links, device files, unsafe
Windows names, traversal paths, duplicate names, and archives over the expanded
size limit are rejected. Use an archive layout without symbolic links. The
package excludes Python bytecode caches and rejects symlinks in application
sources. Verification allows changes under `data/`, and rejects changed,
missing, or additional immutable files. It does not authenticate the manifest:
publish its digest or signature through an independently trusted channel.

A package with no assets is an application-only package. Passing its integrity
check does not prove native platform compatibility, model quality, offline
engine execution, or that the portable suite acceptance criteria are complete.
