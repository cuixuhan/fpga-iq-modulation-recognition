"""Seeded class x SNR calibration, using only the explicitly selected train split."""
import numpy as np
import torch
from torch.utils.data import DataLoader, Subset
from training.quantization import calculate_qparams
from training.quantized_model import ACTIVATION_POINTS


def stratified_indices(y, snr, count, seed=42):
    y, snr = np.asarray(y), np.asarray(snr)
    if y.ndim != 1 or y.shape != snr.shape or not np.isfinite(snr).all():
        raise ValueError('Labels and SNR must be aligned finite vectors')
    if not 0 < count <= len(y):
        raise ValueError('Calibration count must be within the training split')
    rng = np.random.default_rng(seed)
    groups = [rng.permutation(np.flatnonzero((y == label) & (snr == level))).tolist()
              for label, level in sorted(set(zip(y.tolist(), snr.tolist())))]
    # Round-robin ensures complete stratum coverage when count >= number of strata.
    order = rng.permutation(len(groups))
    indices = []
    while len(indices) < count:
        for i in order:
            if groups[i] and len(indices) < count:
                indices.append(groups[i].pop())
    return indices


@torch.inference_mode()
def calibrate(model, splits, count=512, seed=42, batch_size=64, split='train'):
    if split != 'train':
        raise ValueError('Calibration is permitted only on train')
    if any(m.training for m in model.modules()):
        raise ValueError('Calibration requires eval mode')
    dataset = splits['train']
    indices = stratified_indices(dataset.y, dataset.snr, count, seed)
    ranges, hooks = {}, []
    def observe(name, value):
        if not value.numel() or not torch.isfinite(value).all():
            raise ValueError('Non-finite or empty calibration activation')
        low, high = value.min().item(), value.max().item()
        previous = ranges.get(name, (low, high))
        ranges[name] = min(low, previous[0]), max(high, previous[1])
    try:
        for name in ACTIVATION_POINTS[1:]:
            hooks.append(model.get_submodule(name).register_forward_hook(
                lambda module, args, output, name=name: observe(name, output)))
        for x, _, _ in DataLoader(Subset(dataset, indices), batch_size=batch_size):
            observe('input', x)
            model(x)
    finally:
        for hook in hooks:
            hook.remove()
    params = {name: calculate_qparams(torch.tensor(bounds), symmetric=False) for name, bounds in ranges.items()}
    coverage = [dict(label=int(label), snr_db=float(level), count=int(sum(
        dataset.y[i].item() == label and dataset.snr[i].item() == level for i in indices)))
        for label, level in sorted(set(zip(dataset.y.tolist(), dataset.snr.tolist())))]
    report = dict(split='train', seed=seed, sample_count=len(indices), train_indices=indices,
        coverage=coverage, activations={name: dict(min=ranges[name][0], max=ranges[name][1],
                                                 **p.as_dict()) for name, p in params.items()})
    return params, report
