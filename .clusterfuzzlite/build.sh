#!/bin/bash -eu
# Build every tests/fuzz/fuzz_*.py harness into a standalone fuzzer binary.
# compile_python_fuzzer is provided by the oss-fuzz python base image (pyinstaller wrapper).
cd "$SRC/aegisarchive"
for harness in tests/fuzz/fuzz_*.py; do
  compile_python_fuzzer "$harness" \
    --paths=tests/fuzz --paths=cli --paths=. \
    --hidden-import=_harness --hidden-import=warc_verify --hidden-import=mcp.server
done
