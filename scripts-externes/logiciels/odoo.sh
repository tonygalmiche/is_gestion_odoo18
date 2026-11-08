#!/bin/bash
# Version d'Odoo (lecture seule)
# Installations dans /opt/odoo*, premier niveau de /opt uniquement (sous-dossiers d'archives ignorés) :
# sources dans /opt/odooXX ou /opt/odooXX/odoo
# Sortie : une ligne par installation, "série;date des sources" (ex. "18.0;2026-09-24")
# Date des sources : dernier commit git, sinon date de release.py
for D in /opt/odoo*/; do
    for S in "${D}" "${D}odoo/"; do
        F="${S}odoo/release.py"
        [ -f "$F" ] || continue
        V=$(sed -n 's/^version_info *= *(\([^,]*\), *\([^,]*\),.*/\1.\2/p' "$F" | head -1 | tr -d "'\" ")
        [ -n "$V" ] || continue
        P=$(git -c safe.directory='*' -C "$S" log -1 --format=%cs 2>/dev/null)
        [ -n "$P" ] || P=$(date -r "$F" +%F)
        echo "$V;$P"
        break
    done
done
