#!/bin/bash

# RelmBag DMG Build Script
# Version: 1.2

VERSION="1.3"
ICON="assets/icons/pebblit.icns"

# Ensure create-dmg and pyinstaller are available
if ! command -v create-dmg &> /dev/null; then
    echo "[ERROR] create-dmg not found. Install with: brew install create-dmg"
    exit 1
fi

if ! command -v pyinstaller &> /dev/null; then
    echo "[ERROR] pyinstaller not found. Install with: pip install pyinstaller"
    exit 1
fi

build_app() {
    local spec_file=$1
    local app_name=$2
    local output_dmg=$3

    echo "------------------------------------------------"
    echo "Building ${app_name} v${VERSION} using ${spec_file}..."
    echo "------------------------------------------------"

    # 1. Clean up old builds
    rm -rf build dist "${output_dmg}"

    # 2. Build .app bundle using spec file
    python3 -m PyInstaller --noconfirm --clean "${spec_file}"

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

# Build Player App
build_app "RelmBag Player.spec" "RelmBag Player" "RelmBag.Player.${VERSION}.dmg"

# Build Admin App
build_app "RelmBag Admin.spec" "RelmBag Admin" "RelmBag.Admin.${VERSION}.dmg"

echo "------------------------------------------------"
echo "Build Process Complete!"
echo "------------------------------------------------"
