#!/usr/bin/env bash
# =============================================================================
# build.sh —— macOS / Linux 一键打包脚本
# build.sh -- One-click packaging script for macOS / Linux.
#
# 功能 / What it does:
#   1. 使用 backend/.venv 中的 Python 执行 PyInstaller one-folder 打包；
#   2. 校验打包产物是否包含可执行文件与前端资源；
#   3. 在 dist/ 下生成 zip 分发包，解压即可双击运行。
#
# 用法 / Usage:
#   bash scripts/build.sh
# =============================================================================

set -euo pipefail

# 项目根目录（本脚本位于 <项目根>/scripts） / Project root (this script lives in <root>/scripts)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

# 产物名称 / Artifact name
APP_NAME="restaurant-ordering-system"
SPEC_FILE="${PROJECT_ROOT}/${APP_NAME}.spec"
DIST_DIR="${PROJECT_ROOT}/dist"
BUILD_DIR="${PROJECT_ROOT}/build"
ZIP_FILE="${DIST_DIR}/${APP_NAME}-macos.zip"

echo "==> Project root: ${PROJECT_ROOT}"

# -----------------------------------------------------------------------------
# 1. 定位 Python 解释器：优先使用项目虚拟环境
#    Locate the Python interpreter: prefer the project virtualenv.
# -----------------------------------------------------------------------------
if [[ -x "${PROJECT_ROOT}/backend/.venv/bin/python" ]]; then
  PYTHON="${PROJECT_ROOT}/backend/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="$(command -v python3)"
else
  echo "[error] Python 3 not found. Create backend/.venv first." >&2
  exit 1
fi
echo "==> Python: ${PYTHON}"

# 确认 PyInstaller 可用 / Ensure PyInstaller is available
if ! "${PYTHON}" -c "import PyInstaller" >/dev/null 2>&1; then
  echo "[error] PyInstaller is not installed. Run: ${PYTHON} -m pip install -r backend/requirements.txt" >&2
  exit 1
fi

# -----------------------------------------------------------------------------
# 2. 清理旧产物并执行打包 / Clean old artifacts and run PyInstaller
# -----------------------------------------------------------------------------
echo "==> Cleaning previous build output"
rm -rf "${DIST_DIR}" "${BUILD_DIR}"

echo "==> Building with PyInstaller (one-folder)"
"${PYTHON}" -m PyInstaller --clean --noconfirm "${SPEC_FILE}"

# -----------------------------------------------------------------------------
# 3. 校验产物 / Validate the artifact
# -----------------------------------------------------------------------------
APP_DIR="${DIST_DIR}/${APP_NAME}"
EXECUTABLE="${APP_DIR}/${APP_NAME}"
if [[ ! -x "${EXECUTABLE}" ]]; then
  echo "[error] Executable not found: ${EXECUTABLE}" >&2
  exit 1
fi
if [[ ! -f "${APP_DIR}/_internal/frontend/counter/index.html" ]]; then
  echo "[error] Bundled frontend assets are missing under _internal/frontend" >&2
  exit 1
fi
echo "==> Artifact validated: ${EXECUTABLE}"

# -----------------------------------------------------------------------------
# 4. 生成 zip 分发包 / Create the zip distribution
# -----------------------------------------------------------------------------
echo "==> Packaging zip: ${ZIP_FILE}"
mkdir -p "${DIST_DIR}"
( cd "${DIST_DIR}" && zip -q -r -y "${ZIP_FILE}" "${APP_NAME}" )

echo ""
echo "==> Done. Distribution package:"
echo "    ${ZIP_FILE}"
echo "    Unzip it, then double-click ${APP_NAME} inside the folder."
