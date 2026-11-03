"""Run the fixed Day 2 baseline from the project root."""

from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
from comm_signal.dataset import DatasetConfig, MODULATION_TO_LABEL, SNR_LIST
from comm_signal.dataset import generate_dataset, stratified_split, save_dataset
from comm_signal.visualization import generate_plots


def main():
    config = DatasetConfig()
    rng = np.random.default_rng(config.seed)
    dataset = generate_dataset(config, rng)
    splits = stratified_split(dataset, rng)
    path = Path("data/modulation_dataset.npz")
    counts = [np.count_nonzero((dataset["y"] == label) & (dataset["snr"] == target))
              for label in MODULATION_TO_LABEL.values() for target in SNR_LIST]
    assert set(counts) == {config.samples_per_combination}
    save_dataset(path, splits, config)
    figures = generate_plots(dataset, config)
    lines = ["Day 2 Dataset Generation Completed", "", "Modulations:",
             *MODULATION_TO_LABEL, f"SNR levels: {np.unique(dataset['snr']).tolist()} dB",
             f"Samples per modulation/SNR: {counts[0]}", f"Total samples: {len(dataset['X'])}",
             f"IQ layout: {dataset['X'].shape[1:]}"]
    for key in ("X", "y", "snr"):
        lines.append(f"{key} shape: {dataset[key].shape}")
    lines.append(f"dtype: {dataset['X'].dtype}")
    for name in ("train", "val", "test"):
        lines.append(f"{name}: {len(splits[f'y_{name}'])}")
    lines += [f"Saved and reloaded exactly: {path}", "Mean measured SNR (saved float32 IQ):"]
    for target in SNR_LIST:
        measured = dataset["measured_snr"][dataset["snr"] == target].mean()
        assert abs(measured - target) < 0.1
        lines.append(f"Target {target:3d} dB: {measured:.6f} dB")
    lines += ["Figures:", *map(str, figures)]
    summary = "\n".join(lines)
    Path("results/day2_generation.txt").write_text(summary + "\n", encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
