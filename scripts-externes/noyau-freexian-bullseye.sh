#!/bin/bash
# CVE-2026-98432 : installe le noyau corrigé Freexian ELTS sur un VPS Debian 11 (bullseye).
#
# Usage : bash noyau-freexian-bullseye.sh root@serveur
#
# Lancé depuis le poste de Tony, travaille sur le serveur par ssh :
#   1. vérifie que le serveur est en bullseye
#   2. ajoute si besoin la clé Freexian (empreinte contrôlée), le dépôt, le pinning linux-image-*, apt en IPv4
#      (dépôt déjà en place pour PHP2Shell : ajoute seulement le bloc linux-image-* au pinning)
#   3. apt update, contrôle que le candidat vient de Freexian en 5.10.272-1 ou plus
#   4. apt install du méta-paquet noyau (confirmation apt habituelle, rien d'autre n'est mis à jour)
#   5. demande avant de redémarrer, attend le retour du serveur, affiche le noyau actif et les unités en échec
# Relancé sur un serveur déjà fait : s'arrête (« Déjà à jour ») si le noyau actif est le dernier disponible ;
# saute l'installation si le noyau est installé mais pas encore démarré.

set -e
SERVEUR="$1"
if [ -z "$SERVEUR" ]; then
    echo "Usage : $0 root@serveur"
    exit 1
fi
SSH="ssh -o ConnectTimeout=10 $SERVEUR"

echo "=== Préparation sur $SERVEUR"
RESULTAT=$($SSH 'bash -s' <<'EOF'
set -e
EMPREINTE=AB597C4F6F3380BD4B2BEBC2A07310D369055D5A
CLE=/etc/apt/trusted.gpg.d/freexian-archive-extended-lts.gpg
LISTE=/etc/apt/sources.list.d/extended-lts.list
PIN=/etc/apt/preferences.d/extended-lts
IPV4=/etc/apt/apt.conf.d/99force-ipv4

. /etc/os-release
echo "Système : $PRETTY_NAME, noyau actif $(uname -r)" >&2
if [ "$VERSION_CODENAME" != bullseye ]; then
    echo "ERREUR : serveur en $VERSION_CODENAME, pas en bullseye" >&2
    exit 1
fi

if [ ! -f "$CLE" ]; then
    command -v gpg > /dev/null || { echo "ERREUR : gpg absent (apt install gnupg)" >&2; exit 1; }
    wget -4 -q -O "$CLE.tmp" https://deb.freexian.com/extended-lts/archive-key.gpg
    FPR=$(gpg --show-keys --with-colons "$CLE.tmp" 2>/dev/null | awk -F: '/^fpr/{print $10; exit}')
    if [ "$FPR" != "$EMPREINTE" ]; then
        rm -f "$CLE.tmp"
        echo "ERREUR : empreinte de la clé inattendue ($FPR)" >&2
        exit 1
    fi
    mv "$CLE.tmp" "$CLE"
    echo "Clé Freexian ajoutée (empreinte vérifiée)" >&2
fi

if [ ! -f "$LISTE" ]; then
    echo "deb https://deb.freexian.com/extended-lts bullseye main" > "$LISTE"
    echo "Dépôt Freexian ajouté" >&2
fi

if [ ! -f "$PIN" ]; then
    printf 'Package: *\nPin: origin deb.freexian.com\nPin-Priority: 1\n' > "$PIN"
fi
if ! grep -q '^Package: linux-image-\*' "$PIN"; then
    printf '\nPackage: linux-image-*\nPin: origin deb.freexian.com\nPin-Priority: 500\n' >> "$PIN"
    echo "Pinning linux-image-* ajouté" >&2
fi

if [ ! -f "$IPV4" ]; then
    echo 'Acquire::ForceIPv4 "true";' > "$IPV4"
fi

apt-get update -qq >&2

META=""
for P in linux-image-cloud-amd64 linux-image-amd64; do
    if dpkg-query -W -f='${Status}' "$P" 2>/dev/null | grep -q "install ok installed"; then
        META="$META $P"
    fi
done
if [ -z "$META" ]; then
    echo "ERREUR : aucun méta-paquet linux-image-amd64 / linux-image-cloud-amd64 installé" >&2
    exit 1
fi

# Version du paquet du noyau actif (ex. 5.10.272-1)
ACTIF=$(dpkg-query -W -f='${Version}' "linux-image-$(uname -r)" 2>/dev/null || true)
ETAT=A_JOUR
for P in $META; do
    CANDIDAT=$(apt-cache policy "$P" | awk '/Candidat|Candidate/{print $2}')
    INSTALLE=$(dpkg-query -W -f='${Version}' "$P")
    echo "$P : installé $INSTALLE, candidat $CANDIDAT, noyau actif $ACTIF" >&2
    if ! dpkg --compare-versions "$CANDIDAT" ge 5.10.272-1; then
        echo "ERREUR : le candidat de $P n'est pas le noyau corrigé (vérifier le pinning)" >&2
        exit 1
    fi
    if [ "$INSTALLE" != "$CANDIDAT" ]; then
        ETAT=INSTALLER
    elif [ "$ETAT" = A_JOUR ] && [ "$ACTIF" != "$INSTALLE" ]; then
        ETAT=REDEMARRER
    fi
done
echo $ETAT $META
EOF
)
read -r ETAT META <<< "$RESULTAT"

if [ "$ETAT" = A_JOUR ]; then
    echo
    echo "Déjà à jour : le noyau actif est le dernier disponible, rien à faire."
    exit 0
fi

if [ "$ETAT" = INSTALLER ]; then
    echo
    echo "=== Installation de : $META (valider la liste affichée par apt)"
    $SSH -t "apt install $META"
else
    echo
    echo "Noyau déjà installé mais pas encore démarré : installation sautée."
fi

echo
read -r -p "Redémarrer $SERVEUR maintenant ? [o/N] " REPONSE
if [ "$REPONSE" != "o" ] && [ "$REPONSE" != "O" ]; then
    echo "Pas de redémarrage : le correctif ne sera actif qu'après un reboot."
    exit 0
fi
$SSH reboot || true

echo "Attente du redémarrage..."
sleep 20
for i in $(seq 1 30); do
    if $SSH true 2>/dev/null; then
        break
    fi
    sleep 10
done

echo
echo "=== Vérification"
$SSH 'echo "Noyau actif : $(uname -r)"; uptime; ECHECS=$(systemctl --failed --no-legend); if [ -z "$ECHECS" ]; then echo "Services : tous OK"; else echo "Services en échec :"; echo "$ECHECS"; fi'
