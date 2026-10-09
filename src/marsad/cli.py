"""marsad command line: bench, demo, and the log adapters (inspect, replay, make-log)."""
from __future__ import annotations
import argparse
import json
import sys


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="marsad", description="Position-trust layer for autonomous systems.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("bench", help="run the simulated benchmark")
    b.add_argument("--split", default="heldout", choices=["dev", "heldout"])
    b.add_argument("--seeds", type=int, default=30)
    b.add_argument("--workers", type=int, default=4)
    b.add_argument("--out", default=None, help="write JSON results here")
    b.add_argument("--markdown", default=None, help="write markdown report here")
    d = sub.add_parser("demo", help="run one simulated scenario and print state transitions")
    d.add_argument("kind")
    d.add_argument("--seed", type=int, default=1)
    d.add_argument("--split", default="dev")
    sv = sub.add_parser("serve", help="run the REST/SSE service and operator dashboard")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8000)
    mc = sub.add_parser("mcp", help="run the MCP server (stdio by default)")
    mc.add_argument("--http", action="store_true")
    mc.add_argument("--port", type=int, default=8765)
    i = sub.add_parser("inspect", help="show topics, field mapping, reference source and warnings of a PX4 ULog")
    i.add_argument("log")
    i.add_argument("--json", default=None, help="write the inspection result as JSON")
    r = sub.add_parser("replay", help="replay a PX4 ULog (.ulg) or MAVLink log (.tlog) through the trust engine")
    r.add_argument("log")
    r.add_argument("--preset", default="uav_multirotor")
    r.add_argument("--json", default=None, help="write transitions and summary as JSON")
    r.add_argument("--no-contaminated-ref", action="store_true",
                   help="never use EKF-fused velocity as the reference (carry-off check is then off without a real reference)")
    m = sub.add_parser("make-log", help="write a SYNTHETIC PX4-style ULog from a simulated scenario")
    m.add_argument("--kind", default="spoof_drift")
    m.add_argument("--seed", type=int, default=1)
    m.add_argument("--split", default="dev")
    m.add_argument("--out", required=True)
    m.add_argument("--no-satellite-info", action="store_true")
    a = ap.parse_args(argv)

    if a.cmd == "serve":
        from .api.__main__ import main as serve_main
        return serve_main(["--host", a.host, "--port", str(a.port)])
    if a.cmd == "mcp":
        from .mcp_server import main as mcp_main
        return mcp_main((["--http"] if a.http else []) + ["--port", str(a.port)])
    if a.cmd == "bench":
        from .bench import run_benchmark, summarize
        from .bench.report import markdown
        res = run_benchmark(a.split, range(a.seeds), workers=a.workers)
        summ = summarize(res)
        md = markdown(summ, f"Benchmark: {a.split} split, {a.seeds} seeds per scenario",
                      "All results are SIMULATED measurement-level scenarios; see docs/EVALUATION.md.")
        print(md)
        if a.out:
            json.dump({"split": a.split, "seeds": a.seeds, "summary": summ, "runs": res}, open(a.out, "w"), indent=1)
        if a.markdown:
            open(a.markdown, "w").write(md)
        return 0
    if a.cmd == "demo":
        from . import TrustEngine, preset
        from .sim import generate
        r = generate(a.kind, a.seed, a.split)
        eng = TrustEngine(preset("uav_multirotor"))
        prev = None
        print(f"scenario={a.kind} seed={a.seed} split={a.split} attack_start={r.attack_start} (SIMULATED)")
        for s in r.samples:
            rep = eng.update(s)
            if rep.state != prev:
                print(f"t={s.t:7.1f}s  {rep.state.value:9s} trust={rep.trust:.2f}  {rep.summary}")
                prev = rep.state
        return 0
    if a.cmd in ("inspect", "replay", "make-log"):
        return _log_cmd(a)
    return 1


def _is_ulog(path: str) -> bool:
    with open(path, "rb") as fh:
        return fh.read(7) == b"\x55\x4c\x6f\x67\x01\x12\x35"


def _log_cmd(a) -> int:
    import warnings
    from .adapters._common import SYNTHETIC_BANNER
    if a.cmd == "make-log":
        from .sim import generate
        from .adapters.ulog_writer import write_ulog
        run = generate(a.kind, a.seed, a.split)
        info = write_ulog(a.out, run, include_satellite_info=not a.no_satellite_info)
        print(f"wrote {a.out}: {info['gps_rows']} GPS rows, {info['ref_rows']} reference rows, {info['bytes']} bytes")
        print(f"*** {SYNTHETIC_BANNER}")
        print(f"scenario={a.kind} seed={a.seed} split={a.split} attack_start={run.attack_start}")
        return 0
    try:
        ulog = _is_ulog(a.log)
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if a.cmd == "inspect":
        if not ulog:
            return _inspect_tlog(a.log)
        from .adapters.ulog import inspect_ulog
        info = inspect_ulog(a.log)
        print(f"file: {info.path}   duration {info.duration_s:.1f}s")
        if info.synthetic:
            print(f"*** {info.synthetic_note}")
        print(f"GPS: {info.gps_topic} (multi_id {info.gps_instance}), {info.n_gnss} rows"
              + (f", {info.gps_rate_hz:.1f} Hz" if info.gps_rate_hz else ""))
        print(f"C/N0 from satellite_info: {'yes' if info.has_cn0 else 'NO'}   AGC: {'yes' if info.has_agc else 'NO'}"
              f"   PX4 jamming/spoofing state: {'yes' if info.has_px4_flags else 'NO'}")
        print(f"reference velocity: {info.reference_source or 'NONE'} ({info.n_ref} rows)"
              + ("   ** CONTAMINATED **" if info.reference_contaminated else ""))
        print("field mapping:")
        for k, v in sorted(info.mapping.items()):
            print(f"  {k:24s} <- {v}")
        print("topics:")
        for k, v in sorted(info.topics.items()):
            print(f"  {k:32s} {v['n']:7d} rows  multi_ids={v['multi_ids']}")
        for w in info.warnings:
            print(f"WARNING: {w}")
        if a.json:
            json.dump(info.to_dict(), open(a.json, "w"), indent=1)
        return 0
    # replay
    from . import TrustEngine, preset
    from .adapters.replay import replay_samples, format_replay
    eng = TrustEngine(preset(a.preset))
    if ulog:
        from .adapters.ulog import load_ulog
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")      # the same text is printed as WARNING below
            d = load_ulog(a.log, allow_contaminated=not a.no_contaminated_ref, warn=False)
        res = replay_samples(d.samples, eng, d.px4_flags)
        text = format_replay(res, label=f"replay {a.log} preset={a.preset}", synthetic=d.info.synthetic,
                             source=d.info.reference_source or "", warnings=d.info.warnings, flag_source="PX4 flag")
        extra = {"info": d.info.to_dict()}
    else:
        from .adapters.mavlink import MavlinkSource
        src = MavlinkSource(a.log, allow_contaminated=not a.no_contaminated_ref, warn=False)
        samples = list(src.samples())
        mp = src.mapper
        res = replay_samples(samples, eng, mp.flags)
        text = format_replay(res, label=f"replay {a.log} (MAVLink) preset={a.preset}",
                             source=mp.ref_source or "", warnings=mp.warnings, flag_source="GNSS_INTEGRITY")
        extra = {"mavlink": {"ref_source": mp.ref_source, "warnings": mp.warnings, "counts": mp.counts}}
    print(text)
    if a.json:
        json.dump({"log": a.log, "preset": a.preset, "result": res.to_dict(), **extra}, open(a.json, "w"), indent=1)
    return 0


def _inspect_tlog(path: str) -> int:
    from .adapters.mavlink import MavlinkSource
    src = MavlinkSource(path, warn=False)
    n = sum(1 for _ in src.samples())
    mp = src.mapper
    print(f"file: {path} (MAVLink)   {n} NavSamples")
    print(f"reference velocity: {mp.ref_source or 'NONE'}" + ("   ** CONTAMINATED **" if mp.ref_contaminated else ""))
    print("message counts: " + ", ".join(f"{k}={v}" for k, v in sorted(mp.counts.items())))
    print(f"GNSS_INTEGRITY samples: {len(mp.flags)}")
    for w in mp.warnings:
        print(f"WARNING: {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
