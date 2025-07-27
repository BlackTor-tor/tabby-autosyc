import os
import sys
import json
import time
import yaml
import hashlib
import requests
import platform
import shutil
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler
import argparse
try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False

# 设置日志记录
def setup_logger(config_dir=None):
    """设置日志记录器，将日志保存到Tabby安装目录"""
    logger = logging.getLogger('TabbySync')
    logger.setLevel(logging.INFO)
    
    # 清除现有的处理器
    if logger.handlers:
        for handler in logger.handlers:
            logger.removeHandler(handler)
    
    # 创建格式化器
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # 添加控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 确定日志文件位置
    if config_dir:
        log_dir = config_dir
    else:
        # 使用脚本所在目录
        log_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 创建日志目录
    os.makedirs(os.path.join(log_dir, 'logs'), exist_ok=True)
    
    # 添加文件处理器（使用RotatingFileHandler限制日志文件大小）
    log_file = os.path.join(log_dir, 'logs', 'tabby_sync.log')
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5*1024*1024,  # 5MB
        backupCount=3,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger

# 初始化日志记录器（稍后会在TabbyConfigSync类中更新）
logger = setup_logger()

class TabbyConfigSync:
    def __init__(self, gist_id, github_token, config_dir=None, show_progress=True):
        """
        初始化TabbyConfigSync类
        
        Args:
            gist_id (str): GitHub Gist的ID
            github_token (str): GitHub个人访问令牌
            config_dir (str, optional): Tabby配置文件目录，如果为None则使用默认位置
            show_progress (bool, optional): 是否显示进度条，默认为True
        """
        self.gist_id = gist_id
        self.github_token = github_token
        self.headers = {
            'Authorization': f'token {github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        self.show_progress = show_progress and TQDM_AVAILABLE
        
        # 确定Tabby配置文件的位置
        if config_dir:
            self.config_dir = config_dir
        else:
            # Windows默认位置: %APPDATA%/Tabby
            if platform.system() == 'Windows':
                self.config_dir = os.path.join(os.environ.get('APPDATA'), 'Tabby')
            # macOS默认位置: ~/Library/Application Support/Tabby
            elif platform.system() == 'Darwin':
                self.config_dir = os.path.join(os.path.expanduser('~'), 'Library', 'Application Support', 'Tabby')
            # Linux默认位置: ~/.config/tabby
            else:
                self.config_dir = os.path.join(os.path.expanduser('~'), '.config', 'tabby')
        
        self.config_file = os.path.join(self.config_dir, 'config.yaml')
        self.metadata_file = os.path.join(self.config_dir, '.sync_metadata.json')
        
        # 确保配置目录存在
        os.makedirs(self.config_dir, exist_ok=True)
        
        # 重新设置日志记录器，将日志保存到Tabby配置目录
        global logger
        logger = setup_logger(self.config_dir)
        
        logger.info(f"Tabby配置文件位置: {self.config_file}")
        logger.info(f"同步元数据文件位置: {self.metadata_file}")
        logger.info(f"日志文件位置: {os.path.join(self.config_dir, 'logs', 'tabby_sync.log')}")
        
        # 初始化或加载元数据
        self.load_metadata()
    
    def load_metadata(self):
        """
        加载或初始化同步元数据
        """
        if os.path.exists(self.metadata_file):
            try:
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    self.metadata = json.load(f)
                logger.debug("已加载同步元数据")
            except Exception as e:
                logger.error(f"加载元数据文件失败: {e}")
                self.metadata = self._create_default_metadata()
        else:
            logger.info("元数据文件不存在，创建默认元数据")
            self.metadata = self._create_default_metadata()
            self.save_metadata()
    
    def _create_default_metadata(self):
        """
        创建默认的元数据结构
        """
        return {
            "last_sync_time": None,
            "last_local_hash": None,
            "last_remote_hash": None,
            "device_id": self._generate_device_id(),
            "sync_history": []
        }
    
    def _generate_device_id(self):
        """
        生成唯一的设备ID
        """
        # 使用主机名和MAC地址的组合生成唯一ID
        hostname = platform.node()
        # 获取一个唯一标识符，可以是MAC地址或其他系统特定的ID
        unique_id = platform.machine() + platform.processor()
        device_id = hashlib.md5((hostname + unique_id).encode()).hexdigest()
        return device_id
    
    def save_metadata(self):
        """
        保存同步元数据到文件
        """
        try:
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, indent=2)
            logger.debug("已保存同步元数据")
        except Exception as e:
            logger.error(f"保存元数据文件失败: {e}")
    
    def calculate_file_hash(self, file_path):
        """
        计算文件的MD5哈希值
        
        Args:
            file_path (str): 文件路径
            
        Returns:
            str: 文件的MD5哈希值，如果文件不存在则返回None
        """
        if not os.path.exists(file_path):
            return None
        
        try:
            with open(file_path, 'rb') as f:
                file_hash = hashlib.md5(f.read()).hexdigest()
            return file_hash
        except Exception as e:
            logger.error(f"计算文件哈希值失败: {e}")
            return None
    
    def get_remote_config(self):
        """
        从GitHub Gist获取远程配置
        
        Returns:
            tuple: (配置内容, 哈希值, 最后更新时间)
        """
        try:
            url = f"https://api.github.com/gists/{self.gist_id}"
            
            # 显示下载进度
            if self.show_progress:
                print("正在下载远程配置...")
                progress_bar = tqdm(total=100, desc="下载进度", unit="%")
                progress_bar.update(10)  # 初始进度
            
            response = requests.get(url, headers=self.headers)
            
            if self.show_progress:
                progress_bar.update(40)  # 更新进度到50%
            
            response.raise_for_status()
            
            gist_data = response.json()
            
            # 检查是否存在config.yaml文件
            if 'config.yaml' not in gist_data['files']:
                if self.show_progress:
                    progress_bar.close()
                logger.warning("Gist中不存在config.yaml文件")
                return None, None, None
            
            content = gist_data['files']['config.yaml']['content']
            updated_at = gist_data['updated_at']
            
            # 计算内容的哈希值
            content_hash = hashlib.md5(content.encode()).hexdigest()
            
            if self.show_progress:
                progress_bar.update(50)  # 完成进度
                progress_bar.close()
            
            return content, content_hash, updated_at
        except requests.RequestException as e:
            if self.show_progress and 'progress_bar' in locals():
                progress_bar.close()
            logger.error(f"获取远程配置失败: {e}")
            return None, None, None
    
    def update_remote_config(self, content):
        """
        更新GitHub Gist中的配置
        
        Args:
            content (str): 要更新的配置内容
            
        Returns:
            bool: 更新是否成功
        """
        try:
            url = f"https://api.github.com/gists/{self.gist_id}"
            payload = {
                "files": {
                    "config.yaml": {
                        "content": content
                    }
                }
            }
            
            # 显示上传进度
            if self.show_progress:
                print("正在上传配置到远程...")
                progress_bar = tqdm(total=100, desc="上传进度", unit="%")
                progress_bar.update(20)  # 初始进度
            
            response = requests.patch(url, headers=self.headers, json=payload)
            
            if self.show_progress:
                progress_bar.update(60)  # 更新进度
            
            response.raise_for_status()
            
            if self.show_progress:
                progress_bar.update(20)  # 完成进度
                progress_bar.close()
            
            logger.info("成功更新远程配置")
            return True
        except requests.RequestException as e:
            if self.show_progress and 'progress_bar' in locals():
                progress_bar.close()
            logger.error(f"更新远程配置失败: {e}")
            return False
    
    def create_gist_if_not_exists(self):
        """
        如果指定的Gist不存在，则创建一个新的Gist
        
        Returns:
            bool: 创建是否成功
        """
        try:
            # 显示进度
            if self.show_progress:
                print("正在检查Gist状态...")
                progress_bar = tqdm(total=100, desc="Gist检查", unit="%")
                progress_bar.update(10)  # 初始进度
            
            # 首先检查Gist是否存在
            url = f"https://api.github.com/gists/{self.gist_id}"
            response = requests.get(url, headers=self.headers)
            
            if self.show_progress:
                progress_bar.update(40)  # 更新进度
            
            # 如果Gist存在，直接返回True
            if response.status_code == 200:
                if self.show_progress:
                    progress_bar.update(50)  # 完成进度
                    progress_bar.close()
                logger.info("Gist已存在，无需创建")
                return True
            
            # 如果Gist不存在，创建一个新的
            if response.status_code == 404:
                if self.show_progress:
                    progress_bar.update(20)  # 更新进度状态
                    progress_bar.set_description("创建新Gist")
                
                # 读取本地配置文件
                if os.path.exists(self.config_file):
                    with open(self.config_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                else:
                    # 如果本地配置文件不存在，创建一个空的配置
                    content = ""
                
                if self.show_progress:
                    progress_bar.update(10)  # 更新进度
                
                # 创建新的Gist
                create_url = "https://api.github.com/gists"
                payload = {
                    "description": "Tabby Terminal Configuration",
                    "public": False,
                    "files": {
                        "config.yaml": {
                            "content": content
                        }
                    }
                }
                
                if self.show_progress:
                    progress_bar.update(10)  # 更新进度
                
                create_response = requests.post(create_url, headers=self.headers, json=payload)
                
                if self.show_progress:
                    progress_bar.update(10)  # 更新进度
                
                create_response.raise_for_status()
                
                # 获取新创建的Gist ID
                new_gist_id = create_response.json()['id']
                
                if self.show_progress:
                    progress_bar.close()
                
                logger.info(f"已创建新的Gist，ID: {new_gist_id}")
                
                # 如果用户提供的是空Gist ID，更新为新创建的ID
                if not self.gist_id:
                    self.gist_id = new_gist_id
                    logger.info(f"请更新配置，使用新的Gist ID: {new_gist_id}")
                
                return True
            
            # 其他错误情况
            if self.show_progress:
                progress_bar.close()
            response.raise_for_status()
            return False
        except requests.RequestException as e:
            if self.show_progress and 'progress_bar' in locals():
                progress_bar.close()
            logger.error(f"检查或创建Gist失败: {e}")
            return False
    
    def merge_configs(self, local_config, remote_config):
        """
        合并本地和远程配置，处理冲突
        
        Args:
            local_config (dict): 本地配置
            remote_config (dict): 远程配置
            
        Returns:
            dict: 合并后的配置
        """
        # 如果本地或远程配置为空，返回非空的那个
        if not local_config:
            return remote_config
        if not remote_config:
            return local_config
        
        # 创建合并后的配置副本
        merged_config = local_config.copy()
        
        # 处理特定的配置部分，这里需要根据Tabby的配置结构进行定制
        # 例如，合并profiles、hotkeys等，保留两边的设置
        
        # 合并profiles（如果存在）
        if 'profiles' in remote_config and 'profiles' in local_config:
            # 创建一个以name为键的字典，便于查找
            local_profiles = {p.get('name', f'profile_{i}'): p 
                             for i, p in enumerate(local_config.get('profiles', []))}
            remote_profiles = {p.get('name', f'profile_{i}'): p 
                              for i, p in enumerate(remote_config.get('profiles', []))}
            
            # 合并profiles
            merged_profiles = []
            all_profile_names = set(list(local_profiles.keys()) + list(remote_profiles.keys()))
            
            for name in all_profile_names:
                if name in local_profiles and name in remote_profiles:
                    # 如果两边都有，使用最近修改的那个
                    local_profile = local_profiles[name]
                    remote_profile = remote_profiles[name]
                    
                    # 这里可以添加更复杂的合并逻辑，例如比较最后修改时间
                    # 现在简单地使用本地的版本
                    merged_profiles.append(local_profile)
                elif name in local_profiles:
                    merged_profiles.append(local_profiles[name])
                else:
                    merged_profiles.append(remote_profiles[name])
            
            merged_config['profiles'] = merged_profiles
        
        # 可以添加更多特定配置部分的合并逻辑
        
        return merged_config
    
    def sync(self, force_upload=False, force_download=False):
        """
        同步Tabby配置
        
        Args:
            force_upload (bool): 强制上传本地配置到远程
            force_download (bool): 强制从远程下载配置
            
        Returns:
            bool: 同步是否成功
        """
        logger.info("开始同步配置...")
        
        # 显示总体进度
        if self.show_progress:
            print("开始同步Tabby配置...")
            overall_progress = tqdm(total=100, desc="总体进度", unit="%")
            overall_progress.update(10)  # 初始进度
        
        # 确保Gist存在
        if not self.create_gist_if_not_exists():
            logger.error("无法创建或访问Gist，同步失败")
            if self.show_progress:
                overall_progress.close()
            return False
        
        if self.show_progress:
            overall_progress.update(20)  # 更新进度
        
        # 计算本地配置文件的哈希值
        local_hash = self.calculate_file_hash(self.config_file)
        
        # 获取远程配置
        remote_content, remote_hash, remote_updated_at = self.get_remote_config()
        if remote_content is None:
            logger.error("无法获取远程配置，同步失败")
            if self.show_progress:
                overall_progress.close()
            return False
            
        if self.show_progress:
            overall_progress.update(20)  # 更新进度
        
        # 检查是否需要同步
        last_local_hash = self.metadata.get('last_local_hash')
        last_remote_hash = self.metadata.get('last_remote_hash')
        
        logger.info(f"本地配置哈希: {local_hash}")
        logger.info(f"远程配置哈希: {remote_hash}")
        logger.info(f"上次同步的本地哈希: {last_local_hash}")
        logger.info(f"上次同步的远程哈希: {last_remote_hash}")
        
        if self.show_progress:
            overall_progress.update(10)  # 更新进度
        
        # 如果强制上传
        if force_upload:
            logger.info("强制上传本地配置到远程")
            if not os.path.exists(self.config_file):
                logger.error("本地配置文件不存在，无法上传")
                if self.show_progress:
                    overall_progress.close()
                return False
            
            with open(self.config_file, 'r', encoding='utf-8') as f:
                local_content = f.read()
            
            if self.update_remote_config(local_content):
                # 更新元数据
                self.metadata['last_sync_time'] = datetime.now().isoformat()
                self.metadata['last_local_hash'] = local_hash
                self.metadata['last_remote_hash'] = local_hash  # 上传后远程哈希等于本地哈希
                self.metadata['sync_history'].append({
                    "time": datetime.now().isoformat(),
                    "action": "upload",
                    "device_id": self.metadata['device_id']
                })
                self.save_metadata()
                logger.info("强制上传成功")
                if self.show_progress:
                    overall_progress.update(40)  # 完成进度
                    overall_progress.close()
                return True
            logger.error("强制上传失败")
            if self.show_progress:
                overall_progress.close()
            return False
        
        # 如果强制下载
        if force_download:
            logger.info("强制从远程下载配置")
            if not remote_content:
                logger.error("远程配置为空，无法下载")
                if self.show_progress:
                    overall_progress.close()
                return False
            
            # 备份本地配置
            if os.path.exists(self.config_file):
                backup_file = f"{self.config_file}.bak.{int(time.time())}"
                try:
                    with open(self.config_file, 'r', encoding='utf-8') as src, \
                         open(backup_file, 'w', encoding='utf-8') as dst:
                        dst.write(src.read())
                    logger.info(f"已备份本地配置到 {backup_file}")
                except Exception as e:
                    logger.warning(f"备份本地配置失败: {str(e)}")
            
            # 写入远程配置到本地
            try:
                with open(self.config_file, 'w', encoding='utf-8') as f:
                    f.write(remote_content)
                logger.info("已下载远程配置到本地")
                
                # 更新元数据
                self.metadata['last_sync_time'] = datetime.now().isoformat()
                self.metadata['last_local_hash'] = remote_hash
                self.metadata['last_remote_hash'] = remote_hash
                self.metadata['sync_history'].append({
                    "time": datetime.now().isoformat(),
                    "action": "download",
                    "device_id": self.metadata['device_id']
                })
                self.save_metadata()
                logger.info("强制下载成功")
                if self.show_progress:
                    overall_progress.update(40)  # 完成进度
                    overall_progress.close()
                return True
            except Exception as e:
                logger.error(f"写入配置文件失败: {str(e)}")
                if self.show_progress:
                    overall_progress.close()
                return False
        
        if self.show_progress:
            overall_progress.update(10)  # 更新进度
        
        # 正常同步逻辑
        # 情况1: 本地和远程配置都没有变化，无需同步
        if local_hash == last_local_hash and remote_hash == last_remote_hash:
            logger.info("本地和远程配置都没有变化，无需同步")
            if self.show_progress:
                overall_progress.update(30)  # 完成进度
                overall_progress.close()
            return True
        
        # 情况2: 本地配置已更改，远程配置未更改，上传本地配置
        if local_hash != last_local_hash and remote_hash == last_remote_hash:
            logger.info("本地配置已更改，上传到远程")
            with open(self.config_file, 'r', encoding='utf-8') as f:
                local_content = f.read()
            
            if self.update_remote_config(local_content):
                # 更新元数据
                self.metadata['last_sync_time'] = datetime.now().isoformat()
                self.metadata['last_local_hash'] = local_hash
                self.metadata['last_remote_hash'] = local_hash
                self.metadata['sync_history'].append({
                    "time": datetime.now().isoformat(),
                    "action": "upload",
                    "device_id": self.metadata['device_id']
                })
                self.save_metadata()
                logger.info("上传成功")
                if self.show_progress:
                    overall_progress.update(30)  # 完成进度
                    overall_progress.close()
                return True
            logger.error("上传失败")
            if self.show_progress:
                overall_progress.close()
            return False
        
        # 情况3: 本地配置未更改，远程配置已更改，下载远程配置
        if local_hash == last_local_hash and remote_hash != last_remote_hash:
            logger.info("远程配置已更改，下载到本地")
            if not remote_content:
                logger.error("远程配置为空，无法下载")
                if self.show_progress:
                    overall_progress.close()
                return False
            
            # 备份本地配置
            if os.path.exists(self.config_file):
                backup_file = f"{self.config_file}.bak.{int(time.time())}"
                try:
                    with open(self.config_file, 'r', encoding='utf-8') as src, \
                         open(backup_file, 'w', encoding='utf-8') as dst:
                        dst.write(src.read())
                    logger.info(f"已备份本地配置到 {backup_file}")
                except Exception as e:
                    logger.warning(f"备份本地配置失败: {str(e)}")
            
            # 写入远程配置到本地
            try:
                with open(self.config_file, 'w', encoding='utf-8') as f:
                    f.write(remote_content)
                logger.info("已下载远程配置到本地")
                
                # 更新元数据
                self.metadata['last_sync_time'] = datetime.now().isoformat()
                self.metadata['last_local_hash'] = remote_hash
                self.metadata['last_remote_hash'] = remote_hash
                self.metadata['sync_history'].append({
                    "time": datetime.now().isoformat(),
                    "action": "download",
                    "device_id": self.metadata['device_id']
                })
                self.save_metadata()
                logger.info("下载成功")
                if self.show_progress:
                    overall_progress.update(30)  # 完成进度
                    overall_progress.close()
                return True
            except Exception as e:
                logger.error(f"写入配置文件失败: {str(e)}")
                if self.show_progress:
                    overall_progress.close()
                return False
        
        # 情况4: 本地和远程配置都已更改，需要合并
        if local_hash != last_local_hash and remote_hash != last_remote_hash:
            logger.info("本地和远程配置都已更改，尝试合并")
            
            # 读取本地配置
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    local_content = f.read()
                local_config = yaml.safe_load(local_content) or {}
            except Exception as e:
                logger.error(f"读取本地配置失败: {str(e)}")
                if self.show_progress:
                    overall_progress.close()
                return False
            
            # 解析远程配置
            try:
                remote_config = yaml.safe_load(remote_content) or {}
            except Exception as e:
                logger.error(f"解析远程配置失败: {str(e)}")
                if self.show_progress:
                    overall_progress.close()
                return False
            
            # 备份本地配置
            backup_file = f"{self.config_file}.bak.{int(time.time())}"
            try:
                with open(self.config_file, 'r', encoding='utf-8') as src, \
                     open(backup_file, 'w', encoding='utf-8') as dst:
                    dst.write(src.read())
                logger.info(f"已备份本地配置到 {backup_file}")
            except Exception as e:
                logger.warning(f"备份本地配置失败: {str(e)}")
            
            if self.show_progress:
                overall_progress.update(10)  # 更新进度
            
            # 合并配置
            merged_config = self.merge_configs(local_config, remote_config)
            
            # 将合并后的配置转换为YAML
            try:
                merged_content = yaml.dump(merged_config, default_flow_style=False, sort_keys=False)
            except Exception as e:
                logger.error(f"转换合并配置为YAML失败: {str(e)}")
                if self.show_progress:
                    overall_progress.close()
                return False
            
            # 写入合并后的配置到本地
            try:
                with open(self.config_file, 'w', encoding='utf-8') as f:
                    f.write(merged_content)
                logger.info("已写入合并后的配置到本地")
            except Exception as e:
                logger.error(f"写入合并配置失败: {str(e)}")
                if self.show_progress:
                    overall_progress.close()
                return False
            
            if self.show_progress:
                overall_progress.update(10)  # 更新进度
            
            # 上传合并后的配置到远程
            if self.update_remote_config(merged_content):
                # 计算合并后配置的哈希值
                merged_hash = hashlib.md5(merged_content.encode()).hexdigest()
                
                # 更新元数据
                self.metadata['last_sync_time'] = datetime.now().isoformat()
                self.metadata['last_local_hash'] = merged_hash
                self.metadata['last_remote_hash'] = merged_hash
                self.metadata['sync_history'].append({
                    "time": datetime.now().isoformat(),
                    "action": "merge",
                    "device_id": self.metadata['device_id']
                })
                self.save_metadata()
                logger.info("合并并同步成功")
                if self.show_progress:
                    overall_progress.update(10)  # 完成进度
                    overall_progress.close()
                return True
            logger.error("合并后上传失败")
            if self.show_progress:
                overall_progress.close()
            return False
        
        # 不应该到达这里
        logger.error("同步逻辑出现未处理的情况")
        if self.show_progress:
            overall_progress.close()
        return False

def main():
    """
    主函数，处理命令行参数并执行同步
    """
    parser = argparse.ArgumentParser(description='Tabby配置同步工具')
    parser.add_argument('--gist-id', required=True, help='GitHub Gist ID')
    parser.add_argument('--token', required=True, help='GitHub个人访问令牌')
    parser.add_argument('--config-dir', help='Tabby配置目录的自定义路径')
    parser.add_argument('--force-upload', action='store_true', help='强制上传本地配置到远程')
    parser.add_argument('--force-download', action='store_true', help='强制从远程下载配置')
    parser.add_argument('--debug', action='store_true', help='启用调试日志')
    parser.add_argument('--no-progress', action='store_true', help='不显示进度条')
    
    args = parser.parse_args()
    
    # 设置日志级别
    if args.debug:
        logger.setLevel(logging.DEBUG)
    
    # 检查tqdm是否可用，如果不可用且用户没有禁用进度条，则显示警告
    if not TQDM_AVAILABLE and not args.no_progress:
        logger.warning("tqdm库未安装，无法显示进度条。可以使用 'pip install tqdm' 安装，或使用 --no-progress 选项禁用进度条。")
    
    # 创建同步器并执行同步，根据命令行参数决定是否显示进度条
    show_progress = not args.no_progress
    syncer = TabbyConfigSync(args.gist_id, args.token, args.config_dir, show_progress)
    success = syncer.sync(args.force_upload, args.force_download)
    
    if success:
        logger.info("同步完成")
        sys.exit(0)
    else:
        logger.error("同步失败")
        sys.exit(1)

if __name__ == '__main__':
    main()