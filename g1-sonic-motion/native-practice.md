# Public native reproduction on a second Linux computer

Two commodity AMD CPU systems ran the public seed-7 reference controller. The first used an existing CPU Docker image. The second used a fresh Python 3.12 virtual environment inside an unprivileged Linux namespace. No ALE evaluator or hidden assignment was present in the second run.

The 5 m walking stop took 782 control rows and 15.632 s of simulated time. The −90° turning stop took 154 rows and 3.070 s. All 39 public practice fields on each route matched the first-host CPython 3.12 output exactly, including stop dwell, kinematics, motor-code counts, measured acceleration and probe responses. A separate CPython 3.10 comparison differed in one unrounded sum of squared accelerations by $2.33\times10^{-10}$.

The separate camera-guided V4 tabletop practice trial placed the seed-7 box on both hosts, at 554 and 561 rows respectively. Their software renderers used LLVM 15.0.7 and LLVM 20.1.2. The two measurements establish the observed difference in the trajectory and timing. The causal contribution of the graphics stack was not isolated.

The optional five-metre mobile cylinder-19 trial docked on row 685 on both machines. Dock travel matched exactly after parsing in the public JSON (pelvis 5.01307424 m and ankles 4.99348601/5.02345343 m). The camera-guided placement met its full 250 ms stable-release condition in 1,286 and 1,283 rows. Total scratch after all four runs was 589 MiB.

## Run it

Use x86-64 Linux with AVX2 and FMA3, `/usr/bin/python3.12` and `venv`, Git, Bash, Bubblewrap, a working unprivileged user namespace, Mesa EGL/llvmpipe and access to logical CPU IDs 0 and 1. The measured Ubuntu 24.04 installation provides Mesa’s vendor file at `/usr/share/glvnd/egl_vendor.d/50_mesa.json`. The preserved driver pins those exact IDs. Check `python3 -c "import os; print({0, 1} <= os.sched_getaffinity(0))"` before running. If those IDs are unavailable, use two IDs from the allowed affinity set in a separate copy of the driver and record the revised SHA-256. The driver uses an empty participant home and a private scratch directory. Public setup downloads the exact Git revisions, verifies the asset manifests and installs the pinned wheel set into the scratch directory. Native practice then runs with networking disabled. The complete run uses well under 4 GiB of scratch and never needs a Docker daemon or administrator rights.

```sh
scratch=$(mktemp -d /tmp/g1-public-native.XXXXXXXX)
bash reproduce-native.sh "$scratch" locomotion
bash reproduce-native.sh "$scratch" tabletop
bash reproduce-native.sh "$scratch" mobile
```

The locomotion step prepares the virtual environment for the two optional manipulation runs. JSON outputs remain under `receipts/` inside the scratch directory. The compact public receipts record the source identities, wheel and asset hashes, exact measured values and comparison method. Official ALE gates use their own randomly assigned panels and reward calculation.
