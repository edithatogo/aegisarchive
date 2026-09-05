"""Run native offline acceptance against a relocated, provisioned bundle.

Invoke with its bundled Python under an OS egress-denying policy. This writes a
receipt after every step and exits nonzero if any required check fails.
"""
import argparse
import array
import errno
import json
import os
from pathlib import Path
import platform
import re
import socket
import subprocess
import sys
import time
import wave

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from portable.intelligence import LocalTools, Memory
from portable.gguf_embeddings import GGUFEmbedder
from portable.packaging import verify


def resample(source, destination):
    with wave.open(str(source), 'rb') as reader:
        if reader.getnchannels() != 1 or reader.getsampwidth() != 2:
            raise ValueError('Expected mono PCM16 speech')
        rate = reader.getframerate()
        samples = array.array('h', reader.readframes(reader.getnframes()))
    if sys.byteorder != 'little':
        samples.byteswap()
    output = array.array('h')
    for index in range(int(len(samples) * 16000 / rate)):
        point = index * rate / 16000
        left = int(point)
        right = min(left + 1, len(samples) - 1)
        output.append(round(samples[left] + (samples[right] - samples[left]) * (point - left)))
    if sys.byteorder != 'little':
        output.byteswap()
    with wave.open(str(destination), 'wb') as writer:
        writer.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
        writer.writeframes(output.tobytes())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle', type=Path)
    parser.add_argument('receipt', type=Path)
    args = parser.parse_args()
    bundle = args.bundle.resolve(strict=True)
    report = {'platform': platform.platform(), 'machine': platform.machine(),
              'python': sys.executable, 'bundle': str(bundle), 'checks': {}, 'status': 'running'}
    args.receipt.parent.mkdir(parents=True, exist_ok=True)

    def record(name, operation):
        started = time.monotonic()
        try:
            result = operation()
            report['checks'][name] = {'status': 'passed', 'result': result}
        except Exception as error:
            report['checks'][name] = {'status': 'failed', 'error': str(error)}
            if isinstance(error, (subprocess.CalledProcessError, subprocess.TimeoutExpired)):
                for field in ('stdout', 'stderr'):
                    value = getattr(error, field, None)
                    if isinstance(value, bytes):
                        value = value.decode('utf-8', errors='replace')
                    if value:
                        report['checks'][name][field] = value[-6000:]
                report['checks'][name]['returncode'] = getattr(error, 'returncode', None)
            raise
        finally:
            report['checks'][name]['seconds'] = time.monotonic() - started
            args.receipt.write_text(json.dumps(report, indent=2) + '\n')

    def egress():
        with socket.socket() as probe:
            probe.settimeout(3)
            try:
                probe.connect(('1.1.1.1', 443))
            except OSError as error:
                if error.errno in (errno.EPERM, errno.EACCES, errno.ENETUNREACH):
                    return {'blocked_errno': error.errno}
                raise RuntimeError('No verified OS network denial: ' + str(error))
            raise RuntimeError('External network connection permitted')

    try:
        record('external_egress_denied', egress)
        tools = LocalTools(bundle / 'manifest.json')
        expected_python = tools.asset('python')
        record('bundled_python', lambda: same_file(expected_python, Path(sys.executable)))
        record('integrity', lambda: {'immutable_files': len(verify(bundle)['files'])})
        data = bundle / 'data' / ('qualification-' + str(time.time_ns()))
        data.mkdir()
        for tier in ('scout', 'general', 'deep'):
            def generate(tier=tier):
                output = tools.generate('Reply with the word ARCHIVE only. /no_think', tier, 64)
                if not re.search(r'^ARCHIVE[.!]?\s*$', output, re.M | re.I):
                    raise RuntimeError('Expected generated answer absent: ' + output[-1000:])
                return {'generated_output': output[-2000:]}
            record(tier, generate)
        text = 'The archive is available offline. All evidence is stored locally.'
        record('synthesis', lambda: str(tools.speak(text, data / 'speech.wav')))
        resample(data / 'speech.wav', data / 'speech16.wav')
        def transcribe():
            output = tools.transcribe(data / 'speech16.wav')
            if 'archive' not in output.lower() or 'offline' not in output.lower():
                raise RuntimeError('Unexpected transcription: ' + output)
            return output
        record('transcription', transcribe)
        def retrieval():
            with GGUFEmbedder(bundle / 'manifest.json') as encoder:
                vector = encoder.encode('The archive preserves water reports.')
                if len(vector) != 384:
                    raise ValueError('BGE small must produce 384 dimensions')
                memory = Memory(data / 'memory.sqlite')
                try:
                    memory.put('water', 'The archive preserves water reports.', vector)
                    forest = encoder.encode('The forest contains trees.')
                    if sum((a-b)**2 for a,b in zip(vector, forest)) < 0.01:
                        raise ValueError('Unrelated texts must have distinct embeddings')
                    memory.put('trees', 'The forest contains trees.', forest)
                    memory.relate('archive', 'preserves', 'water reports', 'water')
                    results = memory.search('water reports', encoder.encode('water reports', query=True))
                    semantic = memory.search('', encoder.encode('potable supply monitoring', query=True))
                    graph = memory.neighbors('archive')
                    if results[0]['id'] != 'water' or semantic[0]['id'] != 'water' or graph[0]['document'] != 'water':
                        raise ValueError('Retrieval or source graph mismatch')
                    return {'dimensions': len(vector), 'results': results, 'semantic_only': semantic, 'graph': graph}
                finally:
                    memory.close()
        record('embeddings_hybrid_graph', retrieval)
        def git_check():
            workspace = data / 'git-test'
            workspace.mkdir()
            executable = str(tools.asset('git'))
            environment = {**os.environ, 'GIT_CONFIG_NOSYSTEM': '1',
                           'GIT_CONFIG_GLOBAL': os.devnull}
            def git(*args):
                return subprocess.check_output([executable, *args], cwd=workspace,
                    env=environment, text=True, stderr=subprocess.STDOUT, timeout=60)
            git('init')
            (workspace / 'evidence.txt').write_text('Offline portable evidence.\n')
            git('add', 'evidence.txt')
            git('-c', 'user.name=Portable Test', '-c', 'user.email=portable@example.invalid',
                '-c', 'commit.gpgsign=false', 'commit', '-m', 'offline evidence')
            git('fsck', '--full')
            if git('show', 'HEAD:evidence.txt') != 'Offline portable evidence.\n':
                raise ValueError('Git commit readback mismatch')
            return {'version': git('--version'), 'commit': git('rev-parse', 'HEAD').strip()}
        record('git', git_check)
        def console_check():
            output = subprocess.check_output([str(tools.asset('console')), '--noprofile',
                '--norc', '-c', 'printf "%s" "$1"', 'portable', 'ARCHIVE'],
                text=True, timeout=60)
            if output != 'ARCHIVE':
                raise ValueError('Console execution mismatch')
            return output
        record('console', console_check)
        launcher = 'START_WINDOWS.cmd' if os.name == 'nt' else ('START_MAC.command' if sys.platform == 'darwin' else 'START_LINUX.sh')
        launcher_command = [str(bundle / launcher), '--help']
        if os.name == 'nt':
            launcher_command = [str(Path(os.environ['SystemRoot']) / 'System32/cmd.exe'),
                                '/d', '/c', 'call', *launcher_command]
        record('relocated_launcher', lambda: subprocess.check_output(launcher_command, text=True, timeout=60))
        record('integrity_after', lambda: {'immutable_files': len(verify(bundle)['files'])})
        report['status'] = 'passed'
    except Exception:
        report['status'] = 'failed'
    args.receipt.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'status': report['status'], 'checks': {k: v['status'] for k,v in report['checks'].items()}}))
    return 0 if report['status'] == 'passed' else 1


def same_file(expected, actual):
    if expected.resolve() != actual.resolve():
        raise ValueError('Qualification must use bundled Python: ' + str(expected))
    return str(actual)


if __name__ == '__main__':
    raise SystemExit(main())
