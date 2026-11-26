#!/usr/bin/env bash
# Pass an already-created, private mktemp directory on the selected independent Linux host.
set -euo pipefail
work=${1:?supply /tmp/g1-public-native.XXXXXXXX}
mode=${2:-locomotion}
[[ $mode == locomotion || $mode == tabletop || $mode == mobile ]]
case $work in /tmp/g1-public-native.????????) ;; *) exit 2;; esac
[[ -d $work && -O $work ]]
cd "$work"
umask 077
mkdir -p account receipts bootstrap
printf 'participant:x:%s:%s:participant:/work/account:/bin/bash\n' "$(id -u)" "$(id -g)" > participant.passwd
printf 'participant:x:%s:\n' "$(id -g)" > participant.group
box=(/usr/bin/bwrap --die-with-parent --unshare-all --ro-bind /usr /usr --symlink usr/bin /bin --symlink usr/lib /lib --symlink usr/lib64 /lib64 --dir /etc --ro-bind /etc/ld.so.cache /etc/ld.so.cache --ro-bind /etc/ssl /etc/ssl --ro-bind /etc/hosts /etc/hosts --ro-bind /etc/resolv.conf /etc/resolv.conf --ro-bind /etc/nsswitch.conf /etc/nsswitch.conf --ro-bind "$work/participant.passwd" /etc/passwd --ro-bind "$work/participant.group" /etc/group --proc /proc --dev /dev --tmpfs /tmp --bind "$work" /work --chdir /work --clearenv --setenv HOME /work/account --setenv PATH /work/venv/bin:/usr/bin:/bin --setenv LANG C.UTF-8 --setenv GIT_CONFIG_NOSYSTEM 1 --setenv GIT_CONFIG_GLOBAL /dev/null --setenv GIT_TERMINAL_PROMPT 0 --setenv PYTHONNOUSERSITE 1 --setenv PYTHONDONTWRITEBYTECODE 1 --setenv MUJOCO_GL egl --setenv PYOPENGL_PLATFORM egl --setenv EGL_PLATFORM surfaceless --setenv __EGL_VENDOR_LIBRARY_FILENAMES /usr/share/glvnd/egl_vendor.d/50_mesa.json --setenv LIBGL_ALWAYS_SOFTWARE 1 --setenv GALLIUM_DRIVER llvmpipe --setenv LP_NUM_THREADS 2 --setenv OPENBLAS_CORETYPE Haswell --setenv OPENBLAS_NUM_THREADS 1 --setenv OMP_NUM_THREADS 1 --setenv MKL_NUM_THREADS 1 --setenv NPY_DISABLE_CPU_FEATURES 'AVX512F AVX512CD AVX512_KNL AVX512_KNM AVX512_SKX AVX512_CLX AVX512_CNL AVX512_ICL')
# Optional participant-only tabletop follow-up reuses this temporary environment and checked asset store.
if [[ $mode == tabletop || $mode == mobile ]]; then
  taskset -c 0,1 "${box[@]}" --setenv PUBLIC_MODE "$mode" --share-net /bin/bash -euo pipefail <<'TABLE_SETUP'
if [[ $PUBLIC_MODE == tabletop ]]; then
 slug=g1_sonic_token_space_control; revision=7e4d005aee30a97aba26433fe067f7a88c20d3f5
else
 slug=g1_sonic_mobile_pick_place; revision=860b71c4f1b0ff15e639123955bc540cba1fbbe0
fi
repo=/work/source-$PUBLIC_MODE
task=$repo/tasks/humanoid/$slug
if [[ ! -d $repo/.git ]]; then
 git init -q "$repo"; git -C "$repo" remote add origin https://github.com/Zi-ang-Cao/agentic-robotics-benchmark.git
 git -C "$repo" config remote.origin.promisor true; git -C "$repo" config remote.origin.partialclonefilter blob:none
 git -C "$repo" sparse-checkout set --no-cone "/tasks/humanoid/$slug/environment/" "/tasks/humanoid/$slug/solution/" "/tasks/humanoid/$slug/instruction.md"
fi
if [[ ! -f $task/environment/public_assets.sha256 ]]; then
 git -C "$repo" -c credential.helper= fetch -q --no-tags --depth=1 --filter=blob:none origin "$revision"
 git -C "$repo" checkout -q --detach "$revision"
fi
test "$(git -C "$repo" rev-parse HEAD)" = "$revision"; test -z "$(git -C "$repo" status --porcelain)"; test ! -e "$task/tests"
sha256sum "$task/environment/public_assets.sha256" "$task/solution/v4_actor.onnx" > "/work/receipts/$PUBLIC_MODE-sources.sha256"
TABLE_SETUP
  taskset -c 0,1 "${box[@]}" --setenv PUBLIC_MODE "$mode" /bin/bash -euo pipefail <<'TABLE_RUN'
if [[ $PUBLIC_MODE == tabletop ]]; then
 slug=g1_sonic_token_space_control; actor=solution/solve.sh; shape=box_to_pad; seed=7; course=()
else
 slug=g1_sonic_mobile_pick_place; actor=solution/five_metre/install.sh; shape=cylinder_to_pad; seed=19; course=(--course five-metre)
fi
task=/work/source-$PUBLIC_MODE/tasks/humanoid/$slug
mkdir -p "/work/$PUBLIC_MODE-account"
export SONIC_ASSETS=/work/assets SONIC_PYTHON=/work/venv/bin/python PYTHONPATH="$task/environment" ALE_HOME="/work/$PUBLIC_MODE-account" SONIC_REFERENCE_POLICY=v4
/work/venv/bin/python "$task/environment/fetch_public_assets.py" /work/assets --manifest "$task/environment/public_assets.sha256" --check
/bin/bash "$task/$actor"
/work/venv/bin/python -B "$task/environment/setup/payload/practice.py" run "${course[@]}" --task "$shape" --seed "$seed" --assets-root /work/assets --submission "$ALE_HOME/submission" > "/work/receipts/$PUBLIC_MODE-v4.json.tmp"
mv "/work/receipts/$PUBLIC_MODE-v4.json.tmp" "/work/receipts/$PUBLIC_MODE-v4.json"
TABLE_RUN
  du -sm "$work" | awk '{print "Scratch MiB",$1; if ($1 >= 4096) exit 1}'
  exit 0
fi
# Network is available only for anonymous public source, wheels and checksummed assets.
taskset -c 0,1 "${box[@]}" --share-net /bin/bash -euo pipefail <<'SETUP'
slug=g1_sonic_locomotion
revision=e48e2384089c8a46d4414bbfd45f7c905ba20616
repo=/work/source-locomotion
task=$repo/tasks/humanoid/$slug
if [[ ! -d $repo/.git ]]; then
  git init -q "$repo"
  git -C "$repo" remote add origin https://github.com/Zi-ang-Cao/agentic-robotics-benchmark.git
  git -C "$repo" config remote.origin.promisor true
  git -C "$repo" config remote.origin.partialclonefilter blob:none
  git -C "$repo" sparse-checkout set --no-cone "/tasks/humanoid/$slug/environment/" "/tasks/humanoid/$slug/solution/" "/tasks/humanoid/$slug/instruction.md"
fi
if [[ ! -f $task/environment/public_assets.sha256 ]]; then
  git -C "$repo" -c credential.helper= fetch -q --no-tags --depth=1 --filter=blob:none origin "$revision"
  git -C "$repo" checkout -q --detach "$revision"
fi
test "$(git -C "$repo" rev-parse HEAD)" = "$revision"
test -z "$(git -C "$repo" status --porcelain)"
test ! -e "$task/tests"
if [[ ! -x /work/venv/bin/python ]]; then /usr/bin/python3.12 -m venv --without-pip /work/venv; fi
if ! /work/venv/bin/python -m pip --version >/dev/null 2>&1; then
/usr/bin/python3.12 -B - <<'PY'
from hashlib import sha256
import json
from pathlib import Path
from urllib.request import urlopen
with urlopen('https://pypi.org/pypi/pip/25.0.1/json',timeout=30) as response: metadata=json.load(response)
wheel,=[r for r in metadata['urls'] if r['filename']=='pip-25.0.1-py3-none-any.whl'];assert wheel['url'].startswith('https://files.pythonhosted.org/')
with urlopen(wheel['url'],timeout=60) as r: raw=r.read()
assert sha256(raw).hexdigest()==wheel['digests']['sha256'];Path('/work/bootstrap',wheel['filename']).write_bytes(raw)
PY
/work/venv/bin/python -c 'import sys;sys.path.insert(0,"/work/bootstrap/pip-25.0.1-py3-none-any.whl");from pip._internal.cli.main import main;sys.exit(main(["install","--no-index","--no-deps","/work/bootstrap/pip-25.0.1-py3-none-any.whl"]))'
fi
cat > /work/bootstrap/public-wheels.txt <<'PINS'
PyOpenGL==3.1.10
absl-py==2.5.1
coloredlogs==15.0.1
etils==1.15.0
flatbuffers==25.12.19
fsspec==2026.9.0
glfw==2.11.0
humanfriendly==10.0
mpmath==1.3.0
mujoco==3.3.4
numpy==1.26.4
onnxruntime==1.22.1
packaging==26.4
pillow==11.2.1
pip==25.0.1
protobuf==7.36.2
scipy==1.15.3
sympy==1.14.0
typing_extensions==4.16.0
zipp==4.1.2
PINS
if [[ ! -s /work/receipts/wheels.json ]]; then
 /work/venv/bin/python -m pip --isolated --disable-pip-version-check install --quiet --no-cache-dir --only-binary=:all: --index-url https://pypi.org/simple --report /work/receipts/wheels.json -r "$task/environment/requirements.txt" -c /work/bootstrap/public-wheels.txt
fi
/work/venv/bin/python "$task/environment/fetch_public_assets.py" /work/assets --manifest "$task/environment/public_assets.sha256"
SETUP
# No network and no host home, original research tree, Docker socket or host GPU is mounted in this phase.
taskset -c 0,1 "${box[@]}" /bin/bash -euo pipefail <<'PRACTICE'
slug=g1_sonic_locomotion
task=/work/source-locomotion/tasks/humanoid/$slug
export SONIC_ASSETS=/work/assets SONIC_PYTHON=/work/venv/bin/python PYTHONPATH="$task/environment" ALE_HOME=/work/account
/work/venv/bin/python "$task/environment/fetch_public_assets.py" /work/assets --manifest "$task/environment/public_assets.sha256" --check
/bin/bash "$task/solution/solve.sh"
for route in straight_stop right_turn_stop; do
  /work/venv/bin/python -B "$task/environment/setup/payload/practice.py" --task "$route" --seed 7 --assets-root /work/assets --submission /work/account/submission > "/work/receipts/$route.json.tmp"
  mv "/work/receipts/$route.json.tmp" "/work/receipts/$route.json"
done
/work/venv/bin/python - <<'PY'
from pathlib import Path
from hashlib import sha256
import os,sys,json,platform,subprocess,importlib.metadata as md
import numpy.core._multiarray_umath as cpu
import mujoco
from OpenGL import GL
model=mujoco.MjModel.from_xml_string('<mujoco><worldbody><geom size=".1"/></worldbody></mujoco>');data=mujoco.MjData(model)
with mujoco.Renderer(model,32,32) as fg:
 fg.update_scene(data);pixels=fg.render(); assert pixels.shape==(32,32,3); gl=GL.glGetString(GL.GL_RENDERER).decode()
assert 'llvmpipe' in gl.lower();assert cpu.__cpu_features__['AVX2'] and cpu.__cpu_features__['FMA3'] and not cpu.__cpu_features__['AVX512F']
p=Path('/work/receipts');r={'source':subprocess.check_output(['git','-C','/work/source-locomotion','rev-parse','HEAD'],text=True).strip(),'python':sys.version.split()[0],'kernel':platform.release(),'architecture':platform.machine(),'gl_renderer':gl,'allowed_cpus':sorted(os.sched_getaffinity(0)),'avx2':cpu.__cpu_features__['AVX2'],'fma3':cpu.__cpu_features__['FMA3'],'avx512f':cpu.__cpu_features__['AVX512F'],'openblas':os.environ['OPENBLAS_CORETYPE'],'packages':{d.metadata['Name']:d.version for d in md.distributions()},'asset_manifest_sha256':sha256(Path('/work/source-locomotion/tasks/humanoid/g1_sonic_locomotion/environment/public_assets.sha256').read_bytes()).hexdigest(),'assets_verified':True,'public_fork':True,'participant_only_sparse_checkout':not Path('/work/source-locomotion/tasks/humanoid/g1_sonic_locomotion/tests').exists(),'offline':sorted(os.listdir('/sys/class/net')) if Path('/sys/class/net').is_dir() else 'network namespace isolated by bwrap','runtime_uid':os.getuid(),'bound_home':'/work/account'}
(p/'environment.json').write_text(json.dumps(r,indent=2)+'\n')
PY
PRACTICE
du -sm "$work" | awk '{print "Scratch MiB",$1; if ($1 >= 4096) exit 1}'
