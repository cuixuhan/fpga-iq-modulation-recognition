# FPGA 整数推理验证技能包

本包把五类 IQ 调制识别原型开发中的整数验证、协议修复和证据管理经验提炼为可复用流程。既可直接供人阅读，也可将 `SKILL.md` 交给支持技能的编程助手。使用本目录不要求安装到全局技能目录。

## 适用范围与使用方法

| 能力 | 适用场景 | 使用入口 | 失效或不适用条件 |
|---|---|---|---|
| 冻结整数合同与逐层核对 | INT8 CNN、定点 DSP、相同合同的软件/RTL/板级输出 | `SKILL.md`、`references/integer_contract.md` | 不同量化网格或不同算术合同不能直接逐码比较；浮点容差比较不适用本包 CSV 工具 |
| 接口权限与副作用核查 | 寄存器、存储窗口、会话与暂停恢复协议 | `references/workflow.md`、案例 C2 | 合同缺失时先定合同；不能把本项目错误码当通用标准 |
| 文件身份与结果完整性校验 | 迁移工程、发布证据、检查缺项或篡改 | `scripts/check.py`、`references/tools.md` | hash 仅检查内容一致；不能证明测量真实、作者身份或板上配置 |
| 实测结果与报告归属 | FPGA 演示、测试报告、比赛材料 | `references/cases.md`、`assets/result_template.md` | 回放不能生成新板测；没有原始数据时只能标记未验证 |

## 快速开始

需要 Python 3.10 或更新版本；随包检查脚本仅使用标准库，无需 pip、Vivado、NumPy 或板卡。以下命令在本目录执行；`python` 应替换为本机真实 Python 可执行文件，不能使用不可用的 Windows 商店占位别名。

```text
python scripts/check.py verify --manifest evidence/source_manifest.json --root .
python scripts/check.py compare --schema assets/example/schema.json --expected assets/example/expected.csv --actual assets/example/actual.csv
python scripts/self_test.py
```

前两项成功返回 0；比较工具发现差异或输入不合约返回 1；命令参数错误返回 2。示例是人工构造的工具测试数据，绝非板测。

本公开包支持独立复制后执行以上三条命令。历史快照中的本机绝对路径和 JTAG 标识已脱敏；清单分别记录公开文件哈希与原文件哈希。公开快照不再与完整工程原件逐字节相同，因此不要将本清单用于 `--project-root` 原件一致性核验。完整工程的 Vivado 重建和板测不在工具自测范围内。

用于实际任务时，先阅读 `SKILL.md`，选择一个提示词模板，明确工程根目录、冻结输入、允许的动作及输出目录。对新项目，先生成独立 expected 和真实 actual，再按规范导出 CSV，不要把示例答案用于验证生产逻辑。

## 来源与验证效果

| 来源案例 | 历史观察和已有结果 | 提炼的可复用方法 |
|---|---|---|
| C1 整数合同与模型评价 | 固定软件整数测试集 403/525；是软件结果 | 位宽、零点、ties-to-even、逐层结果与分类真值分别核查 |
| C2 读权限不一致与修复 | 2026-10-25 G1 FAIL；2026-10-28 新版本 D1 范围 G1 PASS，962 行权限/边界检查 | 独立从合同推导模型、RTL、host 的共同预期，保留失败版本 |
| C3 单样本全网与恢复 | 2026-10-31 封版记录：1603 对帧、166172 标量零差异；仍是误分类样本 | 原始帧与逐层结果绑定版本；模型错分与硬件不一致分开 |
| C4 结果终端的离线验证 | 2026-11-02 终端 15 项回归通过，现场采集仍 PENDING | 清楚区分回放、软件统计、硬件输出与新采集 |

详情及不能外推的结论见 `references/cases.md`。历史原文件的相对路径、快照路径和 SHA256 在 `evidence/source_manifest.json`，公开快照按脱敏后的字节校验，原件哈希另行保留。快照只含支撑案例的摘要/指标及技能来源，不是完整模型、原始帧、位流或全部工程。

本次新增工具的实际执行记录见 `validation/verification.json` 和 `validation/validation_report.md`。本次公开版重新执行人工夹具、公开快照完整性和临时目录迁移检查；它们不增加硬件覆盖率，也不授予 G1/G2/G3。

## 目录

```text
skill/
  README.md                 人工使用入口和竞赛要求对照
  SKILL.md                  编程助手技能入口
  references/               合同、流程、案例、提示词和工具格式
  scripts/                  标准库检查工具与可重复自测
  assets/                   结果模板及明确标识的人工样例
  evidence/                 来源清单与原字节历史快照
  validation/               本次实际验证记录
```

## 提交说明

本包覆盖技能说明所需的适用范围、使用方法、失效条件、来源案例与已验证效果。它不是 PYNQ Skill，不主张该项额外加分。历史技能文件仅提供来源，不应直接执行其旧绝对路径或旧阶段任务。

本包不包含真实提示词—模型回答—自我纠错对话原文；该材料仍需在设计报告的协作记录附件中单独提交。工具与流程已做本包范围验证，但不同工程的迁移效果需由使用队伍验证。本公开技能包采用仓库根目录的 MIT 许可证；第三方工具遵循其自身许可证。

公开版未包含原目录中无关的 `skill_*.txt`、本机执行命令记录或原始会话。文件范围及校验值见 `package_manifest.json`。

## 能力范围

随包有两个 Python 脚本：`check.py`（规范化整数 CSV 对拍和文件校验）及 `self_test.py`。UART 排查流程见 `references/workflow.md`；项目量化校准实现见 [calibration.py](../src/software/training/calibration.py)。本包尚未提供通用 Vivado 报告抽数脚本，也不声称已有四类独立脚本。
