#!/bin/bash
# Version des paquets Debian installés (lecture seule)
# Paramètres : noms de paquets, * accepté (ex. paquet.sh 'php*-cli' 'php*-fpm')
# Sortie : une ligne par version installée, "version amont;version paquet", rien si absent
# Version amont = version paquet sans l'époque (1:) ni la révision Debian (-5+deb11u3)
[ $# -eq 0 ] && exit 0
dpkg-query -W -f='${db:Status-Abbrev} ${Version}\n' "$@" 2>/dev/null \
| awk '$1 == "ii" { print $2 }' \
| sort -uV \
| while read -r V; do
    A=${V#*:}
    A=${A%-*}
    echo "$A;$V"
done
