"""Day 6 v1: integer-only kernels; INT64 simulation, checked INT32 sums.

No floating MACs. Offline parameter generation is explicitly separate.
"""
import math
import numpy as np

I32 = 2**31 - 1
I64 = 2**63 - 1
CONTRACT = dict(version='day6-v1', activation='int8 [-128,127], per-tensor',
    weight='int8 [-127,127], symmetric output-channel axis 0', bias='int32',
    accumulator='target int32, simulated in int64 after conservative bound check',
    centered_activation='int64, mathematical range [-255,255]',
    product='checked int64', multiplier='positive signed int32 M',
    shift='0..62; largest shift with M<=2^31-1 and B*M<=2^63-1',
    rounding='signed nearest ties-to-even using quotient/remainder',
    saturation='clip before int8 conversion; ReLU before clip at output zero point',
    padding='Conv real zero = input zero point; MaxPool padding unsupported',
    gap='centered integer sum then one M/2**shift for Sx/(L*Sy)',
    parameter_error_budget_codes=0.001, argmax='first maximum, shared logits grid',
    accuracy_quality_threshold='not set', layout='NCL / OIK; Linear NC / OI')


def integer(x):
    x = np.asarray(x)
    if x.dtype.kind not in 'iu' or not x.size:
        raise ValueError('Expected nonempty integer array')
    if int(x.min()) < -I64 or int(x.max()) > I64:
        raise OverflowError('outside symmetric safe int64 domain')
    return x.astype(np.int64)


def zero_point(z):
    if not isinstance(z, (int, np.integer)) or not -128 <= z <= 127:
        raise ValueError('Invalid INT8 zero point')
    return int(z)


def codes(x):
    if np.asarray(x).dtype != np.int8:
        raise ValueError('Activation/weight storage must be INT8')
    return integer(x)


def round_shift(x, shift):
    x, shift = integer(x), np.asarray(shift)
    if shift.dtype.kind not in 'iu' or np.any(shift < 0) or np.any(shift > 62):
        raise ValueError('shift must be integer 0..62')
    divisor = np.left_shift(np.int64(1), shift.astype(np.int64))
    # floor quotient with nonnegative remainder: works for both signs.
    q, r = np.divmod(x, divisor)
    half = divisor // 2
    up = (r > half) | ((divisor > 1) & (r == half) & ((q & 1) != 0))
    return q + up.astype(np.int64)


def saturate(x):
    return np.clip(integer(x), -128, 127).astype(np.int8)


def bias_quantize(bias, scales):
    b, s = np.asarray(bias, dtype=np.float64), np.asarray(scales, dtype=np.float64)
    if b.shape != s.shape or not np.isfinite(b).all() or not np.isfinite(s).all() or np.any(s <= 0):
        raise ValueError('Invalid per-channel bias scales')
    q = np.rint(b / s)
    if not np.isfinite(q).all() or np.any(q < -2**31) or np.any(q > I32):
        raise OverflowError('bias exceeds INT32')
    return q.astype(np.int32)


def fixed_params(ratios, bounds):
    ratios, bounds = np.atleast_1d(ratios), np.atleast_1d(bounds)
    if ratios.shape != bounds.shape:
        raise ValueError('Ratio/bound shape mismatch')
    ms, shifts, errors = [], [], []
    for ratio, bound in zip(ratios, bounds):
        r, b = float(ratio), int(bound)
        if not math.isfinite(r) or r <= 0 or not 0 <= b <= I32:
            raise ValueError('Invalid ratio or INT32 bound')
        for s in range(62, -1, -1):
            m = round(r * 2**s)
            if 0 < m <= I32 and b*m <= I64:
                error = abs(m / 2**s - r)
                if b*error > CONTRACT['parameter_error_budget_codes']:
                    raise ValueError('Fixed point error budget exceeded')
                ms.append(m); shifts.append(s); errors.append(error)
                break
        else:
            raise ValueError('Ratio cannot be represented without silent zero')
    return np.array(ms, np.int32), np.array(shifts, np.int32), np.array(errors)


def accumulator_bound(weight, bias, zx):
    w = codes(weight)
    z = zero_point(zx)
    if np.any(w == -128):
        raise ValueError('Symmetric weight grid excludes -128')
    if np.asarray(bias).dtype != np.int32 or bias.shape != (w.shape[0],):
        raise ValueError('Expected one INT32 bias per output channel')
    bounds = max(abs(-128-z), abs(127-z))*np.abs(w).reshape(w.shape[0], -1).sum(1) + np.abs(bias.astype(np.int64))
    if np.any(bounds > I32):
        raise OverflowError('Conservative partial sum + bias bound exceeds INT32')
    return bounds


def requantize(acc, m, shift, zy, relu=False):
    a, m, shift = integer(acc), integer(m), integer(shift)
    zy = zero_point(zy)
    if np.any(m <= 0) or np.any(m > I32):
        raise ValueError('M outside positive INT32')
    if np.any(a < -2**31) or np.any(a > I32):
        raise OverflowError('Accumulator outside INT32')
    if int(np.abs(a).max())*int(m.max()) > I64:
        raise OverflowError('Fixed product outside INT64')
    product = a*m
    rounded = round_shift(product, shift)
    if int(rounded.min()) < -I64 + abs(zy) or int(rounded.max()) > I64-abs(zy):
        raise OverflowError('Zero-point addition outside INT64')
    raw = rounded + zy
    if relu:
        raw = np.maximum(raw, zy)
    return saturate(raw), dict(acc_min=int(a.min()), acc_max=int(a.max()),
        product_min=int(product.min()), product_max=int(product.max()),
        saturated=int(((raw < -128) | (raw > 127)).sum()), count=raw.size)


def conv1d(x, w, b, zx, padding=0, stride=1, dilation=1, groups=1):
    if stride != 1 or dilation != 1 or groups != 1 or not isinstance(padding, int) or padding < 0:
        raise ValueError('Only stride=dilation=groups=1 and nonnegative padding supported')
    a, weight = codes(x), codes(w)
    if a.ndim != 3 or weight.ndim != 3 or a.shape[1] != weight.shape[1]:
        raise ValueError('Expected NCL/OIK with matching channels')
    bounds = accumulator_bound(w, b, zx)
    # Padding in the uncentered storage grid is exactly zx.
    a = np.pad(a, ((0,0),(0,0),(padding,padding)), constant_values=zx) - zx
    if a.shape[-1] < weight.shape[-1]:
        raise ValueError('Kernel longer than padded input')
    windows = np.lib.stride_tricks.sliding_window_view(a, weight.shape[-1], axis=2)
    acc = np.einsum('nclk,ock->nol', windows, weight, optimize=True) + b.astype(np.int64)[None,:,None]
    if np.any(np.abs(acc) > bounds[None,:,None]):
        raise OverflowError('Accumulator violated proven bound')
    return acc


def linear(x, w, b, zx):
    a, weight = codes(x), codes(w)
    if a.ndim != 2 or weight.ndim != 2 or a.shape[1] != weight.shape[1]:
        raise ValueError('Expected NC/OI')
    bounds = accumulator_bound(w, b, zx)
    acc = (a-zx) @ weight.T + b.astype(np.int64)
    if np.any(np.abs(acc) > bounds):
        raise OverflowError('Accumulator violated proven bound')
    return acc


def relu(x, z):
    return np.maximum(codes(x), zero_point(z)).astype(np.int8)


def maxpool(x, kernel=2, stride=2, padding=0):
    a = codes(x)
    if a.ndim != 3 or kernel != 2 or stride != 2 or padding != 0 or a.shape[-1] < 2:
        raise ValueError('Only nonpadded NCL MaxPool2 stride2 supported')
    return np.maximum(a[:,:,:a.shape[-1]//2*2:2], a[:,:,1:a.shape[-1]//2*2:2]).astype(np.int8)


def gap(x, zx, m, shift, zy):
    a = codes(x)
    zx = zero_point(zx)
    if a.ndim != 3 or a.shape[2]*max(abs(-128-zx), abs(127-zx)) > I32:
        raise OverflowError('GAP sum not INT32 safe')
    acc = (a-zx).sum(2)
    out, stats = requantize(acc, m, shift, zy)
    return out, acc, stats
