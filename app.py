import os
import sys
from pathlib import Path

pkg_dir = Path(__file__).resolve().parent / "eventpilot-ai"
os.chdir(pkg_dir)
sys.path.insert(0, str(pkg_dir))

app_path = pkg_dir / "app.py"
with open(app_path, "r", encoding="utf-8") as f:
    code = compile(f.read(), str(app_path), "exec")
    exec(code, {"__name__": "__main__", "__file__": str(app_path)})
