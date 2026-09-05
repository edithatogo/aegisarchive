"""Provision pinned native speech into a portable bundle before network isolation.

Requires a bundled CPython 3.12 interpreter and a native CMake C/C++ toolchain.
Optional third-party Python packages remain isolated under speech/piper-site.
Output speech-assets.json is merged into the caller's LocalTools assets mapping.
The piper entrypoint is Python: launch it with the manifest's bundled python asset.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request

WHISPER_REVISION = "52a939a2a762224e255d366c1182b2af4dd1a032"
WHISPER_SOURCE_SHA256 = "691dfebd9965295c88d7a041d83aae4160977da489cdfc10c082eb2fd1ca8c7d"
PIPER_REVISION = "639388b6317fc4731e91d53da42aea68fd4166ff"
PIPER_SOURCE_SHA256 = "ffdd256e955e9606fbc8bff36a8830d259c69960958c46178a1ecc10a5901370"
VOICE_REVISION = "1162a9173d0ce503555aed757976b7a9912eae4c"
VOICE_FILES = {
    "en_US-ljspeech-medium.onnx": "6f52a751e2349abe7a76735eb09dc1875298c77ea2342ffd2fef79ff81b87f22",
    "en_US-ljspeech-medium.onnx.json": "141d612cc0a95ed7efc1ca936b845c2364967f2e9217c5dbfcf69fc4d6c65860",
    "MODEL_CARD": "fbee1529c89d36b3fe76d7e9f3f832dce17f44900a52d76a9bda735654766b4d",
}
WHEEL_PINS = {'piper-tts': {'version': '1.8.0',
               'wheels': {'piper_tts-1.8.0-cp39-abi3-macosx_10_9_x86_64.whl': '98c7dd791b2be0f8732e5c9cefd86c54200ac0360e43c643c937bf18ac0e941a',
                          'piper_tts-1.8.0-cp39-abi3-macosx_11_0_arm64.whl': '33e7425933e9290fe651ae127916ed1ca6104cfa3d94e9049295dd3a5c449382',
                          'piper_tts-1.8.0-cp39-abi3-manylinux_2_17_aarch64.manylinux2014_aarch64.manylinux_2_28_aarch64.whl': '3f60c1917de6d8e8033f395878ad3f88f6dfee88a8b05f98971a275f76a38484',
                          'piper_tts-1.8.0-cp39-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.manylinux_2_28_x86_64.whl': '25b4d3f31ff70c8fa7151908e00aaa5650cbdf16bca8fcf21299f3941b89a7d3',
                          'piper_tts-1.8.0-cp39-abi3-win_amd64.whl': '5da9bfdb05dfe15da3536859d422e605483ffa6d2b3ec2c5b9593bae6b5aa6a4'}},
 'flatbuffers': {'version': '25.12.19',
                 'wheels': {'flatbuffers-25.12.19-py2.py3-none-any.whl': '7634f50c427838bb021c2d66a3d1168e9d199b0607e6329399f04846d42e20b4'}},
 'numpy': {'version': '2.5.2',
           'wheels': {'numpy-2.5.2-cp312-cp312-macosx_10_13_x86_64.whl': '14e373cfc6387177e8409dac3c7159be8eb05cd77096cd7c950268b86f62831c',
                      'numpy-2.5.2-cp312-cp312-macosx_11_0_arm64.whl': '4bbd96c833ecc8cc069ce518078fc8c60cb9cbfb0fea5b7a803ad65035596d03',
                      'numpy-2.5.2-cp312-cp312-macosx_14_0_arm64.whl': '6e8172ddfcf5cf74b811d372b570b83c60bd2de87a6fbfbebdadb4a9bd9c6cbb',
                      'numpy-2.5.2-cp312-cp312-macosx_14_0_x86_64.whl': '65f188481f1669e26f62b701e8205d19e460fa4a9b52a1414ba382330e4a3414',
                      'numpy-2.5.2-cp312-cp312-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl': '8ee9c4eeb8454b3660a8b53493563c3e121c2fc94fbd72b848ef814ed7b676a9',
                      'numpy-2.5.2-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl': '3cdec01fa790a186d430433fdd4d4ffb70eed6f0eeb4bf05c8dbe2dce0a9bcb8',
                      'numpy-2.5.2-cp312-cp312-musllinux_1_2_aarch64.whl': '7999d4ddb0c4025018373fd787510d46e04c769467af22869707b3c1cfd459ab',
                      'numpy-2.5.2-cp312-cp312-musllinux_1_2_x86_64.whl': 'c1f017dc0875c9209d219f97feceb7d54c2661bb243deb4114478e1295808af7',
                      'numpy-2.5.2-cp312-cp312-win32.whl': 'd6a48072864e3324e194a8fbb3c657bcc5b5c869dbc64c9537b1d5c862572c0a',
                      'numpy-2.5.2-cp312-cp312-win_amd64.whl': '28ac63476ec7651484215ee7fa15a1f78b57c14621f01e392afe17b9a1390ce4',
                      'numpy-2.5.2-cp312-cp312-win_arm64.whl': '27650bb0e7140fa3d37b9923b4803645e0b125d190f326eecfd3f4dad8e8ade1'}},
 'onnxruntime': {'version': '1.29.0',
                 'wheels': {'onnxruntime-1.29.0-cp312-cp312-macosx_14_0_arm64.whl': '3a3814c041251d6a77fdf513fb282056538ee826d2f1178a0df3c549d3fff6ba',
                            'onnxruntime-1.29.0-cp312-cp312-manylinux_2_28_aarch64.whl': 'd2fb19e848f7c33ed8d3182b52504aaa11c5e8da438bbb47296f85b133cbcf6b',
                            'onnxruntime-1.29.0-cp312-cp312-manylinux_2_28_x86_64.whl': '2b80d8c7ec2cc7438e4da3760b88c24568cba72c9ace96d668800a6c79419acb',
                            'onnxruntime-1.29.0-cp312-cp312-win_amd64.whl': '4acf2b4948b7ede87221ca6332344b8facdc8059d6ac751a7d367d04532b02dd',
                            'onnxruntime-1.29.0-cp312-cp312-win_arm64.whl': 'dc61a79cb39afd66ab3f01fd2c23591a7f01de89c1668e1fb6315067fc279164'}},
 'packaging': {'version': '26.3',
               'wheels': {'packaging-26.3-py3-none-any.whl': 'd7193f7c8e4e93f444fde0262bf90af30e16fa0ad0ad44cb553c87339b23cd1c'}},
 'pathvalidate': {'version': '3.3.1',
                  'wheels': {'pathvalidate-3.3.1-py3-none-any.whl': '5263baab691f8e1af96092fa5137ee17df5bdfbd6cff1fcac4d6ef4bc2e1735f'}},
 'protobuf': {'version': '7.36.1',
              'wheels': {'protobuf-7.36.1-cp310-abi3-macosx_10_9_universal2.whl': '3cf2ee25d006cee57294a1196ea43b37feb78e0dcd1e8af5c1aeddb777655aca',
                         'protobuf-7.36.1-cp310-abi3-manylinux2014_aarch64.whl': '43d3d37b1eb24c113b9b7d02008cac44e423f00b611b7781ae998d7623972969',
                         'protobuf-7.36.1-cp310-abi3-manylinux2014_s390x.whl': '39c518c05586c016d7874ff6079ee115bcec1ea5fbb1d177fbf7867ef4c67e44',
                         'protobuf-7.36.1-cp310-abi3-manylinux2014_x86_64.whl': '97198b77e369a0abd8e262b8f6c7266c55ddb796a3a12c76d7b8881188ed83aa',
                         'protobuf-7.36.1-cp310-abi3-win32.whl': '0b53ce95272aad50ad25d7ff03373743209822e8ba42ea7fad27d2bee1547d00',
                         'protobuf-7.36.1-cp310-abi3-win_amd64.whl': '51139351435d9b43d88a55eaa49fb6f737fbb478fb0cbf2cf694d1a04a9d3363',
                         'protobuf-7.36.1-py3-none-any.whl': '7d951e46b3f963d6c264c367c437921de9d5aedd9c3f9612b9077736b4e3ad5c'}}}


PIPER_ENTRY = '''"""Bundle-owned Piper CLI that honors the separately verified voice config."""
import argparse
import os
from pathlib import Path
import sys
import wave

sys.dont_write_bytecode = True
if os.name == "nt":
    _dll_directory = os.add_dll_directory(str(Path(sys.executable).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "piper-site"))
from piper import PiperVoice

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--model", required=True, type=Path)
parser.add_argument("--config", required=True, type=Path)
parser.add_argument("--output_file", required=True, type=Path)
args = parser.parse_args()
sys.stdin.reconfigure(encoding="utf-8")
text = sys.stdin.read()
if not text.strip():
    parser.error("Speech text must not be empty")
voice = PiperVoice.load(str(args.model), config_path=str(args.config), use_cuda=False)
with args.output_file.open("xb") as output:
    with wave.open(output, "wb") as wav_file:
        voice.synthesize_wav(text, wav_file)
'''


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def download(url, target, expected):
    request = urllib.request.Request(url, headers={"User-Agent": "AegisArchive-native-provisioner/1"})
    with urllib.request.urlopen(request, timeout=180) as source, Path(target).open("wb") as output:
        shutil.copyfileobj(source, output)
    actual = digest(target)
    if actual != expected:
        raise ValueError("Downloaded checksum mismatch: " + str(target))
    return {"url": url, "sha256": actual, "bytes": Path(target).stat().st_size}


def normalize(source, target):
    """Copy trusted build output; materialize only internal symlinks as files."""
    root = Path(source).resolve()
    for incoming in sorted(root.rglob("*")):
        if any(part == "__pycache__" or part.startswith("._") for part in incoming.relative_to(root).parts):
            continue
        resolved = incoming.resolve(strict=True)
        if not resolved.is_relative_to(root):
            raise ValueError("Dependency link escapes runtime: " + str(incoming))
        outgoing = Path(target) / incoming.relative_to(root)
        if resolved.is_dir():
            if incoming.is_symlink():
                raise ValueError("Dependency directory symlink requires explicit materialization: " + str(incoming))
            outgoing.mkdir(parents=True, exist_ok=True)
        elif resolved.is_file():
            outgoing.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(resolved, outgoing)
            outgoing.chmod(0o755 if resolved.stat().st_mode & 0o111 else 0o644)
        else:
            raise ValueError("Non-regular dependency: " + str(incoming))


def run(command, log, **kwargs):
    with Path(log).open("a", encoding="utf-8") as output:
        output.write(json.dumps(list(map(str, command))) + "\n")
        output.flush()
        subprocess.run(list(map(str, command)), stdout=output, stderr=subprocess.STDOUT,
                       check=True, timeout=1800, **kwargs)


def provision(destination, python, cmake="cmake", jobs=2):
    destination = Path(destination).resolve()
    python = Path(python).resolve(strict=True)
    version = subprocess.check_output([str(python), "-I", "-c", "import sys; print('%s.%s'%sys.version_info[:2])"], text=True).strip()
    if version != "3.12":
        raise ValueError("Pinned native wheel matrix requires bundled Python 3.12")
    speech = destination / "speech"
    if speech.exists():
        raise ValueError("Refusing to replace an existing speech runtime")
    speech.mkdir(parents=True)
    provenance = {"platform": platform.platform(), "python": str(python),
                  "whisper_revision": WHISPER_REVISION, "piper_revision": PIPER_REVISION, "voice_revision": VOICE_REVISION,
                  "licences": {"whisper": "MIT", "piper": "GPL-3.0", "voice_repository": "MIT", "voice_dataset": "public domain"},
                  "downloads": [], "validation": "provisioning only; native qualification must run separately"}
    with tempfile.TemporaryDirectory(prefix="aegis-speech-build-") as directory:
        work = Path(directory)
        archive = work / "whisper.tar.gz"
        provenance["downloads"].append(download(
            f"https://api.github.com/repos/ggml-org/whisper.cpp/tarball/{WHISPER_REVISION}", archive, WHISPER_SOURCE_SHA256))
        source_root = work / "source"
        source_root.mkdir()
        # Immutable upstream archive: reject every special member before extraction.
        with tarfile.open(archive) as source:
            for member in source:
                parts = Path(member.name).parts
                if member.name.startswith("/") or ".." in parts or not (member.isfile() or member.isdir()):
                    raise ValueError("Unsafe source archive entry: " + member.name)
            source.extractall(source_root, filter="data")
        source = next(source_root.iterdir())
        build = work / "build"
        flags = ["-DCMAKE_BUILD_TYPE=Release", "-DBUILD_SHARED_LIBS=OFF", "-DGGML_METAL=OFF",
                 "-DGGML_NATIVE=OFF", "-DGGML_OPENMP=OFF", "-DWHISPER_BUILD_TESTS=OFF",
                 "-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreaded"]
        if platform.system() == "Linux":
            flags.append("-DCMAKE_EXE_LINKER_FLAGS=-static-libgcc -static-libstdc++")
        run([cmake, "-S", source, "-B", build, *flags], speech / "build.log")
        run([cmake, "--build", build, "--config", "Release", "--target", "whisper-cli", "-j", str(jobs)], speech / "build.log")
        name = "whisper-cli.exe" if os.name == "nt" else "whisper-cli"
        candidates = list((build / "bin").rglob(name))
        if len(candidates) != 1:
            raise ValueError("Expected one whisper binary: " + repr(candidates))
        shutil.copyfile(candidates[0], speech / name)
        (speech / name).chmod(0o755)
        shutil.copyfile(source / "LICENSE", speech / "WHISPER-LICENSE")
        # Retain exact source for reproducibility; no compiler is required at runtime.
        shutil.copyfile(archive, speech / "whisper-source.tar.gz")
        wheels = work / "wheels"
        wheels.mkdir()
        requirements = [f"{name}=={record['version']}" for name, record in WHEEL_PINS.items()]
        run([python, "-I", "-m", "pip", "download", "--disable-pip-version-check", "--only-binary=:all:",
             "--no-deps", "--dest", wheels, *requirements], speech / "pip.log")
        allowed = {filename: checksum for record in WHEEL_PINS.values() for filename, checksum in record["wheels"].items()}
        wheel_paths = sorted(wheels.glob("*.whl"))
        if len(wheel_paths) != len(WHEEL_PINS):
            raise ValueError("Missing native wheels")
        for wheel in wheel_paths:
            expected = allowed.get(wheel.name)
            if expected is None or digest(wheel) != expected:
                raise ValueError("Wheel absent from pinned hash matrix or checksum mismatch: " + wheel.name)
            provenance["downloads"].append({"filename": wheel.name, "sha256": expected,
                                           "source": "https://pypi.org", "bytes": wheel.stat().st_size})
        site = work / "site"
        run([python, "-I", "-m", "pip", "install", "--disable-pip-version-check", "--no-deps", "--no-index",
             "--no-compile", "--target", site, *wheel_paths], speech / "pip.log")
        # pip generates host-prefix console scripts; only our bundled entry is supported.
        omitted = []
        for generated_directory in ("bin", "Scripts"):
            generated = site / generated_directory
            if generated.is_dir():
                omitted.extend(path.relative_to(site).as_posix() for path in generated.rglob("*") if path.is_file())
                shutil.rmtree(generated)
        provenance["omitted_generated_entrypoints"] = sorted(omitted)
        normalize(site, speech / "piper-site")
        # Wheel bundles package and dependency licence files; expose Piper grant.
        copying = site / "COPYING"
        if not copying.exists():
            candidates = list(site.rglob("COPYING"))
            if not candidates:
                raise ValueError("Piper COPYING missing from wheels")
            copying = candidates[0]
        shutil.copyfile(copying, speech / "PIPER-COPYING")
        entry = speech / "piper_entry.py"
        entry.write_text(PIPER_ENTRY, encoding="utf-8")
        run([python, "-X", "utf8", "-I", "-B", entry, "--help"], speech / "pip.log")
        for filename, expected in VOICE_FILES.items():
            url = f"https://huggingface.co/rhasspy/piper-voices/resolve/{VOICE_REVISION}/en/en_US/ljspeech/medium/{filename}"
            provenance["downloads"].append(download(url, speech / filename, expected))
    provenance["downloads"].append(download(
        f"https://api.github.com/repos/OHF-Voice/piper1-gpl/tarball/{PIPER_REVISION}",
        speech / "piper-source.tar.gz", PIPER_SOURCE_SHA256))
    paths = {"whisper": speech / name, "piper": entry,
             "piper_model": speech / "en_US-ljspeech-medium.onnx",
             "piper_config": speech / "en_US-ljspeech-medium.onnx.json"}
    assets = {key: {"path": value.relative_to(destination).as_posix(), "sha256": digest(value)} for key, value in paths.items()}
    assets["piper"]["interpreter"] = "python"
    (destination / "speech-assets.json").write_text(json.dumps(assets, indent=2) + "\n", encoding="utf-8")
    (speech / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"speech": str(speech), "assets": str(destination / "speech-assets.json")}))
    return assets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument("--python", required=True, type=Path)
    parser.add_argument("--cmake", default="cmake")
    parser.add_argument("--jobs", type=int, default=2)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 64:
        parser.error("--jobs must be between 1 and 64")
    provision(args.destination, args.python, args.cmake, args.jobs)


if __name__ == "__main__":
    main()
