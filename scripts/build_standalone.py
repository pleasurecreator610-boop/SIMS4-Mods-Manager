"""Script d'automatisation de compilation en exécutable Windows standalone via PyInstaller."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    spec_file = project_root / "sims4_mods_manager.spec"

    print("=" * 60)
    print("🛠️  Compilation Standalone - SIMS 4 Mods Manager")
    print(f"📁 Répertoire racine : {project_root}")
    print(f"📄 Fichier spec      : {spec_file.name}")
    print("=" * 60)

    if not spec_file.exists():
        print(f"❌ Erreur : Fichier '{spec_file}' introuvable.")
        return 1

    cmd = [sys.executable, "-m", "PyInstaller", str(spec_file), "--noconfirm"]

    print(f"🚀 Exécution de : {' '.join(cmd)}")
    try:
        res = subprocess.run(cmd, cwd=project_root)
        if res.returncode == 0:
            dist_dir = project_root / "dist" / "SIMS4-Mods-Manager"
            print("=" * 60)
            print("✅ Compilation réussie avec succès !")
            print(f"📦 Binaire généré dans : {dist_dir}")
            print("=" * 60)
            return 0
        else:
            print(f"❌ Échec de la compilation PyInstaller (Code retour: {res.returncode})")
            return res.returncode
    except Exception as e:
        print(f"❌ Exception lors du build : {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
