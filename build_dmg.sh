#!/bin/bash

# RelmBag DMG Build Script
# Version: 1.2.0

VERSION="1.2.0"
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
    pyinstaller --noconsole --noconfirm "${spec_file}"

    if [ $? -ne 0 ]; then
        echo "[ERROR] PyInstaller failed for ${app_name}"
        return 1
    fi

    # 3. Create DMG
    echo "Creating DMG for ${app_name}..."
    create-dmg \
        --volname "${app_name} ${VERSION}" \
        --volicon "${ICON}" \
        --window-pos 200 120 \
        --window-size 800 400 \
        --icon-size 100 \
        --icon "${app_name}.app" 200 190 \
        --hide-extension "${app_name}.app" \
        --app-drop-link 600 185 \
        "${output_dmg}" \
        "dist/${app_name}.app"

    echo "Successfully created: ${output_dmg}"
}

# Build Player App
build_app "RelmBag.Player.spec" "RelmBag" "RelmBag.Player.${VERSION}.dmg"

# Build Admin App
build_app "RelmBag.Admin.spec" "RelmBagAdmin" "RelmBag.Admin.${VERSION}.dmg"

echo "------------------------------------------------"
echo "Build Process Complete!"
echo "------------------------------------------------"
