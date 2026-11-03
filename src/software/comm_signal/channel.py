"""实现复 AWGN 信道及基于功率比的 SNR 测量。"""

import numpy as np


def _finite_signal(signal):
    """转换为复数组，并拒绝空输入及非有限值。"""
    values = np.asarray(signal, dtype=np.complex128)
    if values.size == 0 or not np.all(np.isfinite(values)):
        raise ValueError("signal must be nonempty and finite")
    return values


def _power(signal):
    """计算样本平均功率，拒绝数值溢出。"""
    power = float(np.mean(np.abs(signal) ** 2))
    if not np.isfinite(power):
        raise ValueError("signal power is not finite")
    return power


def add_awgn(signal, snr_db, rng=None):
    """按输入实测功率添加复高斯噪声，每路方差为 P_signal/(2*SNR_linear)。

    不强制缩放随机噪声的样本功率，因此实测 SNR 存在合理抽样误差。
    """
    values = _finite_signal(signal)
    power = _power(values)
    if power <= 0 or not np.isfinite(snr_db):
        raise ValueError("signal power must be positive and SNR finite")
    with np.errstate(over="ignore", under="ignore", divide="ignore"):
        snr_linear = np.power(10.0, float(snr_db) / 10.0)
        noise_power = power / snr_linear
    if not np.isfinite(noise_power) or noise_power <= 0:
        raise ValueError("SNR exceeds supported floating-point range")
    # 两路独立噪声各承担一半功率，标准差是方差的平方根。
    sigma = np.sqrt(noise_power / 2)
    rng = np.random.default_rng(rng)
    noise = sigma * (rng.standard_normal(values.shape)
                     + 1j * rng.standard_normal(values.shape))
    return values + noise


def measure_snr(clean_signal, noisy_signal):
    """由 noisy-clean 的残差功率计算 SNR（dB），要求输入形状一致。

    正功率信号无噪声时返回正无穷；零功率参考信号的 SNR 未定义，拒绝输入。
    """
    clean = _finite_signal(clean_signal)
    noisy = _finite_signal(noisy_signal)
    if clean.shape != noisy.shape:
        raise ValueError("clean and noisy signal shapes must match")
    signal_power = _power(clean)
    if signal_power <= 0:
        raise ValueError("clean signal power must be positive")
    noise_power = _power(noisy - clean)
    if noise_power == 0:
        return float("inf")
    return float(10 * (np.log10(signal_power) - np.log10(noise_power)))
