"""Scanner de couverture i18n pour l'ensemble des fichiers UI.

Détecte les chaînes de caractères en dur dans les composants UI qui n'utilisent pas `tr(...)`.
"""

import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

UI_DIR = Path("src/ui")
LOCALES_DIR = Path("src/i18n/locales")


def load_locales():
    locales = {}
    for f in LOCALES_DIR.glob("*.json"):
        with open(f, "r", encoding="utf-8") as fp:
            locales[f.stem] = json.load(fp)
    return locales


def flatten_keys(d, prefix=""):
    keys = set()
    for k, v in d.items():
        full = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            keys.update(flatten_keys(v, full))
        else:
            keys.add(full)
    return keys


def scan_ui_tr_usage():
    py_files = list(UI_DIR.rglob("*.py"))
    tr_keys_used = set()
    hardcoded_labels = []

    for pf in py_files:
        content = pf.read_text(encoding="utf-8")
        # Trouve les clés passées à tr("...")
        matches = re.findall(r'\btr\(\s*["\']([^"\']+)["\']', content)
        for m in matches:
            tr_keys_used.add((m, pf.name))

        # Détecte les QLabel("Texte") ou QPushButton("Texte") sans tr
        for m in re.finditer(r'(QLabel|QPushButton)\s*\(\s*["\']([^"\']+)["\']\s*\)', content):
            w_type, txt = m.group(1), m.group(2)
            # Ignorer les sélecteurs, styles, URLs, symboles ou icônes
            if txt.startswith(("#", "font", "http", "rgba", "qrc:", "px", "solid", "var", "{", "%")):
                continue
            if len(txt) <= 2 or txt.isdigit():
                continue
            # Ignorer les noms de classes ou identifiants
            if "_" in txt and " " not in txt and txt.islower():
                continue
            hardcoded_labels.append((pf.name, w_type, txt))

    return tr_keys_used, hardcoded_labels


def main():
    print("=" * 60)
    print("AUDIT DE COUVERTURE I18N (INTERNATIONALISATION)")
    print("=" * 60)

    locales = load_locales()
    print(f"Locales trouvées : {list(locales.keys())}")

    fr_keys = flatten_keys(locales.get("fr", {}))
    print(f"Total clés de traduction définies dans fr.json : {len(fr_keys)}")

    for lang, data in locales.items():
        l_keys = flatten_keys(data)
        missing = fr_keys - l_keys
        extra = l_keys - fr_keys
        print(
            f"  - [{lang.upper()}] Clés : {len(l_keys)} | Manquantes : {len(missing)} | Supplémentaires : {len(extra)}"
        )

    tr_keys, hardcoded = scan_ui_tr_usage()
    print(f"\nClés de traduction référencées dans le code UI : {len(tr_keys)}")

    # Vérifie si des clés utilisées dans le code UI manquent dans les fichiers de traduction
    missing_in_fr = []
    for k, fname in tr_keys:
        if k not in fr_keys:
            missing_in_fr.append((k, fname))

    if missing_in_fr:
        print(f"\n[!] ALERTE : {len(missing_in_fr)} clé(s) utilisée(s) dans l'UI sans définition dans fr.json :")
        for k, fname in missing_in_fr:
            print(f"    - '{k}' (dans {fname})")
    else:
        print("\n[*] Toutes les clés tr(...) utilisées dans l'UI sont bien déclarées dans fr.json !")

    print(f"\nLabels potentiellement codés en dur sans tr(...) : {len(hardcoded)}")
    for fname, w_type, txt in hardcoded[:25]:
        print(f"    [{fname}] {w_type}: '{txt}'")


if __name__ == "__main__":
    main()
