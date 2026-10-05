# SIM0 — 已批准的 Linux 恢复尝试

更新日期：**2026-10-01**。证据编号：`20260929T122535Z`，工作跨三日继续。[English report](SIM0-linux-recovery-attempt.md)。已批准范围：[原生赛道恢复](../planning/linux-asset-recovery.zh-CN.md)。

**后续结果：**获批 [Floor-only A/B 诊断](SIM0-floor-contacts.zh-CN.md)完成两次对照及两次处理；激活后目标接触点消失，但处理组车体仍漂移 **3.372／3.414 mm**。P0 与 SIM0-B06 仍未解决，没有采用修复；下一项只读源码/轨迹审查建议等待确认。下文保留前序构建／P0 检查点。

**修正后的 Linux IL2CPP 播放器已成功构建，并通过全部已记录的静态比较。LNX-01／02／03、SIM0-01／02 通过。实时数据已到达八个必需 ROS topic，激光扫描及相机转换内容验证通过。但首次连通的静止试验在完整观察开始 16.53 秒后，因位置报告变化 1 mm 而被保护逻辑终止，期间执行器反馈及编码器值仍为零。此前已安装播放器的保留记录也存在同样变化；物理原因和长期趋势尚未验证。SIM0-B06 阻塞 LNX-04 及 SIM0-03／04，SIM0 和 PRE 尚未完成。**

下文历史生成／导入结果保留其原有边界，不能用于接受两个被拒绝的播放器。失败及已冻结证据均保留。当前输入位于 `track-inputs-v4/track-inputs.json`，其内部格式版本为 2；此前 v2／v3 目录内是格式版本 1，需配合归档的旧工具复现。

## 当前结果与静止验证阻塞

最终生成方式对应的构建在 **698.08 秒**后退出 0，产生 **603 个文件／1,513,674,732 字节**，含调试专用目录。构建期间源码差异及选定资源哈希不变。实际播放器比较通过：**18 个碰撞网格、662 个变换、87 组内置物理／相机记录、120 个脚本身份**，两条赛道的原始顶点／索引字节、全部 14 个通道记录、渲染器设置、四个有序材质映射及预览 RenderTexture 均匹配。没有引入几何容差。着色器二进制／像素身份及未解码脚本字段不在该比较范围内。[构建诊断](../../artifacts/simulator-build/20260929T122535Z/player-build-authoring/diagnostic-review.json)、[最终静态审查](../../artifacts/simulator-build/20260929T122535Z/player-inspection-authoring/final-static-review.json)。

| 保留的运行尝试 | 实际结果 | 验收状态 |
| --- | --- | --- |
| `neutral-authoring` | 无连接或数据；180.66 秒超时。三个自有进程退出 0，清理 0.59 秒，端口释放。 | 未完成。 |
| `neutral-authoring-retry` | 延长点击／聚焦等待后仍无连接；180.64 秒超时。三个进程退出 0，清理 0.64 秒，端口释放。 | 未完成；延时并未解决问题。 |
| `neutral-authoring-input-check` | 新增检查证明 Unity 虽有键盘焦点，但鼠标下方是另一窗口；**点击前即停止**。清理 0.64 秒，进程全部回收。 | 确认验证工具的窗口定位缺陷。前两次缺少该记录，不能声称已证明其确切原因。 |
| `neutral-authoring-activated` | 向窗口管理器请求激活后，指针／焦点／PID 校验通过，Connect 生效。一次本机 Engine.IO 4 WebSocket 请求及连接；65 帧完成处理、65 次严格零值回复；八个 ROS topic 各收到 65 条消息。第 66 帧报告 X 从 **0.742 变为 0.743 m**，在转换／回复前被拒绝。 | **未完成：**完整观察开始后 16.529 秒触发拒绝，未启动第二次独立运行。所有进程退出 0，清理 **1.594 秒**，端口释放。 |

窗口定位修正仅影响验证工具，使用 [EWMH 规范](https://specifications.freedesktop.org/wm/latest-single/)定义的窗口激活请求，访问日期 2026-10-01。模拟器源码、物理、传感器负载、严格零值及位置变化保护保持不变。

连通试验使用 ROS 2 Humble、隔离的 Devkit／AVLite 环境、domain 87、本机 4567 端口、RTX 3080／Vulkan，以及 **1280×720** 窗口，配置为 **Manual／Driver's Eye／Low Quality／Scene Light**。没有切换驾驶模式、Reset 或发送非零命令。数据包含 **1081 个激光距离值**（首帧 1035 个有限值）、报告扫描率 20 Hz，以及 **1280×720 rgb8** 图像。首帧扫描转换为 float32 后的字节及图像解码像素，均与对应 ROS 消息一致。实际桥接收频率为 **3.902 Hz**，间隔 p95 **268.49 ms**、最大 **310.94 ms**，包含明确配置的 0.1 秒回复延时。这些是不完整试验的接收测量，不是源采样率或性能验收通过。完整观察开始后的实际 ROS 覆盖仅 **16.277–16.286 秒**。[分析结果](../../artifacts/simulator-build/20260929T122535Z/neutral-authoring-activated-analysis.json)。

48.01 秒采样窗口（包含启动和截图审查）内：播放器平均 CPU **101.25% 单核／峰值采样 RSS 729.0 MiB**；桥进程 **10.08%／142.6 MiB**；观察进程 **2.08%／67.2 MiB**。启动至首个完整观察为 **31.80 秒**，含截图审查等待，不能当作无人值守启动 benchmark。未测 GPU 显存。

### 事实与判断边界

- **已验证：**此前保留的四个已安装播放器观察片段，也在 9.09–15.61 秒内由报告 X **0.740 变为 0.741 m**，编码器及执行器字段为零。这些包含 GUI Reset 的短片段，不是相同条件下的独立进程 60 秒试验。
- **源码事实：**`IPS.FixedUpdate` 直接读取车辆世界坐标 Transform，没有显式随机噪声项；`Socket.cs` 用 `F3` 输出位置。1 mm 的报告跳变不能精确量化底层亚毫米变化，不能直接认定为无害传感器噪声。
- **尚未验证：**Transform 变化的原因、是否收敛或持续累积，以及两份播放器的动态等价性。接触爬移、静置沉降、数值误差只是候选解释。轮速编码器为零不证明车体绝对不平移。
- **保留诊断：**原播放器与源码播放器存在文字一致的四条车轮凸包警告；退出时的 socket 已关闭／ThreadAbort 诊断保留，进程退出及端口释放经过验证。没有简化车轮或修改物理设置。
- **画面审查：**源码连通截图与此前原播放器截图的相机／UI 配置相同、场景整体相符。这是有限人工检查，不是像素等价或相机标定证据。

[位置／源码／诊断审查](../../artifacts/simulator-build/20260929T122535Z/neutral-motion-review.json)。原 P0 要求意外运动时停止调查；保护逻辑已按要求终止，本次不能算作 P0 完成。

### 历史提议：仅用于诊断的观察范围（随后已批准并执行）

**批准更新（2026-10-01）：**你对这一具体提议回复了“apporve”，获批四次观察现已完成，见[结果与下一项决策](SIM0-neutral-drift.zh-CN.md)；P0／SIM0 验收不变。下文仅保留批准前的提议，不是仍待批准的请求。

**推荐：**先批准一项单独、有界的被动漂移对照，再讨论是否修订 P0。该提议**尚未实现、尚未执行**，不授予任何验收通过。

| 项目 | 建议边界 |
| --- | --- |
| 次数与环境 | 已安装及源码播放器**各两次独立进程观察**；完整帧和八个 topic 到齐后，最多观察 **60 秒**。保持相同显示／传感器／ROS 设置及 0.1 秒回复延时；记录实际启动和连接时刻。 |
| 控制与状态 | Manual 模式，严格零值回复及反馈，试验中不 Reset／重新归零；不改场景、物理、传感器。编码器变化、非法输入、进程故障仍立即结束。 |
| 位置终止条件 | 收到相对首个报告位置的欧氏位移 **≥ 0.010 m** 时停止。这个**待批准的诊断上限**允许观察超过已测到的单次 0.001 m 跳变；它不是测得的基线，也不是验收容差。基于原协议采样的检测不构成实时物理安全边界。 |
| 交付与限制 | 报告位移轨迹、重复性、数据内容、时序、清理和全部提前终止；依据测量另行提出 P0 决策。SIM0-03／04、LNX-04 仍未勾选，不进入 SIM1／S1，不发送非零控制。 |

替代方案是保留当前位置零变化标准，另行批准一份诊断源码构建，记录全精度 Rigidbody／Transform／车轮状态。它提供更强的因果证据，但增加运行时观测代码差异和一次构建；后续任何物理修复仍须独立确认范围与等价性。推荐方案先测量较长静止行为，避免过早修改模拟器。

需要确认的原因是：允许越过首次位置变化继续观察，改变了**已批准 P0 的停止边界**。这不是重复申请已经批准的 Linux 恢复或构建权限。

## 播放器差异与已验证诊断

| 操作 | 实际结果 | 含义 |
| --- | --- | --- |
| 第一次 IL2CPP 构建 | 退出 0，**716.04 秒**。18 个碰撞网格、662 个变换、87 组内置设置、120 个脚本身份、解码赛道属性及材质映射匹配。 | 两条赛道法线通道为 `4`，基线为 `52`，严格比较失败；未启动该播放器。 |
| 直接保留源元数据 | 完整通道元数据写入并校验；两次生成分别 **16.02／349.46 秒**，网格文件逐字节相同；映射场景检查 **11.01 秒**通过，源码及依赖范围审查通过。 | 源资源中保留该值，仍不代表构建后的播放器保留。 |
| 第二次 IL2CPP 构建 | 退出 0，**698.04 秒**，603 个文件／1,513,670,108 字节，含调试专用输出目录。无编译、导入、缺失预制体、异常或着色器错误；构建期间源码差异及选定资源哈希不变。 | 严格比较仍发现 `52 → 4`；材质／纹理元数据及预览 RenderTexture 匹配。保留两条 HDRP 宏重定义警告及已有 C# 警告。历史 **SIM0-B05** 已由最终构建解除。 |
| 独立打包诊断 | **17.02 秒**完成四个网格：两条赛道各用直接 half 法线和无损 float 法线。两种方式原始顶点／索引字节均匹配，仅 float 法线方式生成完整元数据 `52`。临时资源已清理，源码差异不变。 | 这是资源包上的实测因果证据，不推断私有位字段的一般语义，也不代替完整播放器验收。 |
| 生成方式修正 | 首次生成／重载在 **17.02 秒**后通过。独立 NumPy 解码验证法线无损提升、去除的 W 填充值为零，且可逐字节还原原始缓冲。 | 作者资源顶点步长为 **36 字节**；最终播放器恢复 **32 字节**及完整通道元数据。独立无 Library 生成在 **352.45 秒**后通过，作者网格逐字节相同；映射场景检查 **12.01 秒**通过。严格比较不变。 |

Unity 文档说明顶点数据可由 FP32 转为 FP16；本项目 `VertexChannelCompressionMask` 仍为 4054。采用本修正的依据是实际打包对照结果。未修改项目设置、引擎、场景范围、几何数值或运行验收标准。[Unity 2021.3 压缩说明](https://docs.unity3d.com/2021.3/Documentation/Manual/mesh-compression.html)，访问日期 2026-09-30。

证据：[第一次差异](../../artifacts/simulator-build/20260929T122535Z/player-channel-mismatch-review.json)、[第二次差异](../../artifacts/simulator-build/20260929T122535Z/player-channel-mismatch-metadata-review.json)、[第二次构建诊断](../../artifacts/simulator-build/20260929T122535Z/player-build-metadata/diagnostic-review.json)、[打包比较](../../artifacts/simulator-build/20260929T122535Z/packing-probe/comparison.json)、[原始字节一致](../../artifacts/simulator-build/20260929T122535Z/packing-probe/raw-buffer-review.json)、[独立源缓冲验证](../../artifacts/simulator-build/20260929T122535Z/authoring-source-review.json)。

## 实际完成的工作与边界

| 工作 | 已验证结果 | 验收边界 |
| --- | --- | --- |
| 独立恢复副本 | 主副本、重复生成副本、最终构建副本均来自固定提交；每份隔离保存 16 个批准排除的文件，哈希一致；仅删除已禁用的 OpenCAV 构建条目。 | 重复生成已通过；最终副本首次导入已通过。原始源码和已安装播放器保留。 |
| 2026-09-29 首次导入 | 无 Library 起步，**361.44 秒**，退出 0；无编译错误、导入异常或缺失预制体诊断，原有七个 OpenCAV 错误消失。 | 31 条备用着色器查找消息和空渲染设备警告保留；不能据此认定播放器渲染通过。 |
| 输入导出 | 两条赛道原始顶点和索引已导出；独立解码的 float32 属性哈希与先前检查一致，并记录原材质文件指纹。 | 首次错误地假设 Mesh 名称等于 GameObject 名称，失败证据保留；修正导出通过。 |
| 首次原生生成 | **14.02 秒**后退出 1；已生成两组资源，但检查发现 CreateAsset 将原始网格名称改成文件名。 | 失败结果保留，不计通过。输出移出 Assets 后完整归档；两个网格原始缓冲都匹配。 |
| 受限重试 | **31.03 秒**后以 −5／SIGTRAP 退出，77 次网络接口枚举失败和原生信号量断言，没有生成恢复报告。 | 历史 SIM0-B04；由后续主机执行恢复解除。 |
| 修正后的主机重试 | `generate-03` 在 **13.01 秒**后退出 0；原始名称、原始缓冲哈希、32 字节布局、包围盒、子网格、材质和渲染器检查全部通过。 | 原生资源生成证据，不是播放器验收。 |
| 独立重复生成 | `generate-repeat` 无 Library 起步，首次导入加生成共 **361.49 秒**；两份 Mesh 资源文件逐字节相同，预制体语义检查均通过；可读性和 keep 标志仍为 false。 | GUID／预制体本地 ID 不同且已记录，不宣称预制体文件逐字节相同。**LNX-01 通过。** |
| 场景映射 | 精确替换 **16 个 Proto 和 20 个 Berlin** 引用；反向替换恢复原场景每一个字节。主副本实际加载检查 **12.01 秒**通过，包括位姿、激活状态、材质、碰撞器设置及无缺失组件。 | 最终无缓存副本也已通过相同的场景报告。 |
| 依赖审查 | 闭包从 **276 路径变为 285 路径**：移除两个 SKP；新增四个原生资源、四个原有材质和三个原有纹理。原材质／纹理字节与固定源码一致；共享依赖仅场景发生批准的映射变化。 | 静态源码／资源检查；播放器渲染、碰撞烘焙及传感器行为尚未通过。 |
| 最终副本输入 | 含目录元数据和场景的 11 个批准文件已复制至无缓存构建副本，哈希全部一致；首次导入与场景检查在 **361.48 秒**后通过，570 个依赖／元数据哈希均与主副本一致。 | 此为首次构建副本准备记录。后续两个播放器编译成功，但均因完整元数据比较失败而未启动。 |
| 工具检查 | 工具通过对应 AST／导入／help 检查；七个映射测试和七个比较防护测试全部通过（共 14 个），覆盖 64 位 ID、其他字节保留、源文件漂移、失败报告、项目／进程不匹配、GUID 冲突、未知引用及重复应用防护。 | 合成测试不能替代 Unity 场景或运行验证。 |

## 已解除的执行阻塞与保留的失败

`generate-02` 发生在此前无法申请主机执行的受限会话。只读接口／NETLINK 检查复现 errno 1，支持环境限制判断。进程已回收；临时工具已移除；遗留零字节锁经时间、所属运行和独占锁检查后保存并清理。跨挂载点 rename 的 EXDEV 失败也保留。没有启动播放器或运动流程。

你恢复执行权限后要求重试，同一固定编辑器及私有依赖环境完成了 `generate-03`。SIM0-B04 的执行限制已解除，未更换引擎、物理、传感器负载或降低验收标准。

重复运行的初始文本诊断误匹配 31 个成功导入的 `Exception.cs` 文件名和八个警告图标文件名，已逐项分类，原分类保留。实际编译／导入／缺失预制体／异常错误为零。31 条备用着色器消息及批处理空设备警告仍保留，渲染验收仍需实际播放器。

映射前，全部 **552** 个记录的依赖／元数据哈希不变。Unity 虚拟 `Packages/` 路径通过现有包缓存解析函数检查；最初直接拼接路径导致的断言失败已记录为检查方法错误，不是资源漂移。继续执行后的检查确认三份仓库状态、九个选定播放器文件、三个赛道输入文件、原始源码差异及已冻结的 83 份证据文件均不变。[完整性记录](../../artifacts/simulator-build/20260929T122535Z/baseline-integrity-retry.json)。

## 复现与下一步

恢复范围已经批准，不需要再次确认路线。已成功运行的修正命令见[英文报告](SIM0-linux-recovery-attempt.md#reproduction-and-next-action)；历史格式版本 1 命令需配套归档的 `executed-probe.cs`，不能直接使用当前版本 2 生成器；实际参数、输入、工具版本和耗时见每次 `build-result.json`。复现时必须使用新的项目和结果目录，不覆盖 `generate-03` 或其他已有证据。重复生成采用相同输入及 900 秒执行上限；执行上限不是性能合格阈值。

最新实际构建／运行参数及对应工具快照见[重试复现记录](../../artifacts/simulator-build/20260929T122535Z/reproducibility-retry.json)，实时运行命令见[英文报告](SIM0-linux-recovery-attempt.md#reproduction-and-next-action)。成功构建位于 `-authoring` 项目／输出目录，构建记录为 `player-build-authoring`。已失败的静止验证命令保留，不应覆盖证据或反复尝试直到偶然通过。它需要已记录的 Humble／显示环境、主机执行权限及新进程对应的截图审查。当前下一步见[已完成诊断报告](SIM0-neutral-drift.zh-CN.md)；默认保护逻辑未放宽。参数化工具见[说明](../../scripts/README.md)。

## Todo 与阶段状态

- **LNX-01：已通过**，重复生成、重载、身份、布局和保存标志检查均通过。
- **LNX-02：已通过**，隔离、精确映射、两次实际场景检查、最终干净导入及完整源码／依赖审查全部通过。
- **LNX-03：已通过**，最终构建及全部已记录静态比较通过。
- **LNX-04：未勾选**，**SIM0-B06**：首次连通运行因位置变化终止；两次要求的 60 秒观察均未完成。
- 原计划 **2/34** 通过；源码修订 **2/10（SIM0-01／02）** 通过；恢复任务 **3/4** 通过。完整 PRE 仍是 S1 前提，SIM1 保留阶段进入确认。

这是进度报告，不是阶段完成报告；原生资源恢复不会自动授予运动或 SIM1 进入许可。

最终完整性检查：三份参考仓库状态、九个选定原播放器文件、全部 **570** 个依赖／元数据记录、源码差异及原生输入、全部 **603** 个构建输出文件，以及最初冻结的 **83** 份证据均未变化。四次尝试的自有子进程全部回收且已不存在。[完整性记录](../../artifacts/simulator-build/20260929T122535Z/post-run-integrity-retry.json)。四份验证工具历史快照与各次运行哈希一致；默认零值／运动保护和观察函数的 AST 与重试前相同。[工具审查](../../artifacts/simulator-build/20260929T122535Z/final-tool-checks-retry.json)、[工具历史](../../artifacts/simulator-build/20260929T122535Z/neutral-harness-history-review.json)。

恢复工作所需记录：[摘要](../../artifacts/simulator-build/20260929T122535Z/result-summary-retry.json)、[复现参数](../../artifacts/simulator-build/20260929T122535Z/reproducibility-retry.json)、[本次独立哈希清单](../../artifacts/simulator-build/20260929T122535Z/evidence-sha256-retry.json)。原清单及失败尝试完整保留。

## 证据

- [准备](../../artifacts/simulator-build/20260929T122535Z/preparation/preparation.json)、[首次导入](../../artifacts/simulator-build/20260929T122535Z/initial-import/build-result.json)、[导入诊断](../../artifacts/simulator-build/20260929T122535Z/initial-import/diagnostic-review.json)。
- [验证后的输入](../../artifacts/simulator-build/20260929T122535Z/track-inputs-v2/track-inputs.json)、[失败生成](../../artifacts/simulator-build/20260929T122535Z/generate-01/native-track-report.json)、[失败输出归档](../../artifacts/simulator-build/20260929T122535Z/generate-01-archived/result.json)、[原始缓冲检查](../../artifacts/simulator-build/20260929T122535Z/archived-generation-buffer-review.json)。
- [受限重试](../../artifacts/simulator-build/20260929T122535Z/generate-02/build-result.json)、[接口探测](../../artifacts/simulator-build/20260929T122535Z/sandbox-interface-probe.json)、[遗留锁检查](../../artifacts/simulator-build/20260929T122535Z/generate-02/crash-lock-review.json)。
- [主机恢复](../../artifacts/simulator-build/20260929T122535Z/resumption-retry.json)、[成功生成](../../artifacts/simulator-build/20260929T122535Z/generate-03/native-track-report.json)、[重复比较](../../artifacts/simulator-build/20260929T122535Z/repeat-generation-review.json)、[保存标志](../../artifacts/simulator-build/20260929T122535Z/native-readability-review.json)。
- [精确映射](../../artifacts/simulator-build/20260929T122535Z/scene-mapping/result.json)、[实际场景检查](../../artifacts/simulator-build/20260929T122535Z/scene-verify/native-track-report.json)、[依赖审查](../../artifacts/simulator-build/20260929T122535Z/scene-dependency-review.json)、[最终副本转移](../../artifacts/simulator-build/20260929T122535Z/clean-build-input-transfer.json)。
- [工具检查](../../artifacts/simulator-build/20260929T122535Z/tool-checks.json)、[七个测试](../../artifacts/simulator-build/20260929T122535Z/scene-mapping-tests.txt)、[之前的完整性快照](../../artifacts/simulator-build/20260929T122535Z/post-run-integrity.json)。

- [最终干净导入／场景检查](../../artifacts/simulator-build/20260929T122535Z/clean-scene-verify/native-track-report.json)、[完整源码审查](../../artifacts/simulator-build/20260929T122535Z/clean-source-review.json)。

当前生成方式证据：[独立重复](../../artifacts/simulator-build/20260929T122535Z/repeat-authoring-review.json)、[精确映射](../../artifacts/simulator-build/20260929T122535Z/scene-mapping-authoring/result.json)、[场景重载](../../artifacts/simulator-build/20260929T122535Z/scene-verify-authoring/native-track-report.json)、[完整源码审查](../../artifacts/simulator-build/20260929T122535Z/source-review-authoring.json)、[工具检查](../../artifacts/simulator-build/20260929T122535Z/authoring-tool-checks.json)。
