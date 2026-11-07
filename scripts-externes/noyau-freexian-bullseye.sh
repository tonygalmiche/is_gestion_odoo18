#!/bin/bash
# CVE-2026-98432 : installe le noyau corrigé Freexian ELTS sur un VPS Debian 11 (bullseye),
# et, si PHP 7.4 est installé, le PHP corrigé de PHP2Shell (même dépôt Freexian).
#
# Usage : bash noyau-freexian-bullseye.sh root@serveur
#
# Lancé depuis le poste de Tony, travaille sur le serveur par ssh :
#   1. vérifie que le serveur est en bullseye
#   2. ajoute si besoin la clé Freexian (empreinte contrôlée), le dépôt, le pinning linux-image-*, apt en IPv4,
#      et le pinning php7.4* si des paquets php7.4-* sont installés
#      (dépôt déjà en place pour PHP2Shell : ajoute seulement les blocs manquants au pinning)
#   3. apt update, contrôle que le candidat noyau vient de Freexian en 5.10.272-1 ou plus,
#      et le candidat php7.4-common en 7.4.33-1+deb11u14 ou plus
#   4. apt install du méta-paquet noyau, puis apt install --only-upgrade des php7.4-* en retard
#      (confirmation apt habituelle à chaque fois, rien d'autre n'est mis à jour), redémarrage de php7.4-fpm
#   5. demande avant de redémarrer, attend le retour du serveur, affiche le noyau actif, PHP et les unités en échec
# Relancé sur un serveur déjà fait : s'arrête (« Déjà à jour ») si le noyau actif est le dernier disponible
# et PHP à jour ; saute l'installation du noyau s'il est installé mais pas encore démarré.
# libapache2-mod-php7.4 (mod_php) n'est pas couvert par le pinning php7.4* : simple avertissement, à traiter à la main.

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

# PHP2Shell : paquets php7.4-* installés → pinning php7.4* vers Freexian
PHP_INSTALLES=$(dpkg-query -W -f='${Package} ${Status}\n' 'php7.4*' 2>/dev/null | awk '/install ok installed/{print $1}' | tr '\n' ' ')
if [ -n "$PHP_INSTALLES" ] && ! grep -q '^Package: php7\.4\*' "$PIN"; then
    printf '\nPackage: php7.4*\nPin: origin deb.freexian.com\nPin-Priority: 500\n' >> "$PIN"
    echo "Pinning php7.4* ajouté" >&2
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
# PHP 7.4 : paquets installés en retard sur leur candidat
PHP=""
if [ -n "$PHP_INSTALLES" ]; then
    for P in $PHP_INSTALLES; do
        CANDIDAT=$(apt-cache policy "$P" | awk '/Candidat|Candidate/{print $2}')
        INSTALLE=$(dpkg-query -W -f='${Version}' "$P")
        if [ "$INSTALLE" != "$CANDIDAT" ]; then
            PHP="$PHP $P"
        fi
    done
    CANDIDAT=$(apt-cache policy php7.4-common | awk '/Candidat|Candidate/{print $2}')
    echo "php7.4-common : installé $(dpkg-query -W -f='${Version}' php7.4-common 2>/dev/null), candidat $CANDIDAT ; à mettre à jour :${PHP:- rien}" >&2
    if ! dpkg --compare-versions "$CANDIDAT" ge 7.4.33-1+deb11u14; then
        echo "ERREUR : le candidat de php7.4-common n'est pas le PHP corrigé (vérifier le pinning)" >&2
        exit 1
    fi
    if dpkg-query -W -f='${Status}' libapache2-mod-php7.4 2>/dev/null | grep -q "install ok installed"; then
        echo "ATTENTION : libapache2-mod-php7.4 installé, non couvert par le pinning php7.4* : à traiter à la main" >&2
    fi
fi
echo "$ETAT;$META;$PHP"
EOF
)
IFS=';' read -r ETAT META PHP <<< "$RESULTAT"

if [ "$ETAT" = A_JOUR ] && [ -z "$PHP" ]; then
    echo
    echo "Déjà à jour : le noyau actif est le dernier disponible et PHP est à jour, rien à faire."
    exit 0
fi

if [ "$ETAT" = INSTALLER ]; then
    echo
    echo "=== Installation de :$META (valider la liste affichée par apt)"
    $SSH -t "apt install $META"
elif [ "$ETAT" = REDEMARRER ]; then
    echo
    echo "Noyau déjà installé mais pas encore démarré : installation sautée."
fi

if [ -n "$PHP" ]; then
    echo
    echo "=== Mise à jour PHP2Shell de :$PHP (valider la liste affichée par apt : seuls des php7.4-*)"
    $SSH -t "apt install --only-upgrade $PHP"
    $SSH 'systemctl try-restart php7.4-fpm; echo "php7.4-fpm : $(systemctl is-active php7.4-fpm)"'
fi

if [ "$ETAT" = A_JOUR ]; then
    echo
    echo "Noyau déjà à jour : pas de redémarrage nécessaire."
    exit 0
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
$SSH 'echo "Noyau actif : $(uname -r)"; uptime; V=$(dpkg-query -W -f="\${Version}" php7.4-common 2>/dev/null) && echo "PHP 7.4 : $V"; ECHECS=$(systemctl --failed --no-legend); if [ -z "$ECHECS" ]; then echo "Services : tous OK"; else echo "Services en échec :"; echo "$ECHECS"; fi'
