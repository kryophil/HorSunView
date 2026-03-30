# -*- coding: utf-8 -*-
"""
tests/run_all_tests.py – Führt alle Tests aus und gibt einen klaren Exit-Code zurück.

Exit 0 = alle Tests grün
Exit 1 = mindestens ein Test fehlgeschlagen

Wird aufgerufen von:
  - Claude Code PostToolUse-Hook (automatisch nach Datei-Edits)
  - Git pre-commit Hook (blockiert Commit bei Fehler)
  - make_zip.ps1 (blockiert ZIP-Erstellung bei Fehler)
  - Manuell: python tests/run_all_tests.py
"""
import sys
import unittest

# Testmodule laden
from run_spa_tests import TestSVF, TestSPANRELReference, TestAzimuthElevationRanges
from test_qt_compat import TestQt6Compatibility

if __name__ == '__main__':
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    for cls in [TestSVF, TestSPANRELReference, TestAzimuthElevationRanges,
                TestQt6Compatibility]:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=1)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
