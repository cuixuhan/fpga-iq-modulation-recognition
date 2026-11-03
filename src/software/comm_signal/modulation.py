"""生成独立、均匀随机的复基带符号，并统一样本平均功率。"""

import numpy as np


def normalize_power(symbols):
    """返回单位样本平均功率的复数组；拒绝空、非有限或零功率输入。"""
    values = np.asarray(symbols, dtype=np.complex128)
    if values.size == 0 or not np.all(np.isfinite(values)):
        raise ValueError("symbols must be nonempty and finite")
    scale = np.max(np.abs(values))
    if scale == 0:
        raise ValueError("cannot normalize zero-power symbols")
    # 先缩放避免平方溢出，数学上等价于直接除以原始均方根。
    scaled = values / scale
    return scaled / np.sqrt(np.mean(np.abs(scaled) ** 2))


def _generator(num_symbols, rng):
    """检查正整数符号数，复用传入的 Generator，避免全局随机状态。"""
    if isinstance(num_symbols, (bool, np.bool_)) or not isinstance(num_symbols, (int, np.integer)):
        raise ValueError("num_symbols must be a positive integer")
    if num_symbols <= 0:
        raise ValueError("num_symbols must be a positive integer")
    return np.random.default_rng(rng)


def generate_bpsk(num_symbols, rng=None):
    """将等概率 0/1 映射为 -1/+1，返回 complex128 BPSK 符号。"""
    rng = _generator(num_symbols, rng)
    return normalize_power(2 * rng.integers(0, 2, num_symbols) - 1)


def _square_qam(num_symbols, levels, rng):
    """独立抽取 I/Q 电平，组合成复数并归一化样本功率。"""
    rng = _generator(num_symbols, rng)
    i, q = rng.choice(levels, size=(2, num_symbols))
    return normalize_power(i + 1j * q)


def generate_qpsk(num_symbols, rng=None):
    """I/Q 各取 -1/+1，生成四点 QPSK 星座。"""
    return _square_qam(num_symbols, [-1, 1], rng)


def generate_8psk(num_symbols, rng=None):
    """按 theta_k = 2*pi*k/8（k=0,...,7）生成八点 PSK 星座。"""
    rng = _generator(num_symbols, rng)
    phases = 2 * np.pi * rng.integers(0, 8, num_symbols) / 8
    return normalize_power(np.exp(1j * phases))


def generate_16qam(num_symbols, rng=None):
    """使用 -3、-1、+1、+3 四个电平生成 16QAM。"""
    return _square_qam(num_symbols, [-3, -1, 1, 3], rng)


def generate_64qam(num_symbols, rng=None):
    """使用 -7 到 +7 的八个奇数电平生成 64QAM。"""
    return _square_qam(num_symbols, np.arange(-7, 8, 2), rng)


MODULATORS = {
    "BPSK": generate_bpsk,
    "QPSK": generate_qpsk,
    "8PSK": generate_8psk,
    "16QAM": generate_16qam,
    "64QAM": generate_64qam,
}
