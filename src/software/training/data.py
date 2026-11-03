"""Read the original Day 2 splits without signal transformations."""
import json
import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader
from comm_signal.dataset import MODULATION_TO_LABEL, SNR_LIST


class IQDataset(Dataset):
    def __init__(self, x, y, snr):
        if x.ndim != 3 or x.shape[1:] != (2, 1024) or x.dtype != np.float32:
            raise ValueError("IQ must be float32 (N, 2, 1024)")
        if not len(x) or y.shape != (len(x),) or snr.shape != y.shape:
            raise ValueError("empty or misaligned samples/labels/SNR")
        if not np.issubdtype(y.dtype, np.integer) or not np.isin(y, range(5)).all():
            raise ValueError("labels must be integers 0..4")
        if not np.isfinite(x).all() or not np.isin(snr, SNR_LIST).all():
            raise ValueError("invalid IQ or SNR")
        self.x = torch.from_numpy(x)
        self.y = torch.from_numpy(y.astype(np.int64))
        self.snr = torch.from_numpy(snr.astype(np.float32))

    def __len__(self):
        return len(self.y)

    def __getitem__(self, index):
        return self.x[index], self.y[index], self.snr[index]


def load_splits(path):
    with np.load(path, allow_pickle=False) as archive:
        metadata = json.loads(str(archive['metadata']))
        if metadata['channels'] != ['I', 'Q'] or metadata['modulation_to_label'] != MODULATION_TO_LABEL:
            raise ValueError("Day 2 channel/label metadata mismatch")
        splits = {s: IQDataset(archive[f'X_{s}'], archive[f'y_{s}'], archive[f'snr_{s}'])
                  for s in ('train', 'val', 'test')}
        indices = [archive[f'indices_{s}'] for s in splits]
        combined = np.concatenate(indices)
        if len(np.unique(combined)) != len(combined):
            raise ValueError("overlapping split indices")
        for split in splits.values():
            if set(split.y.tolist()) != set(range(5)) or set(split.snr.tolist()) != set(SNR_LIST):
                raise ValueError("missing class or SNR")
    return splits, metadata


def make_loaders(splits, batch_size=64, seed=42):
    return {s: DataLoader(ds, batch_size=batch_size, shuffle=s == 'train', num_workers=0,
                          generator=torch.Generator().manual_seed(seed))
            for s, ds in splits.items()}
