@echo off
title Build Tabby Auto-Sync

echo ========================================
echo Build Tabby Auto-Sync Single EXE
echo ========================================
echo.

echo Checking Python...
python --version
if errorlevel 1 (
    echo ERROR: Python not found
    echo Please install Python from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo.
echo Checking launcher.py...
if not exist "launcher.py" (
    echo ERROR: launcher.py not found
    echo Make sure you are in the correct directory
    pause
    exit /b 1
)

echo.
echo Fixing PyInstaller compatibility...
pip uninstall pathlib -y >nul 2>&1

echo Installing SSL fix packages...
pip install --force-reinstall pyopenssl cryptography
conda install -y openssl

echo.
echo Cleaning old files...
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"
if exist "*.spec" del /q "*.spec"

echo.
echo Building TabbyAutoSync.exe with SSL support...
echo This may take several minutes, please wait...
echo Trying Anaconda-specific SSL packaging...
echo Locating SSL libraries...

REM 查找Anaconda的SSL库
set SSL_LIB_PATH=%CONDA_PREFIX%\Library\bin
if exist "%SSL_LIB_PATH%\libssl-1_1-x64.dll" (
    echo Found SSL libraries in %SSL_LIB_PATH%
    set SSL_FOUND=1
) else (
    set SSL_LIB_PATH=%CONDA_PREFIX%\DLLs
    if exist "%SSL_LIB_PATH%\_ssl.pyd" (
        echo Found SSL in DLLs folder
        set SSL_FOUND=1
    ) else (
        echo SSL libraries not found, using basic packaging
        set SSL_FOUND=0
    )
)

if %SSL_FOUND%==1 (
    echo Building with SSL library inclusion...
    pyinstaller --onefile --console --name "TabbyAutoSync" --clean ^
        --hidden-import=ssl ^
        --hidden-import=_ssl ^
        --hidden-import=certifi ^
        --hidden-import=urllib3 ^
        --hidden-import=urllib.request ^
        --hidden-import=urllib.parse ^
        --hidden-import=urllib.error ^
        --hidden-import=http.client ^
        --hidden-import=socket ^
        --collect-data certifi ^
        --collect-submodules ssl ^
        --collect-submodules urllib3 ^
        --add-data "%SSL_LIB_PATH%\*ssl*;ssl_libs" ^
        --add-data "%SSL_LIB_PATH%\*crypto*;ssl_libs" ^
        launcher.py
) else (
    echo Building with basic SSL support...
    pyinstaller --onefile --console --name "TabbyAutoSync" --clean ^
        --hidden-import=ssl ^
        --hidden-import=certifi ^
        --collect-data certifi ^
        launcher.py
)

if errorlevel 1 (
    echo.
    echo BUILD FAILED!
    echo Try running as Administrator or check error messages above
    pause
    exit /b 1
)

echo.
echo ========================================
echo BUILD SUCCESSFUL!
echo ========================================
echo.
echo Created: dist\TabbyAutoSync.exe
echo.
echo This single EXE file contains everything needed!
echo Copy it to any Windows computer and double-click to run.
echo.
echo To use:
echo 1. Copy TabbyAutoSync.exe to target computer
echo 2. Double-click to run
echo 3. Configure GitHub Token when prompted
echo 4. Enjoy automatic Tabby config sync!
echo.
echo Get GitHub Token: https://github.com/settings/tokens
echo (Create token with 'gist' permission)
echo.
pause
