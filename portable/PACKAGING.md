# Offline package assembly

Run from the repository with Python 3:

```sh
python3 portable/packaging.py build . /path/outside/repository/AegisArchive --assets /path/assets.json
python3 portable/packaging.py verify /path/outside/repository/AegisArchive
```

Assembly creates `app/`, mutable `data/`, `runtime/`, `licenses/`, and
`manifest.json`. The output must not already exist. When a `python` asset is supplied, run the platform launcher at the package
root: it locates the bundled interpreter after relocation and disables user-site
imports and bytecode writes. The source launchers inside `app/` require host Python.
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
`piper_config`, `python`, `git`, `console`, `llama_server`, and `bge`.
A Python Piper entrypoint uses the verified `python` asset in isolated mode. The manifest records source archive digests and individual
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

`provision_native.py --inventory` records pinned runtimes, models, licences and
source URLs. `--verify-bundle` fail-closes on missing or mutated files.
`--smoke-bundle` may claim inference only from a real native qualification
receipt; it never records a passed model run for a missing package.

`--acquire` downloads pinned runtime archives (Python, llama.cpp, Git, Bash,
PortableGit, speech sources, Piper voice, and selected wheels) plus lock-file
models and verifies SHA-256. `--max-bytes` skips oversized GGUF files and
leaves `models_complete` false. A checksum mismatch records `status: failed`
and a non-zero exit when runtimes are incomplete. Acquisition never sets
`inference_claimed`.
