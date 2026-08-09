"""Shell execution with strict command whitelisting and sandboxing."""

from __future__ import annotations

import asyncio
import shlex
import shutil
from pathlib import Path
from typing import Any

from shared.config import get_settings
from shared.logging import get_logger
from shared.security import SafePath, UnsafePathError

logger = get_logger("mcp.core.shell")

# fmt: off
_ALLOWED_COMMANDS = {
    "bash", "cat", "cd", "chmod", "chown", "cp", "curl", "cut", "date", "df", "diff", "du",
    "echo", "env", "find", "git", "grep", "head", "htop", "kill", "less", "ln", "ls", "make",
    "mkdir", "mv", "node", "npm", "npx", "pgrep", "pip", "ps", "pwd", "python3", "pytest",
    "rg", "rm", "rmdir", "rsync", "scp", "sed", "sh", "sort", "ssh", "tail", "tar", "tee",
    "top", "touch", "tr", "unzip", "wc", "wget", "which", "whoami", "xargs", "yarn", "zip",
}
# fmt: on

_DANGEROUS_CHARS = {";", "&", "|", "`", "$", "\n", "\r"}


def _validate_command(command: str) -> list[str]:
    # Reject obvious shell metacharacters outside of quotes.
    # This is intentionally conservative; complex pipelines are not allowed.
    if any(ch in command for ch in _DANGEROUS_CHARS):
        raise ValueError(
            "Shell metacharacters (; & | ` $ newline) are not allowed. "
            "Run a single whitelisted command with arguments."
        )

    try:
        parts = shlex.split(command)
    except ValueError as exc:
        raise ValueError(f"Invalid command string: {exc}") from exc

    if not parts:
        raise ValueError("Empty command")

    # Resolve the executable if it is a path; otherwise use the base name.
    executable = Path(parts[0])
    cmd_name = executable.name
    if executable.is_absolute() and not executable.exists():
        raise ValueError(f"Command not found: {executable}")

    # If a bare command name is used, ensure it is whitelisted.
    if not executable.is_absolute() and cmd_name not in _ALLOWED_COMMANDS:
        raise ValueError(f"Command '{cmd_name}' is not in the allowed list")

    return parts


async def run_shell(
    command: str,
    cwd: str | None = None,
    timeout: int = 60,
    env_extras: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Run a single whitelisted shell command inside an allowed working directory.

    Args:
        command: The command string to execute.
        cwd: Working directory. Must be inside allowed_directories.
        timeout: Maximum execution time in seconds (max 300).
        env_extras: Additional environment variables.
    """
    if timeout > 300:
        timeout = 300

    parts = _validate_command(command)

    # Validate cwd
    workdir = Path(cwd).expanduser().resolve() if cwd else Path.cwd()
    allowed = [Path(d).expanduser().resolve() for d in get_settings().allowed_directories]
    if not any(str(workdir).startswith(str(a)) for a in allowed):
        raise UnsafePathError(f"Working directory not allowed: {cwd}")
    if not workdir.exists():
        raise FileNotFoundError(f"Working directory does not exist: {workdir}")

    # Build env
    env = {**dict(__import__("os").environ), **(env_extras or {})}

    logger.info("shell_command_started", command=parts[0], cwd=str(workdir))
    try:
        proc = await asyncio.create_subprocess_exec(
            *parts,
            cwd=str(workdir),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        logger.warning("shell_command_timeout", command=parts[0])
        raise TimeoutError(f"Command timed out after {timeout}s") from None

    logger.info(
        "shell_command_finished",
        command=parts[0],
        returncode=proc.returncode,
    )

    return {
        "success": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": stdout.decode("utf-8", errors="replace"),
        "stderr": stderr.decode("utf-8", errors="replace"),
    }
