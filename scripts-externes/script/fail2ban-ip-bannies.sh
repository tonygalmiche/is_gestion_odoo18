#!/bin/bash

# =============================================================================
# Comptage des IP bannies par fail2ban
# =============================================================================
#
# USAGE (via verif-update-vps.py) :
#   ./verif-update-vps.py --script script/fail2ban-ip-bannies.sh
#
# Affiche sur une seule ligne : l'état de fail2ban, le nombre de jails actives
# et le nombre total d'IP actuellement bannies (toutes jails confondues).
# =============================================================================

if ! command -v fail2ban-client &> /dev/null; then
    echo "❌ fail2ban non installé"
    exit 0
fi

if ! systemctl is-active --quiet fail2ban 2>/dev/null; then
    echo "❌ fail2ban installé mais inactif"
    exit 0
fi

jails=$(fail2ban-client status 2>/dev/null | grep "Jail list:" | sed 's/.*Jail list:\s*//' | tr ',' '\n' | sed '/^\s*$/d')
nb_jails=$(echo "$jails" | grep -c .)

total_bannies=0
for jail in $jails; do
    jail=$(echo "$jail" | xargs)
    nb=$(fail2ban-client status "$jail" 2>/dev/null | grep "Currently banned:" | grep -oE '[0-9]+')
    if [[ -n "$nb" ]]; then
        total_bannies=$((total_bannies + nb))
    fi
done

echo "✅ fail2ban actif | $nb_jails jail(s) | $total_bannies IP bannie(s) au total"
