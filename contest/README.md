# 五类 IQ 调制识别 · 竞赛材料

实物开发板为正点原子达芬奇 **ATK-DF7A35 V2.1**，板号与版本由背面 PCB 丝印确认。Vivado 工程目标器件为 `xc7a35tfgg484-2`。正反面照片见设计报告文末。

[阅读设计报告 PDF](design_report.pdf) · [下载演示视频 MP4](https://github.com/cuixuhan/fpga-iq-modulation-recognition/raw/refs/heads/main/contest/demo.mp4) · [封版源码 eeba9f7](https://github.com/cuixuhan/fpga-iq-modulation-recognition/tree/eeba9f71ec4658420ed7eae35c255baf9067780d)

材料更新于 2026 年 11 月 4 日。报告为 26 页比赛模板五部分版（v4）；视频约 2 分 48 秒，包含现场操作片段与明确标识的 2026 年 10 月 31 日历史证据回放，并标明中间层证据来源和不含 UART 传输的计算耗时。此次更新不新增板测结论。报告按匿名评审要求不附个人仓库或原始会话链接；源码入口以本页为准。报告保留协作案例；原始会话入口见评审附件 evidence/messages.jsonl，正文不放外部链接。

| 评审附件 | 获取方式 | 内容 |
| --- | --- | --- |
| review_bundle.zip | 随赛提交的轻量评审附件 | 最终 PDF、演示视频、实际交互及证据索引 |
| engineering.zip | 请使用参赛队提供的完整工程附件 | 封存源码、数据、验证脚本、上板记录与历史归档 |

完整工程文件大小为 **3,662,358,687 字节**，SHA-256 为 `cfd64ce46ed11f8a42bff9773412a69ba91e793b04a0c53cba015d013d042853`。下载后可用 PowerShell 的 `Get-FileHash .\engineering.zip -Algorithm SHA256` 核对。GitHub 的 Download ZIP 提供公开源码快照。复现完整的封存工程请解压 engineering.zip，按 complete_out/pockage/README.md 操作。

[项目首页](../README.md) · [源码许可](../LICENSE) · [第三方材料范围](../THIRD_PARTY.md)

[材料版本与 SHA-256 清单](materials_manifest.json) · [公开文件校验](sha256.txt)。公开 PDF 与比赛 PDF 使用同一份 v4 文件，哈希一致；原始会话入口见评审附件，正文不放外部链接。演示视频在两处完全一致。
