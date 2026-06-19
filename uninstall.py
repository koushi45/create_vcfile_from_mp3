from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import tempfile
from pathlib import Path


APP_NAME = "AutoVoiceClipper"
LOG_PATH = Path(tempfile.gettempdir()) / f"{APP_NAME}-uninstall.log"


def message_box(text: str, title: str, flags: int) -> int:
    return ctypes.windll.user32.MessageBoxW(None, text, title, flags)


def log(message: str) -> None:
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(message + "\n")


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except OSError:
        return False


def relaunch_as_admin() -> bool:
    executable = Path(sys.executable).resolve()
    if getattr(sys, "frozen", False):
        params = ""
    else:
        params = f'"{Path(__file__).resolve()}"'

    log(f"Relaunching as admin: executable={executable} params={params!r}")
    result = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        str(executable),
        params,
        None,
        1,
    )
    log(f"ShellExecuteW result={result}")
    return result > 32


def add_existing(targets: list[Path], path: Path) -> None:
    try:
        resolved = path.expanduser().resolve()
    except OSError:
        resolved = path.expanduser().absolute()

    if resolved.exists() and resolved not in targets:
        targets.append(resolved)


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def find_repo_root(current_app_dir: Path) -> Path | None:
    candidates = [
        current_app_dir,
        current_app_dir.parent,
        current_app_dir.parent.parent,
    ]
    for candidate in candidates:
        if (candidate / "requirements-kotoba.txt").exists() and (
            candidate / "setup-kotoba.cmd"
        ).exists():
            return candidate
    return None


def collect_targets() -> list[Path]:
    targets: list[Path] = []
    home = Path.home()
    local_app_data = Path(os.environ.get("LOCALAPPDATA", ""))
    roaming_app_data = Path(os.environ.get("APPDATA", ""))
    current_app_dir = app_dir()
    repo_root = find_repo_root(current_app_dir)

    if getattr(sys, "frozen", False):
        add_existing(targets, current_app_dir)

    if current_app_dir.name == APP_NAME and current_app_dir.parent.name.lower() == "release":
        add_existing(targets, current_app_dir.parent / f"{APP_NAME}-Windows.zip")

    for root in [
        repo_root,
        current_app_dir,
        current_app_dir.parent,
        current_app_dir.parent.parent,
    ]:
        if root:
            add_existing(targets, root / ".venv-kotoba")
            add_existing(targets, root / ".pyinstaller-cache")

    cache_targets = [
        home / ".cache" / "huggingface",
        home / ".cache" / "torch",
        home / ".cache" / "transformers",
        home / ".cache" / "pyannote",
        home / ".cache" / "speechbrain",
        home / ".cache" / "pip",
        home / ".huggingface",
        local_app_data / "huggingface",
        local_app_data / "pip" / "Cache",
        roaming_app_data / "huggingface",
    ]
    for target in cache_targets:
        add_existing(targets, target)

    return targets


def powershell_literal(path: Path) -> str:
    return "'" + str(path).replace("'", "''") + "'"


def write_cleanup_script(targets: list[Path]) -> Path:
    script_path = Path(tempfile.gettempdir()) / f"{APP_NAME}-uninstall-{os.getpid()}.ps1"
    target_lines = "\n".join(f"  {powershell_literal(target)}" for target in targets)
    log_literal = powershell_literal(LOG_PATH)
    temp_literal = powershell_literal(Path(tempfile.gettempdir()))
    script = f"""$ErrorActionPreference = "SilentlyContinue"
function Write-Log([string]$Message) {{
  $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"
  Add-Content -LiteralPath {log_literal} -Encoding UTF8 -Value "[$timestamp] $Message"
}}

Write-Log "cleanup script started. pid=$PID"
Write-Log "cleanup script path=$PSCommandPath"
Write-Log "initial location=$(Get-Location)"
Set-Location -LiteralPath {temp_literal}
Write-Log "changed location=$(Get-Location)"

Start-Sleep -Seconds 1
Write-Log "waiting for uninstaller process id {os.getpid()}"
Wait-Process -Id {os.getpid()} -Timeout 30
Write-Log "wait completed"

$appProcesses = Get-Process -Name "{APP_NAME}" -ErrorAction SilentlyContinue
foreach ($process in $appProcesses) {{
  Write-Log "stopping process name=$($process.ProcessName) id=$($process.Id) path=$($process.Path)"
  Stop-Process -Id $process.Id -Force -ErrorAction Continue 2>&1 | ForEach-Object {{ Write-Log "stop process output: $_" }}
}}

$targets = @(
{target_lines}
)
Write-Log "target count=$($targets.Count)"
foreach ($target in $targets) {{
  Write-Log "target=$target exists=$(Test-Path -LiteralPath $target)"
}}

foreach ($target in $targets) {{
  if (Test-Path -LiteralPath $target) {{
    Write-Log "clearing attributes: $target"
    attrib -r -s -h "$target\\*" /s /d 2>$null
  }}
}}

for ($attempt = 1; $attempt -le 5; $attempt++) {{
  Write-Log "remove attempt $attempt started"
  foreach ($target in $targets) {{
    if (Test-Path -LiteralPath $target) {{
      Write-Log "removing: $target"
      Remove-Item -LiteralPath $target -Recurse -Force -ErrorAction Continue 2>&1 | ForEach-Object {{ Write-Log "remove output: $_" }}
      if (Test-Path -LiteralPath $target) {{
        Write-Log "still exists after remove: $target"
        Get-ChildItem -LiteralPath $target -Force -ErrorAction SilentlyContinue | Select-Object -First 30 | ForEach-Object {{
          Write-Log "remaining child: $($_.FullName)"
        }}
      }} else {{
        Write-Log "removed: $target"
      }}
    }} else {{
      Write-Log "already gone: $target"
    }}
  }}
  Start-Sleep -Milliseconds 700
}}

Write-Log "final target status"
foreach ($target in $targets) {{
  Write-Log "final target=$target exists=$(Test-Path -LiteralPath $target)"
}}

Remove-Item -LiteralPath $PSCommandPath -Force
"""
    script_path.write_text(script, encoding="utf-8")
    return script_path


def main() -> int:
    LOG_PATH.write_text(
        f"{APP_NAME} uninstall log\n"
        f"python executable: {sys.executable}\n"
        f"frozen: {getattr(sys, 'frozen', False)}\n"
        f"cwd: {Path.cwd()}\n"
        f"app_dir: {app_dir()}\n",
        encoding="utf-8",
    )
    log(f"is_admin={is_admin()}")
    if not is_admin():
        if relaunch_as_admin():
            return 0
        message_box(
            "Administrator permission is required to remove the application files.",
            f"{APP_NAME} Uninstaller",
            0x00000010,
        )
        return 1

    targets = collect_targets()
    log(f"collected {len(targets)} targets")
    for target in targets:
        log(f"target: {target}")
    if not targets:
        message_box(
            "No uninstall targets were found.",
            f"{APP_NAME} Uninstaller",
            0x00000040,
        )
        return 0

    target_text = "\n".join(f"- {target}" for target in targets)
    prompt = (
        f"This will remove {APP_NAME}, its virtual environment, packages, and caches.\n\n"
        "Targets:\n"
        f"{target_text}\n\n"
        "This action cannot be undone. Continue?"
    )
    result = message_box(prompt, f"{APP_NAME} Uninstaller", 0x00000034)
    if result != 6:
        return 0

    cleanup_script = write_cleanup_script(targets)
    log(f"cleanup script written: {cleanup_script}")
    subprocess.Popen(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(cleanup_script),
        ],
        creationflags=subprocess.CREATE_NO_WINDOW,
        cwd=tempfile.gettempdir(),
    )
    log("cleanup process launched")
    message_box(
        f"Uninstall has started. The application files will be removed shortly.\n\nLog:\n{LOG_PATH}",
        f"{APP_NAME} Uninstaller",
        0x00000040,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
