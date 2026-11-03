#!/usr/bin/env bash
# Run the 48 SITL EKF2 runs of PREREGISTRATION_SITL_EKF2.md (resumable: a run whose .ulg exists is skipped).
# usage: scripts/sitl_ekf2_batch.sh /path/to/PX4-Autopilot OUTDIR [SPEED]
set -u
PX4=$1; OUT=$2; SPEED=${3:-6}
mkdir -p "$OUT"
run() {
  local name=$1; shift
  [ -s "$OUT/$name.ulg" ] && return 0
  python scripts/sitl_ekf2_spoof.py --px4 "$PX4" --out "$OUT" --speed "$SPEED" --name "$name" "$@" >> "$OUT/batch.log" 2>&1 || echo "FAILED $name" >> "$OUT/batch.log"
}
for h in 0 90 180 270; do
  run "clean_h$h" --case clean --heading $h
  for m in 50 200 1000; do run "jump${m}_h$h" --case jump:$m --heading $h; done
  for r in 0.25 0.5 1.0 2.0; do
    run "drift${r}_h${h}_vel" --case drift:$r --heading $h --velcons
    run "drift${r}_h${h}_pos" --case drift:$r --heading $h
  done
done
echo "batch finished" >> "$OUT/batch.log"
