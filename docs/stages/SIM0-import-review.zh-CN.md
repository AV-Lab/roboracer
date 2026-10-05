# SIM0：首次导入审核与恢复建议

**2026-09-29 更新：** 用户已明确批准下述六项资源的隔离方案。已在独立验证工作区执行，原始文件与历史失败证据保留。针对错误已消除，但发现必需 SketchUp 赛道无法在 Linux 导入，见[最新阻塞报告](SIM0-sketchup-blocker.zh-CN.md)。下文为原审核记录，验收仍未完成。证据：`artifacts/simulator-build/20260929T100424Z/`。


日期：**2026-09-29**。运行编号：`20260929T085557Z`。[英文报告](SIM0-import-review.md)。**SIM0-01 已通过；SIM0-02 因首次资源导入失败受阻，资源范围调整建议等待确认。尚未开始播放器构建或静止运行。**

## 实际结果

首次 AutoDRIVE 导入开始时不存在项目 `Library` 目录，使用固定编辑器、已验证的私有 libssl1.1 及审核过的同版本 Linux 主机编译工具链。导入 **389.49 秒后退出，退出码 0，C# 编译错误为零**；但日志审核发现 **五个资源导入失败**，以及一次 HDRP SpeedTree 材质升级器异常。因此不能将退出码 0 视为干净导入或 SIM0-02 完成。

五个失败文件为 `Assets/ML Resources/Results/CrossJunctionNavigation/` 下的二进制 TensorFlow `.ckpt.index` 训练检查点文件。Unity 的 SearchDatabase 导入器根据 `.index` 扩展名把它们当作搜索索引配置，尝试解析 JSON。每个文件大小为 2,077 字节；这不是下载不完整的证据。

另一个异常来自 `Assets/Plugins/Windridge City/Windridge City Assets/StaticObjects/Models/Foliage/Broadleaf/Broadleaf_Mobile.spm` 导入。日志先出现后备着色器缺失提示，随后进入 HDRP 12.1.7 的 SpeedTree 材质升级器异常。完整原因以及有图形环境的全新导入是否能解决，尚未验证；不擅自修改 HDRP 或切换渲染器。

Unity 还自动删除九个孤立 `.meta` 文件，其对应资源在固定 Git 树中原本就不存在，并升级了两个演示材质。全部差异已保留。**F1TENTH.unity 和 ProjectSettings 无变化**；包配置变化仅为此前审核的两个主机构建工具链修改。

## 目标场景审核

通过有时限的临时 **Editor-only** 探针调用 `AssetDatabase.GetDependencies("Assets/Scenes/F1TENTH.unity", true)`，**12.01 秒后正常退出**，得到 **276 个依赖**。六个失败资源和两个变更材质均不在其中。探针随后移除，没有打开／保存场景，也没有进入 Play 模式。

限定范围字节扫描未在检查的现存场景依赖及元数据中发现上述九个孤立 GUID 的引用；检查的 `Assets/Scripts` C# 文件未匹配到相关动态加载表达式。这些检查不能证明所有运行时动态加载情况，也不能替代播放器运行验证。

增量审核运行未重复出现资源导入错误，但这种已有缓存下的结果不能代替所需的首次干净导入。最初失败记录继续保留。

## 建议恢复方式——尚未执行

建立**独立验证副本**，将已识别的六个资源及其元数据完整保存在 Unity 自动导入区域之外。保留完整上游工作区和逐文件哈希。[具体候选清单](../../artifacts/simulator-build/20260929T085557Z/import-recovery-proposal.json)列出每个文件、大小和 SHA-256。

重新执行干净导入／构建，并将 Unity 报告的 F1TENTH 依赖集合及必需资源哈希与原始审核结果比较。新增缺失引用、必需依赖变化，或物理／传感器／场景变化，均阻止通过。其他非目标资源若引用这些文件，还需继续审核；此建议不授权任意裁剪或修改厂商包。后续仍执行原定两次全新进程、每次 60 秒的静止观测。

**收益：**针对竞速目标场景之外的资源故障处理，保留固定运行时、渲染器及原始文件。**成本：**增加显式源码准备清单，并重新导入／构建。**剩余风险：**静态依赖可能遗漏动态加载，其他未使用资源也可能引用这些文件，因此仍需实际构建及静止运行证据。

另一方案是保持全部资源参与导入，继续调查整个项目的导入器故障，可能涉及额外厂商工具或渲染处理，范围和工作量更不确定。

之所以请你确认，是因为该建议改变了验证构建输入，超出此前明确审核的编译工具链适配。验收条件不降低，也不授权运动或进入 SIM1／S1。此前模板／许可启动问题已经独立解除，本报告不要求再次操作账号。

## 证据

- [启动恢复报告](SIM0-startup-recovery.zh-CN.md)及[运行摘要](../../artifacts/simulator-build/20260929T085557Z/result-summary.json)。
- [首次导入结果](../../artifacts/simulator-build/20260929T085557Z/initial-import/build-result.json)及[生成差异](../../artifacts/simulator-build/20260929T085557Z/initial-import/source-after.patch)。
- [Unity 依赖报告](../../artifacts/simulator-build/20260929T085557Z/scene-audit/scene-audit.json)、[依赖审核](../../artifacts/simulator-build/20260929T085557Z/scene-dependency-review.json)、[限定源码检查](../../artifacts/simulator-build/20260929T085557Z/source-hygiene-review.json)。
- 可复用审核入口：[构建工具](../../scripts/autodrive_build.py)的 `--audit-scene` 模式，调用 [Editor-only 探针](../../scripts/SceneDependencyAudit.cs)，不创建或运行播放器。
