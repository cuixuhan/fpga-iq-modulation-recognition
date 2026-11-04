# 工具输入与输出

## 使用前提

Python 3.10+，仅标准库。`check.py` 只读指定文件，结果输出到标准输出；没有网络、串口或硬件动作。运行路径见 README。脚本适合可装入内存的结果数组；不适合无限数据流或超大张量。文件 hash 清单应由可信来源提供，攻击者同时修改文件及清单无法被简单 hash 检查发现。

## compare

输入三个文件：独立合同导出的 schema、独立参考 expected CSV、被测结果 actual CSV。JSON 示例见 `assets/example/schema.json`，张量 shape 必须是正整数列表，dtype 为 int8/16/32/64 或 uint8/16/32/64；layout 固定为 `c_order_flat`。shape/轴含义和模型身份仍需外部合同与日志说明。

CSV 表头严格为 `tensor,index,value`；index 是 C 顺序展开的零起始索引，value 是十进制整数。tensor 名称采用小写字母开头、后续小写字母/数字/下划线。每个声明张量的全部索引恰好出现一次，行顺序可不同。空张量、未知张量、重复索引、缺项、越界值、浮点文本和 X/Z 均拒绝。

```text
python scripts/check.py compare --schema assets/example/schema.json --expected assets/example/expected.csv --actual assets/example/actual.csv
```

结果含 PASS/FAIL、元素数、差异数量、前十个差异与三个输入的 SHA256。只保证这些规范化整数满足 schema 并相等，**不证明 CSV 来源是 FPGA，不验证 CRC，不重算 CNN，不评价分类准确率**。实际导出适配器必须另行检验，schema 不得从残缺 actual 推导。

## verify

清单字段为 `schema_version: 1` 和非空 `sources` 数组。每项含唯一 `id`、相对项目根的 `source`、相对技能根的 `snapshot`、原字节 `sha256`，可增加标题与用途。路径用正斜杠；拒绝绝对路径、父目录跳转以及解析后逃出指定根目录的路径。

默认只核验快照；提供 `--project-root` 时同时核验原工程文件。历史材料即使声明 PASS，也仅作为文件内容，不影响本工具判断。工具不执行快照。

## self_test

```text
python scripts/self_test.py
python scripts/self_test.py --output new_verification.json
```

受限环境若系统临时目录不可写，可指定包外已存在的可写目录，例如 `--temp-root ../tmp`。工具拒绝把临时根放到本技能目录内部，避免复制递归。

在系统临时目录创建人工输入并复制技能包，通过独立子进程检查实际退出码及 JSON 输出。用例涵盖相等、行重排、改值、缺尾、双方同时缺尾、重复、未知索引/张量、越界、非法数值、清单篡改及路径逃逸。临时夹具结束时清理；指定结果文件必须不存在，避免覆盖历史记录。

自测 PASS 只说明随包工具在列明用例下按预期工作。没有覆盖所有可能输入，未执行生产 RTL 或设备。当前实际结果见 `validation/verification.json`。
