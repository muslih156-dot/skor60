import sys
from pathlib import Path

# Menambahkan root direktori ke sys.path agar modul utama dapat diimpor oleh folder tests/
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
