# Tabby Auto-Sync

🚀 Windows 自动同步 Tabby 终端配置文件的工具，实现多设备间配置的无缝同步。

## ✨ 功能特性

- 🚀 自动检测 Tabby 启动和关闭
- ☁️ 支持 GitHub Gist 和 Google Cloud Storage
- 🔄 智能冲突解决机制
- 💾 自动备份配置文件
- 📱 使用简单，一键启动
- ⚡ 轻量级，资源占用少

## 📋 系统要求

- Windows 10以上版本
- Python 3.7+
- Tabby 终端
- GitHub 账号

## 🚀 快速开始

### 下载.exe文件
1. **下载 `TabbyAutoSync.exe` 单个文件**
   - 无需安装，放在任意文件夹中

2. **双击运行**
   ```
   双击 TabbyAutoSync.exe
   ```

3. **配置 GitHub Token**
   - 程序会提示您配置 GitHub Token
   - 访问 https://github.com/settings/tokens
   - 创建新 token，勾选 `gist` 权限
   - 在程序中输入 token

## 二次开发

1. **核心代码：launcher.py**
   ```
   自行修改想要的功能，修改完代码后执行"build.bat"进行构建打包新的版本发布即可。
   ```

   打包完成后会生成：
   - `dist/TabbyAutoSync.exe` - 单个可执行文件

2. **使用打包的程序**
   - 复制 `TabbyAutoSync.exe` 到任何 Windows 电脑
   - 双击运行（无需 Python 环境）
   - 按提示配置 GitHub Token

## ⚙️ 配置说明

### GitHub Gist 配置（推荐）

1. **获取 GitHub Token**
   - 访问 https://github.com/settings/tokens
   - 点击 "Generate new token (classic)"
   - 勾选 `gist` 权限
   - 复制生成的 token

2. **配置文件设置**
   ```ini
   [cloud_storage]
   storage_type = github_gist
   github_token = ghp_xxxxxxxxxxxxxxxxxxxx
   gist_id =  # 留空，程序会自动创建
   ```

### Google Cloud Storage 配置

1. **创建 GCS Bucket**
   - 在 Google Cloud Console 创建项目
   - 创建 Storage Bucket
   - 下载服务账号密钥文件

2. **配置文件设置**
   ```ini
   [cloud_storage]
   storage_type = google_cloud
   bucket_name = your-bucket-name
   credentials_path = path/to/service-account-key.json
   ```

### 冲突解决策略

```ini
[sync]
# 冲突解决策略
conflict_strategy = newest  # 推荐设置

# 可选值：
# newest  - 使用最新修改的配置（推荐）
# oldest  - 使用最旧的配置
# local   - 总是使用本地配置
# cloud   - 总是使用云端配置
# merge   - 尝试自动合并配置
# manual  - 手动选择解决方案
```

## 📁 项目结构

```
tabby-autosync/
├── src/                    # 源代码目录
│   ├── launcher.py   # 核心代码
│   ├── build.bat       # 一键打包脚本
│   ├── requirements.txt  # Python依赖
│   ├── dist  # 打包输出目录
│      └── TabbyAutoSync.exe # 打包后的可执行文件
│      └── logs/                   # 日志文件目录
│      └── backups/             # 配置备份目录
│      └── config.ini             # 程序配置文件
├── LICENSE  # 许可证
└── README.md                # 项目说明
```

## 🔧 工作原理

1. **自动检测**：检测 Tabby 配置文件位置（`%APPDATA%/Tabby/config.yaml`）
2. **进程监控**：使用 `psutil` 监控 Tabby 进程启动和关闭
3. **智能同步**：
   - Tabby 启动时 → 从云端同步最新配置
   - Tabby 关闭时 → 上传本地配置到云端
4. **冲突处理**：多种策略自动处理配置冲突
5. **安全备份**：每次同步前自动创建本地备份

## ❓ 常见问题

### Q: 如何获取 GitHub Token？
A: 访问 https://github.com/settings/tokens → Generate new token → 勾选 `gist` 权限

### Q: 程序无法检测到 Tabby 配置文件？
A: 确保 Tabby 已安装并至少运行过一次，配置文件位于 `%APPDATA%/Tabby/config.yaml`

### Q: GitHub Gist 同步失败？
A: 检查网络连接和 GitHub Token 是否正确，确保 Token 有 `gist` 权限

### Q: 同步时出现冲突怎么办？
A: 程序会根据设置的策略自动处理，建议使用 `newest` 策略（使用最新的配置）

### Q: 如何备份现有配置？
A: 程序会在每次同步前自动创建备份，存储在 `backups/` 目录中

### Q: 可以在多台电脑上使用吗？
A: 可以！这正是本工具的设计目的。在每台电脑上配置相同的云存储设置即可

## 🎯 使用场景

### 场景1：办公室和家里两台电脑
1. 在办公室电脑上首次设置并上传配置
2. 在家里电脑上下载配置并开始监控
3. 日常使用时配置会自动同步

### 场景2：多台设备频繁切换
设置冲突策略为 `manual`，在配置冲突时手动选择最合适的版本

### 场景3：团队共享基础配置
使用 GitHub Gist 分享基础配置，团队成员可以在此基础上个性化定制

## 🔧 故障排除

### 检查日志
查看 `logs/tabby_sync.log` 文件获取详细错误信息

### 重置配置
删除 `config.ini` 中的 `gist_id`，程序会创建新的 Gist

## 📝 功能日志

### v2.0.0
- ✅ 支持 GitHub Gist 和 Google Cloud Storage
- ✅ 简化用户操作流程
- ✅ 优化用户体验

### v1.0.0
- ✅ 基础功能实现
- ✅ 自动进程监控
- ✅ 本地云存储同步
- ✅ 冲突解决机制

## 📄 许可证

MIT License

如有问题或建议，请创建 Issue。