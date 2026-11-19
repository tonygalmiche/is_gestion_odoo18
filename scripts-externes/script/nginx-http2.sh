#!/bin/bash

# =============================================================================
# HTTP/2 actif dans nginx (lecture seule)
# =============================================================================
#
# USAGE (via verif-update-vps.py) :
#   ./verif-update-vps.py --script script/nginx-http2.sh [filtre]
#
# Alerte CERTFR-2026-ALE-017 (CVE-2026-123007, CVE-2026-123633) : exécution
# de code à distance par HTTP/2.
#
# Affiche sur une seule ligne :
# - HTTP/2 actif ou non (http2 on; ou listen ... http2)
# - HTTP/3 (listen ... quic)
# - version de nginx installée et version disponible (apt)
# =============================================================================

cd / || exit 0

if ! pgrep -x nginx > /dev/null; then
    echo "— nginx absent ou arrêté"
    exit 0
fi

# Configuration complète (sudo si le compte SSH n'est pas root)
if [ "$(id -u)" = 0 ]; then
    conf=$(nginx -T 2>/dev/null)
else
    conf=$(sudo -n nginx -T 2>/dev/null)
fi

installe=$(dpkg-query -W -f='${Version}' nginx 2>/dev/null)
candidat=$(apt-cache policy nginx 2>/dev/null | awk '/Candidat|Candidate/ {print $2}')
if [ -z "$installe" ]; then
    version="nginx hors paquet"
elif [ -n "$candidat" ] && [ "$candidat" != "$installe" ]; then
    version="nginx $installe → $candidat disponible"
else
    version="nginx $installe"
fi

if [ -z "$conf" ]; then
    echo "❓ configuration illisible (nginx -T) | $version"
    exit 0
fi

# Sans commentaires
conf=$(echo "$conf" | sed 's/#.*//')

http2=$(echo "$conf" | grep -cE '^\s*(listen\s[^;]*\shttp2\b|http2\s+on\s*;)')
http3=$(echo "$conf" | grep -cE '^\s*listen\s[^;]*\squic\b')

if [ "$http2" -gt 0 ]; then
    icone="⚠️"
    texte="HTTP/2 actif ($http2 ligne(s))"
else
    icone="✅"
    texte="HTTP/2 absent"
fi

if [ "$http3" -gt 0 ]; then
    icone="⚠️"
    texte="$texte | HTTP/3 actif ($http3 ligne(s))"
fi

echo "$icone $texte | $version"
