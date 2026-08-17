# Claude Code Transport Guard

面向 Claude Code 的本地传输链路防御与双重裸版入口。它不部署代理，不改变 API 网络路径，也不声称提供密码学完整性；目标是降低中转链路注入影响，并在本地执行 Bash 工具前拦截少量高危模式。

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

安装器会先记录已有 settings 和 `claude` 文件。凭证继续从本机已有的
`~/.config/claude-code/credentials.env` 加载，仓库不会保存凭证。

## 管理命令

```bash
ccguard status
ccguard disable
ccguard enable
ccguard uninstall
ccguard uninstall --restore-backup
```

`disable` 和 `enable` 通过 `state.env` 控制 `CCGUARD_PROMPT`、`CCGUARD_GATE`，不会删除 hooks。普通 `uninstall` 只移除本项目拥有的 hooks 和文件，保留其他 settings；`--restore-backup` 用安装时生成的备份恢复 settings 与 shim，适合故障回滚。

## 防御范围

完整模式包含：

- `UserPromptSubmit` 锚点，把伪装成 system、admin、platform 或 reminder 的新增文本当作数据；
- `PreToolUse` Bash 闸门，拦截远程内容直接管道执行、反弹 shell、凭证外发、关键路径递归删除、块设备写入和类似高危模式；
- 手动 `claude-probe run`，使用随机标记检测一部分 system prompt 追加、截断或改写。

中转站可以读取、删除或重写请求中的 prompt，所以 prompt 层不是密码学完整性保护。闸门在本地 hook 执行，不经过中转站；它是窄规则过滤器，不是完整 shell sandbox。命中后应阅读拦截原因，并由用户自行决定是否手动执行。

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

## English summary

Claude Code Transport Guard provides local prompt-injection resistance, a narrow
pre-tool Bash gate, and explicit guarded, minimal-prompt, and no-custom-prompt
launchers. It does not provide cryptographic transport integrity or bypass
provider policies. The no-custom-prompt launcher is experimental and may fail
to use tools reliably.

## License

MIT. See [LICENSE](LICENSE) and [SECURITY.md](SECURITY.md).
