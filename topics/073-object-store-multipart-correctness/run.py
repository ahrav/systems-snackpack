"""Six balanced blocks, one fresh process per candidate and cell per block."""
import csv, hashlib, itertools, json, os, pathlib, platform, re, shlex, shutil, statistics, subprocess, sys
def require(ok, message):
    # Evidence gates stay active under python -O and PYTHONOPTIMIZE.
    if not ok:
        raise SystemExit(f'run.py: {message}')
require(len(sys.argv) == 2, 'run.py <fresh-output-directory>')
root = pathlib.Path(__file__).resolve().parent
# Measured processes inherit this environment; reject compiler/profile and loader-interposition settings before any work.
# Presence is the test: Cargo treats an empty RUSTFLAGS or CARGO_ENCODED_RUSTFLAGS as the selected flag source.
overrides = {k:v for k,v in os.environ.items() if (k in ['RUSTFLAGS','CARGO_ENCODED_RUSTFLAGS','CARGO_BUILD_RUSTFLAGS','RUSTC','CARGO_BUILD_RUSTC','RUSTC_WRAPPER','CARGO_BUILD_RUSTC_WRAPPER','RUSTC_WORKSPACE_WRAPPER','CARGO_BUILD_RUSTC_WORKSPACE_WRAPPER','LD_PRELOAD','LD_AUDIT','DYLD_INSERT_LIBRARIES'] or k.startswith('CARGO_PROFILE_') or (k.startswith('CARGO_TARGET_') and k.endswith('_RUSTFLAGS')))}
require(not overrides, f'clear Cargo compiler/profile and loader-interposition environment overrides before running: {sorted(overrides)}')
out = pathlib.Path(sys.argv[1]).resolve()
out.mkdir(parents=True, exist_ok=False)
TIMEOUT = 600  # seconds per child process; a stalled build or candidate fails the campaign instead of hanging it
def run(args):
    return subprocess.check_output(args, cwd=root, text=True, stderr=subprocess.STDOUT, timeout=TIMEOUT)
def digests():
    # Workspace build configuration is part of the hashed identity: it selects the compiler, profile, and dependency resolution.
    files = [p for p in sorted(root.rglob('*')) if p.is_file() and ('target' not in p.parts) and p.suffix in ['.rs','.toml','.py']]
    files += [p for p in [workspace/'Cargo.toml', workspace/'Cargo.lock', workspace/'rust-toolchain.toml'] if p.is_file()]
    # Cargo merges .cargo/config[.toml] from this directory upward, then $CARGO_HOME/config[.toml].
    config_dirs = [d/'.cargo' for d in [root, *root.parents]] + [cargo_home]
    files += [p for d in config_dirs for p in [d/'config.toml', d/'config'] if p.is_file()]
    return {os.path.relpath(p, root): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
workspace = pathlib.Path(run(['cargo','locate-project','--workspace','--message-format','plain']).strip()).parent
cargo_home = pathlib.Path(os.environ.get('CARGO_HOME') or pathlib.Path.home()/'.cargo').resolve()
meta = {"hostname": platform.node(), "uname": list(platform.uname()), "available_cpus": sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else os.cpu_count(), "ambient_rustc_version": run(["rustc", "-Vv"]), "flags": "release requested; exact compiler arguments in build.log; default rustc cfg is informational; effective settings from build log", "boundary": "allocate, validate, normalize, produce output, drop; source generation/oracle/process startup excluded", "selection": "candidate <= 0.95*rival in ALL six paired process blocks against every rival; otherwise unresolved", "inputs": digests()}
meta['default_rustc_cfg'] = run(['rustc','--print','cfg'])
if sys.platform == 'darwin':
    meta['cpu'] = run(['sysctl','-n','machdep.cpu.brand_string'])
else:
    meta['cpu'] = run(['lscpu'])
    meta['default_rustc_cfg'] = run(['rustc','--print','cfg'])
(out/'host.json').write_text(json.dumps(meta,indent=2)+'\n')
for name, args in [('test',['cargo','test']),('clippy',['cargo','clippy','--all-targets','--','-D','warnings'])]:
    (out/f'{name}.log').write_text(run(args))
# Use a new target directory so verbose build output includes actual compilation.
# Cargo JSON binds the measured executable to this build instead of a caller path.
build = subprocess.run(['cargo','build','--release','--example','manifest','--target-dir',str(out/'build-target'),'--message-format=json-render-diagnostics','-vv'], cwd=root, text=True, capture_output=True, check=True, timeout=TIMEOUT)
(out/'build.log').write_text(build.stderr)
(out/'build.jsonl').write_text(build.stdout)
artifacts = [json.loads(line) for line in build.stdout.splitlines() if line.startswith('{')]
executables = [a['executable'] for a in artifacts if a.get('reason') == 'compiler-artifact' and a.get('target',{}).get('name') == 'manifest' and a.get('executable')]
require(len(executables) == 1, f'expected one manifest executable in Cargo JSON: {executables}')
binary = pathlib.Path(executables[0]).resolve()
meta['binary_sha256']=hashlib.sha256(binary.read_bytes()).hexdigest()
# The compiler Cargo invoked, read from the verbose log, must be the unwrapped ambient rustc recorded above.
programs = {tuple(itertools.takewhile(lambda t: t != '--crate-name', [t for t in shlex.split(line.split('Running `',1)[1].rsplit('`',1)[0]) if not re.match(r'[A-Z_][A-Z0-9_]*=', t)])) for line in build.stderr.splitlines() if 'Running `' in line and '--crate-name' in line}
require(len(programs) == 1 and len(next(iter(programs))) == 1, f'expected one unwrapped compiler executable across build.log rustc invocations: {sorted(programs)}')
compiler = pathlib.Path(shutil.which(next(iter(programs))[0]) or next(iter(programs))[0]).resolve()
meta['effective_rustc'] = {'path': str(compiler), 'sha256': hashlib.sha256(compiler.read_bytes()).hexdigest(), 'version': run([str(compiler), '-Vv'])}
require(meta['effective_rustc']['version'] == meta['ambient_rustc_version'], f"Cargo selected {compiler}, which differs from the ambient rustc; clear build.rustc configuration")
# host.json attributes the binary to the hashed inputs; the inputs must be unchanged at build time and after measurement.
require(digests() == meta['inputs'], 'source inputs changed before the build; rerun from a quiescent tree')
(out/'host.json').write_text(json.dumps(meta,indent=2)+'\n')
cells=[(8,'ordered',1),(8,'shuffle',4),(1024,'reverse',1),(1024,'shuffle',4),(10000,'ordered',1),(10000,'shuffle',4)]
rows=[]
for n,order,copies in cells:
    for c in ['sort','tree','slots']:
        run([str(binary),c,str(n),order,str(copies)])
    for block, candidates in enumerate(itertools.permutations(['sort','tree','slots'])):
        for c in candidates:
            cmd=[str(binary),c,str(n),order,str(copies)]
            if hasattr(os,'sched_getaffinity'):
                cmd=['taskset','-c',str(min(os.sched_getaffinity(0)))]+cmd
            line=run(cmd).strip()
            (out/'processes.txt').open('a').write(f'{block},{line}\n')
            rows.append({'cell':f'{n}-{order}-{copies}','block':block,'candidate':c,'ns':float(line.split(',')[-1])})
require(digests() == meta['inputs'], 'source inputs changed during measurement; rerun from a quiescent tree')
require(hashlib.sha256(binary.read_bytes()).hexdigest() == meta['binary_sha256'], 'measured binary changed during measurement; rerun from a quiescent tree')
(out/'rows.json').write_text(json.dumps(rows,indent=2)+'\n')
report=[]
for n,order,copies in cells:
    cell=f'{n}-{order}-{copies}'
    values={c:[r['ns'] for r in rows if r['cell']==cell and r['candidate']==c] for c in ['sort','tree','slots']}
    winners=[c for c in values if all(all(x<=.95*y for x,y in zip(values[c],values[r])) for r in values if r!=c)]
    report.append({'cell':cell,'winner':winners[0] if len(winners)==1 else 'unresolved','ns':{c:{'median':statistics.median(v),'min':min(v),'max':max(v)} for c,v in values.items()}})
(out/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
