# SIM0：Hub 模板加载问题修复

日期：**2026-09-29**。运行编号：`20260929T084707Z`。[英文报告](SIM0-template-loading.md)。**本页保留历史诊断；后续正确登记、项目创建和批处理启动已在[恢复报告](SIM0-startup-recovery.zh-CN.md)中验证。完整 SIM0／PRE 尚未通过。** 以下保留原始失败重试和交接记录。

## 已验证原因

你在创建项目时遇到 **Unable to load templates**。Hub 保存的编辑器版本为 `unity-2021.3.9f1`，日志明确记录该版本未被识别，并被缓存为不支持。编辑器实际版本已验证为 **2021.3.9f1**；安装目录内的三个模板归档均存在。

只读检查已安装的 Hub **3.21.3** 代码发现：Linux 的 `findUnityVersion` 从安装目录名获取版本，只会去除首字母大写的 `Unity-` 前缀。我此前使用的小写 `unity-` 因而被错误保留在版本字符串中。模板查询在访问远程接口前会构造 Unity 版本对象，该解析器拒绝这个字符串。使用随附解析器的未修改副本实际执行，复现了 `unity-2021.3.9f1` 的错误；`2021.3.9f1` 则成功解析为 `2021.3` 分支。

日志另有模板 manifest 缺失记录，但 Hub 会创建空 manifest 处理此情况，该文件现已存在。所检查的相关日志没有证据证明本次模板错误由网络下载失败引起；这不代表所有网络访问均正常，也不代表修复后模板界面已经验证通过。

## 已执行修正

将我们安装的临时工具链目录改为：

```text
/tmp/roboracer-work/toolchains/2021.3.9f1
```

旧的 `unity-2021.3.9f1` 路径保留为兼容符号链接，两个编辑器路径对应同一 inode。移动前检查未发现运行中的 Editor。编辑器／模块内容、Hub 程序代码和正在使用的用户配置未修改；没有重新安装或升级引擎。

## 需要在 Hub 刷新关联

1. 在 **Installs** 对标为 `unity-2021.3.9f1` 的条目选择 **Remove**。按[官方说明](https://docs.unity.com/en-us/hub/add-editor)，移除手动关联的条目会保留磁盘上的安装文件。
2. 点击 **Locate**，选择 `/tmp/roboracer-work/toolchains/2021.3.9f1/Editor/Unity`。
3. 在 **New project** 选择 **2021.3.9f1**，检查 **3D** 模板是否出现。通过运行中的 Hub 界面刷新，可避免从外部修改其正在使用的登记文件。
4. 使用该版本创建／打开空项目；账号和许可提示仍由你处理。模板能显示，不等于编辑器许可或自动构建已通过验证。

**第一次重试：**你仍遇到错误。保存的登记及 08:47:58 UTC 日志表明，Hub 再次关联了旧的小写前缀路径，因此修正后的路径尚未通过 Hub 实测。请在 Locate 文件选择窗口按 **Ctrl+L** 输入上面的完整规范路径；重试模板前，确认 Installs 卡片显示 **2021.3.9f1**，没有 `unity-` 前缀。

此前的 `Access token is unavailable` 仍须通过新的编辑器启动来验证是否解除；尚未确定它与本次登记错误的关系。GUI 能启动后，还需再次验证有时限的批处理启动，再执行 AutoDRIVE 导入／构建。本次不涉及模拟器插桩、运动指令、新增通过项或 S1 功能实现。

## 证据

- [修正结果及实际解析器输出](../../artifacts/simulator-build/20260929T084707Z/recovery-result.json)。
- [修正前的 Hub 登记](../../artifacts/simulator-build/20260929T084707Z/hub-registration-before.json)。
- [选取的诊断证据](../../artifacts/simulator-build/20260929T084707Z/diagnostic-evidence.json)。
- 只读检查官方 `app.asar` 中的 `editorUtils_linux-qBKwSSJb.js`、`unityTemplateService-ZY-LcmL-.js` 和 `dist-cfnt_kzM.js`；未修改厂商代码。
- 上述官方手动关联／移除说明访问日期：**2026-09-29**。

下一步观察：你刷新编辑器条目并反馈模板加载结果，随后验证最新登记及实际项目启动。解析器检查成功不代替 GUI 恢复验收。
