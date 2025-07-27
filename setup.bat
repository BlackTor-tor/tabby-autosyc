@echo off
setlocal enabledelayedexpansion

echo ===================================
echo Tabby配置同步工具 - 安装脚本
echo ===================================
echo.

:: 检查Python是否安装
echo 检查Python安装...
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [错误] Python未安装。请安装Python 3.6或更高版本，并确保添加到PATH环境变量中。
    echo 您可以从 https://www.python.org/downloads/ 下载Python。
    pause
    exit /b 1
)

:: 显示Python版本
for /f "tokens=*" %%i in ('python --version') do set PYTHON_VERSION=%%i
echo [成功] 检测到 %PYTHON_VERSION%

:: 安装依赖
echo 安装必要的Python包...
pip install -r "%~dp0requirements.txt"
if %ERRORLEVEL% neq 0 (
    echo [错误] 安装Python包失败。请尝试手动运行: pip install -r requirements.txt
    echo 需要安装的包包括:
    echo - pyyaml
    echo - requests
    echo - tqdm（可选，用于显示进度条）
    pause
    exit /b 1
)
echo [成功] 已安装所需的Python包

:: 提示用户配置GitHub Token和Gist ID
echo.
echo ===================================
echo 配置GitHub Token和Gist ID
echo ===================================
echo.
echo 请按照README.md中的说明获取GitHub个人访问令牌和Gist ID。
echo 然后编辑tabby_sync_launcher.bat文件，替换以下内容：
echo   1. 将 your_gist_id_here 替换为您的Gist ID
echo   2. 将 your_github_token_here 替换为您的GitHub个人访问令牌
echo.

:: 检查Tabby是否安装
echo 检查Tabby安装...
if exist "%LOCALAPPDATA%\Programs\Tabby\Tabby.exe" (
    echo [成功] 在默认位置找到Tabby安装
) else (
    echo [警告] 在默认位置未找到Tabby安装
    echo 如果Tabby安装在非默认位置，请编辑tabby_sync_launcher.bat文件，
    echo 更新Tabby.exe的路径。
)

echo.
echo ===================================
echo 安装完成！
echo ===================================
echo.
echo 请按照README.md中的说明配置和使用Tabby配置同步工具。
echo 使用tabby_sync_launcher.bat来启动Tabby，以启用自动同步功能。
echo.

pause