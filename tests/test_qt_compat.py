# -*- coding: utf-8 -*-
"""
tests/test_qt_compat.py – Statischer Lint-Test für Qt5→Qt6-Enum-Kompatibilität.

Sucht in allen Plugin-.py-Dateien nach bekannten Qt5-Enum-Mustern,
die in Qt6/QGIS 4 nicht mehr funktionieren.

Ausführen:  python tests/test_qt_compat.py
"""
import os
import re
import unittest

# Verzeichnis mit den Plugin-Dateien
PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Dateien, die geprüft werden (keine Tests, kein spa_strict)
SKIP_FILES = {'spa_strict.py', 'spa_nrel.py'}

# Bekannte Qt5-Enum-Muster, die in Qt6 ohne Namespace nicht mehr existieren.
# Format: (regex-Muster, Erklärung, empfohlene Qt6-Alternative)
QT5_PATTERNS = [
    (
        r'QDialogButtonBox\.(Ok|Cancel|Yes|No|Close|Save|Discard|Apply|Reset|'
        r'RestoreDefaults|Help|SaveAll|Abort|Retry|Ignore)\b(?!\s*\()',
        "QDialogButtonBox-Enum ohne StandardButton-Namespace",
        "QDialogButtonBox.StandardButton.Ok  (Qt6-Stil) oder try/except-Kompatblock",
    ),
    (
        r'QDialog\.Accepted\b|QDialog\.Rejected\b',
        "QDialog-Enum ohne DialogCode-Namespace",
        "QDialog.DialogCode.Accepted  (Qt6-Stil) oder try/except-Kompatblock",
    ),
    (
        r'QFormLayout\.(WrapLongRows|WrapAllRows|DontWrapRows)\b',
        "QFormLayout-Enum ohne RowWrapPolicy-Namespace",
        "QFormLayout.RowWrapPolicy.WrapLongRows  (Qt6-Stil) oder Zeile entfernen",
    ),
    (
        r'QMessageBox\.(Ok|Cancel|Yes|No|Information|Warning|Critical|Question)\b'
        r'(?!\s*\()',
        "QMessageBox-Enum ohne Namespace",
        "QMessageBox.StandardButton.Ok  (Qt6-Stil)",
    ),
    (
        r'Qt\.AlignLeft\b|Qt\.AlignRight\b|Qt\.AlignCenter\b|Qt\.AlignTop\b|'
        r'Qt\.AlignBottom\b',
        "Qt.Alignment-Enum ohne AlignmentFlag-Namespace",
        "Qt.AlignmentFlag.AlignLeft  (Qt6-Stil)",
    ),
]


def _plugin_py_files():
    """Gibt alle .py-Dateien im Plugin-Verzeichnis zurück (keine Tests)."""
    files = []
    for fname in os.listdir(PLUGIN_DIR):
        if fname.endswith('.py') and fname not in SKIP_FILES:
            files.append(os.path.join(PLUGIN_DIR, fname))
    return sorted(files)


class TestQt6Compatibility(unittest.TestCase):
    """Prüft alle Plugin-.py-Dateien auf Qt5-only-Enum-Muster."""

    def _scan_file(self, filepath, pattern, description):
        """Gibt Liste von (Zeilennummer, Zeile) für alle Treffer zurück."""
        hits = []
        with open(filepath, encoding='utf-8') as f:
            for lineno, line in enumerate(f, 1):
                stripped = line.strip()
                # Reine Kommentarzeilen überspringen
                if stripped.startswith('#'):
                    continue
                # Absichtliche Qt5-Fallback-Zeilen (in except-Blöcken) sind
                # mit '# type: ignore' markiert – diese überspringen
                if '# type: ignore' in line:
                    continue
                if re.search(pattern, line):
                    hits.append((lineno, line.rstrip()))
        return hits

    def test_no_qt5_enums(self):
        """Keine Qt5-only-Enum-Muster in Plugin-Dateien."""
        violations = []

        for filepath in _plugin_py_files():
            fname = os.path.basename(filepath)
            for pattern, description, suggestion in QT5_PATTERNS:
                hits = self._scan_file(filepath, pattern, description)
                for lineno, line in hits:
                    violations.append(
                        f"\n  {fname}:{lineno}  [{description}]\n"
                        f"    Code:    {line.strip()}\n"
                        f"    Fix:     {suggestion}"
                    )

        if violations:
            self.fail(
                f"Qt5-Enum-Muster gefunden ({len(violations)} Treffer):"
                + "".join(violations)
            )


if __name__ == '__main__':
    unittest.main(verbosity=2)
