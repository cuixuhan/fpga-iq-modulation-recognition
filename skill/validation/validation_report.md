# 公开技能包验证记录

日期：2026-11-04。结果见 verification.json。

- Python 3.12.14 执行 scripts/self_test.py：22/22 通过，退出码 0。
- scripts/check.py verify：9 个公开快照 SHA-256 校验通过，退出码 0。
- 测试包含整数边界、行序变化、单值篡改、缺尾、重复、越界、非法值、清单路径逃逸及复制到另一目录后的使用。
- 示例为人工夹具；不是新增 CNN 运行、Vivado 构建或板级采集。
- 首次使用沙箱系统临时目录遇到 WinError 5，未完成；改用包外工作区 tmp 后完成上述运行。未将首次环境失败计为通过。

复跑（从仓库根目录执行，tmp 必须存在且位于 skill/ 外）：

```text
python skill/scripts/self_test.py --temp-root tmp --output new_verification.json
python skill/scripts/check.py verify --manifest skill/evidence/source_manifest.json --root skill
```

输出文件必须尚不存在。公开历史快照中的机器路径和 JTAG 标识已脱敏，清单保留原件哈希与公开文件哈希；本次只校验公开副本，不冒充原件逐字节一致验证。不同电脑或项目的完整工程复现仍需单独验证。
