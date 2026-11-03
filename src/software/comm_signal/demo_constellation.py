"""从项目根目录运行 python -m comm_signal.demo_constellation 生成可复现星座图。"""

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", ".mplconfig")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .modulation import MODULATORS
from .channel import add_awgn, measure_snr


def _plot(ax, received, name, snr, limit):
    """绘制等比例 IQ 散点图，每对 SNR 图保持相同坐标范围。"""
    ax.scatter(received.real, received.imag, s=7, alpha=0.35, linewidths=0)
    ax.set(xlabel="In-phase (I)", ylabel="Quadrature (Q)",
           title=f"{name} Constellation — SNR = {snr} dB", xlim=(-limit, limit), ylim=(-limit, limit))
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, alpha=0.3)
    ax.axhline(0, color="gray", linewidth=0.7)
    ax.axvline(0, color="gray", linewidth=0.7)


def main(argv=None):
    """固定种子 42 保存十张星座图及总览，保留已有实验结果。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path,
                        default=Path("results") / "constellations")
    args = parser.parse_args(argv)
    if args.output_dir.is_absolute():
        parser.error("output-dir must be relative to the project root")
    # 目录已有内容时分配独立实验目录，避免覆盖不同实验。
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        args.output_dir /= datetime.now().strftime("run_%Y%m%d_%H%M%S_%f")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {args.output_dir.as_posix()}")
    rng = np.random.default_rng(42)
    overview, axes = plt.subplots(5, 2, figsize=(10, 23))
    records = []
    for row, (name, generate) in enumerate(MODULATORS.items()):
        clean = generate(2000, rng)
        received = {snr: add_awgn(clean, snr, rng) for snr in (20, 0)}
        limit = 1.08 * max(max(np.max(abs(r.real)), np.max(abs(r.imag)))
                           for r in received.values())
        for col, (snr, noisy) in enumerate(received.items()):
            fig, ax = plt.subplots(figsize=(6, 6))
            _plot(ax, noisy, name, snr, limit)
            filename = f"{name}_{snr}dB.png"
            fig.tight_layout()
            fig.savefig(args.output_dir / filename, dpi=150)
            plt.close(fig)
            _plot(axes[row, col], noisy, name, snr, limit)
            measured = measure_snr(clean, noisy)
            records.append({"modulation": name, "target_snr_db": snr,
                            "measured_snr_db": measured,
                            "noise_power": float(np.mean(abs(noisy-clean)**2)),
                            "symbols": len(clean), "file": filename})
            print(f"Saved {filename}: measured SNR = {measured:.6f} dB")
    overview.tight_layout()
    overview.savefig(args.output_dir / "overview.png", dpi=100)
    plt.close(overview)
    (args.output_dir / "measurements.json").write_text(
        json.dumps({"seed": 42, "figures": records}, indent=2) + "\n", encoding="utf-8")
    print("PASS: generated 10 constellation figures and overview.png")


if __name__ == "__main__":
    main()
