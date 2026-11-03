# 第三方来源与公开范围

本仓库选自完整工程的 Stage5 冻结源码、软件信号链及训练模块。vectors 中的十六进制文件来自工程生成的板测输入与整数模型参数。接口沿用项目内部 person2 的寄存器协议，后处理沿用 person1 的算子，卷积和串口模块沿用项目早期实现。项目源码的许可见 LICENSE。

| 外部来源 | 在工程中的用途 | 获取方式 |
| --- | --- | --- |
| AMD Vivado / XSim | Artix-7 综合、实现及 RTL 仿真 | [AMD Vivado](https://www.amd.com/en/products/software/adaptive-socs-and-fpgas/vivado.html) |
| 正点原子 ALIENTEK | XDC 中时钟、复位和 UART 引脚依据 ATK-DF7A35 V2.1 原理图第 6–7、10 页整理 | [正点原子](https://www.alientek.com/) |
| NumPy、SciPy、Matplotlib | 数组运算、信号处理和结果绘图 | [NumPy](https://numpy.org/)、[SciPy](https://scipy.org/)、[Matplotlib](https://matplotlib.org/) |
| PyTorch、pytest | 训练模型与软件测试依赖 | [PyTorch](https://pytorch.org/)、[pytest](https://pytest.org/) |

第三方软件由使用者单独安装，各自许可由上游提供。公开版未打包厂商手册、原理图、Vivado 安装文件、pySerial 副本、原始会话记录或完整交付归档。
