"""Shell 自动补全脚本生成

为支持的 shell（bash / zsh / fish / powershell）生成补全脚本。
用法::

    sbackup completion bash    # 输出 bash 补全脚本
    sbackup completion zsh     # 输出 zsh 补全脚本
    sbackup completion fish    # 输出 fish 补全脚本
    sbackup completion powershell  # 输出 PowerShell 补全脚本

安装示例::

    # Bash
    sbackup completion bash > /etc/bash_completion.d/sbackup

    # Zsh
    sbackup completion zsh > /usr/local/share/zsh/site-functions/_sbackup

    # Fish
    sbackup completion fish > ~/.config/fish/completions/sbackup.fish

    # PowerShell
    sbackup completion powershell >> $PROFILE
"""

# 所有子命令列表（与 cli.py 中的 _COMMAND_HANDLERS 保持同步）
_SUBCOMMANDS = [
    "add",
    "rm",
    "remove",
    "edit",
    "all",
    "list",
    "history",
    "save",
    "watch",
    "restore",
    "info",
    "diff",
    "verify",
    "sftp",
    "webdav",
    "remote",
    "export",
    "import",
    "status",
    "ignore",
    "versions",
    "schedule",
    "webhook",
    "config",
    "report",
    "search",
    "clean",
    "version",
    "init",
    "completion",
]

# 全局 flag（适用于所有命令）
_GLOBAL_FLAGS = [
    "--debug",
    "--lang",
    "--format",
    "--help",
    "--follow-symlinks",
    "--incremental",
    "--checksum",
]

# 各子命令的专属 flag
_SUBCOMMAND_FLAGS: dict[str, list[str]] = {
    "add": ["-i", "--ignore", "--format", "--name-template", "--from-gitignore"],
    "rm": ["--all"],
    "edit": ["--dest", "--ignore", "--format", "--name-template"],
    "save": [
        "--keep",
        "--keep-days",
        "--password",
        "--sftp",
        "--webdav",
        "--dry-run",
        "--verify",
        "--name-template",
        "--webhook",
        "--max-size",
        "--min-size",
        "--split",
        "--tag",
        "--older-than",
        "--pre-hook",
        "--post-hook",
    ],
    "watch": [
        "--interval",
        "--keep",
        "--keep-days",
        "--password",
        "--sftp",
        "--webdav",
        "--dry-run",
        "--verify",
        "--name-template",
        "--webhook",
        "--max-size",
        "--min-size",
        "--split",
        "--tag",
        "--older-than",
        "--pre-hook",
        "--post-hook",
        "--realtime",
        "--debounce",
    ],
    "restore": ["--password", "-l", "--list", "--select"],
    "sftp": ["config", "test"],
    "webdav": ["config", "test"],
    "remote": ["list", "rm"],
    "schedule": ["export"],
    "webhook": ["preset"],
    "config": ["lock", "unlock"],
    "verify": ["--fast", "--all", "--detail", "--split"],
    "diff": ["--password"],
    "info": ["--password"],
    "search": ["--password"],
    "versions": ["--password"],
    "export": [],
    "import": [],
    "ignore": ["--preset"],
    "clean": ["--keep", "--keep-days", "--dry-run"],
    "report": ["--format", "--output"],
    "completion": ["bash", "zsh", "fish", "powershell"],
    "all": [],
    "list": [],
    "history": [],
    "version": [],
    "init": [],
    "status": [],
}


def generate_bash() -> str:
    """生成 Bash 自动补全脚本"""
    lines = [
        "# sbackup Bash completion",
        f"_{_esc('_sbackup_completion')}() {{",
        "    local cur prev words cword",
        "    _init_completion || return",
        "",
        "    if [[ $cword -eq 1 ]]; then",
        f'        COMPREPLY=($(compgen -W "{" ".join(_SUBCOMMANDS)}" -- "$cur"))',
        "        return 0",
        "    fi",
        "",
        "    local cmd=${words[1]}",
        '    local global_flags="{}"'.format(" ".join(_GLOBAL_FLAGS)),
        "",
        "    case $cmd in",
    ]

    for cmd, flags in sorted(_SUBCOMMAND_FLAGS.items()):
        if cmd in ("rm", "list", "history", "all", "version", "init", "status"):
            continue  # handled by aliases or no flags
        flag_str = " ".join(flags) if flags else ""
        lines.append(f"        {cmd})")
        lines.append(
            f'            COMPREPLY=($(compgen -W "$global_flags {flag_str}" -- "$cur"))'
        )
        lines.append("            ;;")

    lines += [
        "        rm|remove)",
        '            COMPREPLY=($(compgen -W "$global_flags --all" -- "$cur"))',
        "            ;;",
        "        list|history)",
        '            COMPREPLY=($(compgen -W "$global_flags" -- "$cur"))',
        "            ;;",
        "        *)",
        '            COMPREPLY=($(compgen -W "$global_flags" -- "$cur"))',
        "            ;;",
        "    esac",
        "} &&",
        "complete -F _sbackup_completion sbackup",
        "",
    ]
    return "\n".join(lines)


def generate_zsh() -> str:
    """生成 Zsh 自动补全脚本"""
    lines = [
        "#compdef sbackup",
        "",
        "_sbackup_completion() {",
        "    local -a subcommands",
        "    subcommands=(",
    ]
    for cmd in _SUBCOMMANDS:
        lines.append(f"        '{cmd}:{_get_desc(cmd)}'")
    lines += [
        "    )",
        "",
        "    _arguments \\",
        "        '--debug[Enable debug mode]' \\",
        "        '--lang[Set interface language]:lang:(zh_CN en_US fr_FR es_ES ru_RU de_DE ja_JP pt_BR ko_KR)' \\",
        "        '--format[Set packaging format]:format:(zip tar tar.gz tar.bz2 tar.xz tar.zst 7z)' \\",
        "        '--follow-symlinks[Follow symbolic links]' \\",
        "        '--incremental[File-level incremental backup]' \\",
        "        '--checksum[Use SHA256 checksum]' \\",
        "        '--help[Show help]' \\",
        "        '1: :->command' \\",
        "        '*: :->args'",
        "",
        "    case $state in",
        "        command)",
        "            _describe 'command' subcommands",
        "            ;;",
        "        args)",
        "            _sbackup_args ${words[1]}",
        "            ;;",
        "    esac",
        "}",
        "",
        "_sbackup_args() {",
        "    case $1 in",
    ]
    for cmd, flags in sorted(_SUBCOMMAND_FLAGS.items()):
        if not flags:
            continue
        flag_parts = []
        for f in flags:
            if f.startswith("--"):
                flag_parts.append(f"'{f}[ ]'")
            elif f.startswith("-"):
                flag_parts.append(f"'{f}[ ]'")
        flag_str = " \\\n            ".join(flag_parts)
        lines += [
            f"        {cmd})",
            f"            _arguments : {flag_str}",
            "            ;;",
        ]
    lines += [
        "    esac",
        "}",
        "",
        '_sbackup_completion "$@"',
        "",
    ]
    return "\n".join(lines)


def generate_fish() -> str:
    """生成 Fish 自动补全脚本"""
    lines = [
        "# sbackup Fish completion",
        "",
    ]
    # 全局 flags
    lines += [
        "complete -c sbackup -l debug -d 'Enable debug mode'",
        "complete -c sbackup -l lang -x -a 'zh_CN en_US fr_FR es_ES ru_RU de_DE ja_JP pt_BR ko_KR' -d 'Set interface language'",
        "complete -c sbackup -l format -x -a 'zip tar tar.gz tar.bz2 tar.xz tar.zst 7z' -d 'Set packaging format'",
        "complete -c sbackup -l follow-symlinks -d 'Follow symbolic links'",
        "complete -c sbackup -l incremental -d 'File-level incremental backup'",
        "complete -c sbackup -l checksum -d 'Use SHA256 checksum'",
        "",
        "# Subcommands",
    ]
    for cmd in _SUBCOMMANDS:
        lines.append(
            f"complete -c sbackup -n 'not __fish_seen_subcommand_from {_esc(' '.join(_SUBCOMMANDS))}' -a {cmd} -d '{_get_desc(cmd)}'"
        )

    lines.append("")
    # 各子命令的 flags
    for cmd, flags in sorted(_SUBCOMMAND_FLAGS.items()):
        if not flags:
            continue
        for f in flags:
            if f.startswith("--"):
                lines.append(
                    f"complete -c sbackup -n '__fish_seen_subcommand_from {cmd}' "
                    f"-l {f[2:]} -d ''"
                )
            elif f.startswith("-") and not f.startswith("--"):
                lines.append(
                    f"complete -c sbackup -n '__fish_seen_subcommand_from {cmd}' "
                    f"-s {f[1:]} -d ''"
                )

    lines.append("")
    return "\n".join(lines)


def generate_powershell() -> str:
    """生成 PowerShell 自动补全脚本"""
    commands_json = ", ".join(f"'{c}'" for c in _SUBCOMMANDS)
    lines = [
        "# sbackup PowerShell completion",
        "Register-ArgumentCompleter -Native -CommandName sbackup -ScriptBlock {",
        "    param($wordToComplete, $commandAst, $cursorPosition)",
        "",
        f"    $commands = @({commands_json})",
        "    $globalFlags = @(",
        "        '--debug', '--lang', '--format', '--help',",
        "        '--follow-symlinks', '--incremental', '--checksum'",
        "    )",
        "",
        "    $cmdFlags = @{",
    ]
    for cmd, flags in sorted(_SUBCOMMAND_FLAGS.items()):
        flag_str = ", ".join(f"'{f}'" for f in flags) if flags else ""
        lines.append(f"        '{cmd}' = @({flag_str})")
    lines += [
        "    }",
        "",
        "    $tokens = $commandAst.CommandElements",
        "    $cmd = if ($tokens.Count -gt 1) { $tokens[1].Value } else { $null }",
        "",
        "    if ($tokens.Count -le 2) {",
        '        $commands | Where-Object { $_ -like "$wordToComplete*" }',
        "    } else {",
        "        $flags = $globalFlags + $cmdFlags[$cmd]",
        '        $flags | Where-Object { $_ -like "$wordToComplete*" }',
        "    }",
        "}",
        "",
    ]
    return "\n".join(lines)


def _get_desc(cmd: str) -> str:
    """获取子命令的简短描述"""
    desc_map = {
        "add": "Add a new backup strategy",
        "rm": "Remove a backup strategy",
        "remove": "Remove a backup strategy",
        "edit": "Edit a backup strategy",
        "all": "Show all backup strategies",
        "list": "Show backup history",
        "history": "Show backup history",
        "save": "Execute backup tasks",
        "watch": "Run backups periodically",
        "restore": "Restore from backup file",
        "info": "Show backup file info",
        "diff": "Show differences between source and backup",
        "verify": "Verify backup integrity",
        "sftp": "Manage SFTP remote backup",
        "webdav": "Manage WebDAV remote backup",
        "remote": "Manage remote files",
        "export": "Export backup strategies",
        "import": "Import backup strategies",
        "status": "Show backup status dashboard",
        "ignore": "Generate .sbackupignore file",
        "versions": "Show all versions for a source",
        "schedule": "Export schedule config",
        "webhook": "Configure webhook presets",
        "config": "Manage configuration",
        "report": "Export backup report",
        "search": "Search files in backups",
        "clean": "Clean old backups",
        "version": "Show version info",
        "init": "Generate config template",
        "completion": "Generate shell completion script",
    }
    return desc_map.get(cmd, "")


def _esc(s: str) -> str:
    """Shell 转义（简单处理）"""
    return s.replace("'", "'\\''")


def generate(shell: str) -> str:
    """生成指定 shell 的补全脚本"""
    generators = {
        "bash": generate_bash,
        "zsh": generate_zsh,
        "fish": generate_fish,
        "powershell": generate_powershell,
    }
    gen = generators.get(shell.lower())
    if gen is None:
        shells = ", ".join(generators)
        raise ValueError(f"Unsupported shell: {shell}. Supported: {shells}")
    return gen()
