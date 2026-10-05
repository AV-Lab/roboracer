# SIM0：工具链已获取，编辑器许可衔接受阻

**历史尝试：**本页记录的启动阻塞现已通过[实际恢复验证](SIM0-startup-recovery.zh-CN.md)解除。当前未完成项为[源码资源导入](SIM0-import-review.zh-CN.md)。

日期：**2026-09-29**。运行编号：`20260929T063510Z`。[英文报告](SIM0-toolchain-attempt.md)。**SIM0 尚未通过。** 固定版本源码、编辑器和 Linux IL2CPP 模块均已获取；编辑器在创建／导入项目之前因许可衔接失败而退出。继续保持完整 PRE 通过后才能进入 S1。

## 已完成工作和实际结果

**后续恢复更新：**你报告的模板加载错误暴露了小写目录前缀造成的版本登记问题。临时安装目录现为 `/tmp/roboracer-work/toolchains/2021.3.9f1`，旧路径保留为符号链接。请按[最新 Remove／Locate 步骤](SIM0-template-loading.zh-CN.md)刷新；以下结果属于原始尝试，不能据此声称恢复成功。

| 检查 | 实际结果 | 证据与边界 |
| --- | --- | --- |
| Unity Hub | 官方 **3.21.3** 用户级安装；启动命令、桌面入口、回调关联已验证，安装时观察到可见窗口。 | [安装证据](../../artifacts/preflight/20260929T062054Z/installation-result.json)。随后你报告已登录并确认许可。 |
| 模拟器完整源码 | 固定提交 `635dbb6d86ec98e25ea845a97188f7bbe85a09e8`；**9,422 个受版本控制的文件，6,868,307,583 字节**，工作区干净，逐文件记录哈希。 | [源码清单](../../artifacts/simulator-build/20260929T063510Z/source-closure.json)。完整资源已获取，Unity 导入及包依赖闭合尚未验证。 |
| 编辑器归档 | 官方精确版本下载，**2,480,027,276 字节**。 | SHA-256：`2d9c7643f317d255dc12b72fa7ddffac6c13794d7ba04272941d3d977e087480`。 |
| Linux IL2CPP 归档 | **55,713,748 字节**，解压后相应构建模块存在。 | SHA-256：`c89634943258c7a2ee5d8b363ed1e833f8440f689befd98708e590aec2a75b57`。 |
| 解压校验 | 两份归档均完成；合计解压／哈希操作 **98.73 秒**，保留随附许可声明。 | [安装清单](../../artifacts/simulator-build/20260929T063510Z/toolchain-installation.json)。本地哈希用于标识文件，不代表另行验证了发布者签名。 |
| 编辑器版本与链接库 | `Unity -version` 返回 **2021.3.9f1**，退出码 0；启动日志确认为 **ad3870b89536**。主程序 `ldd` 未报告缺失链接库。 | [检查结果](../../artifacts/simulator-build/20260929T063510Z/editor-binary-check.json)。不代表所有运行时动态加载组件均可用。 |
| 空项目启动 | **46.70 秒后退出，错误码 1**，未创建项目。许可服务连接及更新消息之后，出现访问令牌不可用和激活对话框取消。 | [运行结果](../../artifacts/simulator-build/20260929T063510Z/editor-startup/result.json)、[脱敏诊断](../../artifacts/simulator-build/20260929T063510Z/editor-startup/diagnostic-summary.json)。**失败，不能标记编辑器就绪。** |
| Hub 命令行关联 | 关联命令退出码为 0，但随后安装清单仍返回 `[]`，并有配置数据库锁定诊断。 | [关联尝试](../../artifacts/simulator-build/20260929T063510Z/hub-editor-registration.json)。未证实登记成功，也未确定具体原因。 |
| 构建工具 | 新增独立、参数化且导入无副作用的[构建入口](../../scripts/autodrive_build.py)及[说明](../../scripts/README.md)，CLI／导入检查通过。 | 尚未执行 AutoDRIVE 导入或构建；属于工具准备，不是驾驶功能验收。 |

保留首次 Hub CLI 查询和后续关联失败的记录。窗口检查最初使用的环境缺少 Xlib；更换到已有依赖的环境后成功执行，但未找到可见的匹配 Hub 窗口。该结果不能证明账号已退出，也不能证明其他显示器／工作区没有 Hub。未检查账号内容。

## SIM0-B01：编辑器许可衔接

**已验证：**你已报告完成登录和许可确认；编辑器能够连接 LicensingClient，但随后报告 `Access token is unavailable`，并在创建空项目之前激活／更新失败。之后的通用用户名／密码错误不能用于断定你的密码错误或许可不适用。

**尚未确定：**通过已登录的 Hub 关联并首次打开这个旧版编辑器，是否能完成许可衔接；是否还需你处理额外账号／许可提示；或者是否存在其他新 Hub 与旧编辑器之间的兼容性问题。现有 AutoDRIVE 播放器能够运行，不能回答这些问题。

**需要的恢复操作：**在 Hub 的 **Installs → Locate** 中选择：

```text
/tmp/roboracer-work/toolchains/2021.3.9f1/Editor/Unity
```

随后使用 **2021.3.9f1** 创建并打开空项目；如出现账号或许可提示，由你完成。只需反馈能否进入编辑器，或非敏感错误文本，无需密码、密钥、许可文件或账号截图。[官方手动关联流程](https://docs.unity.com/en-us/hub/add-editor)支持此操作。这是针对实际运行错误的恢复步骤，不是再次确认开发路线。

如果成功，我会重新运行有时限的批处理启动检查，独立确认自动构建链路；GUI 能打开本身不等于批处理构建通过。如果失败，则保留诊断并针对具体原因讨论恢复方式，不自动更换引擎、许可或操作系统。

## 已保存的进度与后续工作

- 源码：`/tmp/roboracer-work/autodrive-635dbb6d-baseline`。
- 编辑器与模块：`/tmp/roboracer-work/toolchains/unity-2021.3.9f1`。
- 证据：`artifacts/simulator-build/20260929T063510Z/`；归档与一次性安装诊断工具保留在 `/tmp/roboracer-work/sim0-20260929T063510Z/`。
- 已准备仅涉及两个包配置文件的 [Linux 主机构建工具链修改](../../artifacts/simulator-build/20260929T063510Z/linux-host-toolchain.proposed.patch)，**尚未应用**。只将 Windows 主机交叉编译器替换为同版本 **2.0.4** 的 Linux 主机编译器，sysroot **2.0.5／2.0.4** 保持不变。[依据与哈希](../../artifacts/simulator-build/20260929T063510Z/linux-host-toolchain-proposal.json)。依赖解析和实际构建仍未验证。

编辑器许可访问恢复后，继续验证批准范围内的主机工具链适配、首次完整导入和构建、检查导入产生的差异和诊断，再通过已验证的 Humble／AVLite 环境执行两次全新进程、每次 **60 秒**的静止观测。记录资源占用、接收时序、传感器字段及图像、位移、几何差异和清理结果。未凭空设置性能阈值。

本次没有修改模拟器运行代码，没有启动模拟器、发送运动指令或实现 S1 插件功能。原 AVLite／A2RL 仓库和现有 AutoDRIVE 安装未被修改；没有系统级包安装、引擎升级、实车操作或发布。获准的编辑器启动可能更新用户缓存与服务日志；原始日志保持私有并排除在 Git 之外。临时源码／工具链属于可重建缓存，不是可直接再分发的软件包。

**验收状态不变：**原计划仅 PRE-01／02 通过；四项 SIM0 todo 均保持未勾选。SIM0-01 受实际编辑器许可访问阻塞，SIM0-02／03／04 依赖它。SIM1 仍须在 SIM0 报告后明确确认进入；运动测试仍须确认数值协议。

## 来源和证据范围

官方资料访问日期为 **2026-09-29**：[Hub Linux 安装](https://docs.unity.com/en-us/hub/install-hub-linux)、[精确编辑器版本](https://unity.com/releases/editor/whats-new/2021.3.9f1)、[2021.3 编辑器命令行](https://docs.unity3d.com/2021.3/Documentation/Manual/EditorCommandLineArguments.html)、[Hub CLI 用法](https://docs.unity.com/en-us/hub/use-hub-cli)、[手动关联编辑器](https://docs.unity.com/en-us/hub/add-editor)。Hub CLI reference 页面超时，关联选项另经本地 3.21.3 随附帮助与解析代码核对；未修改 Hub 代码或配置数据库。

运行结论来自本机实际结果。Ubuntu 22.04 仍不在固定旧编辑器的版本化官方主机列表内；`-version` 成功或本次许可错误都不足以判断整体兼容性。
