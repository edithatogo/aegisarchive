"""Acquire pinned assets, assemble a native bundle, and qualify it offline.

Provisioning uses the network. Qualification is a separate child behind an OS
network boundary and uses the relocated package's interpreter and runtimes.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from portable.native_platform_probe import ASSETS, RELEASE, VERSION
from portable.packaging import assemble, digest
from portable.provision_models import main as models_main, load_lock
from portable.provision_speech import provision as speech_provision, normalize

LLAMA = {
    'Darwin': ('llama-b10819-bin-macos-arm64.tar.gz', '8933e736495eadfef0731ae32054acfaa75699bf4a6ccba77cd8475db085ec66'),
    'Linux': ('llama-b10819-bin-ubuntu-x64.tar.gz', 'bff96585dfa126d2bc915367b3735982a5e67ddf887138a7c6e9d7cc9b438146'),
    'Windows': ('llama-b10819-bin-win-cpu-x64.zip', '4599e502b374196d24600ea9b03c842a448c853116a15b55e8ba502bdc727b3f'),
}
GIT_URL = 'https://github.com/git/git/archive/refs/tags/v2.55.0.tar.gz'
GIT_SHA = '72923418db7b26dfddc21e2268660c5118e560bdfaa09b4489b67b38e9b69c49'
BASH_URL = 'https://ftp.gnu.org/gnu/bash/bash-5.3.tar.gz'
BASH_SHA = '0d5cd86965f869a26cf64f4b71be7b96f90a3ba8b3d74e27e8e9d9d5550f31ba'
WIN_GIT_URL = 'https://github.com/git-for-windows/git/releases/download/v2.55.0.windows.5/PortableGit-2.55.0.5-64-bit.7z.exe'
WIN_GIT_SHA = '5aa8a20f6e9abb2c755f0e73c91c687701a46b309ad84a0ca6509380fa4ae290'

PYTHON_LICENSES = {'LICENSE': '1f256ecad192880510e84ad60474eab7589218784b9a50bc7ceee34c2b91f1d5', 'LICENSE.bzip2.txt': '1f38bbc7caacafd65169276d759c0d88c991b753b643ce35d0e45ea1971dd441', 'LICENSE.cpython.txt': '86e61415828a8b5b06ec8d024e6f086ce155a8b85fd0c419c0ba4dc004e74fdd', 'LICENSE.expat.txt': '122f2c27000472a201d337b9b31f7eb2b52d091b02857061a8880371612d9534', 'LICENSE.libedit.txt': '29cea33c32bbc9785142386377915612a2fa786482c46843383384aded2e09b1', 'LICENSE.libffi.txt': 'deaf3a42effb551a5b140fa9afefed183a27f1341c6d1bf430d106a5e6931fc0', 'LICENSE.liblzma.txt': '9a4062de0a2c388a98cf35a35d348b62fa97c838a71c3c28ee1a2d7d0a565b02', 'LICENSE.mpdecimal.txt': '669512af7219f58be03a398766d7c9da11a3b3df9d3f05cb74c5ceca25c8da3b', 'LICENSE.ncurses.txt': '87a4c4442337b8968ef956031c406b74f9cb7149b7ba87311bdaba534816201c', 'LICENSE.openssl-3.txt': '7d5450cb2d142651b8afa315b5f238efc805dad827d91ba367d8516bc9d49e7a', 'LICENSE.sqlite.txt': '38bef3d28b24f145ea293bd3b6eb4b20396982abc8303128fb493986ea5bc719', 'LICENSE.tcl.txt': 'c0a69a2bfd757361ec7e6143973b103c90409316b49e9c88db26ad6388e79f16', 'LICENSE.tix.txt': '3ac5cdd0bef6c43ce34c6a7ced452081d9e5a0bf94082b9f9147d23ec9e214f5', 'LICENSE.zlib.txt': '818922b2620f12801a12bf78e399644a30990e66824abd8ca8ec24d451d6f92c'}


def fetch(url, target, sha, receipt):
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists() or digest(target) != sha:
        temporary = target.with_suffix(target.suffix + '.part')
        with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent':'AegisArchive-provisioner/1'}), timeout=180) as source, temporary.open('wb') as output:
            shutil.copyfileobj(source, output)
        if digest(temporary) != sha:
            raise ValueError('Upstream checksum mismatch: ' + url)
        os.replace(temporary, target)
    receipt.append({'url': url, 'sha256': sha, 'bytes': target.stat().st_size})
    return target


def unpack(archive, destination):
    """Only call after upstream SHA verification; reject escaping links."""
    destination.mkdir(parents=True)
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as bundle:
            for name in bundle.namelist():
                if not (destination / name).resolve().is_relative_to(destination.resolve()):
                    raise ValueError('Archive path escapes destination')
            bundle.extractall(destination)
    else:
        with tarfile.open(archive) as bundle:
            bundle.extractall(destination, filter='data')
    for path in destination.rglob('*'):
        if not path.resolve().is_relative_to(destination.resolve()):
            raise ValueError('Upstream link escapes runtime')


def run(command, log, **kwargs):
    print('Running:', ' '.join(map(str, command)), flush=True)
    with log.open('a') as out:
        subprocess.run(list(map(str, command)), stdout=out, stderr=subprocess.STDOUT,
                       check=True, timeout=1800, **kwargs)


def asset_record(identifier, directory, entrypoint, license_file, license_id, source, work, platform_id, **extra):
    archive = work / 'archives' / (identifier + '.tar')
    archive.parent.mkdir(exist_ok=True)
    with tarfile.open(archive, 'w', dereference=True) as bundle:
        for item in sorted(directory.rglob('*')):
            if item.is_file() and not any(p.startswith('._') or p == '__pycache__' for p in item.relative_to(directory).parts):
                info = bundle.gettarinfo(str(item), item.relative_to(directory).as_posix())
                info.uid = info.gid = 0
                info.uname = info.gname = ''
                with item.open('rb') as source_file:
                    bundle.addfile(info, source_file)
    return dict(id=identifier, platform=platform_id, archive=str(archive), sha256=digest(archive),
                source_url=source, license=license_id, license_file=license_file,
                entrypoint=entrypoint, **extra)


def git_console(work, receipts, system):
    if system == 'Windows':
        archive = fetch(WIN_GIT_URL, work/'downloads/portablegit.exe', WIN_GIT_SHA, receipts)
        output = work/'git-console'
        sevenzip = Path(os.environ.get('ProgramFiles', 'C:/Program Files'))/'7-Zip/7z.exe'
        run([sevenzip, 'x', archive, '-o'+str(output), '-y'], work/'git-build.log')
        # Full official PortableGit provides all DLLs and its console tools.
        fetch('https://raw.githubusercontent.com/git/git/v2.55.0/COPYING',output/'GIT-COPYING',
              '5b2198d1645f767585e8a88ac0499b04472164c0d2da22e75ecf97ef443ab32e',receipts)
        bash_archive=fetch(BASH_URL,work/'downloads/bash.tar.gz',BASH_SHA,receipts)
        unpack(bash_archive,work/'bash-source')
        shutil.copyfile(next((work/'bash-source').iterdir())/'COPYING',output/'BASH-COPYING')
        return output, 'cmd/git.exe', output, 'usr/bin/bash.exe', 'GIT-COPYING', 'BASH-COPYING', WIN_GIT_URL
    git_archive = fetch(GIT_URL, work/'downloads/git.tar.gz', GIT_SHA, receipts)
    bash_archive = fetch(BASH_URL, work/'downloads/bash.tar.gz', BASH_SHA, receipts)
    unpack(git_archive, work/'git-source')
    unpack(bash_archive, work/'bash-source')
    git_source = next((work/'git-source').iterdir())
    bash_source = next((work/'bash-source').iterdir())
    installed = work/'git-installed'
    options = [f'prefix={installed}', 'NO_GETTEXT=YesPlease', 'NO_PERL=YesPlease', 'NO_TCLTK=YesPlease',
               'NO_PYTHON=YesPlease', 'NO_CURL=YesPlease', 'NO_EXPAT=YesPlease', 'RUNTIME_PREFIX=YesPlease']
    if system == 'Linux':
        static_z = subprocess.check_output(['cc', '-print-file-name=libz.a'], text=True).strip()
        if not Path(static_z).is_file():
            raise ValueError('Native Git build requires static zlib development archive')
        options += ['EXTLIBS='+static_z+' -lpthread -lrt', 'LDFLAGS=-static-libgcc']
    run(['make', '-C', git_source, '-j2', *options, 'install'], work/'git-build.log')
    git = work/'git'
    (git/'bin').mkdir(parents=True)
    shutil.copyfile(installed/'bin/git', git/'bin/git')
    (git/'bin/git').chmod(0o755)
    shutil.copytree(installed/'share/git-core/templates', git/'share/git-core/templates')
    shutil.copyfile(git_source/'COPYING', git/'COPYING')
    # Small native dispatcher preserves every builtin alias without symlinks or
    # hundreds of copies of the full git executable in a regular-files bundle.
    shim = work/'git-shim.c'
    shim.write_text('''/* SPDX-License-Identifier: MIT */
#include <stdlib.h>
#include <stdint.h>
#include <limits.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#ifdef __APPLE__
#include <mach-o/dyld.h>
#endif
int main(int argc,char **argv){char p[PATH_MAX],r[PATH_MAX],t[PATH_MAX];
#ifdef __APPLE__
uint32_t n=sizeof(p);if(_NSGetExecutablePath(p,&n))return 126;
#else
ssize_t n=readlink("/proc/self/exe",p,sizeof(p)-1);if(n<0)return 126;p[n]=0;
#endif
if(!realpath(p,r))return 126;char*s=strrchr(r,'/');if(!s)return 126;*s=0;
if(snprintf(t,sizeof(t),"%s/../../bin/git",r)>=sizeof(t))return 126;
execv(t,argv);perror("bundled git");return 126;}
''')
    run(['cc', '-Os', shim, '-o', work/'git-shim'], work/'git-build.log')
    aliases=git/'libexec/git-core';aliases.mkdir(parents=True)
    for candidate in (installed/'libexec/git-core').iterdir():
        if candidate.is_file() and os.path.samefile(candidate, installed/'bin/git'):
            shutil.copyfile(work/'git-shim', aliases/candidate.name)
            (aliases/candidate.name).chmod(0o755)
    shutil.copyfile(shim, git/'git-shim.c')
    console=work/'console';console.mkdir()
    run([bash_source/'configure', '--prefix='+str(work/'bash-installed'), '--without-bash-malloc', '--disable-nls', '--disable-readline'], work/'bash-build.log', cwd=bash_source)
    run(['make', '-j2'], work/'bash-build.log', cwd=bash_source)
    (console/'bin').mkdir()
    shutil.copyfile(bash_source/'bash',console/'bin/bash');(console/'bin/bash').chmod(0o755)
    shutil.copyfile(bash_source/'COPYING',console/'COPYING')
    return git,'bin/git',console,'bin/bash','COPYING','COPYING',GIT_URL


def retain_linux_libraries(root, receipts):
    """Retain non-glibc ELF dependencies and make their lookup relocatable."""
    system_names=('libc.so', 'libm.so', 'libdl.so', 'librt.so', 'libpthread.so', 'ld-linux')
    original=[]
    for path in root.rglob('*'):
        if path.is_file():
            with path.open('rb') as source:
                if source.read(4)==b'\x7fELF':original.append(path)
    copied=set()
    for elf in original:
        queue=[elf];visited=set();destinations={elf}
        while queue:
            current=queue.pop()
            if current in visited:continue
            visited.add(current)
            listing=subprocess.check_output(['ldd',str(current)],text=True)
            if 'not found' in listing:raise ValueError('Unresolved native dependency: '+listing)
            for dependency in re.findall(r'=> (/[^ ]+)',listing):
                source=Path(dependency)
                if source.name.startswith(system_names):continue
                target=elf.parent/source.name
                if not target.exists():
                    shutil.copyfile(source,target);target.chmod(0o755)
                    copied.add(str(source))
                queue.append(source)
                destinations.add(target)
        for current in destinations:
            subprocess.run(['patchelf','--set-rpath','$ORIGIN',str(current)],check=True)
    notices=root/'dependency-licenses';notices.mkdir(exist_ok=True)
    for package in ('gcc-14-base','gcc-13-base','libstdc++6','libgomp1','zlib1g'):
        notice=Path('/usr/share/doc')/package/'copyright'
        if notice.is_file():shutil.copyfile(notice,notices/(package+'.txt'))
    receipts.append({'native_dependency_intake':sorted(copied),'system_baseline':'Linux glibc/loader',
                     'relocation':'ELF RUNPATH=$ORIGIN; non-glibc shared libraries copied'})


def qualify(bundle, receipt, work, system):
    python=bundle/'runtime/python'/('python.exe' if system=='Windows' else 'bin/python3')
    command=[str(python),'-I','-B',str(bundle/'app/portable/native_qualification.py'),str(bundle),str(receipt)]
    env=dict(os.environ)
    for key in tuple(env):
        if key.startswith('PYTHON'):env.pop(key)
    # Root launchers use only declared OS shell utilities plus bundled Python.
    env['PATH']=str(bundle/'runtime/git/bin')+os.pathsep+('/usr/bin:/bin' if system!='Windows' else os.environ['SystemRoot']+'\\System32')
    env['OMP_NUM_THREADS']='2'
    policy_receipt=receipt.with_name('network-policy.json')
    policy_evidence={'platform':system,'scope':'all qualification descendants' if system!='Windows' else 'all bundled executable files; hosted runner remains online',
                     'native_receipt':str(receipt),'enforcement_check':'external_egress_denied must pass inside child'}
    if system=='Windows':
        policy_evidence['executables']=[{'path':str(p.resolve()),'sha256':digest(p)} for p in bundle.rglob('*.exe')]
        policy_evidence['rule_count']=len(policy_evidence['executables'])
    policy_receipt.write_text(json.dumps(policy_evidence,indent=2)+'\n')
    if system=='Darwin':
        policy='(version 1)(allow default)(deny network*)(allow network-inbound (local ip "localhost:*"))(allow network-outbound (remote ip "localhost:*"))'
        policy_evidence['policy']=policy;policy_receipt.write_text(json.dumps(policy_evidence,indent=2)+'\n')
        subprocess.run(['/usr/bin/sandbox-exec','-p',policy,*command],env=env,check=True,timeout=3000)
    elif system=='Linux':
        # New namespace has no external interfaces/routes; enable loopback for BGE.
        network=work/'network.sh'
        network.write_text('#!/bin/sh\nset -eu\n/sbin/ip link set lo up\nexec "$@"\n');network.chmod(0o755)
        policy_evidence['policy']='unshare --net; loopback up; no external interface or route';policy_receipt.write_text(json.dumps(policy_evidence,indent=2)+'\n')
        subprocess.run(['/usr/bin/sudo','/usr/bin/unshare','--net','--',str(network),*command],env=env,check=True,timeout=3000)
    else:
        script=work/'restrict-full.ps1'
        script.write_text("""$ErrorActionPreference='Stop'
$cmd=ConvertFrom-Json $env:AEGIS_FULL_COMMAND
$root=$env:AEGIS_FULL_BUNDLE
$rules=@()
try {
 if(Get-NetFirewallProfile | Where-Object { $_.Enabled -ne 'True' }) { throw 'Firewall disabled' }
 foreach($exe in Get-ChildItem -LiteralPath $root -Recurse -Filter *.exe) {
  $rule='AegisFull-'+[guid]::NewGuid().ToString()
  New-NetFirewallRule -DisplayName $rule -Direction Outbound -Action Block -Enabled True -Profile Any -Program $exe.FullName -RemoteAddress '0.0.0.0-126.255.255.255','128.0.0.0-255.255.255.255','::2-ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff' | Out-Null
  $rules+=$rule
  $active=Get-NetFirewallRule -DisplayName $rule -PolicyStore ActiveStore
  if($active.Action -ne 'Block' -or $active.Enabled -ne 'True'){throw 'Native executable firewall rule not active'}
 }
 & $cmd[0] $cmd[1..($cmd.Length-1)]
 if($LASTEXITCODE -ne 0){throw 'Native qualification failed'}
} finally {foreach($rule in $rules){Remove-NetFirewallRule -DisplayName $rule -ErrorAction SilentlyContinue}}
""")
        policy_evidence['policy']='ActiveStore outbound block per bundled EXE, all profiles; exclude IPv4 127/8 and IPv6 ::1';policy_receipt.write_text(json.dumps(policy_evidence,indent=2)+'\n')
        env['AEGIS_FULL_COMMAND']=json.dumps(command);env['AEGIS_FULL_BUNDLE']=str(bundle)
        powershell=Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
        subprocess.run([str(powershell),'-NoProfile','-ExecutionPolicy','Bypass','-File',str(script)],env=env,check=True,timeout=3000)


def retain_runtime_payload(bundle, output, model_lock):
    """Retain qualified runtime bytes once; common heavy models stay deduplicated."""
    omitted=[]
    for model in model_lock['models']:
        entry=model['files'][0]
        identifier={'transcription':'whisper_model','embeddings':'bge'}.get(model['role'],model['role'])
        omitted.append({'package_path':'runtime/'+identifier+'/'+Path(entry['path']).name,
                        'cache_path':entry['path'],'sha256':entry['sha256'],
                        'size_bytes':entry['size_bytes'],'url':entry['url'],'role':model['role']})
    skip={entry['package_path'] for entry in omitted}
    payload=output/'qualified-runtime.tar.gz'
    with tarfile.open(payload,'w:gz',compresslevel=1,dereference=True) as archive:
        for item in sorted(bundle.rglob('*')):
            relative=item.relative_to(bundle).as_posix()
            if relative in skip or relative.startswith('data/'):continue
            archive.add(item,arcname=relative,recursive=False)
    (output/'restore-models.json').write_text(json.dumps({'omitted_models':omitted,
        'runtime_payload_sha256':digest(payload),'complete_manifest_sha256':digest(bundle/'manifest.json')},indent=2)+'\n')
    (output/'RESTORE.md').write_text(
        'Qualified native runtime delivery\n\n'
        'Extract qualified-runtime.tar.gz into a new empty directory. Five common model files are omitted to avoid storing identical multi-gigabyte assets for each OS. All native runtime, voice, application, licence and manifest bytes are retained.\n\n'
        'Provision the exact locked model cache with app/portable/provision_models.py --output <model-cache> using Python3. Then run restore_models.py --package <extracted-directory> --models <model-cache>. The helper verifies each model against restore-models.json, copies it to the exact manifest path, and verifies the complete assembled package. Use bundled runtime/python/bin/python3 on POSIX or runtime/python/python.exe on Windows.\n\n'
        'The retained native-qualification.json applies to the original complete assembled bytes. The final complete manifest validates the reconstructed bytes. Runtime payload retention is one day; download promptly.\n')
    (output/'restore_models.py').write_text("""import argparse, hashlib, json, shutil, sys
from pathlib import Path
sys.dont_write_bytecode=True
p=argparse.ArgumentParser();p.add_argument('--package',type=Path,required=True);p.add_argument('--models',type=Path,required=True);a=p.parse_args()
root=a.package.resolve();cache=a.models.resolve()
def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as source:
  for chunk in iter(lambda:source.read(1048576),b''):h.update(chunk)
 return h.hexdigest()
receipt=json.loads(Path(__file__).with_name('restore-models.json').read_text())
if sha(root/'manifest.json')!=receipt['complete_manifest_sha256']:raise ValueError('Manifest mismatch')
for item in receipt['omitted_models']:
 source=(cache/item['cache_path']).resolve();target=(root/item['package_path']).resolve()
 if not source.is_relative_to(cache) or not target.is_relative_to(root):raise ValueError('Path escape')
 if source.stat().st_size!=item['size_bytes'] or sha(source)!=item['sha256']:raise ValueError('Model mismatch')
 if target.exists():
  if sha(target)!=item['sha256']:raise ValueError('Refusing to overwrite existing different bytes')
 else:
  target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
sys.path.insert(0,str(root/'app'))
from portable.packaging import verify
print('Complete package verified:',len(verify(root)['files']))
""")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    work=args.work.resolve();work.mkdir(parents=True,exist_ok=True)
    if (work/'provisioning.json').exists():raise ValueError('Use a fresh native provisioning directory')
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    system=platform.system();arch=platform.machine()
    if (system,arch) not in [('Darwin','arm64'),('Linux','x86_64'),('Windows','AMD64')]:
        raise ValueError('Full runtime pins currently target Darwin arm64, Linux x64, Windows x64')
    platform_id={'Darwin':'macos-arm64','Linux':'linux-x64','Windows':'windows-x64'}[system]
    receipts=[];assets=[]
    def add(identifier,directory,entrypoint,licence,license_id,source,**extra):
        assets.append(asset_record(identifier,directory,entrypoint,licence,license_id,source,work,platform_id,**extra))
    target,sha=ASSETS[(system,arch)]
    python_url=f'https://github.com/astral-sh/python-build-standalone/releases/download/{RELEASE}/cpython-{VERSION}%2B{RELEASE}-{target}-install_only.tar.gz'
    archive=fetch(python_url,work/'downloads/python.tar.gz',sha,receipts)
    unpack(archive,work/'python-raw');normalize(work/'python-raw/python',work/'python')
    terminfo=work/'python/share/terminfo'
    if terminfo.exists():
        shutil.rmtree(terminfo)
        (work/'python/PRUNED.txt').write_text('Optional share/terminfo database omitted: upstream case-distinct terminal aliases conflict with cross-platform package path rules. Required CLI, SQLite, SSL, inference and speech functions do not use curses; console is built without readline.\n')
    python=work/'python'/('python.exe' if system=='Windows' else 'bin/python3')
    for name,sha in PYTHON_LICENSES.items():
        fetch('https://raw.githubusercontent.com/astral-sh/python-build-standalone/4bb01f09aaf362c71e891be4a41cb6d6ddf830b3/'+name,work/'python/licenses'/name,sha,receipts)
    pylicense=next((work/'python').rglob('LICENSE.txt')).relative_to(work/'python').as_posix()
    add('python',work/'python',python.relative_to(work/'python').as_posix(),pylicense,'Python-2.0',python_url)
    llama_name,llama_sha=LLAMA[system]
    llama_url='https://github.com/ggml-org/llama.cpp/releases/download/b10819/'+llama_name
    archive=fetch(llama_url,work/'downloads'/llama_name,llama_sha,receipts)
    unpack(archive,work/'llama-raw');normalize(work/'llama-raw',work/'llama')
    licence=fetch('https://raw.githubusercontent.com/ggml-org/llama.cpp/6a1a922d269908a29cbd4b49c27e6a8e7fd10fae/LICENSE',work/'llama/LICENSE','94f29bbed6a22c35b992c5c6ebf0e7c92f13b836b90f36f461c9cf2f0f1d010d',receipts)
    if system=='Linux':retain_linux_libraries(work/'llama',receipts)
    suffix='.exe' if system=='Windows' else ''
    for identifier,filename in [('llama','llama-cli'),('llama_server','llama-server')]:
        matches=list((work/'llama').rglob(filename+suffix))
        if len(matches)!=1:raise ValueError('Native llama entrypoint ambiguous: '+filename)
        matches[0].chmod(0o755)
        add(identifier,work/'llama',matches[0].relative_to(work/'llama').as_posix(),'LICENSE','MIT',llama_url)
    git,git_entry,console,console_entry,git_license,console_license,git_source=git_console(work,receipts,system)
    add('git',git,git_entry,git_license,'GPL-2.0-only',git_source)
    add('console',console,console_entry,console_license,'GPL-3.0-or-later',WIN_GIT_URL if system=='Windows' else BASH_URL)
    speech_provision(work,python,jobs=2)
    speech=work/'speech'
    if system=='Linux':retain_linux_libraries(speech,receipts)
    add('whisper',speech,'whisper-cli'+suffix,'WHISPER-LICENSE','MIT','https://github.com/ggml-org/whisper.cpp')
    add('piper',speech,'piper_entry.py','PIPER-COPYING','GPL-3.0','https://pypi.org/project/piper-tts/1.8.0/',interpreter='python')
    for identifier,filename in [('piper_model','en_US-ljspeech-medium.onnx'),('piper_config','en_US-ljspeech-medium.onnx.json')]:
        directory=work/identifier;directory.mkdir()
        shutil.copyfile(speech/filename,directory/filename);shutil.copyfile(speech/'MODEL_CARD',directory/'MODEL_CARD')
        add(identifier,directory,filename,'MODEL_CARD','Public-Domain','https://huggingface.co/rhasspy/piper-voices')
    model_lock=load_lock(Path(__file__).with_name('model-lock.json'))
    all_assets=[]
    def streaming_assets():
        # Provision/extract the largest models first and consume each archive
        # before acquiring the next. Peak disk stays near two largest models,
        # instead of retaining raw + archive + assembled copies of every model.
        for asset in assets:
            all_assets.append(asset)
            yield asset
            Path(asset['archive']).unlink()
        for model in sorted(model_lock['models'],key=lambda m:m['files'][0]['size_bytes'],reverse=True):
            role=model['role']
            models_main(['--output',str(work/'models'),'--roles',role])
            identifier={'transcription':'whisper_model','embeddings':'bge'}.get(role,role)
            filename=Path(model['files'][0]['path']).name
            asset=asset_record(identifier,work/'models'/role,filename,'LICENSE',model['license'],
                               model['files'][0]['url'],work,platform_id)
            shutil.rmtree(work/'models'/role)
            all_assets.append(asset)
            yield asset
            Path(asset['archive']).unlink()
    original=work/'assembled package'
    assemble(Path(__file__).resolve().parents[1],original,streaming_assets())
    (output/'provisioning.json').write_text(json.dumps({'platform':platform_id,'upstream':receipts,
        'assets':all_assets,'model_lock':model_lock,'system_dependencies':
        'Native OS kernel and C runtime; shell utilities for root launcher; Linux glibc baseline. Native runtime dependencies retained with their distributions.'},indent=2)+'\n')
    relocated=work/'relocated package with spaces';original.rename(relocated)
    shutil.copyfile(relocated/'manifest.json',output/'manifest.json')
    qualify(relocated,output/'native-qualification.json',work,system)
    retain_runtime_payload(relocated,output,model_lock)
    print('Full native qualification passed:',platform_id,flush=True)


if __name__=='__main__':
    main()
