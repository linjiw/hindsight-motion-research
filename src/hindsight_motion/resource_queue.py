"""Serial native launches after a recorded shared-resource gate; no launch retries."""

import argparse
import json
from pathlib import Path
import subprocess
import time

from .critical import dump, launch


def resources():
    free = int(
        subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            text=True,
        ).strip()
    )
    available = next(
        int(line.split()[1]) / 1024
        for line in Path("/proc/meminfo").read_text().splitlines()
        if line.startswith("MemAvailable:")
    )
    return dict(unix_s=time.time(), free_gpu_mib=free, available_host_mib=available)


def run(paths, timeout_s=3600):
    for path in paths:
        path = Path(path).resolve()
        if (path / "launch.json").exists():
            raise FileExistsError("Queue refuses an already attempted run")
        started, stable = time.monotonic(), 0
        ledger = path / "resource_wait.jsonl"
        while time.monotonic() - started < timeout_s:
            sample = resources()
            ready = (
                sample["free_gpu_mib"] >= 12000
                and sample["available_host_mib"] >= 16384
            )
            stable = stable + 1 if ready else 0
            sample.update(ready=ready, consecutive_ready_samples=stable)
            with ledger.open("a") as f:
                f.write(json.dumps(sample) + "\n")
            if stable >= 2:
                dump(path / "resource_admission.json", sample)
                print(json.dumps(dict(admitted=str(path), **sample)), flush=True)
                launch(path)
                status = json.loads((path / "exit.json").read_text())
                if status["exit_code"] != 0:
                    raise RuntimeError(
                        f"Native failure retained; queue stopped: {path}"
                    )
                break
            time.sleep(20)
        else:
            dump(
                path / "resource_deferred.json",
                dict(
                    reason="Resource gate timeout; no native launch",
                    timeout_s=timeout_s,
                ),
            )
            print(f"Resource gate deferred {path}", flush=True)
            return


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--timeout-s", type=int, default=3600)
    args = parser.parse_args()
    run(args.paths, args.timeout_s)
