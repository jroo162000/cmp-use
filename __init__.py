"""Project root initializer."""

import os
import sys

# Ensure project root is on PYTHONPATH so subpackages like 'shared' and
# 'commander' can be imported when running scripts directly from this
# repository.
sys.path.insert(0, os.getcwd())

