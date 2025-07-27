@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: 设置GitHub Gist ID和Token
set GIST_ID=your_gist_id_here
set GITHUB_TOKEN=your_github_token_here

:: 设置Python脚本路径
set SCRIPT_PATH=%~dp0tabby_config_sync.py

:: 检查Python是否安装
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Python未安装，请安装Python并确保添加到PATH环境变量中。
    pause
    exit /b 1
)

:: 检查必要的Python包是否安装
echo 检查必要的Python包...
python -c "import yaml, requests" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo 安装必要的Python包...
    pip install pyyaml requests
    if %ERRORLEVEL% neq 0 (
        echo 安装Python包失败，请手动安装pyyaml和requests包。
        pause
        exit /b 1
    )
)

:: 检查tqdm包是否安装（用于显示进度条）
python -c "import tqdm" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo 正在安装tqdm包（用于显示进度条）...
    pip install tqdm
    if %ERRORLEVEL% neq 0 (
        echo 安装tqdm失败，将继续但不显示进度条
    )
)

:: 确保日志目录存在
if not exist "%APPDATA%\Tabby\logs" (
    mkdir "%APPDATA%\Tabby\logs"
)

:: 在启动Tabby前同步配置（下载最新配置）
echo 正在同步Tabby配置...

:: 检查是否需要自动创建Gist ID
if "%GIST_ID%"=="your_gist_id_here" (
    echo 未设置Gist ID，将自动创建...
    python "%SCRIPT_PATH%" --token %GITHUB_TOKEN% --save-gist-id "%~f0"
) else (
    python "%SCRIPT_PATH%" --gist-id %GIST_ID% --token %GITHUB_TOKEN%
)

if %ERRORLEVEL% neq 0 (
    echo 同步配置失败，但仍将继续启动Tabby。
)

:: 启动Tabby
echo 正在启动Tabby...
start "" "%LOCALAPPDATA%\Programs\Tabby\Tabby.exe"

:: 等待Tabby进程结束
:wait_loop
timeout /t 5 /nobreak >nul
tasklist /fi "imagename eq Tabby.exe" /fo csv 2>nul | find /i "Tabby.exe" >nul
if %ERRORLEVEL% equ 0 goto wait_loop

:: Tabby已关闭，上传配置
echo Tabby已关闭，正在上传配置...

:: 检查是否需要自动创建Gist ID（理论上此时应该已经创建，但为了健壮性仍然检查）
if "%GIST_ID%"=="your_gist_id_here" (
    echo 未设置Gist ID，将自动创建并上传...
    python "%SCRIPT_PATH%" --token %GITHUB_TOKEN% --force-upload --save-gist-id "%~f0"
) else (
    python "%SCRIPT_PATH%" --gist-id %GIST_ID% --token %GITHUB_TOKEN% --force-upload
)

if %ERRORLEVEL% neq 0 (
    echo 上传配置失败。
    pause
    exit /b 1
)

echo 配置已成功上传。
exit /b 0
