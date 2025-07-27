import os
import json
import requests
import argparse
import sys
import shutil
import base64
import zipfile
import io
import hashlib
import fnmatch
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# 配置路径
CONFIG_DIR = {
    "win32": Path(os.getenv('APPDATA')) / "tabby",
    "darwin": Path.home() / "Library" / "Application Support" / "tabby",
    "linux": Path.home() / ".config" / "tabby"
}[sys.platform]

# 需要同步的所有文件和目录
SYNC_ITEMS = [
    "config.yaml",  # 主配置文件
    "keymaps.yaml",  # 快捷键配置
    "window-config.yaml",  # 窗口设置
    "vault/",  # 保险库目录
    "profiles/",  # 配置文件目录
    "plugins/",  # 插件目录
    "themes/"  # 主题目录
]

# 排除不需要同步的文件模式
EXCLUDE_PATTERNS = [
    "*.log", "*.tmp", "*.cache", "node_modules/*", "*.gitkeep"
]

GIST_CONFIG_PATH = CONFIG_DIR / "gist.json"

# GitHub API 设置
GITHUB_API = "https://api.github.com"
GIST_FILENAME = "tabby-config.zip"


def load_gist_config():
    if GIST_CONFIG_PATH.exists():
        with open(GIST_CONFIG_PATH, 'r') as f:
            return json.load(f)
    return {"gist_id": "", "token": "", "hashes": {}}


def save_gist_config(config):
    with open(GIST_CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=2)


def file_hash(path):
    """计算文件的MD5哈希值"""
    if not path.exists():
        return ""
    try:
        with open(path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()
    except:
        return ""


def dir_hash(path):
    """计算目录的MD5哈希值（基于文件名和内容）"""
    if not path.exists():
        return ""
    hasher = hashlib.md5()
    for root, _, files in os.walk(path):
        for file in files:
            file_path = Path(root) / file
            # 跳过排除的文件
            if any(fnmatch.fnmatch(file, pattern) for pattern in EXCLUDE_PATTERNS):
                continue
            try:
                with open(file_path, "rb") as f:
                    hasher.update(file_path.relative_to(path).as_posix().encode())
                    hasher.update(f.read())
            except:
                pass
    return hasher.hexdigest()


def get_item_hash(item_path):
    """获取项目（文件或目录）的哈希值"""
    if item_path.is_dir():
        return dir_hash(item_path)
    return file_hash(item_path)


def create_zip_archive(items=None):
    """创建包含配置文件的ZIP压缩包"""
    items = items or SYNC_ITEMS
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    zip_path = CONFIG_DIR / f"tabby-config-{timestamp}.zip"

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for item in items:
            item_path = CONFIG_DIR / item
            if not item_path.exists():
                continue

            if os.path.isdir(item_path):
                for root, _, files in os.walk(item_path):
                    for file in files:
                        file_path = Path(root) / file
                        arcname = file_path.relative_to(CONFIG_DIR).as_posix()

                        # 跳过排除的文件
                        if any(fnmatch.fnmatch(file, pattern) for pattern in EXCLUDE_PATTERNS):
                            continue

                        zipf.write(file_path, arcname)
            else:
                # 跳过排除的文件
                if any(fnmatch.fnmatch(item, pattern) for pattern in EXCLUDE_PATTERNS):
                    continue

                arcname = os.path.basename(item_path)
                zipf.write(item_path, arcname)

    return zip_path


def extract_zip_archive(zip_content):
    """从ZIP内容中提取所有配置文件"""
    # 备份当前配置
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backup_dir = CONFIG_DIR / f"backup-{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    for item in SYNC_ITEMS:
        item_path = CONFIG_DIR / item
        if os.path.exists(item_path):
            if os.path.isdir(item_path):
                shutil.copytree(item_path, backup_dir / item)
            else:
                shutil.copy2(item_path, backup_dir / os.path.basename(item))

    # 并行解压
    with zipfile.ZipFile(io.BytesIO(zip_content)) as zipf:
        file_list = zipf.namelist()
        with ThreadPoolExecutor(max_workers=8) as executor:
            executor.map(lambda f: zipf.extract(f, CONFIG_DIR), file_list)

    print(f"配置已提取! 备份创建于: {backup_dir}")
    return True


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
        "files": {GIST_FILENAME: {"content": "Initial placeholder for Tabby config"}}
    }
    response = requests.post(f"{GITHUB_API}/gists", headers=headers, json=data)
    if response.status_code == 201:
        return response.json()
    raise Exception(f"创建 Gist 失败: {response.text}")


def upload_config(token, gist_id):
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}

    gist_config = load_gist_config()

    # 1. 检测变更的文件
    changed_items = []
    for item in SYNC_ITEMS:
        item_path = CONFIG_DIR / item
        current_hash = get_item_hash(item_path)
        stored_hash = gist_config.get("hashes", {}).get(item, "")

        if current_hash != stored_hash:
            changed_items.append(item)
            print(f"检测到变更: {item}")

    # 没有变更则跳过
    if not changed_items:
        print("无文件变更，跳过上传")
        return

    # 2. 创建只包含变更文件的ZIP
    zip_path = create_zip_archive(changed_items)

    # 3. 读取ZIP内容并使用base64编码
    with open(zip_path, 'rb') as f:
        zip_content = f.read()
    zip_b64 = base64.b64encode(zip_content).decode('utf-8')

    # 4. 上传到Gist
    data = {
        "description": f"Tabby Config Backup {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "files": {
            GIST_FILENAME: {
                "content": zip_b64,
                "encoding": "base64"
            }
        }
    }

    response = requests.patch(f"{GITHUB_API}/gists/{gist_id}", headers=headers, json=data)
    if response.status_code == 200:
        print("配置上传成功!")

        # 更新哈希值
        if "hashes" not in gist_config:
            gist_config["hashes"] = {}

        for item in changed_items:
            item_path = CONFIG_DIR / item
            gist_config["hashes"][item] = get_item_hash(item_path)

        save_gist_config(gist_config)

        # 删除临时ZIP
        os.remove(zip_path)
        return response.json()

    # 添加上传失败时的详细错误信息
    error_msg = f"上传失败 ({response.status_code}): "
    try:
        error_details = response.json()
        error_msg += error_details.get("message", "未知错误")
        if "errors" in error_details:
            error_msg += "\n" + "\n".join([e.get("message", "") for e in error_details["errors"]])
    except:
        error_msg += response.text[:200]  # 只取前200字符避免太长

    raise Exception(error_msg)


def download_config(token, gist_id):
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}

    # 1. 获取Gist元数据
    response = requests.get(f"{GITHUB_API}/gists/{gist_id}", headers=headers)
    if response.status_code != 200:
        # 检查API错误
        error_msg = f"下载失败 ({response.status_code}): "
        try:
            error_details = response.json()
            error_msg += error_details.get("message", "未知错误")
        except:
            error_msg += response.text[:200]
        raise Exception(error_msg)

    gist_data = response.json()
    file_info = gist_data["files"].get(GIST_FILENAME)

    if not file_info:
        # 保存完整响应用于调试
        debug_path = CONFIG_DIR / "gist_response.json"
        with open(debug_path, 'w') as f:
            json.dump(gist_data, f, indent=2)
        raise Exception(f"文件 {GIST_FILENAME} 在 Gist 中未找到\n完整响应已保存到: {debug_path}")

    # 2. 获取ZIP内容（添加详细错误处理）
    try:
        if file_info.get("encoding") == "base64":
            zip_content = base64.b64decode(file_info["content"])
        else:
            zip_url = file_info["raw_url"]
            zip_response = requests.get(zip_url)
            if zip_response.status_code != 200:
                raise Exception(f"下载ZIP失败: {zip_response.status_code} - {zip_response.text[:100]}")
            zip_content = zip_response.content

        # 3. 验证ZIP文件头
        if len(zip_content) < 4 or zip_content[:4] != b'PK\x03\x04':
            # 保存原始内容用于调试
            debug_path = CONFIG_DIR / "invalid_zip_content.bin"
            with open(debug_path, 'wb') as f:
                f.write(zip_content)
            raise Exception(f"下载内容不是有效的ZIP文件 (开头字节: {zip_content[:4]}). 已保存到 {debug_path}")
    except Exception as e:
        # 保存API响应用于调试
        debug_path = CONFIG_DIR / "gist_response.json"
        with open(debug_path, 'w') as f:
            json.dump(gist_data, f, indent=2)
        raise Exception(f"处理Gist内容失败: {str(e)}\nGist响应已保存到 {debug_path}")

    # 4. 提取ZIP内容
    try:
        extract_zip_archive(zip_content)
    except zipfile.BadZipfile:
        # 保存损坏的ZIP文件用于调试
        debug_path = CONFIG_DIR / "corrupted_zip.zip"
        with open(debug_path, 'wb') as f:
            f.write(zip_content)
        raise Exception(f"ZIP文件损坏。已保存到 {debug_path} 用于分析")

    # 5. 更新哈希值
    gist_config = load_gist_config()
    if "hashes" not in gist_config:
        gist_config["hashes"] = {}

    for item in SYNC_ITEMS:
        item_path = CONFIG_DIR / item
        gist_config["hashes"][item] = get_item_hash(item_path)

    save_gist_config(gist_config)

    print("配置下载成功!")
    return True


def get_gist_updated_time(token, gist_id):
    """获取Gist的最后更新时间"""
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    response = requests.get(f"{GITHUB_API}/gists/{gist_id}", headers=headers)
    if response.status_code == 200:
        return response.json()["updated_at"]
    return ""


def main():
    parser = argparse.ArgumentParser(description="通过 GitHub Gist 同步 Tabby 配置")
    parser.add_argument("action", choices=["init", "push", "pull"], help="同步操作")
    parser.add_argument("--token", help="GitHub 个人访问令牌")
    args = parser.parse_args()

    # 确保配置目录存在
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    gist_config = load_gist_config()
    token = args.token or gist_config.get("token", "")

    if not token:
        print("错误: 需要 GitHub token。使用 --token 或先运行 'init'")
        return

    if args.action == "init":
        if not token:
            print("请通过 --token 提供 token")
            return

        gist = get_gist(token)
        gist_id = gist["id"]
        gist_config = {
            "token": token,
            "gist_id": gist_id,
            "hashes": {}
        }
        save_gist_config(gist_config)

        # 上传初始配置
        upload_config(token, gist_id)
        print(f"同步已初始化! Gist ID: {gist_id}")
        print(f"Gist URL: {gist['html_url']}")
        return

    gist_id = gist_config.get("gist_id", "")
    if not gist_id:
        print("未找到 Gist ID。请先运行 'init'")
        return

    # 对于 pull 操作，检查是否需要更新
    if args.action == "pull":
        remote_updated = get_gist_updated_time(token, gist_id)
        local_updated = gist_config.get("last_pull", "")

        if remote_updated and local_updated and remote_updated <= local_updated:
            print("远程配置未变更，跳过下载")
            return

    try:
        if args.action == "push":
            upload_config(token, gist_id)
        elif args.action == "pull":
            download_config(token, gist_id)
            # 更新最后拉取时间
            gist_config = load_gist_config()  # 重新加载，避免竞争条件
            gist_config["last_pull"] = datetime.now().isoformat()
            save_gist_config(gist_config)
            print("请重启 Tabby 以应用更改")

            # 可选：自动重启 Tabby
            print("是否立即重启 Tabby? [y/N]")
            if input().lower() == "y":
                if sys.platform == "win32":
                    os.system("taskkill /f /im tabby.exe >nul 2>&1")
                    os.system("start tabby")
                elif sys.platform == "darwin":
                    os.system("pkill -f Tabby")
                    os.system("open -a Tabby")
                else:  # Linux
                    os.system("pkill -f tabby")
                    os.system("tabby &")
    except Exception as e:
        print(f"错误: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"错误: {str(e)}")
        sys.exit(1)