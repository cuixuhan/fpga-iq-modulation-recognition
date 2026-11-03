"""Evaluation preserves labels and SNR in the same batch order."""
import numpy as np
import torch
from torch import nn


@torch.inference_mode()
def evaluate(model, loader, device):
    model.eval()
    labels, predictions, snrs, confidences = [], [], [], []
    loss_sum = 0.
    for x, y, snr in loader:
        logits = model(x.to(device))
        if not torch.isfinite(logits).all():
            raise RuntimeError('non-finite logits')
        loss_sum += nn.functional.cross_entropy(logits, y.to(device), reduction='sum').item()
        labels.append(y.cpu().numpy())
        predictions.append(logits.argmax(1).cpu().numpy())
        confidences.append(logits.softmax(1).amax(1).cpu().numpy())
        snrs.append(snr.cpu().numpy())
    if not labels:
        raise ValueError('cannot evaluate an empty loader')
    y, pred, snr = map(np.concatenate, (labels, predictions, snrs))
    correct, total = int((y == pred).sum()), len(y)
    return dict(loss=loss_sum / total, accuracy=correct / total, correct=correct,
                total=total, y=y, pred=pred, snr=snr,
                confidence=np.concatenate(confidences))
