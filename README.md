# Tabby 配置同步工具

这个工具可以帮助你在多台电脑之间同步 Tabby 终端工具的配置文件，通过 GitHub Gist 作为中间存储。它能够自动处理配置冲突，并在 Tabby 启动时下载最新配置，关闭时上传当前配置。

## 功能特点

- 在 Tabby 启动时自动下载最新配置
- 在 Tabby 关闭时自动上传当前配置
- 智能处理配置冲突，合并不同设备的配置
- 高效同步，只在配置有变更时才进行上传/下载
- 自动备份本地配置，防止意外丢失
- 支持 Windows、macOS 和 Linux 系统
- 直观显示上传和下载进度
- 保存详细的同步日志，方便问题排查

## 前提条件

- Python 3.6 或更高版本
- 安装了 `pyyaml` 和 `requests` Python 包
- GitHub 账号和个人访问令牌（Personal Access Token）
pyyaml>=6.0
requests>=2.28.0
tqdm>=4.64.0

## 安装步骤

### 1. 创建 GitHub 个人访问令牌

1. 登录你的 GitHub 账号
2. 点击右上角头像 -> Settings -> Developer settings -> Personal access tokens -> Tokens (classic)
3. 点击 "Generate new token" -> "Generate new token (classic)"
4. 为令牌添加描述，例如 "Tabby Config Sync"
5. 勾选 `gist` 权限
6. 点击 "Generate token" 按钮
7. 复制生成的令牌（注意：这是你唯一能看到令牌的机会，请妥善保存）

### 2. 创建 GitHub Gist（可选）

你可以预先创建一个 Gist 来存储配置，或者让脚本自动创建：

1. 访问 https://gist.github.com/
2. 创建一个新的 Gist，添加一个名为 `config.yaml` 的文件
3. 设置为 Secret Gist
4. 点击 "Create secret gist"
5. 从浏览器地址栏复制 Gist ID（URL 中最后一部分，例如 `https://gist.github.com/yourusername/abcdef1234567890` 中的 `abcdef1234567890`）

### 3. 配置同步脚本

1. 编辑 `tabby_sync_launcher.bat` 文件
2. 将 `your_gist_id_here` 替换为你的 Gist ID
3. 将 `your_github_token_here` 替换为你的 GitHub 个人访问令牌
4. 如果 Tabby 安装在非默认位置，请更新启动路径

## 使用方法

### 通过启动器启动 Tabby

不要直接启动 Tabby，而是使用 `tabby_sync_launcher.bat` 来启动：

1. 双击 `tabby_sync_launcher.bat`
2. 脚本会先同步配置，然后启动 Tabby
3. 当你关闭 Tabby 时，脚本会自动上传配置

### 手动同步配置

你也可以使用以下命令手动同步配置：

```bash
# 正常同步（智能决定上传或下载）
python tabby_config_sync.py --gist-id YOUR_GIST_ID --token YOUR_GITHUB_TOKEN

# 强制上传本地配置
python tabby_config_sync.py --gist-id YOUR_GIST_ID --token YOUR_GITHUB_TOKEN --force-upload

# 强制下载远程配置
python tabby_config_sync.py --gist-id YOUR_GIST_ID --token YOUR_GITHUB_TOKEN --force-download
```

## 创建快捷方式（可选）

为了更方便地使用同步启动器，你可以创建一个桌面快捷方式：

1. 右键点击 `tabby_sync_launcher.bat`
2. 选择 "创建快捷方式"
3. 将快捷方式移动到桌面或其他方便的位置
4. 右键点击快捷方式 -> 属性
5. 可以更改图标为 Tabby 的图标（通常位于 `%LOCALAPPDATA%\Programs\Tabby\Tabby.exe`）

## 故障排除

### 同步失败

- 检查你的网络连接
- 确认 GitHub 个人访问令牌和 Gist ID 是否正确
- 查看日志文件获取详细错误信息
  - 日志文件位置：`%APPDATA%\Tabby\logs\tabby_sync.log`（Windows）
  - 或脚本目录下的`logs/tabby_sync.log`（如果使用自定义配置目录）

### 配置冲突

如果在不同设备上对配置进行了冲突的修改，脚本会尝试智能合并。如果你不满意合并结果，可以：

1. 使用备份文件（位于 Tabby 配置目录，格式为 `config.yaml.bak.TIMESTAMP`）恢复之前的配置
2. 手动编辑配置文件解决冲突
3. 使用 `--force-upload` 或 `--force-download` 参数强制使用某一版本

## 高级选项

同步脚本支持以下高级选项：

```
python tabby_config_sync.py --help
```

- `--no-progress`：禁用进度条显示
- `--debug`：启用详细的调试日志
- `--force-upload`：强制上传本地配置到远程，忽略远程更改
- `--force-download`：强制下载远程配置到本地，忽略本地更改

## 安全注意事项

- 不要将你的 GitHub 个人访问令牌分享给他人
- 确保将 Gist 设置为私有（Secret Gist）
- 定期更换 GitHub 个人访问令牌

## 卸载

如果你不再需要此同步工具，只需：

1. 删除 `tabby_config_sync.py` 和 `tabby_sync_launcher.bat` 文件
2. 删除 Tabby 配置目录中的 `.sync_metadata.json` 文件

## 许可证

此工具使用 MIT 许可证。