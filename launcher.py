#!/usr/bin/env python3
"""
Tabby Auto-Sync 启动器
简化的单文件启动器，包含所有必要功能
"""

import sys
import os
import logging
import argparse
import configparser
import time
import json
import psutil
import yaml
import shutil
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
from enum import Enum
import urllib.request
import urllib.parse
import urllib.error

# 尝试导入requests作为备用
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# SSL处理 - 使用urllib避免requests的SSL问题
try:
    import ssl
    # 创建不验证SSL的上下文
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    SSL_CONTEXT = ssl_context
    HTTPS_AVAILABLE = True
except ImportError:
    SSL_CONTEXT = None
    HTTPS_AVAILABLE = False

# 如果HTTPS不可用，安装HTTPS处理器
if not HTTPS_AVAILABLE:
    try:
        import urllib.request
        import urllib.parse
        # 尝试创建一个基本的HTTPS处理器
        https_handler = urllib.request.HTTPSHandler()
        opener = urllib.request.build_opener(https_handler)
        urllib.request.install_opener(opener)
        HTTPS_AVAILABLE = True
    except:
        pass


class SyncResult(Enum):
    """同步结果枚举"""
    SUCCESS = "success"
    NO_CHANGES = "no_changes"
    CONFLICT_RESOLVED = "conflict_resolved"
    ERROR = "error"
    CANCELLED = "cancelled"


class ConflictStrategy(Enum):
    """冲突解决策略"""
    NEWEST = "newest"
    OLDEST = "oldest"
    LOCAL = "local"
    CLOUD = "cloud"
    MERGE = "merge"
    MANUAL = "manual"


class TabbyAutoSyncLauncher:
    """Tabby 自动同步启动器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.config = configparser.ConfigParser()
        self.config_file = "config.ini"
        self.is_running = False
        
        # 初始化
        self.setup_logging()
        self.load_config()
        self.create_directories()
        
        # 配置路径
        self.tabby_config_path = self.detect_tabby_config()
        self.backup_dir = Path("backups")
        
        # GitHub Gist 配置
        self.github_token = self.config.get('cloud_storage', 'github_token', fallback='')
        self.gist_id = self.config.get('cloud_storage', 'gist_id', fallback='')
        
        # 冲突解决策略
        strategy_name = self.config.get('sync', 'conflict_strategy', fallback='newest')
        self.conflict_strategy = getattr(ConflictStrategy, strategy_name.upper(), ConflictStrategy.NEWEST)

        # 配置文件变化监控
        self.last_config_mtime = None
        self.config_changed_since_start = False
        self._init_config_monitoring()
    
    def setup_logging(self):
        """设置日志"""
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/tabby_sync.log', encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
    
    def load_config(self):
        """加载配置"""
        try:
            if Path(self.config_file).exists():
                self.config.read(self.config_file, encoding='utf-8')
            else:
                self.create_default_config()
        except Exception as e:
            self.logger.error(f"加载配置失败: {e}")
    
    def create_default_config(self):
        """创建默认配置"""
        self.config['cloud_storage'] = {
            'storage_type': 'github_gist',
            'github_token': '',
            'gist_id': ''
        }
        self.config['sync'] = {
            'auto_sync': 'true',
            'conflict_strategy': 'newest',
            'create_backup': 'true',
            'max_backups': '10'
        }
        self.config['monitoring'] = {
            'monitor_interval': '5'
        }
        self.config['logging'] = {
            'log_level': 'INFO',
            'log_file': './logs/tabby_sync.log'
        }
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            self.config.write(f)
        
        self.logger.info("创建默认配置文件")
    
    def create_directories(self):
        """创建必要目录"""
        Path("logs").mkdir(exist_ok=True)
        Path("backups").mkdir(exist_ok=True)

    def _init_config_monitoring(self):
        """初始化配置文件监控"""
        if self.tabby_config_path and self.tabby_config_path.exists():
            self.last_config_mtime = self.tabby_config_path.stat().st_mtime
            self.logger.debug(f"初始化配置文件监控，当前修改时间: {self.last_config_mtime}")
        else:
            self.last_config_mtime = None

    def _check_config_changes(self):
        """检查配置文件是否有变化"""
        if not self.tabby_config_path or not self.tabby_config_path.exists():
            return False

        try:
            current_mtime = self.tabby_config_path.stat().st_mtime
            if self.last_config_mtime is None:
                self.last_config_mtime = current_mtime
                return False

            if current_mtime != self.last_config_mtime:
                self.logger.info(f"检测到配置文件变化: {self.tabby_config_path}")
                self.last_config_mtime = current_mtime
                self.config_changed_since_start = True
                return True

            return False
        except Exception as e:
            self.logger.error(f"检查配置文件变化时出错: {e}")
            return False

    def _reset_change_tracking(self):
        """重置变化跟踪状态"""
        self.config_changed_since_start = False
        if self.tabby_config_path and self.tabby_config_path.exists():
            self.last_config_mtime = self.tabby_config_path.stat().st_mtime
    
    def detect_tabby_config(self) -> Optional[Path]:
        """检测 Tabby 配置文件"""
        appdata = os.environ.get('APPDATA')
        if not appdata:
            return None
        
        config_path = Path(appdata) / "Tabby" / "config.yaml"
        if config_path.exists():
            self.logger.info(f"找到 Tabby 配置: {config_path}")
            return config_path
        else:
            self.logger.warning(f"Tabby 配置不存在: {config_path}")
            return config_path
    
    def create_backup(self, source_path: Path) -> Optional[Path]:
        """创建备份"""
        try:
            if not source_path.exists():
                return None
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"config_backup_{timestamp}.yaml"
            backup_path = self.backup_dir / backup_filename
            
            shutil.copy2(source_path, backup_path)
            self.logger.info(f"创建备份: {backup_path}")
            
            # 清理旧备份
            self.cleanup_old_backups()
            return backup_path
        except Exception as e:
            self.logger.error(f"创建备份失败: {e}")
            return None
    
    def cleanup_old_backups(self):
        """清理旧备份"""
        try:
            max_backups = int(self.config.get('sync', 'max_backups', fallback='10'))
            backup_files = list(self.backup_dir.glob("config_backup_*.yaml"))
            backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            for old_backup in backup_files[max_backups:]:
                old_backup.unlink()
                self.logger.debug(f"删除旧备份: {old_backup}")
        except Exception as e:
            self.logger.error(f"清理备份失败: {e}")

    def list_backups(self):
        """列出所有备份文件"""
        backup_files = sorted(self.backup_dir.glob("config_backup_*.yaml"),
                             key=lambda x: x.stat().st_mtime, reverse=True)
        return backup_files

    def show_backups_menu(self):
        """显示备份恢复菜单"""
        backup_files = self.list_backups()

        if not backup_files:
            print("❌ 没有找到备份文件")
            input("按回车键继续...")
            return

        print("\n📁 可用备份列表：")
        print("-" * 60)

        for i, backup in enumerate(backup_files[:15], 1):  # 显示最近15个
            mtime = datetime.fromtimestamp(backup.stat().st_mtime)
            size = backup.stat().st_size
            print(f"{i:2d}. {backup.name}")
            print(f"    时间: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"    大小: {size} 字节")
            print()

        print("0. 返回主菜单")
        print("-" * 60)

        try:
            choice = input("请选择要恢复的备份 (输入序号): ").strip()

            if choice == "0":
                return

            choice_num = int(choice)
            if 1 <= choice_num <= len(backup_files):
                selected_backup = backup_files[choice_num - 1]
                self.restore_from_backup(selected_backup)
            else:
                print("❌ 无效选择")
                input("按回车键继续...")
        except ValueError:
            print("❌ 请输入有效数字")
            input("按回车键继续...")

    def restore_from_backup(self, backup_path: Path):
        """从备份恢复配置"""
        try:
            if not backup_path.exists():
                print(f"❌ 备份文件不存在: {backup_path}")
                return False

            if not self.tabby_config_path:
                print("❌ Tabby配置路径未找到")
                return False

            # 确认操作
            print(f"\n⚠️  即将恢复备份: {backup_path.name}")
            print(f"目标位置: {self.tabby_config_path}")
            confirm = input("确认恢复？这将覆盖当前配置 (y/N): ").strip().lower()

            if confirm != 'y':
                print("❌ 操作已取消")
                return False

            # 先备份当前配置（以防万一）
            current_backup = self.create_backup(self.tabby_config_path)
            if current_backup:
                print(f"✅ 已备份当前配置到: {current_backup.name}")

            # 恢复备份
            shutil.copy2(backup_path, self.tabby_config_path)

            print(f"✅ 成功恢复备份: {backup_path.name}")
            print(f"✅ 配置已恢复到: {self.tabby_config_path}")

            # 验证恢复的配置
            if self.validate_config():
                print("✅ 配置文件验证通过")
            else:
                print("⚠️  配置文件可能有问题，请检查")

            input("\n按回车键继续...")
            return True

        except Exception as e:
            print(f"❌ 恢复失败: {e}")
            input("按回车键继续...")
            return False

    def validate_config(self):
        """验证配置文件是否有效"""
        try:
            if not self.tabby_config_path or not self.tabby_config_path.exists():
                return False

            # 尝试解析YAML
            with open(self.tabby_config_path, 'r', encoding='utf-8') as f:
                yaml.safe_load(f.read())

            return True
        except Exception as e:
            self.logger.error(f"配置验证失败: {e}")
            return False

    def upload_to_gist(self, config_content: str) -> bool:
        """上传到 GitHub Gist"""
        try:
            if not self.github_token:
                self.logger.error("GitHub token 未设置")
                return False

            # 尝试多种上传方式
            # 1. 首先尝试系统HTTP（最可靠）
            if self._upload_with_system_http(config_content):
                return True

            # 2. 如果系统HTTP失败，尝试requests
            if REQUESTS_AVAILABLE:
                if self._upload_with_requests(config_content):
                    return True

            # 3. 最后尝试urllib
            if self._upload_with_urllib_original(config_content):
                return True

            # 4. 所有方法都失败，启用本地备份
            self._create_local_backup(config_content, "fallback")
            return False  # 返回False表示网络上传失败

        except Exception as e:
            self.logger.error(f"上传到 Gist 失败: {e}")
            return False

    def _upload_with_requests(self, config_content: str) -> bool:
        """使用requests上传"""
        try:
            headers = {'Authorization': f'token {self.github_token}'}

            if self.gist_id:
                # 更新现有 Gist
                data = {
                    "files": {
                        "tabby_config.yaml": {
                            "content": config_content
                        }
                    }
                }
                response = requests.patch(
                    f"https://api.github.com/gists/{self.gist_id}",
                    headers=headers,
                    json=data,
                    timeout=30,
                    verify=False
                )
            else:
                # 创建新 Gist
                data = {
                    "description": "Tabby Terminal Configuration",
                    "public": False,
                    "files": {
                        "tabby_config.yaml": {
                            "content": config_content
                        }
                    }
                }
                response = requests.post(
                    "https://api.github.com/gists",
                    headers=headers,
                    json=data,
                    timeout=30,
                    verify=False
                )

                if response.status_code == 201:
                    self.gist_id = response.json()['id']
                    self.config.set('cloud_storage', 'gist_id', self.gist_id)
                    with open(self.config_file, 'w', encoding='utf-8') as f:
                        self.config.write(f)
                    self.logger.info(f"创建新 Gist: {self.gist_id}")

            if response.status_code in [200, 201]:
                self.logger.info("成功上传到 GitHub Gist (使用requests)")
                return True
            else:
                self.logger.error(f"上传失败: {response.status_code}")
                return False

        except Exception as e:
            self.logger.error(f"requests上传失败: {e}")
            return False

    def _create_local_backup(self, config_content: str, backup_type: str = "fallback") -> bool:
        """创建本地备份"""
        try:
            backup_dir = Path("backups")
            backup_dir.mkdir(exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            if backup_type == "fallback":
                # 网络失败时的替代备份
                backup_file = backup_dir / f"fallback_backup_{timestamp}.yaml"
                self.logger.info("=" * 50)
                self.logger.info("🔄 网络同步失败，创建本地备份")
                self.logger.info("💡 您可以手动将此文件复制到其他设备实现同步")
                self.logger.info("=" * 50)
            else:
                # 常规备份
                backup_file = backup_dir / f"config_backup_{timestamp}.yaml"

            with open(backup_file, 'w', encoding='utf-8') as f:
                f.write(config_content)

            self.logger.info(f"📁 配置已保存到: {backup_file}")

            # 清理旧备份
            self._cleanup_old_backups_in_dir(backup_dir)

            return True

        except Exception as e:
            self.logger.error(f"创建本地备份失败: {e}")
            return False

    def _cleanup_old_backups_in_dir(self, backup_dir: Path):
        """清理指定目录中的旧备份"""
        try:
            max_backups = int(self.config.get('sync', 'max_backups', fallback='10'))
            backup_files = sorted(backup_dir.glob("*_backup_*.yaml"))

            while len(backup_files) > max_backups:
                old_backup = backup_files.pop(0)
                old_backup.unlink()
                self.logger.debug(f"删除旧备份: {old_backup}")

        except Exception as e:
            self.logger.error(f"清理备份失败: {e}")

    def _upload_with_urllib(self, config_content: str) -> bool:
        """使用urllib上传（已弃用，重定向到系统HTTP）"""
        return self._upload_with_system_http(config_content)

    def _upload_with_system_http(self, config_content: str) -> bool:
        """使用系统级HTTP客户端上传（绕过Python SSL问题）"""
        self.logger.info("🔄 尝试使用系统HTTP客户端上传...")
        try:
            import subprocess
            import tempfile

            # 准备数据
            if self.gist_id:
                # 更新现有 Gist
                url = f"https://api.github.com/gists/{self.gist_id}"
                method = "PATCH"
                data = {
                    "files": {
                        "tabby_config.yaml": {
                            "content": config_content
                        }
                    }
                }
            else:
                # 创建新 Gist
                url = "https://api.github.com/gists"
                method = "POST"
                data = {
                    "description": "Tabby Terminal Configuration",
                    "public": False,
                    "files": {
                        "tabby_config.yaml": {
                            "content": config_content
                        }
                    }
                }

            # 将JSON数据写入临时文件
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                json_file = f.name

            try:
                # 使用PowerShell的Invoke-WebRequest
                ps_script = f'''
$headers = @{{
    "Authorization" = "token {self.github_token}"
    "Content-Type" = "application/json"
    "User-Agent" = "TabbyAutoSync/1.0"
}}

$body = Get-Content -Path "{json_file}" -Raw -Encoding UTF8

try {{
    if ("{method}" -eq "PATCH") {{
        $response = Invoke-WebRequest -Uri "{url}" -Method PATCH -Headers $headers -Body $body -UseBasicParsing
    }} else {{
        $response = Invoke-WebRequest -Uri "{url}" -Method POST -Headers $headers -Body $body -UseBasicParsing
    }}

    Write-Output "STATUS:$($response.StatusCode)"
    Write-Output "CONTENT:$($response.Content)"
}} catch {{
    Write-Output "ERROR:$($_.Exception.Message)"
    exit 1
}}
'''

                # 执行PowerShell脚本
                result = subprocess.run(
                    ["powershell", "-Command", ps_script],
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                if result.returncode == 0:
                    output = result.stdout.strip()
                    lines = output.split('\n')

                    status_code = None
                    content = None

                    for line in lines:
                        if line.startswith("STATUS:"):
                            status_code = int(line.split(":", 1)[1])
                        elif line.startswith("CONTENT:"):
                            content = line.split(":", 1)[1]

                    if status_code in [200, 201]:
                        self.logger.info("成功上传到 GitHub Gist (使用系统HTTP)")

                        # 如果是新创建的Gist，保存ID
                        if status_code == 201 and not self.gist_id and content:
                            try:
                                response_data = json.loads(content)
                                self.gist_id = response_data['id']
                                self.config.set('cloud_storage', 'gist_id', self.gist_id)
                                with open(self.config_file, 'w', encoding='utf-8') as f:
                                    self.config.write(f)
                                self.logger.info(f"创建新 Gist: {self.gist_id}")
                            except:
                                pass

                        return True
                    else:
                        self.logger.error(f"上传失败: HTTP {status_code}")
                        return False
                else:
                    error_msg = result.stderr.strip() if result.stderr else "未知错误"
                    self.logger.error(f"PowerShell执行失败: {error_msg}")
                    return False

            finally:
                # 清理临时文件
                try:
                    os.unlink(json_file)
                except:
                    pass

        except Exception as e:
            self.logger.error(f"系统HTTP上传失败: {e}")
            return False

    def _upload_with_urllib_original(self, config_content: str) -> bool:
        """原始的urllib上传方法"""
        try:

            if self.gist_id:
                # 更新现有 Gist
                url = f"https://api.github.com/gists/{self.gist_id}"
                method = "PATCH"
                data = {
                    "files": {
                        "tabby_config.yaml": {
                            "content": config_content
                        }
                    }
                }
            else:
                # 创建新 Gist
                url = "https://api.github.com/gists"
                method = "POST"
                data = {
                    "description": "Tabby Terminal Configuration",
                    "public": False,
                    "files": {
                        "tabby_config.yaml": {
                            "content": config_content
                        }
                    }
                }

            # 使用urllib发送请求
            json_data = json.dumps(data).encode('utf-8')
            req = urllib.request.Request(
                url,
                data=json_data,
                headers={
                    'Authorization': f'token {self.github_token}',
                    'Content-Type': 'application/json',
                    'User-Agent': 'TabbyAutoSync/1.0'
                },
                method=method
            )

            # 发送请求
            try:
                if SSL_CONTEXT:
                    response = urllib.request.urlopen(req, context=SSL_CONTEXT, timeout=30)
                else:
                    response = urllib.request.urlopen(req, timeout=30)
            except urllib.error.URLError as e:
                if "unknown url type: https" in str(e):
                    self.logger.error("HTTPS协议不支持，这通常是SSL模块缺失导致的")
                    self.logger.error("=" * 50)
                    self.logger.error("解决方案：")
                    self.logger.error("1. 使用源码版本：python launcher.py")
                    self.logger.error("2. 或下载完整Python环境版本")
                    self.logger.error("3. 源码版本功能完全正常，推荐使用")
                    self.logger.error("=" * 50)
                    return False
                else:
                    raise

            response_data = response.read().decode('utf-8')
            status_code = response.getcode()

            if status_code == 201 and not self.gist_id:
                # 新创建的Gist，保存ID
                response_json = json.loads(response_data)
                self.gist_id = response_json['id']
                self.config.set('cloud_storage', 'gist_id', self.gist_id)
                with open(self.config_file, 'w', encoding='utf-8') as f:
                    self.config.write(f)
                self.logger.info(f"创建新 Gist: {self.gist_id}")

            if status_code in [200, 201]:
                self.logger.info("成功上传到 GitHub Gist")
                return True
            else:
                self.logger.error(f"上传失败: {status_code}")
                return False

        except Exception as e:
            self.logger.error(f"上传到 Gist 失败: {e}")
            return False
    
    def download_from_gist(self) -> Optional[str]:
        """从 GitHub Gist 下载"""
        try:
            if not self.github_token or not self.gist_id:
                return None

            # 优先尝试系统HTTP客户端
            return self._download_with_system_http()

        except Exception as e:
            self.logger.error(f"从 Gist 下载失败: {e}")
            return None

    def _download_with_system_http(self) -> Optional[str]:
        """使用系统级HTTP客户端下载"""
        try:
            import subprocess

            url = f"https://api.github.com/gists/{self.gist_id}"

            # 使用PowerShell的Invoke-WebRequest
            ps_script = f'''
$headers = @{{
    "Authorization" = "token {self.github_token}"
    "User-Agent" = "TabbyAutoSync/1.0"
}}

try {{
    $response = Invoke-WebRequest -Uri "{url}" -Headers $headers -UseBasicParsing
    Write-Output "STATUS:$($response.StatusCode)"
    Write-Output "CONTENT:$($response.Content)"
}} catch {{
    Write-Output "ERROR:$($_.Exception.Message)"
    exit 1
}}
'''

            # 执行PowerShell脚本
            result = subprocess.run(
                ["powershell", "-Command", ps_script],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                output = result.stdout.strip()
                lines = output.split('\n')

                status_code = None
                content = None

                for line in lines:
                    if line.startswith("STATUS:"):
                        status_code = int(line.split(":", 1)[1])
                    elif line.startswith("CONTENT:"):
                        content = line.split(":", 1)[1]

                if status_code == 200 and content:
                    try:
                        gist_data = json.loads(content)
                        files = gist_data.get('files', {})

                        if 'tabby_config.yaml' not in files:
                            self.logger.error("Gist 中未找到配置文件")
                            return None

                        config_content = files['tabby_config.yaml']['content']
                        self.logger.info("成功从 GitHub Gist 下载 (使用系统HTTP)")
                        return config_content

                    except json.JSONDecodeError as e:
                        self.logger.error(f"解析响应失败: {e}")
                        return None
                else:
                    self.logger.error(f"下载失败: HTTP {status_code}")
                    return None
            else:
                error_msg = result.stderr.strip() if result.stderr else "未知错误"
                self.logger.error(f"PowerShell执行失败: {error_msg}")
                return None

        except Exception as e:
            self.logger.error(f"系统HTTP下载失败: {e}")
            return None

    def _download_with_urllib_original(self) -> Optional[str]:
        """原始的urllib下载方法"""
        try:
            
            url = f"https://api.github.com/gists/{self.gist_id}"
            req = urllib.request.Request(
                url,
                headers={
                    'Authorization': f'token {self.github_token}',
                    'User-Agent': 'TabbyAutoSync/1.0'
                }
            )

            # 发送请求
            try:
                if SSL_CONTEXT:
                    response = urllib.request.urlopen(req, context=SSL_CONTEXT, timeout=30)
                else:
                    response = urllib.request.urlopen(req, timeout=30)
            except urllib.error.URLError as e:
                if "unknown url type: https" in str(e):
                    self.logger.error("HTTPS协议不支持，这通常是SSL模块缺失导致的")
                    return None
                else:
                    raise
            
            if response.getcode() != 200:
                self.logger.error(f"获取 Gist 失败: {response.getcode()}")
                return None

            response_data = response.read().decode('utf-8')
            gist_data = json.loads(response_data)
            files = gist_data.get('files', {})
            
            if 'tabby_config.yaml' not in files:
                self.logger.error("Gist 中未找到配置文件")
                return None
            
            content = files['tabby_config.yaml']['content']
            self.logger.info("成功从 GitHub Gist 下载")
            return content
            
        except Exception as e:
            self.logger.error(f"从 Gist 下载失败: {e}")
            return None
    
    def sync_from_cloud(self) -> Tuple[SyncResult, str]:
        """从云端同步"""
        try:
            if not self.tabby_config_path:
                return SyncResult.ERROR, "Tabby 配置路径未找到"

            cloud_content = self.download_from_gist()
            if not cloud_content:
                return SyncResult.NO_CHANGES, "云端配置不存在"

            # 创建备份
            backup_path = None
            if self.tabby_config_path.exists():
                backup_path = self.create_backup(self.tabby_config_path)

            # 写入配置
            self.tabby_config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.tabby_config_path, 'w', encoding='utf-8') as f:
                f.write(cloud_content)

            # 验证新配置
            if not self.validate_config():
                print("\n⚠️  警告：检测到配置可能有问题！")
                if backup_path:
                    print(f"备份文件：{backup_path.name}")
                    rollback = input("是否回滚到备份配置？(y/N): ").strip().lower()
                    if rollback == 'y':
                        shutil.copy2(backup_path, self.tabby_config_path)
                        return SyncResult.SUCCESS, "已回滚到备份配置"

            return SyncResult.SUCCESS, "成功从云端同步配置"

        except Exception as e:
            return SyncResult.ERROR, f"同步失败: {str(e)}"
    
    def sync_to_cloud(self, force: bool = False) -> Tuple[SyncResult, str]:
        """同步到云端"""
        try:
            if not self.tabby_config_path or not self.tabby_config_path.exists():
                return SyncResult.NO_CHANGES, "本地配置文件不存在"

            with open(self.tabby_config_path, 'r', encoding='utf-8') as f:
                content = f.read()

            upload_result = self.upload_to_gist(content)

            if upload_result:
                # 真正的网络上传成功
                self._reset_change_tracking()
                return SyncResult.SUCCESS, "成功上传配置到云端"
            else:
                # 上传失败，检查是否创建了离线备份
                backup_dir = Path("backups")
                if backup_dir.exists():
                    fallback_files = sorted(backup_dir.glob("fallback_backup_*.yaml"),
                                          key=lambda x: x.stat().st_mtime, reverse=True)
                    if fallback_files and (time.time() - fallback_files[0].stat().st_mtime) < 10:  # 10秒内创建的
                        return SyncResult.SUCCESS, "网络不可用，已保存到本地备份"

                return SyncResult.ERROR, "上传失败"

        except Exception as e:
            return SyncResult.ERROR, f"上传失败: {str(e)}"
    
    def is_tabby_running(self) -> bool:
        """检查 Tabby 是否运行"""
        try:
            for proc in psutil.process_iter(['name']):
                if proc.info['name'] and proc.info['name'].lower() == 'tabby.exe':
                    return True
            return False
        except Exception:
            return False
    
    def monitor_tabby(self):
        """监控 Tabby 进程"""
        self.logger.info("开始监控 Tabby 进程...")
        self.is_running = True

        was_running = self.is_tabby_running()
        # 重置变化跟踪状态
        self._reset_change_tracking()

        try:
            while self.is_running:
                is_running = self.is_tabby_running()

                if is_running and not was_running:
                    # Tabby 启动
                    self.logger.info("检测到 Tabby 启动")
                    result, message = self.sync_from_cloud()
                    print(f"📥 启动同步: {message}")
                    # 启动后重置变化跟踪
                    self._reset_change_tracking()

                elif not is_running and was_running:
                    # Tabby 关闭
                    self.logger.info("检测到 Tabby 关闭")

                    # 在关闭时检查配置是否有变化
                    has_changes = self._check_config_changes()

                    if has_changes or self.config_changed_since_start:
                        print("🔄 检测到配置文件有变化")
                        result, message = self.sync_to_cloud()
                        print(f"📤 关闭同步: {message}")
                    else:
                        print("📝 配置文件无变化，跳过上传")
                        self.logger.info("配置文件无变化，跳过云端同步")

                was_running = is_running
                time.sleep(5)  # 5秒检查一次

        except KeyboardInterrupt:
            self.logger.info("用户停止监控")
        finally:
            self.is_running = False
    
    def show_status(self):
        """显示状态"""
        print("=== Tabby Auto-Sync 状态 ===")
        
        # Tabby 配置
        if self.tabby_config_path and self.tabby_config_path.exists():
            print(f"✅ Tabby 配置: {self.tabby_config_path}")
        else:
            print("❌ Tabby 配置: 未找到")
        
        # GitHub 配置
        if self.github_token:
            print("✅ GitHub Token: 已配置")
            if self.gist_id:
                print(f"✅ Gist ID: {self.gist_id}")
            else:
                print("⚠️  Gist ID: 未创建（首次上传时自动创建）")
        else:
            print("❌ GitHub Token: 未配置")
        
        # Tabby 进程
        if self.is_tabby_running():
            print("✅ Tabby 进程: 运行中")
        else:
            print("❌ Tabby 进程: 未运行")
        
        # 监控状态
        if self.is_running:
            print("✅ 进程监控: 监控中")
        else:
            print("❌ 进程监控: 未监控")
    
    def show_menu(self):
        """显示菜单"""
        while True:
            print("\n" + "="*50)
            print("    Tabby Auto-Sync 配置同步工具")
            print("="*50)
            print()
            print("请选择操作：")
            print()
            print("1. 🚀 开始监控 Tabby（推荐）")
            print("2. 📊 查看状态")
            print("3. ⬇️  从云端同步配置")
            print("4. ⬆️  上传配置到云端")
            print("5. ⚙️  配置设置")
            print("6. 🔄 恢复备份")
            print("7. ❌ 退出")
            print()

            choice = input("请输入选择 (1-7): ").strip()
            
            if choice == "1":
                print("\n🚀 启动监控模式...")
                print("程序将监控 Tabby 进程，按 Ctrl+C 停止")
                print()
                self.monitor_tabby()
            elif choice == "2":
                print()
                self.show_status()
                input("\n按回车键继续...")
            elif choice == "3":
                print("\n⬇️ 从云端同步配置...")
                result, message = self.sync_from_cloud()
                if result == SyncResult.SUCCESS:
                    print(f"✅ {message}")
                else:
                    print(f"⚠️ {message}")
                input("\n按回车键继续...")
            elif choice == "4":
                print("\n⬆️ 上传配置到云端...")
                result, message = self.sync_to_cloud(force=True)  # 手动上传时强制执行
                if result == SyncResult.SUCCESS:
                    print(f"✅ {message}")
                else:
                    print(f"⚠️ {message}")
                input("\n按回车键继续...")
            elif choice == "5":
                print("\n⚙️ 配置设置")
                print("请编辑 config.ini 文件来修改设置")
                print("主要配置项：")
                print("  - github_token: GitHub 访问令牌")
                print("  - conflict_strategy: 冲突解决策略")
                print()
                print("获取 GitHub Token: https://github.com/settings/tokens")
                input("\n按回车键继续...")
            elif choice == "6":
                self.show_backups_menu()
            elif choice == "7":
                print("\n👋 感谢使用 Tabby Auto-Sync！")
                break
            else:
                print("\n❌ 无效选择，请重新输入")
                input("按回车键继续...")


def main():
    """主函数"""
    try:
        launcher = TabbyAutoSyncLauncher()
        
        # 检查命令行参数
        if len(sys.argv) > 1:
            command = sys.argv[1]
            if command == "status":
                launcher.show_status()
            elif command == "sync-from-cloud":
                result, message = launcher.sync_from_cloud()
                print(f"同步结果: {message}")
            elif command == "sync-to-cloud":
                result, message = launcher.sync_to_cloud(force=True)  # 命令行调用时强制执行
                print(f"上传结果: {message}")
            elif command == "monitor":
                launcher.monitor_tabby()
            elif command == "list-backups":
                backups = launcher.list_backups()
                if backups:
                    print("可用备份：")
                    for backup in backups[:10]:
                        mtime = datetime.fromtimestamp(backup.stat().st_mtime)
                        print(f"  {backup.name} ({mtime.strftime('%Y-%m-%d %H:%M:%S')})")
                else:
                    print("没有找到备份文件")
            elif command == "restore-latest":
                backups = launcher.list_backups()
                if backups:
                    launcher.restore_from_backup(backups[0])
                else:
                    print("没有找到备份文件")
            else:
                print("未知命令，启动图形界面...")
                launcher.show_menu()
        else:
            # 默认显示菜单
            launcher.show_menu()
            
    except KeyboardInterrupt:
        print("\n程序已退出")
    except Exception as e:
        print(f"程序出错: {e}")
        input("按回车键退出...")


if __name__ == "__main__":
    main()
