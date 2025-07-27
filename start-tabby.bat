@echo off
chcp 65001 > nul
set PYTHON_SCRIPT="E:\BaiduSyncdisk\CodePath\Config\tabby-sync.py"
set TABBY_PATH="D:\Application\Code_Tools\Tabby\Tabby.exe"

echo 正在拉取最新配置...
python %PYTHON_SCRIPT% pull
if %errorlevel% neq 0 (
    echo 拉取配置失败！请检查错误信息
    pause
    exit /b 1
)

echo 启动Tabby终端...
start /wait "" %TABBY_PATH%

echo 正在上传配置...
python %PYTHON_SCRIPT% push
if %errorlevel% neq 0 (
    echo 上传配置失败！请检查错误信息
    pause
    exit /b 1
)

echo Tabby已关闭，所有配置已同步！
timeout /t 3