# FPGA IQ 调制识别

实物开发板为正点原子达芬奇 **ATK-DF7A35 V2.1**，板号与版本由背面 PCB 丝印确认。Vivado 工程目标器件为 `xc7a35tfgg484-2`。正反面照片见设计报告文末。

本工程使用 Artix-7 上的单处理单元执行稠密 INT8 CNN，识别 BPSK、QPSK、8PSK、16QAM 和 64QAM。输入为 I、Q 两路各 1024 个采样点。软件端可生成带噪信号、训练浮点基线并研究整数量化，硬件端通过 UART 接收输入和参数并返回推理结果。

## 竞赛提交材料

[报告、演示视频和完整工程校验信息](contest/README.md) · [公开报告 PDF](contest/design_report.pdf) · [封版源码 eeba9f7](https://github.com/cuixuhan/fpga-iq-modulation-recognition/tree/eeba9f71ec4658420ed7eae35c255baf9067780d)。

## 源码与附件

| 目录 | 内容 |
| --- | --- |
| `src/software/` | 合成数据生成器、CNN、训练与量化实现、软件配置和信号链测试 |
| `src/fpga/rtl/` | Stage5 顶层、存储、调度、卷积与后处理模块 |
| `src/fpga/constraints/` | 正点原子达芬奇 ATK-DF7A35 V2.1 时钟、复位与 UART 管脚约束 |
| `src/fpga/contracts/` | UART 访问、阶段状态与错误记录的接口说明 |
| `src/fpga/sim/`、`vectors/` | 适配器和全网测试台，以及全网测试台读取的输入和整型参数 |

## 运行软件

从仓库根目录进入软件目录，在 Python 3.10+ 的独立环境中执行以下命令。依赖版本沿用原工程记录。

```sh
cd src/software
python -m pip install -r requirements.txt
python tests/test_signal_chain.py
python scripts/generate_dataset.py
python scripts/train_baseline.py --config configs/baseline_v1.json
```

数据生成器在当前目录写入 data 和 results。训练使用生成的数据，并将检查点写入本地。仅运行信号链测试时只需 NumPy。

## FPGA 实现与仿真

在配置好 Vivado 的命令行中，从仓库根目录执行。历史实现使用 Vivado 2026.1、xc7a35tfgg484-2 和 50 MHz 时钟。构建目录必须尚不存在。

```sh
vivado -mode batch -source src/fpga/scripts/day2_build.tcl -tclargs src/fpga build-stage5
```

脚本运行综合和布局布线并生成报告。`src/rtl_gate.json` 是该脚本读取的历史输入。全网仿真顶层为 `tb_network`，使用 SystemVerilog 编译生产 RTL 和对应测试台；运行仿真时，工作目录下须能访问仓库提供的 `vectors/`。

## 结果的适用范围

历史封版位流在 ID2259（16QAM，−5 dB）上输出与整数参考一致，两者均误判为 8PSK。403/525 是软件整数参考在测试集上的分类结果。历史实现使用 15,832 个 LUT、9 个 DSP、65 个 BRAM18 等效块，50 MHz 下 WNS 为 +2.102 ns，报告保留 116 条 REQP-1840 告警。

本次公开整理在软件端运行了 10 项信号链测试，全部通过。上述硬件结果来自完整包的封版记录，本次未重跑 Vivado、全网仿真或板测。

项目采用仓库已有的 [MIT 许可证](LICENSE)。外部工具、依赖和板卡资料见[第三方来源说明](THIRD_PARTY.md)。
