#!/bin/bash

# RelmBag DMG Build Script
# Version: 1.3

VERSION="1.4"
ICON="assets/icons/pebblit.icns"

# Ensure npx/create-dmg and PyInstaller are available
if ! command -v npx &> /dev/null; then
    echo "[ERROR] npx not found. Install Node.js/npm first."
    exit 1
fi

if ! python3.14 -m PyInstaller --version &> /dev/null; then
    echo "[ERROR] pyinstaller not found. Install with: python3.14 -m pip install pyinstaller"
    exit 1
fi

# Set a local PyInstaller config directory to avoid global permission issues
export PYINSTALLER_CONFIG_DIR="$(pwd)/.pyinstaller_config"
rm -rf "$PYINSTALLER_CONFIG_DIR"
mkdir -p "$PYINSTALLER_CONFIG_DIR"

build_app() {
    local spec_file=$1
    local app_name=$2
    local output_dmg=$3

    echo "------------------------------------------------"
    echo "Building ${app_name} v${VERSION} using ${spec_file}..."
    echo "------------------------------------------------"

    # 1. Clean up old local build artifacts
    rm -rf build dist "${output_dmg}"

    # 2. Build .app bundle using spec file
    # --clean wipes the PyInstaller cache to avoid stale/corrupt binary errors
    python3.14 -m PyInstaller --noconfirm --clean --workpath="./build" --distpath="./dist" "${spec_file}"

    if [ $? -ne 0 ]; then
        echo "[ERROR] PyInstaller failed for ${app_name}"
        return 1
    fi

    # 3. Create DMG
    echo "Creating DMG for ${app_name}..."
    npx create-dmg "dist/${app_name}.app" . --overwrite --no-code-sign --no-version-in-filename --dmg-title="${app_name}"

    if [ ! -f "${app_name}.dmg" ]; then
        echo "[ERROR] create-dmg did not produce ${app_name}.dmg"
        return 1
    fi

    mv -f "${app_name}.dmg" "${output_dmg}"

    echo "Successfully created: ${output_dmg}"
}

# Delete old DMGs before building new ones
echo "Cleaning up old DMG files..."
rm -f RelmBag.Player.*.dmg RelmBag.Admin.*.dmg

# Build Player App
build_app "RelmBag Player.spec" "RelmBag Player" "RelmBag.Player.${VERSION}.dmg"

# Build Admin App
build_app "RelmBag Admin.spec" "RelmBag Admin" "RelmBag.Admin.${VERSION}.dmg"

echo "------------------------------------------------"
echo "Build Process Complete!"
echo "------------------------------------------------"
