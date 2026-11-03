"""Zero insertion, unit-energy RRC, and transient-free complex waveforms."""

import numpy as np

from .modulation import MODULATORS, normalize_power


def positive_integer(value, name):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return int(value)


def upsample(symbols, sps=4):
    sps = positive_integer(sps, "sps")
    symbols = np.asarray(symbols, dtype=np.complex128)
    if symbols.ndim != 1 or not symbols.size or not np.isfinite(symbols).all():
        raise ValueError("symbols must be a nonempty finite vector")
    result = np.zeros(symbols.size * sps, dtype=np.complex128)
    result[::sps] = symbols
    return result


def rrc_filter(beta=0.35, span=8, sps=4):
    """beta: roll-off factor; span: filter span in symbols; sps: samples per symbol."""
    span = positive_integer(span, "span")
    sps = positive_integer(sps, "sps")
    if not np.isfinite(beta) or not 0 <= beta <= 1:
        raise ValueError("beta must be in [0, 1]")
    if span * sps % 2:
        raise ValueError("span*sps must be even for integer group delay")
    t = (np.arange(span * sps + 1) - span * sps / 2) / sps
    if beta == 0:
        h = np.sinc(t)
    else:
        h = np.empty_like(t)
        zero = t == 0
        singular = np.isclose(np.abs(t), 1 / (4 * beta), rtol=1e-12, atol=1e-14)
        regular = ~(zero | singular)
        h[zero] = 1 + beta * (4 / np.pi - 1)
        h[singular] = beta / np.sqrt(2) * (
            (1 + 2 / np.pi) * np.sin(np.pi / (4 * beta))
            + (1 - 2 / np.pi) * np.cos(np.pi / (4 * beta)))
        u = t[regular]
        h[regular] = (np.sin(np.pi * u * (1 - beta))
                      + 4 * beta * u * np.cos(np.pi * u * (1 + beta))) / (
                          np.pi * u * (1 - (4 * beta * u) ** 2))
    return h / np.linalg.norm(h)


def pulse_shape(symbols, beta=0.35, span=8, sps=4):
    """Remove FIR delay, then both unsupported boundary regions (D each)."""
    h = rrc_filter(beta, span, sps)
    impulses = upsample(symbols, sps)
    delay = (h.size - 1) // 2
    if impulses.size <= 2 * delay:
        raise ValueError("not enough symbols for a stable waveform")
    full = np.convolve(impulses, h, mode="full")
    aligned = full[delay:delay + impulses.size]
    return aligned[delay:impulses.size - delay]


def generate_waveform(modulation, sample_length=1024, sps=4, beta=0.35, span=8, rng=None):
    """Generate fresh symbols with guard symbols; normalize the final clean crop."""
    sample_length = positive_integer(sample_length, "sample_length")
    h = rrc_filter(beta, span, sps)
    delay = (h.size - 1) // 2
    count = (sample_length + 2 * delay + sps - 1) // sps
    symbols = MODULATORS[modulation](count, np.random.default_rng(rng))
    valid = pulse_shape(symbols, beta, span, sps)
    if valid.size < sample_length:
        raise RuntimeError("insufficient stable waveform length")
    return normalize_power(valid[:sample_length])
