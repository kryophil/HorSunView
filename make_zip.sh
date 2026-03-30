#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# make_zip.sh – QGIS-Plugin-ZIP für HorSunView erstellen
#
# Verwendung:
#   cd /pfad/zu/HorSunView
#   bash make_zip.sh
#
# Das erzeugte ZIP kann in QGIS direkt über
#   Erweiterungen → Aus ZIP installieren
# eingespielt werden.
# ---------------------------------------------------------------------------
set -euo pipefail

PLUGIN_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_NAME="HorSunView"
VERSION=$(grep '^version=' "${PLUGIN_DIR}/metadata.txt" | cut -d= -f2 | tr -d '[:space:]')
ZIP_NAME="${PLUGIN_NAME}_v${VERSION}.zip"
ZIP_PATH="${PLUGIN_DIR}/${ZIP_NAME}"
PARENT_DIR="$(dirname "${PLUGIN_DIR}")"

# Altes ZIP löschen
rm -f "${ZIP_PATH}"

cd "${PARENT_DIR}"

zip -r "${ZIP_PATH}" "${PLUGIN_NAME}/" \
    --exclude "${PLUGIN_NAME}/.git/*" \
    --exclude "${PLUGIN_NAME}/.gitignore" \
    --exclude "${PLUGIN_NAME}/__pycache__/*" \
    --exclude "${PLUGIN_NAME}/*/__pycache__/*" \
    --exclude "${PLUGIN_NAME}/tests/*" \
    --exclude "${PLUGIN_NAME}/make_zip.sh" \
    --exclude "${PLUGIN_NAME}/*.zip"

echo ""
echo "✓ ZIP erstellt: ${ZIP_PATH}"
echo "  Version:      ${VERSION}"
echo "  Grösse:       $(du -sh "${ZIP_PATH}" | cut -f1)"
echo ""
echo "In QGIS installieren:"
echo "  Erweiterungen → Aus ZIP installieren → Datei wählen → Erweiterung installieren"
