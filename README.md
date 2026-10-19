# SafeInvest：三台电脑、三位 AI 协作

当前分工：**GPT-6 Astra 主控；Codex GPT-6.1 Sol 工程与独立复核；WorkBuddy HY3 计算执行。** 这是 2026 MCM Senior Group Problem A 的研究仓库，原题和合成数据已加入。提交截止为 **2026-10-20 23:59（北京时间）**。

## 现在转发给另外两台电脑

- [完整提示词：Codex GPT-6.1 Sol](ops/prompts/START_SOL.txt)
- [完整提示词：WorkBuddy HY3](ops/prompts/START_HY3.txt)

让各端 AI 打开对应文件并执行。它们需要各自机器上已经登录的 GitHub 写权限；本机权限不会自动传给另一台。不要在聊天或仓库中粘贴密钥。首次接入后，它们会在各自 `status/sol`、`status/hy3` 分支写入真实状态。

## 工作区

主控维护 `main` 和 `ops/queue.json`；任务分支为 `work/sol/<任务>-a<尝试号>`、`work/hy3/<任务>-a<尝试号>`。每项任务固定起始代码版本和可写目录。旧版记录保存在 Git 历史及 `archive/pre-coordination-20261019`，旧文档的角色分工不再有效。

| 内容 | 目录 |
| --- | --- |
| 原题、原始数据、来源与校验值 | `problem/`、`data/raw/`、`data/manifest.json` |
| 开发集 / 最终测试集 | `data/development/` / `data/final_holdout/` |
| 数学规格、会计口径、实验计划 | `specs/` |
| 计算程序与测试 | `src/safeinvest/`、`tests/` |
| 结果与独立复核 | `results/`、`audit/` |
| 最终英文报告 | `report/` |
| 任务、提示词、控制开关 | `ops/` |
| 每项任务的提交回执 | `handoff/` |

## 自动协作如何运行

主控发布任务 → 指定电脑领取 → 独立分支执行 → 自动检查并推送回执 → 主控审查/复核 → 验收并下发下一项。GitHub 负责同步，实际工作由每台电脑的本地进程执行。只在出现需要推理的新任务或新的交付时调用模型。

- Sol 端：`python scripts/coop.py watch --role sol --backend codex`
- HY3 端：`python scripts/coop.py watch --role hy3 --backend commands`
- 主控端：`python scripts/coop.py watch --role chief --backend codex`
- 查看三端：`python scripts/coop.py status`
- 停止本机：`python scripts/coop.py stop`

Windows 也可用 `Start-Worker.ps1 -Role sol -Python <本机Python路径> -Background`（HY3 将角色换为 `hy3`）。不要重复启动相同角色。首次需实际验证 GitHub 回执，再认定在线。电脑休眠、断网、额度耗尽或登录失效都会影响运行；工作流会保留进度并报告实际阻塞。

Python 建议 3.12，数值依赖见 `requirements.txt`。启动程序和第一项输入检查仅依赖 Python 标准库，随后数值任务使用各机独立环境。主控已经具备 GPU 环境，但三资产问题可优先使用 CPU。

## 自校验与研究约束

固定输入哈希、任务版本和参数；检查转移费用、初始建仓、财富守恒、通胀、未来信息泄漏及情景边界；每次提交真实检查日志；关键实现与结论由另一强模型独立复核。自检通过不等于主控验收。

开发只使用情景1–120。主控锁定策略、参数、指标和严重案例选择规则后，才能对121–180进行最终评估，随后不得调参。通用投资skill的默认费率、日频指标或历史数据切分不能覆盖原题。

详细执行约定见 [协作协议](ops/PROTOCOL.md)、[题目要求](specs/PROBLEM_LOCK.md)、[费用与指标口径](specs/ACCOUNTING.md)。当前无已验收的策略效果结论；不得将环境测试或待审结果当作比赛答案。

## 人员最后要提供的内容

各端首次登录/授权在本机完成。最终写报告时还需要三位成员的姓名。工作流默认在北京时间10月20日23:30停止启动新任务，为队长检查和提交预留时间；这不是比赛官方截止时间。正式提交由队长完成。
