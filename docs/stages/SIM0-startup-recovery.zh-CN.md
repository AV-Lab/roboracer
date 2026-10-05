# SIM0：项目创建与批处理启动恢复

日期：**2026-09-29**。运行编号：`20260929T085557Z`。[英文报告](SIM0-startup-recovery.md)。**模板登记和实际批处理启动已恢复，SIM0-01 通过；完整 SIM0／PRE 仍待验收。**

## 已验证结果

- Hub 现已正确登记 **2021.3.9f1／ad3870b89536**，路径为 `/tmp/roboracer-work/toolchains/2021.3.9f1/Editor/Unity`，官方版本查询成功。你报告项目创建成功；`/home/a2rl/My project/ProjectSettings/ProjectVersion.txt` 独立确认了固定编辑器版本和修订号。我只读检查了这个由你创建的项目。
- 第一次全新批处理重试创建了临时项目，并识别到已有有效许可，但随附 **.NET 5.0.3** 编译器报告 `No usable version of libssl was found`。编辑器清理随后触发信号量断言和 SIGTRAP：子进程退出码 **-5**，耗时 **10.09 秒**。该失败保留为证据，不计为启动通过。
- 将 Ubuntu `libssl1.1` **1.1.1f-1ubuntu2.24／amd64** 解压到隔离目录。使用本机 Ubuntu 归档密钥环验证官方 `focal-security` InRelease 签名，再逐级校验包索引和软件包 SHA-256。没有安装系统包，也没有执行软件包维护脚本。
- 第二次全新批处理项目仅增加这一个私有动态库搜索路径，完成编译，**22.34 秒后正常退出，退出码 0**。项目文件已生成，日志包含固定修订号及批处理成功退出标记，没有上述编译／libssl 错误，所启动编辑器已回收。

访问令牌警告可能先出现，随后编辑器仍能识别已有有效许可，因此不能仅凭该警告判断许可阻塞。新的全新项目批处理成功验证解除本机此配置下的 **SIM0-B01**。模板错误与许可状态分别依据各自证据判断。

## 依赖与适用范围

私有库目录为：

```text
/tmp/roboracer-work/sim0-20260929T085557Z/openssl-compat/extracted/usr/lib/x86_64-linux-gnu
```

通过 `scripts/autodrive_build.py --native-library-dir PATH` 显式传入。工具记录库指纹，只修改其编辑器子进程环境；不修改系统 OpenSSL 3、固定编辑器二进制、Hub 启动环境或直接经 Hub 打开的项目。你创建的 GUI 项目尚不能作为编译／构建通过的证据。

首次下载被沙箱域名许可列表阻止；随后范围明确的提权请求从 `security.ubuntu.com` 获取已签名元数据和所需单个软件包，仅使用 `dpkg-deb --extract` 解压到 `/tmp/roboracer-work/`。

这属于本机实际通过的兼容配置，不代表 Unity 2021.3.9f1／.NET 5 对 Ubuntu 22.04 的官方支持，也不将旧依赖视为当前通用安全基线。微软 [.NET Ubuntu 文档](https://learn.microsoft.com/en-us/dotnet/core/install/linux-ubuntu-decision)说明了不同 Ubuntu 版本的 OpenSSL 依赖和旧运行时支持状态；访问日期为 **2026-09-29**。

## 后续与证据

**后续导入审核：**首次完整导入退出码为 0，但存在资源导入失败。Unity 审核确认相关资源不在 F1TENTH 依赖集合中，范围明确的准备方案等待确认。详见[当前导入报告](SIM0-import-review.zh-CN.md)。启动恢复不代表这些源码资源问题已解除。

已在独立固定 AutoDRIVE 工作区应用此前审核的两个 manifest／lock 修改，将 Windows 主机构建工具链替换为同版本 **2.0.4** 的 Linux 主机构建工具链。此适配未修改物理、传感器、场景或运行源码。初次导入开始时不存在 `Library` 目录；仍需审核导入结果和全部生成差异后才能构建播放器。本次恢复不授权驾驶或 SIM1 插桩。

- [Hub／项目验证](../../artifacts/simulator-build/20260929T085557Z/hub-recovery-verification.json)。
- [第一次批处理失败](../../artifacts/simulator-build/20260929T085557Z/editor-startup/result.json)。
- [依赖签名来源和哈希](../../artifacts/simulator-build/20260929T085557Z/openssl-compatibility-dependency.json)。
- [成功的批处理恢复验证](../../artifacts/simulator-build/20260929T085557Z/startup-recovery-result.json)。
- [初次导入记录](../../artifacts/simulator-build/20260929T085557Z/initial-import/build-result.json)。

原计划仍为 **PRE-01／02 通过，PRE-03／04 未通过**。源码构建补充计划现有 **SIM0-01 通过**，SIM0-02／03／04 和全部 SIM1 项仍待验收。完整 SIM0 还需要合格源码构建、两次规定的静止观测及阶段报告，之后再审核是否进入 SIM1。
