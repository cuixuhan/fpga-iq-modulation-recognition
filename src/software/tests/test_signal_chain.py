"""使用标准库 unittest 从项目根目录验证 Day 1 通信链路。"""

import sys
import unittest
import numpy as np

# 支持从项目根目录直接执行 python tests/test_signal_chain.py。
if __name__ == "__main__" and not __package__:
    sys.path.insert(0, ".")
from comm_signal.modulation import MODULATORS, normalize_power
from comm_signal.channel import add_awgn, measure_snr


class TestPower(unittest.TestCase):
    """Test B：每种调制使用 100000 个符号验证平均功率。"""

    def test_average_power(self):
        """验证所有调制的样本平均功率误差小于 0.02。"""
        for name, generate in MODULATORS.items():
            with self.subTest(modulation=name):
                symbols = generate(100000, np.random.default_rng(42))
                power = float(np.mean(np.abs(symbols) ** 2))
                self.assertLess(abs(power - 1), 0.02)
                print(f"{name:5s} average power = {power:.6f} PASS")


class TestOutput(unittest.TestCase):
    """Test A：验证数组约定和独立推导的理想星座几何。"""

    def test_array_contract(self):
        """验证复数组类型、长度和有限性。"""
        for name, generate in MODULATORS.items():
            with self.subTest(modulation=name):
                s = generate(100000, np.random.default_rng(42))
                self.assertIsInstance(s, np.ndarray)
                self.assertTrue(np.iscomplexobj(s))
                self.assertEqual(s.shape, (100000,))
                self.assertTrue(np.all(np.isfinite(s)))
        print("Test A: all array types, complex dtypes and lengths PASS")

    def test_constellation_geometry(self):
        """验证星座点数量、相位和 QAM 电平比例。"""
        for (name, generate), count in zip(MODULATORS.items(), (2, 4, 8, 16, 64)):
            with self.subTest(modulation=name):
                s = generate(100000, np.random.default_rng(42))
                self.assertEqual(len(np.unique(s)), count)
                if name == "BPSK":
                    np.testing.assert_array_equal(np.unique(s), [-1+0j, 1+0j])
                elif name in ("QPSK", "8PSK"):
                    np.testing.assert_allclose(abs(s), 1, atol=1e-12)
                    offset = np.pi/4 if name == "QPSK" else 0
                    expected = np.exp(1j * (offset + np.arange(count)*2*np.pi/count))
                    self.assertTrue(np.all(np.min(abs(np.unique(s)[:, None]-expected), axis=1)<1e-12))
                else:
                    side = int(np.sqrt(count))
                    levels = np.arange(-side+1, side, 2)
                    for component in (s.real, s.imag):
                        unique = np.unique(component)
                        np.testing.assert_allclose(unique/np.min(abs(unique)), levels, atol=1e-12)


class TestRepeatability(unittest.TestCase):
    """Test D：相同种子应复现发送符号与加噪样本。"""

    def test_seed(self):
        """验证相同种子完全复现，不同种子产生不同符号。"""
        for name, generate in MODULATORS.items():
            with self.subTest(modulation=name):
                rng_a = np.random.default_rng(42)
                rng_b = np.random.default_rng(42)
                a, b = generate(4096, rng_a), generate(4096, rng_b)
                np.testing.assert_array_equal(a, b)
                np.testing.assert_array_equal(add_awgn(a, 10, rng_a), add_awgn(b, 10, rng_b))
                self.assertFalse(np.array_equal(a, generate(4096, np.random.default_rng(43))))
        print("Test D: identical seeds reproduce all clean/noisy signals PASS")


class TestEdgesAndNoise(unittest.TestCase):
    """检查异常输入，并独立于 SNR 测量函数验证噪声统计。"""

    def test_normalization(self):
        """验证归一化、输入不变及非法输入处理。"""
        original = np.array([3+4j, 6+8j])
        before = original.copy()
        normalized = normalize_power(original)
        self.assertAlmostEqual(float(np.mean(abs(normalized)**2)), 1)
        np.testing.assert_array_equal(original, before)
        np.testing.assert_allclose(normalized[1]/normalized[0], 2)
        for bad in ([], [0, 0], [np.nan], [np.inf]):
            with self.assertRaises(ValueError):
                normalize_power(bad)

    def test_invalid_counts(self):
        """验证符号数必须为正整数。"""
        for generate in MODULATORS.values():
            for count in (0, -1, 1.5, True):
                with self.assertRaises(ValueError):
                    generate(count)
            self.assertEqual(generate(1).shape, (1,))

    def test_noise_statistics(self):
        """以非单位功率信号验证两路噪声方差与独立性。"""
        clean = np.full(100000, 3+4j)
        noise = add_awgn(clean, 10, np.random.default_rng(42)) - clean
        for component in (noise.real, noise.imag):
            self.assertLess(abs(float(np.mean(component))), 0.02)
            self.assertLess(abs(float(np.var(component))-1.25), 0.03)
        self.assertLess(abs(float(np.corrcoef(noise.real, noise.imag)[0, 1])), 0.02)
        self.assertLess(abs(measure_snr(clean, clean+noise)-10), 0.3)

    def test_measurement_and_invalid_inputs(self):
        """验证已知 SNR、零噪声与非法输入。"""
        clean = np.ones(16, dtype=complex)
        self.assertAlmostEqual(measure_snr(clean, clean+0.1j), 20)
        self.assertTrue(np.isposinf(measure_snr(clean, clean)))
        for bad in ([], [0, 0], [np.nan]):
            with self.assertRaises(ValueError):
                add_awgn(bad, 10)
        for bad_snr in (np.nan, np.inf, -np.inf, 10000, -10000):
            with self.assertRaises(ValueError):
                add_awgn(clean, bad_snr)
        with self.assertRaises(ValueError):
            measure_snr(clean, np.ones((16, 1)))
        with self.assertRaises(ValueError):
            measure_snr(np.zeros(16), clean)


class TestSNR(unittest.TestCase):
    """Test C：对四个目标 SNR 分别独立抽取噪声进行验证。"""

    def test_snr(self):
        """对两个调制与四个 SNR 验证误差小于 0.3 dB。"""
        rng = np.random.default_rng(42)
        print("Modulation | Target SNR | Measured SNR | Error | Result")
        for name in ("QPSK", "16QAM"):
            clean = MODULATORS[name](100000, rng)
            for target in (-5, 0, 10, 20):
                with self.subTest(modulation=name, snr=target):
                    measured = measure_snr(clean, add_awgn(clean, target, rng))
                    error = abs(measured - target)
                    self.assertLess(error, 0.3)
                    print(f"{name} | {target:.1f} dB | {measured:.6f} dB | {error:.6f} dB | PASS")


class TestShape(unittest.TestCase):
    """Test E：加噪保持输入形状，且不修改输入数组。"""

    def test_awgn_shape(self):
        """覆盖全部调制的一维符号及二维、三维数组。"""
        rng = np.random.default_rng(42)
        for generate in MODULATORS.values():
            for shape in ((120,), (12, 10), (3, 4, 10)):
                clean = generate(120, rng).reshape(shape)
                before = clean.copy()
                noisy = add_awgn(clean, 10, rng)
                self.assertEqual(noisy.shape, clean.shape)
                self.assertTrue(np.iscomplexobj(noisy))
                np.testing.assert_array_equal(clean, before)
        print("Test E: AWGN shapes and unchanged inputs PASS")


if __name__ == "__main__":
    unittest.main(verbosity=2)
