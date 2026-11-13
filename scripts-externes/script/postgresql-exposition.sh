#!/bin/bash

# =============================================================================
# Exposition de PostgreSQL (lecture seule)
# =============================================================================
#
# USAGE (via verif-update-vps.py) :
#   ./verif-update-vps.py --script script/postgresql-exposition.sh [filtre]
#
# Affiche sur une seule ligne :
# - adresses d'écoute de PostgreSQL (local ou réseau)
# - rôles avec connexion autres que postgres (* = superutilisateur)
# - extensions à risque installées (plperl, pltcl, dblink, postgres_fdw)
# =============================================================================

cd / || exit 0

if ! pgrep -x postgres > /dev/null; then
    echo "— PostgreSQL absent ou arrêté"
    exit 0
fi

# Requête SQL en tant que postgres (sudo si le compte SSH n'est pas root)
pgq() {
    if [ "$(id -u)" = 0 ]; then
        su postgres -s /bin/sh -c "psql -X -At -d '$1' -c \"$2\"" 2>/dev/null
    else
        sudo -n -u postgres psql -X -At -d "$1" -c "$2" 2>/dev/null
    fi
}

ecoute=$(pgq postgres "show listen_addresses;")
roles=$(pgq postgres "select rolname || case when rolsuper then '*' else '' end from pg_roles where rolcanlogin and rolname <> 'postgres' order by 1;" | xargs)

extensions=""
for base in $(pgq postgres "select datname from pg_database where datallowconn and not datistemplate;"); do
    extensions="$extensions $(pgq "$base" "select extname from pg_extension where extname in ('plperl','plperlu','pltcl','pltclu','dblink','postgres_fdw');")"
done
extensions=$(echo $extensions | xargs -r -n1 | sort -u | xargs)

case "$ecoute" in
    localhost|127.0.0.1) icone="✅" ;;
    '') icone="❓" ;;
    *) icone="⚠️" ;;
esac

echo "$icone écoute : ${ecoute:-?} | rôles : ${roles:-aucun} | extensions : ${extensions:-aucune}"
