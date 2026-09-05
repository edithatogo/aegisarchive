"""Shared runner: use atheris when available, otherwise a stdlib random smoke loop.

Each harness defines ``TestOneInput(data: bytes) -> None`` and calls ``run(TestOneInput)``.
``--smoke N`` (or a missing atheris module) runs N random inputs with the stdlib only.
"""
import os
import random
import sys


def run(test_one_input):
    argv = sys.argv[1:]
    smoke = None
    if "--smoke" in argv:
        idx = argv.index("--smoke")
        smoke = int(argv[idx + 1]) if idx + 1 < len(argv) else 200
    try:
        import atheris  # noqa: F401  (dev-only; tests/requirements-dev.txt)
    except ImportError:
        atheris = None
    if smoke is None and atheris is not None:
        atheris.Setup(sys.argv, test_one_input)
        atheris.Fuzz()
        return
    rng = random.Random(int(os.environ.get("FUZZ_SEED", "1")))
    for _ in range(smoke or 200):
        size = rng.randint(0, 512)
        test_one_input(bytes(rng.getrandbits(8) for _ in range(size)))
    print("%s: smoke OK (%d inputs)" % (os.path.basename(sys.argv[0]), smoke or 200))
