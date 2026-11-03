"""Headless time-domain, all-sample constellation, and two-sided Welch PSD."""

import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parents[1] / ".mplconfig"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import welch

from .dataset import MODULATION_TO_LABEL
from .pulse_shaping import generate_waveform


def waveform_psd(waveform, nperseg=1024):
    """Two-sided Welch PSD in cycles/sample, sorted numerically."""
    f, p = welch(waveform, fs=1.0, nperseg=nperseg, return_onesided=False, detrend=False)
    order = np.argsort(f)
    return f[order], 10 * np.log10(np.maximum(p[order], np.finfo(float).tiny))


def generate_plots(dataset, config, output_dir="results"):
    root = Path(output_dir)
    files = []

    def save(fig, folder, filename):
        path = root / folder / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.tight_layout()
        fig.savefig(path, dpi=150)
        plt.close(fig)
        files.append(path)

    for target in (20, 0, -10):
        index = np.flatnonzero((dataset["y"] == MODULATION_TO_LABEL["QPSK"]) &
                               (dataset["snr"] == target))[0]
        iq = dataset["X"][index]
        fig, ax = plt.subplots(figsize=(9, 3))
        ax.plot(iq[0, :256], label="I[n]", linewidth=0.9)
        ax.plot(iq[1, :256], label="Q[n]", linewidth=0.9)
        ax.set(title=f"QPSK RRC waveform | {target} dB", xlabel="Sample index n", ylabel="Amplitude")
        ax.legend()
        ax.grid(alpha=0.3)
        save(fig, "waveforms", f"day2_QPSK_{target}dB.png")

        fig, ax = plt.subplots(figsize=(5, 5))
        ax.scatter(iq[0], iq[1], s=6, alpha=0.4, label="All 1024 samples (includes transitions)")
        ax.set(title=f"QPSK RRC constellation | {target} dB", xlabel="I", ylabel="Q")
        ax.set_aspect("equal", adjustable="box")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=7)
        save(fig, "constellations", f"day2_QPSK_{target}dB.png")

    rng = np.random.default_rng(config.seed)
    for name in ("BPSK", "QPSK", "16QAM"):
        clean = generate_waveform(name, 65536, config.sps, config.beta, config.span, rng)
        f, psd_db = waveform_psd(clean)
        fig, ax = plt.subplots(figsize=(7, 4))
        ax.plot(f, psd_db, label="Clean RRC waveform")
        edge = (1 + config.beta) / (2 * config.sps)
        ax.axvline(-edge, color="gray", linestyle="--", label="Nominal band edges")
        ax.axvline(edge, color="gray", linestyle="--")
        ax.set(title=f"{name} Welch PSD | beta={config.beta}, sps={config.sps}",
               xlabel="Normalized frequency (cycles/sample)", ylabel="PSD (dB / cycles/sample)")
        ax.legend()
        ax.grid(alpha=0.3)
        save(fig, "psd", f"day2_{name}.png")
    return files
