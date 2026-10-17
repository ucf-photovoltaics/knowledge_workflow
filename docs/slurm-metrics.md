# Slurm execution setup and compute accounting

Author: Brent Thompson <brent.thompson@ucf.edu>

Submit the existing launcher with `sbatch scripts/slurm-sweep.sh`. New domain invocations save an
`environment` block in `run.json` before processing begins. Reopening a run appends captured snapshots
to `environment_history`; `environment` is the current invocation, not an assertion about every past
stage. Completed integrations save the same block in `integration.json`. Older runs are not backfilled
with the report-rendering machine's hardware.

The snapshot records capture time, host, GPU UUID/name/memory/count, host CPU count/RAM, requested Slurm
CPUs/RAM, job ID, partition/node, Python version and vLLM version. GPU probes time out after five
seconds; unavailable hardware remains explicit. Host capacity and requested allocation are distinct.
The Slurm script selects job GPU IDs for both metadata and sampling rather than monitoring unrelated
GPUs on the node. Slurm's GPU IDs and CUDA-visible ordinals can differ; see the
[Slurm GPU resource guide](https://slurm.schedmd.com/gres.html).

The launcher exports `KW_VLLM_*` settings for TP, DP, context length, GPU memory utilization,
prefix caching, workers, domain concurrency and the version installed in its separate vLLM environment.
`VLLM_MODEL` and `VLLM_REASONING_EFFORT` are recorded as well. Selected safe `VLLM_EXTRA_ARGS` overrides
(such as dtype, quantization and context length) are recorded; arbitrary flags, URLs, API keys and the
complete environment are not copied into this block. The existing run configuration remains separate.
Workers are the invocation's requested per-run concurrency, including reduced retry limits; actual
adaptive worker counts remain in the existing stage/worker records. Git commit identifies HEAD;
it does not checksum uncommitted working-tree edits.

## Sweep files

Each submission writes fresh files under `outputs/sweep-<SWEEP_ID>/`:

- `sweep-session-<job>-<timestamp>-<pid>.json`: execution start/end, allocated GPU count, sample filename
  and the 30-second target sampling interval. The start includes model environment/server preparation;
  normal completion closes the interval before final report generation.
- `gpu-metrics-<job>-<timestamp>-<pid>.csv`: Unix epoch timestamp, GPU UUID, power in watts and GPU
  utilization percentage. A final sample closes the last interval on normal exit, SIGINT or SIGTERM.
- `gpu-sampling.log`: probe failures. Unsupported counters remain unavailable; they do not stop the
  literature pipeline. SIGKILL/node loss cannot finalize session metadata, so allocation totals may be
  incomplete. CSV filenames isolate resubmissions with the same sweep ID.

Sampling uses `nvidia-smi` and GNU coreutils `timeout`. No extra Python package or model call is needed.
Power/utilization are device counters, not process-isolated measurements. Use an exclusive GPU
allocation for attribution; shared/MIG devices can have unsupported or shared board-power counters.
Field definitions and device selection are described in the
[NVIDIA nvidia-smi reference](https://docs.nvidia.com/deploy/nvidia-smi/index.html).

## Report interpretation

`python -m src.figures --sweep-summary outputs/sweep-<SWEEP_ID>/summary.csv --out outputs/sweep-<SWEEP_ID>/report`
reads only saved artifacts. Both report formats begin with a Setup table and a totals line:

- **Wall time** is the union of finalized submission execution intervals. Resumed idle gaps and
  overlapping parallel domains do not inflate it. Without allocation metadata it uses sampled spans,
  then summed recorded stage durations, explicitly labeled; the last fallback can include parallel overlap.
- **GPU-hours** sum submission duration × allocated GPU count. Without metadata only covered sample
  intervals are available. These are allocation hours, not an estimate of busy GPU time.
- **Input/output tokens** sum actual ledger entries for the selected runs and integrations, including
  listed failed attempts. Client-side cache hits add no model-request tokens. Manifest/evaluation totals
  are fallbacks for older runs. Missing or truncated records produce a partial-accounting note.
- **Tokens/s** divides input + output tokens by the stated wall time. It is end-to-end aggregate
  throughput, including setup, not a vLLM decoding benchmark.
- **GPU energy** uses trapezoidal integration of sampled watts: joules ÷ 3,600,000 = kWh. It excludes
  CPU/RAM/facility energy. **Average utilization** is weighted by sampled GPU seconds. Coverage is
  displayed in GPU-hours for each counter. Missing counters remain unavailable, gaps longer than 90
  seconds are omitted, and samples from different submissions are never connected across idle gaps.

Per-size token figures describe additional work recorded for that run size. They are not cumulative
sweep token totals; reused extraction outputs do not consume fresh model-request tokens.
