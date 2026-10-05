# SIM0 — 仅使用 Linux 的赛道资源恢复提案

日期：**2026-09-29**，执行状态更新于 **2026-10-01**。**已收到你明确回复 confirmed 的批准。**[English report](linux-asset-recovery.md)。只读证据：`20260929T102620Z`；[执行报告](../stages/SIM0-linux-recovery-attempt.zh-CN.md)：`20260929T122535Z`。

**LNX-01／02／03／04 已通过（2026-10-05）。**用户选择方案 A，将 SIM0-B06 作为继承自模拟器的蠕移关闭，并把 P0 位置规则修订为包含式 10 mm 上限；随后两次修订后 P0 静止运行均通过（[SIM0 报告](../stages/SIM0-completion.zh-CN.md)）。未采用任何物理修复；S1 前须完成完整 PRE 的要求不变。

下文保留 Windows 主机不可用后获批的路线：从已提供 Linux 播放器恢复两条必需赛道，并验证独立标识的源码构建。本方法绕过这两条赛道的 SketchUp 导入，不改变引擎、物理、传感器负载或最终比较标准。

## 1. 已查证的事实

[上一份阻塞报告](../stages/SIM0-sketchup-blocker.zh-CN.md)已验证：Unity 2021.3.9f1 的 Linux 编辑器不能导入必需的 SketchUp 赛道。这与先前已经恢复的 Hub／模板显示、编译器依赖问题不同。已安装播放器包含编译好的几何，仍可在此前验证的范围内使用。

本次只读检查确认：

| 项目 | Proto Track | Berlin Track |
| --- | --- | --- |
| 顶点／32 位索引数 | 110,436／167,340 | 104,460／157,644 |
| 子网格／材质顺序 | 2 个／Outer Face、Inner Face | 2 个／Outer Face、Inner Face |
| 渲染与碰撞网格 | 引用同一个网格，path ID 213 | 引用同一个网格，path ID 413 |
| 局部变换 | 位置 `(0, 0.127, 0)`，无旋转，缩放 1 | 相同位置／旋转，缩放 0.5 |
| 激活状态 | 激活 | 未激活 |

两个赛道根对象均无子对象，渲染器没有使用静态合批网格或附加顶点流。位置、法线、切线、UV0、索引、子网格描述和包围盒均可读取。属性值均为有限值，索引未越界。直接解码资源文件原始字节的独立检查，与 UnityPy MeshHandler 对两条赛道全部四种有效属性的结果一致。顶点步长为 32 字节：位置为 float32，法线／切线／UV0 为 float16。

四个材质分别与固定源码中的对应材质匹配：按 float32 归一化比较的 120 个浮点属性、16 个颜色属性，以及渲染队列均一致。引用的三份纹理源文件存在。**这些结果不证明着色器二进制、纹理像素或实际相机画面完全一致。** 复用源材质是待验证的设计方案。

扩展后的检查工具实际运行 **0.795 秒**，读取 18 个碰撞网格、120 个脚本标识，未报告解析错误。这只是单次静态检查耗时，不是模拟器性能指标。本次没有启动 Editor／播放器，也没有修改模拟器源场景、资源或设置。

## 2. 申请批准的具体修改范围

仅在固定提交 `635dbb6d86ec98e25ea845a97188f7bbe85a09e8` 的**全新独立派生工作区**操作。保留现有播放器、原始源码、先前验证副本、隔离资源及失败证据。

| 位置 | 拟执行的修改与边界 |
| --- | --- |
| `Assets/RoboRacerQualification/Tracks/` | 新增 `Proto Track.asset`、`Berlin Track.asset`、`Proto Track.prefab`、`Berlin Track.prefab` 及文件／目录元数据。网格来自有指纹记录的已安装资源；预制体提供对应对象、变换、MeshFilter 和 MeshRenderer。 |
| `Assets/Scenes/F1TENTH.unity` | 仅把两条赛道的预制体／模型／网格引用映射到原生资源；保留场景局部对象 ID、父子关系、变换、激活状态、材质顺序、渲染设置及现有碰撞组件／配置。现有 Proto、Berlin 引用分别出现 16、20 次，不能当作简单改文件名。 |
| `Assets/Prefabs/OpenCAV/OpenCAV.prefab` 及 `.meta` | 校验并保留原始字节后移出导入树。该首版不使用的预制体产生剩余七项 SketchUp 预制体引用诊断。 |
| `Assets/Scenes/OpenCAV.unity` 及 `.meta` | 与预制体一起隔离。这是静态扫描找到的唯一引用场景，避免只移除预制体后引入新的悬空场景引用。 |
| `ProjectSettings/EditorBuildSettings.asset` | 仅移除已禁用的 OpenCAV 场景条目，保留 F1TENTH 唯一启用状态及所有其他条目／设置。 |
| 原六项隔离及 Linux 编译工具链补丁 | 保持先前批准的精确范围，不自动扩大资源清理或升级依赖。 |
| 本项目的验证工具及证据 | 扩展参数化准备／检查入口，显式生成与比较原生资源；独立于插件默认运行流程，记录输入／工具／产物哈希和命令。 |

OpenCAV 预制体与场景不在已记录的 276 项 F1TENTH 依赖闭包内。序列化 GUID 扫描显示，该场景只被构建设置中的禁用条目引用。这是有限静态证据，不能排除所有动态加载。四份拟新增隔离文件的精确哈希见[隔离范围审核](../../artifacts/simulator-build/20260929T102620Z/additional-exclusion-review.json)。获批后，这些精确隔离和禁用条目修改已在独立恢复副本中应用；原始文件仍完整保留。

继续使用固定 Editor **2021.3.9f1/ad3870b89536**、Linux IL2CPP 模块、私有本地库配置、ROS 2 Humble，以及原车辆／物理／传感器负载和插件架构。这条路线仅绕过两条赛道所需的 SketchUp 导入，不使上游所有 SketchUp 场景自动兼容 Linux。

## 3. 拟执行步骤与验收

以下四项是**已批准的恢复任务**，独立于原计划 34 项及源码修订 10 项；实施开始时尚无完成项。

- [x] LNX-01 — 按有指纹的输入生成并重载两组网格／预制体，保留属性值、拓扑、子网格、包围盒、材质顺序及运行时可读性／负载；不简化、优化或重算几何。无 Library 的独立副本重复验证。**当前修订于 2026-09-30 通过：**首次生成 **17.02 秒**，独立导入／生成 **352.45 秒**，作者网格文件逐字节相同。捕获的法线 XYZ 精确提升为 float32，作者顶点为 36 字节；原始 W 填充值为零，可无损还原原始缓冲，已独立验证。未修改的 Unity 压缩流程在诊断资源包中恢复 32 字节布局及完整元数据；完整播放器比较仍属于 LNX-03。[重复证据](../../artifacts/simulator-build/20260929T122535Z/repeat-authoring-review.json)、[独立缓冲验证](../../artifacts/simulator-build/20260929T122535Z/authoring-source-review.json)。此前直接 half 版本保留，不作为播放器通过证据。
- [x] LNX-02 — 仅应用精确赛道映射、OpenCAV 四文件隔离及禁用条目移除；审查全部引用、场景覆盖、碰撞／材质设置及源码差异，不能有未解析对象或阻塞导入／编译诊断。**当前修订于 2026-09-30 通过：**精确 **16 + 20** 处替换可反向恢复原场景每个字节；实际加载检查 **12.01 秒**通过。首次导入无 Library，285 个依赖路径／570 个资源及元数据记录和完整变更允许范围均已审查。保留已知孤立元数据清理和两个未使用材质自动迁移。[最终源码审查](../../artifacts/simulator-build/20260929T122535Z/source-review-authoring.json)。
- [x] LNX-03 — LNX-02 后构建并严格比较 F1TENTH Linux IL2CPP 播放器。**2026-09-30 通过：**698.08 秒构建，原始赛道顶点／索引字节及全部通道记录、18 个碰撞网格、662 个变换、87 组内置设置、120 个脚本身份、材质／预览映射均匹配。历史失败保留，没有引入几何容差。[最终审查](../../artifacts/simulator-build/20260929T122535Z/player-inspection-authoring/final-static-review.json)。
- [x] LNX-04 — 按原 P0 完成两次独立进程、各 60 秒的静止观察及内容／清理审查。**2026-10-05 在用户批准的修订 P0（10 mm 蠕移上限，其余守卫不变）下通过**，见 [SIM0 报告](../stages/SIM0-completion.zh-CN.md)。历史记录：**阻塞：SIM0-B06。**首次 P0 因 1 mm 位置跳变终止，完整 P0 次数为零。后续四次获批诊断表明两套播放器均持续漂移，不能用于通过 P0。完整精度诊断已确认车身漂移；先解决原因／修复，再满足完整 P0。资源恢复不授权运动或进入 SIM1／S1。

结果存入新的 `artifacts/simulator-build/<run-id>/`。生成的第三方资源、Unity 缓存和播放器保存在独立工作／输出目录；保留声明和输入来源。此次仅限本地验证，不包含向 GitHub 发布重建资源，也不据此推定未来再分发权限。

Unity 2021.3 文档提供原生网格资源创建及顶点／子网格布局接口，但**本次具体布局已通过编辑器重载及独立重复生成检查**。半精度法线、序列化、渲染属性和碰撞烘焙都需实际检查。[Mesh API](https://docs.unity3d.com/2021.3/Documentation/ScriptReference/Mesh.html)、[资源创建](https://docs.unity3d.com/2021.3/Documentation/ScriptReference/AssetDatabase.CreateAsset.html)、[顶点布局](https://docs.unity3d.com/2021.3/Documentation/ScriptReference/Rendering.VertexAttributeDescriptor.html)、[子网格接口](https://docs.unity3d.com/2021.3/Documentation/ScriptReference/Mesh.SetSubMesh.html)，访问日期 2026-09-29。

## 4. 收益、风险及替代路线

| 项目 | 评估及处理 |
| --- | --- |
| 本机开发周期 | 若验证成功，后续可本机重复构建，不依赖不可用的 Windows 主机；代价是新增准备及比较工具。尚无实测工期或性能收益。 |
| 来源与等价性 | 几何来自所提供播放器，而非重新导入作者模型。必须标为派生后端；静态一致不等于整个源码／二进制或实车行为一致。 |
| 渲染／物理 | 已有属性和材质数值匹配证据，但着色器编译、相机画面及碰撞烘焙仍需构建／运行验证；保留负载，出现差异停止验收。 |
| 可复现性 | 固定输入、编辑器和工具指纹，比较两次全新生成。`/tmp` 可被清理，不能把 Library 缓存当作可复现源码输入。 |
| 新的导入错误 | OpenCAV 隔离未必消除所有问题。保留新失败，任何进一步扩大场景／资源范围的修改仍需审核。 |
| 替代方案 | 权威来源的可移植导出仍有价值，但目前未提供；本次检查的固定赛道目录只有两个 SKP 和四个材质，不能推断网上完全没有其他导出。Windows 主机不可用；引擎迁移是另一个尚未验证的变更。 |

当前上游模拟器 README 要求比本项目固定版本更新的 Editor，但这不证明升级历史源码可以保持行为。[官方模拟器分支](https://github.com/Tinker-Twins/AutoDRIVE/tree/AutoDRIVE-Simulator)，访问日期 2026-09-29。本提案没有选择引擎迁移。

## 5. 需要确认的决定与当前状态

**批准已记录：你的明确回复 confirmed 批准第 2–3 节的完整有限范围：在独立副本中恢复两条原生赛道、映射 F1TENTH 引用、隔离未使用的 OpenCAV 预制体及场景并移除其禁用构建条目，然后执行原定 SIM0 验证。**

该确认满足必需几何／场景修改及新增隔离的变更控制要求。批准不会降低验收标准或授权运动／自动进入 SIM1；环境对具体命令仍可能要求有限范围的额外访问授权。

原计划 **2/34** 通过；源码修订 **3/10（SIM0-01／02／03）**；恢复任务 **4/4**。SIM0-04（阶段评审）、PRE-03／04 及全部插件功能验收仍未完成。

## 6. 证据

- [调查范围](../../artifacts/simulator-build/20260929T102620Z/scope.json)、[已安装赛道详情](../../artifacts/simulator-build/20260929T102620Z/installed-detail/scene.json)、[组件设置](../../artifacts/simulator-build/20260929T102620Z/track-component-detail.json)。
- [独立属性／材质比较](../../artifacts/simulator-build/20260929T102620Z/attribute-material-review.json)、[纹理源映射](../../artifacts/simulator-build/20260929T102620Z/texture-source-review.json)。
- [新增隔离及引用审核](../../artifacts/simulator-build/20260929T102620Z/additional-exclusion-review.json)、[尚未应用的范围清单](../../artifacts/simulator-build/20260929T102620Z/local-recovery-proposal.json)。
- [可复用只读工具](../../scripts/autodrive_inspect.py)、[工具说明](../../scripts/README.md)、[先前实际导入审计](../../artifacts/simulator-build/20260929T100424Z/model-audit/scene-audit.json)。
