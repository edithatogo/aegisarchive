# Native implementation and review checkpoint

The track remains **in progress** and is **not archive eligible** while the full native platform matrix is pending. Adapter tests are not native acceptance evidence.

## Actual macOS acceptance

The internally stored macOS ARM64 package contains 14 asset records and 9,516 immutable files totalling 9,518,169,205 bytes. The complete package was relocated from an assembly directory to a path containing spaces, then to durable internal storage. The final run used bundled CPython, an empty inherited environment with declared OS shell paths, and an inherited macOS sandbox denying external traffic while allowing loopback IPC.

All 13 checks passed: OS external-egress denial, bundled interpreter identity, complete integrity before execution, Scout inference, General inference, Deep inference, Piper synthesis, Whisper transcription of synthesized audio, real BGE384 embeddings with distinct-text and semantic-only retrieval assertions plus hybrid search and sourced graph, Git init/add/commit/fsck/readback, console script execution, relocated launcher help, and complete integrity after execution.

Evidence: [native receipt](native-evidence/darwin-full-native.json), [package inventory and manifest digest](native-evidence/darwin-package.json), [native dependency audit](native-evidence/darwin-dependencies.json), and [network policy](native-evidence/offline-macos.sb). The load-command audit inspected 354 native files and found no absolute load dependency or search path outside macOS system locations. Two dylib build identifiers refer to an old build directory; these are LC_ID_DYLIB identifiers, not loading instructions.

## Provisioning and resource records

`portable/model-lock.json` pins all five model files and their licences/cards by exact source revision, SHA-256 and byte size. Scout is Qwen2.5 1.5B Instruct Q4_K_M, General Qwen3 4B Q4_K_M, and Deep Qwen3 8B Q4_K_M; Whisper tiny.en and BGE small en v1.5 Q8_0 complete the set. The five weights total 8,756,774,347 bytes. Recommended one-model-at-a-time RAM is 4/8/12 GiB for inference tiers at 2,048 tokens; transcription and embeddings each have a 1 GiB planning allowance, and voice 0.5 GiB. These are estimates, not measured peak-RSS guarantees.

Runtime pins and acquisition/build provenance are in the native provisioners and package inventory. The macOS bundle includes Git 2.55.0, Bash 5.3, llama.cpp b10819, pinned whisper.cpp source, Piper 1.8.0 and its native dependencies, bundled Python, and the pinned LJSpeech medium English voice. Component licences are retained separately; the repository licence does not replace them. The selected macOS speech wheels require macOS 14 or later.

## Review fixes

- Replacing source text now invalidates graph edges citing that text; identical text updates retain them.
- Extreme finite vectors use scaled normalization without overflow or underflow.
- Native qualification requires semantically distinct embeddings and semantic-only retrieval, functional Git and console execution, and post-execution integrity.
- Piper Python entrypoints use the verified bundled interpreter in isolated mode. Runtime invocations suppress bytecode and user-site loading.
- Relocated launcher regression executes literal arguments through the explicit bundled interpreter on both POSIX launchers, and the Windows launcher script keeps the same isolated interpreter flags.
- Semantic-only retrieval no longer fuses an empty lexical ranking; qualification fails if that score is mixed.
- Model receipts use securely created temporary files and atomic replacement; 12 regression cases cover cache integrity, resume behavior, lock validation and malicious old receipt symlinks.

Focused packaging/intelligence tests passed 18 cases; the repository gate passed 48 Python and 36 Node cases. The 18 station-hardening tests passed. No native claim rests on these unit tests alone. T4 stays in progress: Done-when still requires full native receipts on each target OS.

## Remaining acceptance and storage recovery

T4 code review-fixes are in the tree. T4 is not complete: Linux and Windows full native qualification receipts are absent, and the hosted full native matrix remains pending (gate `full-native-platforms`). The existing Darwin ARM64 receipt is preserved as direct execution evidence for that one host; it does not close the OS matrix. Do not treat adapter tests or a single-platform receipt as complete native acceptance.

The Python/SQLite/CLI foundation previously passed on all three hosted OS targets in run 33968041129. Foundation success does not substitute for inference/speech/retrieval acceptance. Archive only after all full native receipts and applicable review fixes pass, and final runtime payloads/provenance are retained.

The DM ExFAT volume unmounted during an earlier native run and failed normal and read-only mount attempts. No disk repair was attempted. Source was recovered to an internal checkout from the sealed package and exact task transcripts, revalidated and pushed. The failed receipt write is not successful evidence. The complete macOS package and final receipts are retained under `/Users/doughnut/.codex/artifacts/aegisarchive-20260905/`; synchronization to the original DM checkout requires recovery of that volume.
