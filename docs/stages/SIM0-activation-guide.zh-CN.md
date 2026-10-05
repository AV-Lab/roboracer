# SIM0：Unity 安装与激活准备

**当前状态：**Hub／项目创建及使用私有编译依赖的全新批处理编译、正常退出均已通过，见[启动恢复报告](SIM0-startup-recovery.zh-CN.md)。当前阻塞为 [AutoDRIVE 源码资源导入](SIM0-import-review.zh-CN.md)，无需再次操作账号或 Locate。下文保留早期安装交接记录。

日期：**2026-09-29**。[英文版本](SIM0-activation-guide.md)。你已确认完整 PRE 通过后进入 S1，S1a 后置方案不采用。当前已选择本机路线：按你的要求安装了 **Unity Hub 3.21.3**，随后你已报告登录并确认许可。该前置条件记录为用户确认；固定版本编辑器与模块现已安装，但空项目启动在许可衔接处失败。详见[本次报告](SIM0-toolchain-attempt.zh-CN.md)；导入和构建仍未验证。

Hub 安装位置为 `/home/a2rl/Applications/UnityHub/UnityHub.AppImage`。可通过应用菜单或 `unityhub` 启动；命令入口位于 `/home/a2rl/.local/bin/unityhub`。桌面入口、`unityhub://` 回调关联均已验证，安装时已观察到可见窗口。启动器使用官方解压运行方式，未关闭 Chromium 沙箱。[安装证据](../../artifacts/preflight/20260929T062054Z/installation-result.json)。此步骤未包含 Editor。

1. **Hub 安装：已完成。** 使用用户级 AppImage，无系统包修改。[官方安装说明](https://docs.unity.com/en-us/hub/install-hub-linux)。
2. **登录和许可确认：你已报告完成。** 编辑器后续实际启动时验证许可可用性；项目记录无需账号信息或许可文件。[官方许可流程](https://docs.unity.com/en-us/hub/manage-license)。
3. **固定编辑器与模块：已下载并解压到隔离路径。** 使用 **Unity 2021.3.9f1**（`ad3870b89536`）及 **Linux Build Support (IL2CPP)**，通过历史版本入口获取。[精确版本页面](https://unity.com/releases/editor/whats-new/2021.3.9f1)。
4. **记录编辑器就绪状态。** 当前规范安装位置为 `/tmp/roboracer-work/toolchains/2021.3.9f1/`；原小写前缀路径保留为兼容符号链接。此前实际启动报告 `Access token is unavailable`，退出码 1。随后 Hub 关联暴露出目录名导致的版本／模板解析错误，详见[修复报告](SIM0-template-loading.zh-CN.md)。请在 **Installs** 对 `unity-2021.3.9f1` 条目选择 **Remove**，再 **Locate** `/tmp/roboracer-work/toolchains/2021.3.9f1/Editor/Unity`。在 New project 选择 **2021.3.9f1**，检查模板加载并首次打开空项目；账号／许可提示由你处理。随后再独立验证批处理启动。目录修正后的 GUI 恢复及实际许可访问尚未验证。
5. **执行 SIM0 验证。** 检查编辑器启动、完整资源／包依赖、独立 F1TENTH 构建及规定的两次静止运行；通过后提交阶段报告，再确认进入 SIM1。

当前主机为 Ubuntu 22.04，而旧编辑器的官方系统列表未包含该版本，须实际验证兼容性；现有模拟器播放器能运行，不能证明编辑器构建也会成功。[版本化系统要求](https://docs.unity3d.com/2021.3/Documentation/Manual/system-requirements.html)。

我负责工具链、依赖、构建与验证的工程工作；账号登录、许可选择和激活由你完成。本次已记录你的完成确认，不读取或收集账号秘密，不代为购买。GUI 启动或允许目录之外的写入，仍可能触发实际的范围明确的执行审批。

SIM0-01 在完整源码、编辑器、模块及运行前提全部验证前继续保持未完成。阶段顺序无需再次确认；SIM1 的阶段进入确认和运动前数值协议继续有效。当前下载／验证证据位于 `artifacts/simulator-build/20260929T063510Z/`，未授权运动。资料访问日期为 **2026-09-29**；旧的 engine-6000.5 许可页面访问超时，流程依据可访问的官方 Hub 许可页面。安装记录与本次许可确认替代此前“环境尚未确定”的状态。
