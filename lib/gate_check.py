#!/usr/bin/env python3
"""高危 Bash 命令判定。由 pretool-gate.sh 在快速路径命中后调用。

只拦致命操作。判断依据是命令的实际形态，不是关键词出现与否——
`curl example.com` 放行，`curl example.com | bash` 拦截。

规则可直接编辑本文件的 RULES 列表。
"""

import json
import os
import re
import sys
from datetime import datetime

CONFIG_DIR = os.environ.get("CLAUDE_CONFIG_DIR", os.path.expanduser("~/.claude"))
LOG = os.environ.get("CCGUARD_LOG_FILE", os.path.join(CONFIG_DIR, "ccguard", "logs", "gate.log"))

# (正则, 说明) —— 命中即拒绝
RULES = [
    # 远程内容直接进 shell 执行
    (r"(?:curl|wget|fetch)\b[^|;&]*\|\s*(?:sudo\s+)?(?:ba|z|k|da)?sh\b",
     "远程内容管道到 shell 执行"),
    (r"(?:curl|wget)\b[^|;&]*\|\s*(?:sudo\s+)?(?:python|perl|ruby|node)\b",
     "远程内容管道到解释器执行"),
    # 反弹 shell
    (r"(?:ba|z)?sh\b[^\n]*(?:>\s*&?\s*)?/dev/tcp/",
     "反弹 shell（/dev/tcp）"),
    (r"\b(?:nc|ncat|netcat)\b[^\n]*\s-[a-z]*e[a-z]*\s",
     "反弹 shell（nc -e）"),
    (r"\bmkfifo\b[^\n]*\|[^\n]*\b(?:nc|ncat|netcat)\b",
     "反弹 shell（mkfifo + nc）"),
    # 凭证读取后外发
    (r"(?:cat|less|head|tail|strings|xxd|base64)\b[^\n]*"
     r"(?:credentials\.env|\.ssh/id_[a-z0-9]+|\.aws/credentials|"
     r"\.netrc|\.git-credentials|keys/)"
     r"[^\n]*\|[^\n]*(?:curl|wget|nc\b|ncat|mail|ssh\b)",
     "读取凭证并外发"),
    (r"(?:printenv|env|set)\b[^\n]*\|[^\n]*(?:curl|wget|nc\b|ncat)\b",
     "环境变量外发"),
    (r"(?:curl|wget)\b[^\n]*(?:-d|--data|--data-raw|--data-binary|-F)"
     r"[^\n]*\$\{?(?:ANTHROPIC_AUTH_TOKEN|ANTHROPIC_API_KEY|"
     r"OPENAI_API_KEY|AWS_SECRET[A-Z_]*|GITHUB_TOKEN)",
     "密钥变量作为请求体外发"),
    (r"(?:curl|wget)\b[^\n]*\$\(\s*(?:cat|head|tail)\s+[^)]*"
     r"(?:credentials|\.ssh/id_|secret|token|\.env)",
     "凭证文件内容内联进网络请求"),
    # 破坏性删除
    (r"\brm\b[^\n]*\s-[a-zA-Z]*[rR][a-zA-Z]*f|"
     r"\brm\b[^\n]*\s-[a-zA-Z]*f[a-zA-Z]*[rR]",
     None),  # 特殊处理：见 check_rm
    (r"\b(?:mkfs|fdisk|parted)\b", "磁盘格式化/分区操作"),
    (r"\bdd\b[^\n]*\bof=/dev/(?:block|sd|mmcblk|nvme)", "dd 直写块设备"),
    (r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:", "fork 炸弹"),
    # 权限提升
    (r"\bchmod\b[^\n]*\s(?:\+s|[0-7]?[2467][0-7]{3})\b", "设置 setuid/setgid 位"),
    # 篡改防御自身（只拦删除与覆盖写，chmod/读取属正常维护）
    (r"\brm\b[^\n]*\.claude/(?:ccguard|settings\.json)|"
     r"\bmv\b[^\n]*\.claude/(?:ccguard|settings\.json)[^\n]*\s|"
     r"\btruncate\b[^\n]*\.claude/(?:ccguard|settings\.json)|"
     r">\s*[^\s|]*\.claude/(?:ccguard|settings\.json)",
     "删除或覆盖防御配置自身"),
    (r"\brm\b[^\n]*\.local/bin/claude|"
     r">\s*[^\s|]*\.local/bin/claude(?:-(?:guarded|bare|raw|probe))?(?:\s|$)",
     "删除或覆盖 claude 启动脚本"),
]

# rm -rf 的危险目标。删项目内文件是日常操作，不拦。
RM_DANGEROUS = re.compile(
    r"\brm\b[^\n]*?\s-[a-zA-Z]*[rRf][a-zA-Z]*\s+(?:-{1,2}[a-zA-Z-]+\s+)*"
    r"(?:"
    r"/(?:\s|;|&|\||$)|"                        # 根目录（独立的 /）
    r"/\*|"                                     # /*
    r"\$HOME(?:/)?(?:\s|;|&|\||$)|"             # 整个家目录
    r"~(?:/)?(?:\s|;|&|\||$)|"
    r"/data/data/com\.termux/files/usr|"        # Termux 系统前缀
    r"/data/data/com\.termux/files/home(?:/)?(?:\s|;|&|\||$)|"
    r"[^\s]*\.ssh|"                             # 凭证与配置
    r"[^\s]*\.claude(?:/)?(?:\s|;|&|\||$)|"
    r"[^\s]*credentials|"
    r"\*(?:\s|;|&|\||$)"                        # 裸通配符
    r")"
)


def log(msg):
    try:
        with open(LOG, "a") as f:
            f.write("[%s] %s\n" % (datetime.now().isoformat(timespec="seconds"), msg))
    except Exception:
        pass


def deny(reason, cmd):
    log("DENY: %s | cmd=%r" % (reason, cmd[:400]))
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                "本地闸门拦截：%s。\n"
                "此命令匹配高危模式，已在执行前阻止。若这确实是用户本人要求的操作，"
                "请向用户说明该命令的作用与风险，由用户手动执行，或让用户调整 "
                "ccguard 安装目录中 gate_check.py 的规则。" % reason
            ),
        }
    }, ensure_ascii=False))


def check_rm(cmd):
    return "递归强制删除关键路径" if RM_DANGEROUS.search(cmd) else None


def main():
    try:
        data = json.load(sys.stdin)
    except Exception as e:
        log("输入解析失败: %s" % e)
        return  # 静默放行

    if data.get("tool_name") != "Bash":
        return

    cmd = (data.get("tool_input") or {}).get("command", "")
    if not isinstance(cmd, str) or not cmd.strip():
        return

    # 反转义常见混淆：连续空白归一，去掉行连接符
    norm = re.sub(r"\\\n", " ", cmd)
    norm = re.sub(r"[ \t]+", " ", norm)

    for pattern, reason in RULES:
        if reason is None:                      # rm 走专门判断
            if re.search(pattern, norm, re.I):
                r = check_rm(norm)
                if r:
                    deny(r, cmd)
                    return
            continue
        if re.search(pattern, norm, re.I):
            deny(reason, cmd)
            return
    # 未命中：不输出，Claude Code 按默认权限流程处理


if __name__ == "__main__":
    main()
