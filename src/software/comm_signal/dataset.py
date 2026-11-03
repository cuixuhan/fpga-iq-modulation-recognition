"""Balanced independent IQ examples and reproducible stratified splits."""

from dataclasses import asdict, dataclass
import json
from pathlib import Path

import numpy as np

from .channel import add_awgn, measure_snr
from .pulse_shaping import generate_waveform, positive_integer

MODULATION_TO_LABEL = {"BPSK": 0, "QPSK": 1, "8PSK": 2, "16QAM": 3, "64QAM": 4}
SNR_LIST = [-10, -5, 0, 5, 10, 15, 20]


@dataclass(frozen=True)
class DatasetConfig:
    sample_length: int = 1024
    sps: int = 4
    beta: float = 0.35
    span: int = 8
    seed: int = 42
    samples_per_combination: int = 100


def complex_to_iq(waveform):
    waveform = np.asarray(waveform)
    if waveform.ndim != 1 or not np.iscomplexobj(waveform) or not np.isfinite(waveform).all():
        raise ValueError("waveform must be a finite complex vector")
    return np.stack([waveform.real, waveform.imag], axis=0).astype(np.float32)


def generate_dataset(config=DatasetConfig(), rng=None):
    rng = np.random.default_rng(config.seed if rng is None else rng)
    count = positive_integer(config.samples_per_combination, "samples_per_combination")
    length = positive_integer(config.sample_length, "sample_length")
    total = len(MODULATION_TO_LABEL) * len(SNR_LIST) * count
    X = np.empty((total, 2, length), dtype=np.float32)
    y = np.empty(total, dtype=np.int64)
    snr = np.empty(total, dtype=np.int16)
    measured = np.empty(total, dtype=np.float64)
    index = 0
    for name, label in MODULATION_TO_LABEL.items():
        for target in SNR_LIST:
            for _ in range(count):
                clean = generate_waveform(name, length, config.sps, config.beta, config.span, rng)
                X[index] = complex_to_iq(add_awgn(clean, target, rng))
                # Measure the actual float32 representation saved in the dataset.
                received = X[index, 0].astype(float) + 1j * X[index, 1].astype(float)
                measured[index] = measure_snr(clean, received)
                y[index], snr[index] = label, target
                index += 1
    return {"X": X, "y": y, "snr": snr, "measured_snr": measured}


def stratified_split(dataset, rng=None):
    """Exact 70/15/15 within each modulation/SNR group; reject rounding."""
    rng = np.random.default_rng(rng)
    groups = {name: [] for name in ("train", "val", "test")}
    for label in MODULATION_TO_LABEL.values():
        for target in SNR_LIST:
            indices = np.flatnonzero((dataset["y"] == label) & (dataset["snr"] == target))
            if not indices.size or indices.size % 20:
                raise ValueError("each group count must be a positive multiple of 20")
            indices = rng.permutation(indices)
            a, b = indices.size * 70 // 100, indices.size * 85 // 100
            for name, part in zip(groups, (indices[:a], indices[a:b], indices[b:])):
                groups[name].append(part)
    result = {}
    for name, parts in groups.items():
        indices = rng.permutation(np.concatenate(parts))
        result[f"indices_{name}"] = indices
        for key in ("X", "y", "snr", "measured_snr"):
            result[f"{key}_{name}"] = dataset[key][indices]
    return result


def save_dataset(path, splits, config):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    metadata = {"config": asdict(config), "modulation_to_label": MODULATION_TO_LABEL,
                "snr_levels": SNR_LIST, "channels": ["I", "Q"], "split_ratios": [0.7, 0.15, 0.15]}
    np.savez_compressed(path, **splits, metadata=np.array(json.dumps(metadata)))
    with np.load(path, allow_pickle=False) as loaded:
        for key, value in splits.items():
            np.testing.assert_array_equal(loaded[key], value)
        assert json.loads(str(loaded["metadata"])) == metadata
