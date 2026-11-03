"""Explicit signed INT8 grids; torch.round uses ties-to-even rounding."""
from dataclasses import dataclass
import torch


@dataclass
class QParams:
    scale: torch.Tensor
    zero_point: torch.Tensor
    qmin: int
    qmax: int
    axis: int | None = None

    def as_dict(self):
        return dict(scale=self.scale.tolist(), zero_point=self.zero_point.tolist(),
                    qmin=self.qmin, qmax=self.qmax, axis=self.axis)


def calculate_qparams(x, symmetric=True, axis=None):
    if not x.is_floating_point() or not x.numel() or not torch.isfinite(x).all():
        raise ValueError('Expected a nonempty finite floating tensor')
    if axis is not None and not 0 <= axis < x.ndim:
        raise ValueError('Invalid channel axis')
    dims = tuple(i for i in range(x.ndim) if i != axis)
    low = x.amin(dims, keepdim=axis is not None) if dims else x
    high = x.amax(dims, keepdim=axis is not None) if dims else x
    if symmetric:
        bound = torch.maximum(low.abs(), high.abs())
        scale = torch.where(bound > 0, bound / 127, torch.ones_like(bound))
        zero = torch.zeros_like(scale)
        qmin, qmax = -127, 127
    else:
        low = torch.minimum(low, torch.zeros_like(low))
        high = torch.maximum(high, torch.zeros_like(high))
        span = high - low
        scale = torch.where(span > 0, span / 255, torch.ones_like(span))
        zero = (-128 - torch.round(low / scale)).clamp(-128, 127)
        qmin, qmax = -128, 127
    if not torch.isfinite(scale).all() or not (scale > 0).all():
        raise ValueError('Range cannot be represented with a finite positive scale')
    return QParams(scale, zero, qmin, qmax, axis)


def quantize_tensor(x, params):
    if not torch.isfinite(x).all():
        raise ValueError('Non-finite quantization input')
    return (torch.round(x / params.scale) + params.zero_point).clamp(params.qmin, params.qmax).to(torch.int8)


def dequantize_tensor(q, params):
    return (q.to(params.scale.dtype) - params.zero_point) * params.scale


def fake_quantize(x, params):
    return dequantize_tensor(quantize_tensor(x, params), params)


def error_metrics(x, reconstructed):
    if x.shape != reconstructed.shape or not x.numel():
        raise ValueError('Error tensors must have the same nonempty shape')
    delta = (x.double() - reconstructed.double()).abs()
    if not torch.isfinite(delta).all():
        raise ValueError('Non-finite quantization error')
    return dict(mae=delta.mean().item(), mse=delta.square().mean().item(), max_abs_error=delta.max().item())
