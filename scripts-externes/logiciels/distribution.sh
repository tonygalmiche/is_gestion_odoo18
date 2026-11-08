#!/bin/bash
# Distribution (lecture seule)
# Sortie : "id version nom de code;version précise" (ex. "debian 12 bookworm;12.8")
# Version précise : /etc/debian_version sur Debian, VERSION de os-release sur Ubuntu (ex. 22.04.5 LTS)
[ -r /etc/os-release ] || exit 0
. /etc/os-release
case "$ID" in
    debian) P=$(cat /etc/debian_version 2>/dev/null) ;;
    *)      P=${VERSION%% (*} ;;
esac
echo "$ID $VERSION_ID $VERSION_CODENAME;$P"
