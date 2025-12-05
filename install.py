#!/usr/bin/env python3
"""Herald 安裝腳本 - 互動式設定音量與靜音時段。

此腳本會：
1. 詢問使用者偏好的音量百分比
2. 詢問靜音時段（24小時制）
3. 將 Herald hooks 設定寫入專案的 .claude/settings.json
4. 保留使用者原有的設定內容
"""
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path


# ANSI 顏色碼
class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def print_header(text: str) -> None:
    """印出標題樣式文字。"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.RESET}")
    print(f"{Colors.HEADER}{Colors.BOLD}  {text}{Colors.RESET}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.RESET}\n")


def print_info(text: str) -> None:
    """印出資訊文字。"""
    print(f"{Colors.CYAN}ℹ {text}{Colors.RESET}")


def print_success(text: str) -> None:
    """印出成功文字。"""
    print(f"{Colors.GREEN}✓ {text}{Colors.RESET}")


def print_warning(text: str) -> None:
    """印出警告文字。"""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.RESET}")


def print_error(text: str) -> None:
    """印出錯誤文字。"""
    print(f"{Colors.RED}✗ {text}{Colors.RESET}")


def get_volume_input() -> int:
    """詢問使用者音量設定。"""
    print(f"{Colors.BOLD}【音量設定】{Colors.RESET}")
    print("請輸入音量百分比 (0-100)")
    print(f"{Colors.CYAN}  範例: 30  (代表 30% 音量){Colors.RESET}")
    print(f"{Colors.CYAN}  範例: 0   (代表靜音){Colors.RESET}")
    print(f"{Colors.CYAN}  範例: 100 (代表最大音量){Colors.RESET}")
    print()

    while True:
        try:
            user_input = input(f"{Colors.BLUE}請輸入音量 (0-100) [預設: 30]: {Colors.RESET}").strip()
            if not user_input:
                return 30  # 預設值

            volume = int(user_input)
            if 0 <= volume <= 100:
                return volume
            print_error("請輸入 0 到 100 之間的數字")
        except ValueError:
            print_error("請輸入有效的數字")


def parse_time(time_str: str) -> tuple[int, int] | None:
    """解析時間字串，支援多種格式。"""
    time_str = time_str.strip().replace("：", ":").replace(" ", "")

    # 嘗試 HH:MM 格式
    if ":" in time_str:
        parts = time_str.split(":")
        if len(parts) == 2:
            try:
                hour = int(parts[0])
                minute = int(parts[1])
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    return (hour, minute)
            except ValueError:
                pass

    # 嘗試純數字格式 (如 2300 或 23)
    try:
        num = int(time_str)
        if 0 <= num <= 23:
            return (num, 0)
        if 100 <= num <= 2359:
            hour = num // 100
            minute = num % 100
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return (hour, minute)
    except ValueError:
        pass

    return None


def format_time(hour: int, minute: int) -> str:
    """格式化時間為 HH:MM。"""
    return f"{hour:02d}:{minute:02d}"


def get_quiet_hours_input() -> dict[str, str] | None:
    """詢問使用者靜音時段設定。"""
    print()
    print(f"{Colors.BOLD}【靜音時段設定】{Colors.RESET}")
    print("設定一個時段內不播放音效（使用 24 小時制）")
    print()
    print(f"{Colors.CYAN}  範例輸入格式：{Colors.RESET}")
    print(f"{Colors.CYAN}  - 22:00 或 22:00 (晚上 10 點){Colors.RESET}")
    print(f"{Colors.CYAN}  - 2300 (晚上 11 點){Colors.RESET}")
    print(f"{Colors.CYAN}  - 8 或 08 (早上 8 點){Colors.RESET}")
    print()
    print(f"{Colors.CYAN}  常見設定：{Colors.RESET}")
    print(f"{Colors.CYAN}  - 夜間靜音: 開始 22:00, 結束 08:00{Colors.RESET}")
    print(f"{Colors.CYAN}  - 午休靜音: 開始 12:00, 結束 13:30{Colors.RESET}")
    print()

    # 是否要設定靜音時段
    enable = input(f"{Colors.BLUE}是否要設定靜音時段? (y/N): {Colors.RESET}").strip().lower()
    if enable not in ("y", "yes", "是"):
        return None

    print()

    # 開始時間
    while True:
        start_input = input(f"{Colors.BLUE}請輸入靜音開始時間 [範例: 22:00]: {Colors.RESET}").strip()
        if not start_input:
            print_warning("已取消靜音時段設定")
            return None

        start_time = parse_time(start_input)
        if start_time:
            break
        print_error("無法解析時間，請使用 HH:MM 格式（如 22:00）")

    # 結束時間
    while True:
        end_input = input(f"{Colors.BLUE}請輸入靜音結束時間 [範例: 08:00]: {Colors.RESET}").strip()
        if not end_input:
            print_warning("已取消靜音時段設定")
            return None

        end_time = parse_time(end_input)
        if end_time:
            break
        print_error("無法解析時間，請使用 HH:MM 格式（如 08:00）")

    return {
        "start": format_time(*start_time),
        "end": format_time(*end_time),
    }


def get_herald_hooks_config() -> dict:
    """取得 Herald hooks 設定。"""
    hook_events = [
        "Notification",
        "Stop",
        "SubagentStop",
        "SessionStart",
        "SessionEnd",
        "UserPromptSubmit",
    ]

    hooks_config = {}
    for event in hook_events:
        hooks_config[event] = [
            {
                "matcher": "*",
                "hooks": [
                    {
                        "type": "command",
                        "command": f"$CLAUDE_PROJECT_DIR/.claude/herald/dispatcher.py --hook {event}",
                    }
                ],
            }
        ]

    return hooks_config


def merge_settings(existing: dict, new_hooks: dict, herald_settings: dict) -> dict:
    """合併現有設定與新設定，保留使用者原有內容。"""
    result = existing.copy()

    # 合併 hooks
    if "hooks" not in result:
        result["hooks"] = {}

    for event, config in new_hooks.items():
        result["hooks"][event] = config

    # 加入 herald 設定
    if "herald" not in result:
        result["herald"] = {}

    result["herald"].update(herald_settings)

    return result


def backup_file(file_path: Path) -> Path | None:
    """備份檔案。"""
    if not file_path.exists():
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = file_path.with_suffix(f".backup_{timestamp}.json")
    shutil.copy2(file_path, backup_path)
    return backup_path


def main() -> int:
    """主程式。"""
    print_header("Herald 安裝精靈")
    print_info("此腳本將幫助您設定 Herald 音效系統")
    print_info("您的現有設定將被保留，只會新增或更新 Herald 相關設定")
    print()

    # 確認專案目錄
    project_dir = Path.cwd()
    settings_path = project_dir / ".claude" / "settings.json"

    print(f"專案目錄: {Colors.BOLD}{project_dir}{Colors.RESET}")
    print(f"設定檔案: {Colors.BOLD}{settings_path}{Colors.RESET}")
    print()

    # 檢查 .claude 目錄
    claude_dir = project_dir / ".claude"
    if not claude_dir.exists():
        print_warning(".claude 目錄不存在，將自動建立")
        claude_dir.mkdir(parents=True, exist_ok=True)

    # 讀取現有設定
    existing_settings: dict = {}
    if settings_path.exists():
        try:
            existing_settings = json.loads(settings_path.read_text(encoding="utf-8"))
            print_success(f"已讀取現有設定檔 ({len(existing_settings)} 個頂層項目)")
        except json.JSONDecodeError as e:
            print_error(f"無法解析現有設定檔: {e}")
            print_warning("將建立新的設定檔")
            existing_settings = {}
    else:
        print_info("設定檔不存在，將建立新檔案")

    print()

    # 取得使用者輸入
    volume = get_volume_input()
    quiet_hours = get_quiet_hours_input()

    # 顯示摘要
    print()
    print_header("設定摘要")
    print(f"  音量: {Colors.BOLD}{volume}%{Colors.RESET}")
    if quiet_hours:
        print(f"  靜音時段: {Colors.BOLD}{quiet_hours['start']} - {quiet_hours['end']}{Colors.RESET}")
    else:
        print(f"  靜音時段: {Colors.BOLD}未設定{Colors.RESET}")
    print()

    # 確認
    confirm = input(f"{Colors.BLUE}確認套用以上設定? (Y/n): {Colors.RESET}").strip().lower()
    if confirm in ("n", "no", "否"):
        print_warning("已取消安裝")
        return 1

    # 準備 Herald 設定
    herald_settings: dict[str, object] = {
        "volume": volume / 100.0,  # 轉換為 0-1 範圍
    }
    if quiet_hours:
        herald_settings["quiet_hours"] = quiet_hours

    # 合併設定
    hooks_config = get_herald_hooks_config()
    final_settings = merge_settings(existing_settings, hooks_config, herald_settings)

    # 備份現有檔案
    if settings_path.exists():
        backup_path = backup_file(settings_path)
        if backup_path:
            print_success(f"已備份現有設定至: {backup_path.name}")

    # 寫入設定
    try:
        settings_path.write_text(
            json.dumps(final_settings, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print_success(f"設定已寫入: {settings_path}")
    except OSError as e:
        print_error(f"無法寫入設定檔: {e}")
        return 1

    print()
    print_header("安裝完成!")
    print_info("Herald 音效系統已設定完成")
    print_info("重新啟動 Claude Code 後，設定將生效")
    print()

    # 顯示最終設定檔內容摘要
    print(f"{Colors.CYAN}設定檔內容預覽:{Colors.RESET}")
    print(f"{Colors.CYAN}{'─'*40}{Colors.RESET}")

    # 只顯示 herald 相關設定
    preview = {
        "herald": final_settings.get("herald", {}),
        "hooks": {k: "..." for k in final_settings.get("hooks", {}).keys()},
    }
    print(json.dumps(preview, indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print()
        print_warning("安裝已取消")
        sys.exit(1)
