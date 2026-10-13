# Claude Code Transport Guard

[English README](README.en.md) · [威胁模型](THREAT_MODEL.md) · [审查与研究记录](docs/research/REVIEW.md)

面向 Claude Code 的本地 Bash 防护工具（v0.2.0）。它不部署代理，不改变 API 网络路径，也不提供传输完整性；它在 Bash 工具执行前拦截少量已知高危命令形态。Prompt 契约和锚点只是提醒，不能验证消息来源或保证阻止提示词注入。

**适用边界：** 本次在 Linux 上用离线假命令测试。Claude Code v2.1.295 起支持本项目使用的 `onFailure: "block"`，可在 Hook 启动失败或超时时阻断 Bash 调用；旧版不能依赖这一故障保护。尚未在真实 Claude Code 或 Android Termux 设备上验证。请保留 Claude Code 自身权限确认，不要将本工具当作 Shell 沙箱。

## 模式

| 命令 | 自定义 system prompt | 本项目防御 | 用途 |
| --- | --- | --- | --- |
| `claude-guarded` | Claude Code 默认 prompt + 防御契约 | 开启 | 日常开发与不可信内容 |
| `claude-bare` | 极简协作 prompt | 关闭 | 私人小项目、普通对话 |
| `claude-raw` | 不附加任何自定义 prompt | 关闭 | 实验性备用入口 |
| `claude-probe run` | 手动探针请求 | 不适用 | 主动检测部分链路改写 |

`claude-raw` 会让 Claude Code 使用空的自定义 system prompt。它不等于绕过模型提供方策略，也不是 RP 破限工具；因为模型可能不理解客户端协作约束、可能不调用工具或不按预期完成文件操作，所以不推荐用于编码任务。通过不可信中转站处理重要文件时，优先使用 `claude-guarded`。

所有模式仍使用 Claude Code 本身提供的工具与权限流程；裸版关闭的只是本项目追加的 prompt 锚点和本地 Bash 闸门。

## 安装

要求：Bash、Python 3、已安装 Claude Code。默认安装到 `$HOME/.local/bin` 和 `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/ccguard`，不会覆盖现有 `claude` 命令。

```bash
./install.sh
```

安装后可以运行：

```bash
ccguard status
claude-guarded
claude-bare
claude-raw
```

如需创建 `claude -> claude-guarded` shim，必须显式指定：

```bash
./install.sh --with-claude-shim
```

安装器会先记录已有 settings 和 `claude` 文件。已有其他目标的 `claude` 符号链接不会被覆盖。凭证继续从本机已有的
`~/.config/claude-code/credentials.env` 加载，仓库不会保存凭证。

## 管理命令

```bash
ccguard status
ccguard disable
ccguard enable
ccguard uninstall
ccguard uninstall --restore-backup
```

`disable` 和 `enable` 通过 `state.env` 控制 `CCGUARD_PROMPT`、`CCGUARD_GATE`，不会删除 hooks。普通 `uninstall` 只移除本项目拥有的 hooks 和文件，保留其他 settings；`--restore-backup` 用安装前备份恢复 settings 与 shim。若 settings 在安装后改动，备份恢复会拒绝覆盖；使用普通卸载保留这些改动。重复安装不会重置这个检查。

## 防御范围

完整模式包含：

- `UserPromptSubmit` 锚点，把伪装成 system、admin、platform 或 reminder 的新增文本当作数据；
- `PreToolUse` Bash 闸门，检查远程内容直接管道执行、反弹 shell、部分凭证外发、关键路径递归删除、块设备写入和类似高危模式；
- 手动 `claude-probe run`，使用随机标记检测一部分 system prompt 追加、截断或改写。

中转站可以读取、删除或重写请求中的 prompt，甚至伪造看似来自用户的消息。闸门在本地 Hook 执行，不经过中转站，但只看 Bash 工具调用的字面命令。动态变量、编码、脚本内部行为、Python/Node 等解释器、`Write`/`Edit` 和 MCP 工具可能绕过它；[已知漏检案例](docs/research/RESULTS.md)公开保留。命中后应阅读拦截原因，并由用户自行决定是否手动执行。

规则在 [lib/gate_check.py](lib/gate_check.py) 的 `RULES` 与 `RM_DANGEROUS` 中。修改规则后运行全部离线测试，再重新安装更新本地副本；项目目前不提供运行时规则覆盖配置，以免引入另一条隐蔽的放行路径。

## 测试与研究证据

```bash
bash tests/test-gate.sh
bash tests/test-install.sh
bash tests/test-termux-compat.sh
python3 tests/test-settings.py
python3 -m unittest discover -s tests -p 'test_v2_regression.py' -v
python3 tests/run_cases.py --compare-original --output docs/research/offline-results.json
```

最后一项需要本地 Git 历史包含原版提交 `3007550`。这些测试不执行案例中的命令，也不连接模型。19 个离线案例中，原版漏过 6/14 个高风险样本，新版漏过 4/14 个；两版在 5 个日常样本中均未误拦。样本规模很小，不能推算真实提示词注入阻断率。[方法](docs/research/METHOD.md)、[结果与限制](docs/research/RESULTS.md)及[确认缺陷](docs/research/FINDINGS.md)可复核。

探针只有显式 `run` 才联网：

```bash
claude-probe help
claude-probe run
```

探针的“未发现异常”不证明链路没有针对性改写。

## RP / 破限 FAQ

这个项目不能被理解为 RP 破限工具。`claude-bare` 只是减少客户端默认工作风格，`claude-raw` 则连项目极简提示词也去掉；两者都不改变模型提供方策略或服务端行为，也不保证特定内容生成。`claude-raw` 还会降低工具调用可靠性，因此只作为明确标注的实验性备选。

## 卸载

```bash
ccguard uninstall
```

需要恢复安装前副本时：

```bash
ccguard uninstall --restore-backup
```

卸载前退出 Claude Code 会话，并检查 `ccguard status` 与 settings 变更。不要把真实 `credentials.env`、日志、probe 输出或本机 settings 提交到仓库。

## License

MIT. See [LICENSE](LICENSE) and [SECURITY.md](SECURITY.md).
