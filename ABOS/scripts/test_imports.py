import importlib
import pkgutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

errors = []
for pkg_name in ['backend', 'evaluation']:
    try:
        pkg = importlib.import_module(pkg_name)
    except Exception as e:
        print(f"FAIL to import root package {pkg_name}: {e}")
        errors.append((pkg_name, str(e)))
        continue

    for importer, modname, ispkg in pkgutil.walk_packages(pkg.__path__, pkg.__name__ + '.'):
        try:
            importlib.import_module(modname)
            print(f"OK: {modname}")
        except Exception as e:
            print(f"FAIL: {modname} -> {e}")
            errors.append((modname, str(e)))

print("--- SUMMARY ---")
if errors:
    print(f"Total import errors: {len(errors)}")
    for mod, err in errors:
        print(f"  {mod}: {err}")
    sys.exit(1)
else:
    print("All modules imported successfully!")
