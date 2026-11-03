# stage5-solo-d1-v1 单人整合合同

规范数值和地址见solo_interface.json。组织：用户统筹，Codex实施；数值/接口、可测试性和独立整合验收均待新聊天审核，不代表原三方签核。

来源映射：person2 stage5-p2-d1-v2（hash记于JSON upstream_contract）提供regions、weights、parameters、post_ports、八阶段及session/job/token语义；person1 Day2两个算子模块保持原端口与算术；生产cnn_dense_core的scanner/FIFO/MAC/requant被提取为外置RAM分支，来源与复制hash见lineage_initial.json及最终run lineage.json。旧person和Stage2–4不改。

选择FULL_RESIDENT_SINGLE_START和person1串行128输入Linear；固定day6-v1量化/模型/split，1PE dense。参数在开始前完整装载，计算阶段不接受host写激活。Conv1/Pool1/Conv2/Pool2/Conv3/GAP/Linear/argmax均由调度推进。W35904/AW16、参数229 words/AW8；所有算子共用一套A/B/W/参数/debug RAMB18E1。66 BRAM18是该拓扑估算，不是综合测量，80规划不改。

网络/Conv/Post启动计数uint64：MAX-1可增至MAX，下一次增量饱和并fatal OVERFLOW，不发该子模块START；reset清零。stage admission单独占一拍，完成依赖生产者done和adapter/生产者排空。wr_ready为物理RAM边沿commit。reset清事务有效位和管线，不清整片BRAM；session每次完整重装重新设置，host不得重用，有限tag不保证任意重放安全。

新wire VERSION=0x00050003。原因：单人整合新增ERROR_RECORD；0x00050002旧客户端必须拒绝混用。本实现当前只接受完整寄存器读取（首地址且精确长度），不是旧v2允许的寄存器内子窗口读取。内存诊断仍按1..256B顺序分块；其他访问拒绝。LOAD_COUNTS保持JSON region顺序A/B/W/bias/M/shift/gap/debug，其中B/debug为0。旧CMD0x04拒绝。

ERROR_RECORD在0x180..0x1bf、64B、只读、little endian。偏移：version0/4B、valid4/4B、source8/4B、local_code12/4B、shared_code16/4B、stage20/4B、session24/8B、job32/4B、token36/4B、address40/4B、operation44/4B、Conv启动48/8B、Post启动56/8B。source0=host拒绝、source1=调度错误、source2=post错误、source3=Conv错误；local_code保留算子原码，post失败读地址可用，Conv内部地址未导出时用0xffffffff表示未知，不能把该值当实测地址。CLEAR_ERROR不复活输出。

诊断每阶段排空后暂停，Conv每层读B32768+debug2048，Pool读A16384，GAP读A128+debug512，Linear读B5+debug[512:532]，argmax读WINNER4；完整发送响应后才计完成。normal不等host。内层探针全部acc和板上每层512 debug acc分开。

实现/测试边界：stage5_top为完整帧端点；stage5_wire_top含真实CRC字节桥；stage5_board_top连接既有UART和引脚命名，仅作后续构建顶层，本日不综合/route/bit/硬件操作。tb_d1_top是实际Conv1→Pool1前缀集成，tb_post_memory是独立GAP→Linear→argmax共享RAM链路，以oracle Conv3输出作明确的单元刺激，绝不据此宣称完整网络已执行。tb_network才是完整八阶段入口，须全部完成并独立逐项比较才能升级。

当前必须留待审查/补齐：全部错误源原码/内部地址捕获、寄存器副作用完整矩阵、顶层各状态reset/timeout/ABORT覆盖、normal/diagnostic整网一致性、全部八阶段真实顶层数值和独立验收。合同描述不是这些项目的PASS。D2先清G1阻塞，再做全网RTL与实现。

F2修订（2026-10-25）：LOAD阶段所有通过帧格式及单region完整范围检查的host内存读均拒绝NOT_READY=6，包括已物理提交的输入/参数；通过LOAD_COUNTS完整寄存器查询装载进度。其他非PAUSED/DONE状态也不开放内存读。PAUSED仅当前层顺序诊断窗口，DONE仅有效B logits[0:5]。完整寄存器首地址/精确长度策略不变，偏移/短读/跨界返回ACCESS=3；模型同步，不改变wire布局。


## 2026-10-27 权限错误优先级修订

本修订闭合独立审计 day1_20261026T125813_3997684Z_1eea8751 的两项分歧。wire VERSION和数据布局保持不变，修改被拒绝读取的错误分类；不把实施回归视为独立G1通过。

读取检查按顺序执行，命中前项即返回：
1. 帧长度1..256、非负地址、末端不超过20-bit地址空间，否则 LENGTH_SEQUENCE=4。
2. 寄存器必须是可读寄存器首地址及精确长度，否则ACCESS=3。内存请求的全部字节必须落在同一已映射region内；未映射或跨region均ACCESS=3，包括LOAD状态。
3. 通过上述几何检查后，LOAD/IDLE/ADMIT/RUN/DRAIN/ERROR的内存读返回NOT_READY=6。原“LOAD所有内存读6”限定为通过前两步的请求，不能覆盖跨界错误。
4. PAUSED debug先检查当前阶段窗口：Pool1/Pool2/argmax无debug窗口，返回ACCESS=3；Conv允许debug偏移[0,2048)，GAP允许[0,512)，Linear允许[512,532)。请求全部字节不在当前窗口内返回ACCESS=3。全部字节在窗口内但首偏移不等于窗口起点+已成功发送字节数，返回LENGTH_SEQUENCE=4。
5. host Client.read在本地按同样的帧/region几何检查优先于LOAD状态检查；动态PAUSED窗口/顺序由设备检查，host保留设备原错误码。底层request/exchange仍可用于负向帧测试。

因此Pool1 PAUSED的0x50000/1B、0x50000/4B、0x507ff/1B均为ACCESS=3；LOAD的八个region末字节起始2B跨界均为ACCESS=3，而每个region内合法读取仍为NOT_READY=6。已授权输出窗口、写入、START、计数和算术路径不在此次变更范围内。


## 2026-10-28 普通输出窗口错误优先级修订

闭合独立审计 day1_20261027T102024_0659145Z_e65fdaa3 的七阶段输出游标分歧。前述帧几何→完整寄存器/单region→状态权限检查保持不变。PAUSED普通输出读取再按以下顺序判定：

1. 当前阶段授权窗口：Conv1/2/3为B[0,32768)，Pool1/2为A[0,16384)，GAP为A[0,128)，Linear为B[0,5)。argmax不授权普通内存输出窗口。未授权region、无窗口或任意字节越出窗口先返回ACCESS=3，即使游标也错误。
2. 全部字节在授权窗口内，但首偏移不等于diag_output，返回LENGTH_SEQUENCE=4。diag_output=0时合法窗口偏移1/长度1因此为4。
3. 合法顺序请求返回数据，仅成功响应发送完成后推进diag_output；拒绝读取不推进游标或改变推理状态。host保留设备原错误码，不自行推测动态游标，不重试。

debug窗口规则和LOAD跨region=3/合法region=6保持不变。wire版本、布局、算术、写入和计数行为不变。实施回归不代表独立G1通过。
