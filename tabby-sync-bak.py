import os
import json
import shutil
import requests
import argparse
import sys
from pathlib import Path
from datetime import datetime

# 配置路径
CONFIG_DIR = {
    "win32": Path(os.getenv('APPDATA')) / "tabby",
    "darwin": Path.home() / "Library" / "Application Support" / "tabby",
    "linux": Path.home() / ".config" / "tabby"
}[sys.platform]

CONFIG_PATH = CONFIG_DIR / "config.yaml"
GIST_CONFIG_PATH = CONFIG_DIR / "gist.json"

# GitHub API 设置
GITHUB_API = "https://api.github.com"
GIST_FILENAME = "tabby-config.yaml"


def load_gist_config():
    if GIST_CONFIG_PATH.exists():
        with open(GIST_CONFIG_PATH, 'r') as f:
            return json.load(f)
    return {"gist_id": "", "token": ""}


def save_gist_config(config):
    with open(GIST_CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=2)


def get_gist(token, gist_id=None):
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}

    if gist_id:
        response = requests.get(f"{GITHUB_API}/gists/{gist_id}", headers=headers)
        if response.status_code == 200:
            return response.json()

    # 创建新 Gist
    data = {
        "description": "Tabby Configuration Sync",
        "public": False,
        "files": {GIST_FILENAME: {"content": "Tabby configuration file"}}
    }
    response = requests.post(f"{GITHUB_API}/gists", headers=headers, json=data)
    if response.status_code == 201:
        return response.json()
    raise Exception(f"Failed to create Gist: {response.text}")


def upload_config(token, gist_id):
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}

    with open(CONFIG_PATH, 'r') as f:
        config_content = f.read()

    data = {
        "files": {GIST_FILENAME: {"content": config_content}}
    }
    response = requests.patch(f"{GITHUB_API}/gists/{gist_id}", headers=headers, json=data)
    if response.status_code == 200:
        print("Configuration uploaded successfully!")
        return response.json()
    raise Exception(f"Upload failed: {response.text}")

    # 添加历史版本
    history_file = f"history/{datetime.now().isoformat()}.yaml"
    data["files"][history_file] = {"content": config_content}


def download_config(token, gist_id):
    # 备份当前配置
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backup_path = CONFIG_PATH.with_name(f"config_backup_{timestamp}.yaml")
    shutil.copy(CONFIG_PATH, backup_path)

    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}

    response = requests.get(f"{GITHUB_API}/gists/{gist_id}", headers=headers)
    if response.status_code != 200:
        raise Exception(f"Download failed: {response.text}")

    gist_data = response.json()
    config_content = gist_data["files"][GIST_FILENAME]["content"]

    with open(CONFIG_PATH, 'w') as f:
        f.write(config_content)

    print("Configuration downloaded successfully!")
    return gist_data


def main():
    parser = argparse.ArgumentParser(description="Sync Tabby configuration via GitHub Gist")
    parser.add_argument("action", choices=["init", "push", "pull"], help="Sync action")
    parser.add_argument("--token", help="GitHub personal access token")
    args = parser.parse_args()

    gist_config = load_gist_config()
    token = args.token or gist_config.get("token", "")

    if not token:
        print("Error: GitHub token is required. Use --token or run 'init' first.")
        return

    if args.action == "init":
        if not token:
            print("Please provide token with --token")
            return

        gist = get_gist(token)
        gist_id = gist["id"]
        gist_config = {"token": token, "gist_id": gist_id}
        save_gist_config(gist_config)

        # 上传初始配置
        upload_config(token, gist_id)
        print(f"Sync initialized! Gist ID: {gist_id}")
        print(f"Gist URL: {gist['html_url']}")
        return

    gist_id = gist_config.get("gist_id", "")
    if not gist_id:
        print("Gist ID not found. Please run 'init' first.")
        return

    if args.action == "push":
        upload_config(token, gist_id)
    elif args.action == "pull":
        download_config(token, gist_id)
        print("Please restart Tabby to apply changes")


if __name__ == "__main__":
    main()