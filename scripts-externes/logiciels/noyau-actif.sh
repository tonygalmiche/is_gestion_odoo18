#!/bin/bash
# Noyau actif (lecture seule)
# Sortie : "version amont;version paquet" du paquet linux-image du noyau actif,
# comparable avec paquet.sh 'linux-image-[0-9]*' (noyau installé : redémarrage en attente si différent)
# Sans paquet (noyau hors Debian / Ubuntu) : uname -r seul
R=$(uname -r)
V=$(dpkg-query -W -f='${Version}' "linux-image-$R" 2>/dev/null)
if [ -z "$V" ]; then
    echo "$R"
    exit 0
fi
A=${V#*:}
A=${A%-*}
echo "$A;$V"
