#!/bin/bash

# =============================================================================
# Script de détection de vulnérabilité CIFSwitch (CVE-2024-12368)
# =============================================================================
#
# CONTEXTE :
#   CIFSwitch est une vulnérabilité de privilege escalation dans le noyau Linux
#   qui affecte les systèmes avec cifs-utils installé et User Namespaces activés.
#   Elle nécessite trois conditions pour être exploitable :
#   1. cifs-utils (Common Internet File System) installé
#   2. User Namespaces activés dans le noyau
#   3. Un attaquant avec certains privilèges
#
# USER NAMESPACES SUR DEBIAN :
#   - Debian 9 (Stretch) et avant : DÉSACTIVÉS par défaut
#   - Debian 10 (Buster) et après : ACTIVÉS par défaut
#   - Bullseye moderne : activés par défaut (kernel.unprivileged_userns_clone = 1)
#
#   Pour vérifier manuellement sur votre système :
#   - Statut : cat /proc/sys/kernel/unprivileged_userns_clone
#     * 0 = désactivés
#     * 1 = activés
#   - Limite  : cat /proc/sys/user/max_user_namespaces
#     * 0 = désactivés
#     * > 0 = activés (valeur typique : 3884)
#
# RÉSULTAT ATTENDU :
#   Le système est VULNÉRABLE seulement si TOUS ces critères sont vrais :
#   ✅ cifs-utils installé
#   ✅ User Namespaces activés (max_user_namespaces > 0)
#
#   Exemples de résultats :
#   - "✅ cifs non installé | ❌ UserNS activé | ✅ Pas vulnérable" → SÛRE
#   - "❌ cifs installé | ✅ UserNS désactivé | ✅ Pas vulnérable" → SÛRE
#   - "❌ cifs installé | ❌ UserNS activé | 🚨 VULNÉRABLE" → À CORRIGER
#
# =============================================================================

# Test si le paquet debian cifs-utils est installé
cifs_status=""
cifs_installed=false
if dpkg-query -W -f='${Status}' cifs-utils 2>/dev/null | grep -q "install ok installed"; then
    cifs_status="❌ cifs-utils installé"
    cifs_installed=true
else
    cifs_status="✅ cifs-utils non installé"
fi

# Test si les User Namespaces sont activés
ns_status=""
ns_enabled=false
if [[ -f /proc/sys/user/max_user_namespaces ]]; then
    max_ns=$(cat /proc/sys/user/max_user_namespaces)
    if [[ "$max_ns" -gt 0 ]]; then
        ns_count="?"
        if command -v lsns &> /dev/null; then
            ns_count=$(($(lsns -t user 2>/dev/null | wc -l) - 1))
        fi
        ns_status="❌ User Namespaces activé ($ns_count/$max_ns)"
        ns_enabled=true
    else
        ns_status="✅ User Namespaces non activé"
    fi
else
    ns_status="✅ User Namespaces non activé"
fi

# Déterminer si vulnérable à CIFSwitch
vulnerability=""
if [[ "$cifs_installed" == true ]] && [[ "$ns_enabled" == true ]]; then
    vulnerability="🚨 VULNÉRABLE à CIFSwitch"
else
    vulnerability="✅ Pas vulnérable à CIFSwitch"
fi

# Afficher sur une seule ligne
echo "$cifs_status | $ns_status => $vulnerability"
