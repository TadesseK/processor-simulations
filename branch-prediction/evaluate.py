#!/usr/bin/env python3
"""Run all three predictors on all complete CBP2 traces and retain exact counts."""
import argparse
import concurrent.futures
import csv
import hashlib
import json
import pathlib
import platform
import subprocess
import time
from datetime import datetime, timezone

BASE = pathlib.Path(__file__).resolve().parent


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate_one(trace, name, binary, results):
    command = [str(BASE / "src" / binary), "--json", str(trace)]
    started = time.perf_counter()
    process = subprocess.run(command, capture_output=True, text=True)
    elapsed = time.perf_counter() - started
    log = {
        "command": [f"src/{binary}", "--json", str(trace.relative_to(BASE))],
        "exit_code": process.returncode,
        "elapsed_seconds": elapsed,
        "stdout": process.stdout,
        "stderr": process.stderr,
    }
    (results / "raw_logs" / f"{trace.parent.name}_{name}.json").write_text(json.dumps(log, indent=2) + "\n")
    if process.returncode:
        raise RuntimeError(f"{name} failed on {trace}: {process.stderr}")
    row = json.loads(process.stdout)
    if row["predictor"] != name or not (0 <= row["direction_misses"] <= row["conditional_branches"] <= row["branches"]):
        raise RuntimeError(f"Invalid statistics: {row}")
    row["benchmark"] = trace.parent.name
    row["trace"] = str(trace.relative_to(BASE))
    row["elapsed_seconds"] = elapsed
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", type=int, default=3, help="Concurrent simulator processes (default 3)")
    arguments = parser.parse_args()
    if arguments.jobs < 1:
        parser.error("--jobs must be positive")
    traces = sorted((BASE / "traces").rglob("*.trace.*"))
    if len(traces) != 20:
        raise RuntimeError(f"Expected the 20 provided complete traces, found {len(traces)}")
    results = BASE / "results"
    (results / "raw_logs").mkdir(parents=True, exist_ok=True)
    build = subprocess.run(["make", "-C", str(BASE / "src"), "all", "baselines"], capture_output=True, text=True)
    (results / "build.log").write_text(build.stdout + build.stderr)
    build.check_returncode()
    names = [("hybrid", "predict"), ("bimodal", "predict_bimodal"), ("gshare", "predict_gshare")]
    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=arguments.jobs) as executor:
        futures = [executor.submit(evaluate_one, trace, name, binary, results)
                   for trace in traces for name, binary in names]
        for future in concurrent.futures.as_completed(futures):
            row = future.result()
            rows.append(row)
            print(f"{row['benchmark']:15s} {row['predictor']:7s} {row['direction_misses']:9d} misses {row['direction_mpki']:.5f} MPKI", flush=True)
    rows.sort(key=lambda r: (r["benchmark"], r["predictor"]))
    (results / "exact_statistics.json").write_text(json.dumps(rows, indent=2) + "\n")
    by_benchmark = {}
    for row in rows:
        by_benchmark.setdefault(row["benchmark"], {})[row["predictor"]] = row
    for benchmark, group in by_benchmark.items():
        counts = {(r["branches"], r["conditional_branches"], r["instructions"]) for r in group.values()}
        if len(counts) != 1:
            raise RuntimeError(f"Trace count inconsistency for {benchmark}")
    columns = ["benchmark", "instructions", "branches", "conditional_branches", "hybrid_misses", "hybrid_mpki", "bimodal_misses", "bimodal_mpki", "gshare_misses", "gshare_mpki", "hybrid_vs_bimodal_percent"]
    with (results / "benchmark_results.csv").open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        for benchmark, group in sorted(by_benchmark.items()):
            row = {"benchmark": benchmark, **{k: group["hybrid"][k] for k in columns[1:4]}}
            for name, _ in names:
                row[f"{name}_misses"] = group[name]["direction_misses"]
                row[f"{name}_mpki"] = f"{group[name]['direction_mpki']:.5f}"
            row["hybrid_vs_bimodal_percent"] = f"{100 * (group['bimodal']['direction_misses'] - group['hybrid']['direction_misses']) / group['bimodal']['direction_misses']:.6f}"
            writer.writerow(row)
    aggregates = {}
    for name, _ in names:
        subset = [r for r in rows if r["predictor"] == name]
        total_misses = sum(r["direction_misses"] for r in subset)
        total_instructions = sum(r["instructions"] for r in subset)
        total_conditional = sum(r["conditional_branches"] for r in subset)
        aggregates[name] = {"direction_misses": total_misses, "instructions": total_instructions,
                            "conditional_branches": total_conditional,
                            "average_mpki": 1000 * total_misses / total_instructions,
                            "conditional_miss_rate": total_misses / total_conditional}
    summary = {"aggregates": aggregates,
               "hybrid_improvement_vs_bimodal_percent": 100 * (aggregates["bimodal"]["direction_misses"] - aggregates["hybrid"]["direction_misses"]) / aggregates["bimodal"]["direction_misses"],
               "hybrid_wins_vs_bimodal": sum(g["hybrid"]["direction_misses"] < g["bimodal"]["direction_misses"] for g in by_benchmark.values()),
               "hybrid_wins_vs_gshare": sum(g["hybrid"]["direction_misses"] < g["gshare"]["direction_misses"] for g in by_benchmark.values())}
    (results / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    manifest = {
        "utc_completed": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(),
        "compiler": subprocess.check_output(["g++", "--version"], text=True).splitlines()[0],
        "trace_count": len(traces), "predictor_runs": len(rows), "jobs": arguments.jobs,
        "instructions_per_trace": 100000000,
        "hashes": {str(p.relative_to(BASE)): sha256(p) for p in [*sorted((BASE / "src").glob("*.h")), *sorted((BASE / "src").glob("*.cc")), BASE / "src" / "Makefile", BASE / "evaluate.py", *traces]},
    }
    (results / "run_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
