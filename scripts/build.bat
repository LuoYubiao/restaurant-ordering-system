@echo off
rem ============================================================================
rem build.bat -- Windows one-click packaging script
rem build.bat —— Windows 一键打包脚本
rem
rem 功能 / What it does:
rem   1. 使用 backend\.venv 中的 Python 执行 PyInstaller one-folder 打包；
rem      Run PyInstaller (one-folder) with the project virtualenv.
rem   2. 校验打包产物是否包含可执行文件与前端资源；
rem      Validate that the executable and frontend assets exist.
rem   3. 在 dist\ 下生成 zip 分发包，解压即可双击运行。
rem      Produce a zip distribution under dist\ that runs after unzip.
rem
rem 用法 / Usage:
rem   scripts\build.bat
rem ============================================================================

setlocal enabledelayedexpansion

rem 项目根目录（本脚本位于 <项目根>\scripts）/ Project root (this script lives in <root>\scripts)
set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%.."
set "PROJECT_ROOT=%CD%"
popd

set "APP_NAME=restaurant-ordering-system"
set "SPEC_FILE=%PROJECT_ROOT%\%APP_NAME%.spec"
set "DIST_DIR=%PROJECT_ROOT%\dist"
set "BUILD_DIR=%PROJECT_ROOT%\build"
set "ZIP_FILE=%DIST_DIR%\%APP_NAME%-windows.zip"

echo ==^> Project root: %PROJECT_ROOT%

rem ---------------------------------------------------------------------------
rem 1. 定位 Python 解释器：优先使用项目虚拟环境
rem    Locate Python: prefer the project virtualenv.
rem ---------------------------------------------------------------------------
set "PYTHON=%PROJECT_ROOT%\backend\.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
  where python >nul 2>nul
  if errorlevel 1 (
    echo [error] Python 3 not found. Create backend\.venv first. 1>&2
    exit /b 1
  )
  for /f "delims=" %%i in ('where python') do (
    if not defined FALLBACK_PYTHON set "FALLBACK_PYTHON=%%i"
  )
  set "PYTHON=!FALLBACK_PYTHON!"
)
echo ==^> Python: %PYTHON%

rem 确认 PyInstaller 可用 / Ensure PyInstaller is available
"%PYTHON%" -c "import PyInstaller" >nul 2>nul
if errorlevel 1 (
  echo [error] PyInstaller is not installed. Run: "%PYTHON%" -m pip install -r backend\requirements.txt 1>&2
  exit /b 1
)

rem ---------------------------------------------------------------------------
rem 2. 清理旧产物并执行打包 / Clean old artifacts and run PyInstaller
rem ---------------------------------------------------------------------------
echo ==^> Cleaning previous build output
if exist "%DIST_DIR%" rmdir /s /q "%DIST_DIR%"
if exist "%BUILD_DIR%" rmdir /s /q "%BUILD_DIR%"

echo ==^> Building with PyInstaller (one-folder)
"%PYTHON%" -m PyInstaller --clean --noconfirm "%SPEC_FILE%"
if errorlevel 1 (
  echo [error] PyInstaller build failed. 1>&2
  exit /b 1
)

rem ---------------------------------------------------------------------------
rem 3. 校验产物 / Validate the artifact
rem ---------------------------------------------------------------------------
set "APP_DIR=%DIST_DIR%\%APP_NAME%"
set "EXECUTABLE=%APP_DIR%\%APP_NAME%.exe"
if not exist "%EXECUTABLE%" (
  echo [error] Executable not found: %EXECUTABLE% 1>&2
  exit /b 1
)
if not exist "%APP_DIR%\_internal\frontend\counter\index.html" (
  echo [error] Bundled frontend assets are missing under _internal\frontend 1>&2
  exit /b 1
)
echo ==^> Artifact validated: %EXECUTABLE%

rem ---------------------------------------------------------------------------
rem 4. 生成 zip 分发包 / Create the zip distribution
rem ---------------------------------------------------------------------------
echo ==^> Packaging zip: %ZIP_FILE%
powershell -NoProfile -Command "Compress-Archive -Path '%APP_DIR%' -DestinationPath '%ZIP_FILE%' -Force"
if errorlevel 1 (
  echo [error] Failed to create the zip package. 1>&2
  exit /b 1
)

echo.
echo ==^> Done. Distribution package:
echo     %ZIP_FILE%
echo     Unzip it, then double-click %APP_NAME%.exe inside the folder.

endlocal
