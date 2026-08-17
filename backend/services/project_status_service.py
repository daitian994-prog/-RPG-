import json
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATUS_PATH = PROJECT_ROOT / "game-data" / "project_status.json"
CHANGELOG_PATH = PROJECT_ROOT / "CHANGELOG.md"
VERSION_PATH = PROJECT_ROOT / "VERSION"


def parse_changelog(markdown: str) -> list[dict[str, object]]:
    releases: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    for raw_line in markdown.splitlines():
        heading = re.match(r"^##\s+v?([^\s—-]+)\s*[—-]\s*(.+?)\s*$", raw_line)
        if heading:
            current = {"version": heading.group(1), "date": heading.group(2), "changes": []}
            releases.append(current)
        elif current is not None and raw_line.startswith("- "):
            current["changes"].append(raw_line[2:].strip())
    return releases


def build_integration_markdown(status: dict[str, object]) -> str:
    project = status["project"]
    web = status["web_integration"]
    lines = [
        f"# {project['name']} · 项目状态与网页端对接记录",
        "",
        f"- 当前版本：v{status['version']}",
        f"- 当前阶段：{project['current_stage']}",
        f"- 项目类型：{project['type']}",
        f"- 项目定位：{project['setting']}",
        "",
        "## 已实现系统",
        "",
    ]
    for system in status["systems"]:
        lines.append(f"- **{system['name']}（{system['status']}）**：{system['details']}")
    lines.extend(["", "## 技术结构", ""])
    for layer in status["architecture"]:
        lines.append(f"- **{layer['layer']}**：{layer['technology']}；{layer['responsibility']}")
    lines.extend(["", "## 网页端对接", "", f"- 状态接口：`{web['project_status']}`"])
    lines.extend(f"- `{endpoint}`" for endpoint in web["game_endpoints"])
    lines.extend(["", "### 对接规则", ""])
    lines.extend(f"- {rule}" for rule in web["rules"])
    lines.extend(["", "## 当前边界", ""])
    lines.extend(f"- {item}" for item in status["known_boundaries"])
    lines.extend(["", "## 版本更新日志", ""])
    for release in status["changelog"]:
        lines.extend([f"### v{release['version']} · {release['date']}", ""])
        lines.extend(f"- {change}" for change in release["changes"])
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def get_project_status() -> dict[str, object]:
    status = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    status["version"] = VERSION_PATH.read_text(encoding="utf-8").strip()
    status["changelog"] = parse_changelog(CHANGELOG_PATH.read_text(encoding="utf-8"))
    status["integration_markdown"] = build_integration_markdown(status)
    return status
