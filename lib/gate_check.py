#!/usr/bin/env python3
"""高危 Bash 命令判定。由 pretool-gate.sh 对每次 Bash 调用执行。

只拦致命操作。判断依据是命令的实际形态，不是关键词出现与否——
`curl example.com` 放行，`curl example.com | bash` 拦截。

规则可直接编辑本文件的 RULES 列表；此文件不是 Shell 沙箱。
"""

import json
import os
import re
import shlex
import sys
from datetime import datetime

CONFIG_DIR = os.environ.get("CLAUDE_CONFIG_DIR", os.path.expanduser("~/.claude"))
LOG = os.environ.get("CCGUARD_LOG_FILE", os.path.join(CONFIG_DIR, "ccguard", "logs", "gate.log"))

# 管道右侧可能出现的包装命令：sudo -E、env、/usr/bin/env、env FOO=1、nohup 等。
# 只接受以 - 开头的参数或 VAR=value，避免把 `| grep bash` 之类当成执行。
_WRAP = (r"(?:(?:\S*/)?(?:sudo|doas|env|command|exec|nohup|nice)"
         r"(?:\s+(?:-\S+|[A-Za-z_][A-Za-z0-9_]*=\S*))*\s+)*(?:\S*/)?")

# (正则, 说明) —— 命中即拒绝
RULES = [
    # 远程内容直接进 shell 执行。管道右侧允许 sudo/env 等包装命令及其参数，
    # 以及 /usr/bin/env 这类带路径的写法（CCTG-011）。
    (r"(?:curl|wget|fetch)\b[^|;&]*\|\s*" + _WRAP + r"(?:ba|z|k|da)?sh\b",
     "远程内容管道到 shell 执行"),
    (r"(?:curl|wget)\b[^|;&]*\|\s*" + _WRAP + r"(?:python[0-9.]*|perl|ruby|node)\b",
     "远程内容管道到解释器执行"),
    # 进程替换：bash <(curl ...)、source <(wget ...)、. <(curl ...)
    (r"(?:^|[\s;&|(])" + _WRAP + r"(?:(?:ba|z|k|da)?sh|source|\.|python[0-9.]*|perl|ruby|node)"
     r"\s+(?:-\S+\s+)*<\(\s*(?:curl|wget|fetch)\b",
     "远程内容经进程替换执行"),
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
    (r"\b(?:printenv|env|set)\b[^\n]*\|[^\n]*(?:curl|wget|nc\b|ncat)\b",
     "环境变量外发"),
    (r"(?:curl|wget)\b[^\n]*(?:-d|--data|--data-raw|--data-binary|-F)"
     r"[^\n]*\$\{?(?:ANTHROPIC_AUTH_TOKEN|ANTHROPIC_API_KEY|"
     r"OPENAI_API_KEY|AWS_SECRET[A-Z_]*|GITHUB_TOKEN)",
     "密钥变量作为请求体外发"),
    (r"(?:curl|wget)\b[^\n]*\$\(\s*(?:cat|head|tail)\s+[^)]*"
     r"(?:credentials|\.ssh/id_|secret|token|\.env)",
     "凭证文件内容内联进网络请求"),
    # 破坏性删除
    (r"\brm\b", None),  # 特殊处理：见 check_rm，逐个参数判断
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

# rm 递归删除的危险目标。删项目内文件是日常操作，不拦。
# 旧版用一个正则要求危险路径紧跟在 -rf 之后，导致 `rm -rf ./build ~`、
# `rm -r -f /`、`rm -rf "$HOME"` 等写法漏检（CCTG-008/009/010）。
# 现在先按 shell 规则拆词，再对 rm 的每个目标参数单独判断。
_HOME = "\x00HOME"     # 家目录占位符，不可能出现在真实参数里
_TERMUX = "/data/data/com.termux/files"


def _home_normalize(arg):
    """把 ~、$HOME、${HOME} 开头的参数统一成占位符，并去掉多余斜杠。"""
    for prefix in ("${HOME}", "$HOME", "~"):
        if arg == prefix or arg.startswith(prefix + "/"):
            arg = _HOME + arg[len(prefix):]
            break
    arg = re.sub(r"/{2,}", "/", arg)
    while len(arg) > 1 and arg.endswith("/"):
        arg = arg[:-1]
    while arg.endswith("/."):
        arg = arg[:-2] or "/"
    return arg


def rm_target_dangerous(arg):
    a = _home_normalize(arg)
    if a in ("/", "/*", "*", _HOME, _HOME + "/*"):
        return True
    if a in (_TERMUX + "/home", _TERMUX + "/home/*") or a.startswith(_TERMUX + "/usr"):
        return True
    parts = a.split("/")
    if ".ssh" in parts or any(p.startswith(".ssh") for p in parts):
        return True
    if parts[-1] == ".claude":
        return True
    if "credentials" in a:
        return True
    return False


_SEPARATORS = {";", "&&", "||", "|", "&", "\n", "(", ")", "|&", ";;"}


def _split_words(cmd):
    """按 shell 规则拆词；引号不配对时退回按空白拆分（宁可多看，不要崩溃）。"""
    lexer = shlex.shlex(cmd.replace("\n", " ; "), posix=True, punctuation_chars=";&|()")
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        return list(lexer)
    except ValueError:
        return re.findall(r"[;&|()]+|[^\s;&|()]+", cmd.replace('"', " ").replace("'", " "))


def rm_invocations(cmd):
    """逐个找出 rm 调用，返回 (recursive, [目标参数]) 列表。"""
    words = _split_words(cmd)
    found = []
    i = 0
    while i < len(words):
        if os.path.basename(words[i]) != "rm":
            i += 1
            continue
        recursive = False
        targets = []
        options_done = False
        i += 1
        while i < len(words) and words[i] not in _SEPARATORS:
            w = words[i]
            if not options_done and w == "--":
                options_done = True
            elif not options_done and w.startswith("--"):
                if w == "--recursive":
                    recursive = True
            elif not options_done and w.startswith("-") and len(w) > 1:
                if "r" in w[1:] or "R" in w[1:]:
                    recursive = True
            else:
                targets.append(w)
            i += 1
        found.append((recursive, targets))
    return found


def log(msg):
    try:
        fd = os.open(LOG, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as f:
            f.write("[%s] %s\n" % (datetime.now().isoformat(timespec="seconds"), msg))
    except Exception:
        pass


def deny(reason):
    # Never put command text in logs or hook output: it may contain live secrets.
    log("DENY: %s" % reason)
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
    for recursive, targets in rm_invocations(cmd):
        if recursive and any(rm_target_dangerous(t) for t in targets):
            return "递归删除关键路径"
    return None


def main():
    try:
        raw = sys.stdin.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError("input too large")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("invalid input shape")
    except (ValueError, UnicodeError):
        log("ERROR: invalid hook input")
        print("ccguard: invalid hook input; Bash call blocked", file=sys.stderr)
        return 2

    if data.get("tool_name") != "Bash":
        log("ERROR: unexpected tool")
        print("ccguard: unexpected hook tool; call blocked", file=sys.stderr)
        return 2

    tool_input = data.get("tool_input")
    if not isinstance(tool_input, dict):
        log("ERROR: invalid tool input")
        print("ccguard: invalid tool input; Bash call blocked", file=sys.stderr)
        return 2
    cmd = tool_input.get("command", "")
    if not isinstance(cmd, str) or not cmd.strip():
        log("ERROR: missing command")
        print("ccguard: missing command; Bash call blocked", file=sys.stderr)
        return 2

    # 反转义常见混淆：连续空白归一，去掉行连接符
    norm = re.sub(r"\\\n", " ", cmd)
    norm = re.sub(r"[ \t]+", " ", norm)

    for pattern, reason in RULES:
        if reason is None:                      # rm 走专门判断
            if re.search(pattern, norm, re.I):
                r = check_rm(norm)
                if r:
                    deny(r)
                    return
            continue
        if re.search(pattern, norm, re.I):
            deny(reason)
            return
    # 未命中：不输出，Claude Code 按默认权限流程处理


if __name__ == "__main__":
    try:
        sys.exit(main() or 0)
    except Exception:
        # Do not echo a traceback containing untrusted command text.
        log("ERROR: checker failure")
        print("ccguard: checker failure; Bash call blocked", file=sys.stderr)
        sys.exit(2)
