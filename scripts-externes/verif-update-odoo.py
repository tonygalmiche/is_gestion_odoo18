#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""Suivi de la sécurité des serveurs Odoo (is.serveur dont le service contient « odoo »), lecture seule.

Depuis le poste (HTTPS et ports) :
  - gestionnaire de bases (fermé par nginx, ou page affichée avec opérations bloquées par list_db = False),
    réinitialisation du mot de passe, inscription publique (/web/signup) ;
  - accès direct : ports 8069 et 8072 joignables de l'extérieur, Odoo par l'adresse IP (pas de bloc
    default_server dans nginx), /xmlrpc non bloqué par nginx.
Par SSH (une connexion par serveur, commandes en lecture seule), pour chaque installation /opt/odoo* :
  - version et date des sources (dernier commit git, sinon date de release.py) ;
  - CVE-2026-130028 (injection SQL, ≤ 16) : patch de l'avis présent dans odoo/models.py ;
  - CVE-2026-130029 (XSS) : correctif présent dans odoo/tools/mail.py (16.0 et plus, 2 commits :
    « stabilize » et « refine HTML normalization », le second absent d'Odoo 16.0, PR OCA/OCB 1378 ;
    12.0 à 15.0 : report OCA/OCB, PR 1373 à 1376), sinon version de libxml2 chargée par le Python d'Odoo (≥ 2.10 : atténué) ;
  - journaux Odoo : lignes avec les motifs d'attaque de l'avis (forts : pg_sleep, « as z -- » ;
    faibles : InvalidTextRepresentation, aussi produits par des erreurs ordinaires) ; 500 derniers Mo
    des fichiers non compressés et 500 premiers Mo des fichiers compressés des 31 derniers jours, à basse
    priorité, en dernier (délai dépassé : le reste du relevé est gardé) ;
  - messages piégés en base (CVE-2026-130029) : requête d'Akretion sur mail_message, dans toutes les
    bases du PostgreSQL local (psql en postgres : runuser si root, sinon sudo sans mot de passe),
    30 s au plus par base, 60 s en tout.
  Journaux et messages piégés : même colonne « Traces ».
  - pare-feu ufw (ufw status verbose, root ou sudo sans mot de passe) : actif, entrées refusées par défaut et
    aucun port web (80, 443, 8069, 8072) ouvert à tous → 🔴 et 🟠 des colonnes testées depuis le poste, SQLi et
    XSS passent en 🟡 « (pare-feu) » (le poste est une adresse autorisée : il voit Odoo ouvert).

Usage :
    python3 verif-update-odoo.py                      # tableau dans le terminal
    python3 verif-update-odoo.py plastigray           # filtre sur le client ou le serveur
    python3 verif-update-odoo.py --markdown FICHIER   # écrit aussi le relevé en Markdown
    python3 verif-update-odoo.py --markdown FICHIER plastigray   # avec un filtre : seules les lignes
                                                      # des serveurs relevés sont remplacées dans FICHIER
                                                      # (serveurs derrière un VPN : Plastigray, BSA, Alençon…)
    python3 verif-update-odoo.py --delai 300          # relevé SSH plus long par serveur (défaut : 120 s)

Relevé Markdown : Documentation/Odoo/securite/suivi-serveurs.md (ne pas le modifier à la main).
"""

import xmlrpc.client
import os
import re
import sys
import argparse
import socket
import ssl
import subprocess
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/../../../scripts-externes')
from config import URL as url, DB as db, USERNAME as username, PASSWORD as password

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode    = ssl.CERT_NONE

parser = argparse.ArgumentParser(description="Suivi de la sécurité des serveurs Odoo (lecture seule)")
parser.add_argument('filtre', nargs='?', default='', help='Filtre sur le nom du client ou du serveur')
parser.add_argument('--version', type=str, default='', help='Filtre sur la version de Odoo (Service), ex: odoo18')
parser.add_argument('--markdown', type=str, default='', help='Écrire le relevé en Markdown dans ce fichier (sans filtre)')
parser.add_argument('--jobs', type=int, default=10, help='Nombre de serveurs traités en parallèle (défaut : 10)')
parser.add_argument('--delai', type=int, default=120, help='Durée maximale du relevé SSH par serveur, en secondes (défaut : 120)')
args    = parser.parse_args()

filtre  = args.filtre.lower()
version = args.version.lower()
MAINTENANT = datetime.now().strftime('%d/%m/%Y %H:%M')

common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(url), context=ssl_context)
uid    = common.authenticate(db, username, password, {})
models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(url), context=ssl_context)

# INFO (jaune) : protégé, mais pas comme recommandé (ex. gestionnaire de bases désactivé par Odoo, page affichée)
OK, KO, WARN, INFO = 'ok', 'ko', 'warn', 'info'
ROND     = {OK: '🟢', KO: '🔴', WARN: '🟠', INFO: '🟡'}

# Programme envoyé par SSH (bash -s), lecture seule.
# Sortie : « INSTALL;dossier;version;date;sqli;xss_stabilize;xss_refine;libxml2 » par installation,
#          puis « ROT;rotation;Mo;nb_fichiers », « UFW;ligne de ufw status verbose » (une par ligne), « MSG;messages;bases_en_erreur;raison », « LOGS;forts;faibles;nb_fichiers »
#          (journaux en dernier : délai dépassé → sortie partielle gardée).
PROGRAMME = r'''
for D in /opt/odoo*/; do
    for S in "${D}" "${D}odoo/"; do
        F="${S}odoo/release.py"
        [ -f "$F" ] || continue
        V=$(sed -n "s/^version_info *= *(\([^,]*\), *\([^,]*\),.*/\1.\2/p" "$F" | head -1 | tr -d "'\" ")
        [ -n "$V" ] || continue
        P=$(git -c safe.directory='*' -C "$S" log -1 --format=%cs 2>/dev/null)
        [ -n "$P" ] || P=$(date -r "$F" +%F)
        SQ=0; grep -q "def parse_read_group_spec" "${S}odoo/models.py" 2>/dev/null && SQ=1
        # XSS : correctif d'Odoo (16.0 et plus) ou report OCA/OCB (12.0 à 15.0, PR 1373 à 1376)
        X2=0; grep -qE "replace\(b?'--!>'" "${S}odoo/tools/mail.py" 2>/dev/null && X2=1
        X3=0; grep -qF -e '</?o:[^<>\n]*?>' -e 'remove charset declarations from meta tags' "${S}odoo/tools/mail.py" 2>/dev/null && X3=1
        LX=""
        for PID in $(pgrep -f "odoo-bin|openerp-server|odoo.py" 2>/dev/null); do
            C=$(tr '\0' ' ' < /proc/$PID/cmdline 2>/dev/null)
            case "$C" in *"$D"*) ;; *) continue ;; esac
            PY=$(tr '\0' '\n' < /proc/$PID/cmdline | head -1)
            case "$PY" in
                *python*) ;;
                *) PY=$(head -1 "$PY" 2>/dev/null | sed 's/^#! *//; s/ .*//')
                   case "$PY" in */env|"") PY=python3 ;; esac ;;
            esac
            U=$(stat -c %U /proc/$PID)
            H=$(getent passwd "$U" | cut -d: -f6)
            LX=$(cd /tmp && HOME="$H" "$PY" -c "from lxml import etree; print('%d.%d.%d' % etree.LIBXML_VERSION[:3])" 2>/dev/null)
            [ -n "$LX" ] && break
        done
        echo "INSTALL;$D;$V;$P;$SQ;$X2;$X3;$LX"
        break
    done
done
L=$(grep -hs "^ *logfile *=" /etc/odoo*.conf /etc/odoo*/*.conf /opt/odoo*/*.conf 2>/dev/null | sed 's/^[^=]*= *//' | sort -u)
FICHIERS=""
for F in $L; do FICHIERS="$FICHIERS $(ls "$F"* 2>/dev/null)"; done
FICHIERS="$FICHIERS $(ls /var/log/odoo*/*.log* /var/log/odoo*.log* 2>/dev/null)"
FICHIERS=$(echo $FICHIERS | tr ' ' '\n' | sort -u)
NB=0
[ -n "$FICHIERS" ] && NB=$(echo "$FICHIERS" | wc -l)
# Rotation des journaux : fichier de /etc/logrotate.d/ qui cite odoo, ou option logrotate d'Odoo ;
# taille du plus gros journal non compressé, en Mo
ROT=""
grep -qsi "odoo" /etc/logrotate.d/* 2>/dev/null && ROT="logrotate"
grep -qsiE "^ *logrotate *= *(true|1)" /etc/odoo*.conf /etc/odoo*/*.conf /opt/odoo*/*.conf 2>/dev/null \
    && ROT="${ROT:+$ROT, }option Odoo"
MO=0
for F in $FICHIERS; do
    case "$F" in
        *.gz) ;;
        *) T=$(( $(stat -c %s "$F" 2>/dev/null || echo 0) / 1048576 )); [ "$T" -gt "$MO" ] && MO=$T ;;
    esac
done
echo "ROT;$ROT;$MO;$NB"
# Pare-feu ufw : état et règles (root, sinon sudo sans mot de passe, sinon rien)
U=/usr/sbin/ufw
if [ -x "$U" ]; then
    if [ "$(id -u)" = 0 ]; then "$U" status verbose 2>/dev/null
    else sudo -n "$U" status verbose 2>/dev/null; fi | sed 's/^/UFW;/'
fi
# Messages piégés en base (CVE-2026-130029) : requête d'Akretion sur mail_message, toutes les bases
# du PostgreSQL local ; base sans mail_message (pas Odoo) ignorée ; 30 s au plus par base, 60 s en tout.
# psql en postgres : runuser si root, sinon sudo sans mot de passe, sinon avec l'utilisateur SSH.
PSQL=""
if command -v psql >/dev/null; then
    if [ "$(id -u)" = 0 ] && id postgres >/dev/null 2>&1; then PSQL="runuser -u postgres -- psql"
    elif sudo -n -u postgres true 2>/dev/null; then PSQL="sudo -n -u postgres psql"
    else PSQL="psql"; fi
fi
MSG=""; ERR=0; RAISON=""
if ! pgrep -x postgres >/dev/null && ! pgrep -x postmaster >/dev/null; then
    RAISON="arrete"
elif [ -n "$PSQL" ]; then
    BASES=$(cd /tmp && $PSQL -XAtq -d postgres -c "SELECT datname FROM pg_database WHERE datallowconn AND NOT datistemplate AND datname <> 'postgres'" 2>/dev/null)
    if [ -n "$BASES" ]; then
        MSG=0; DEBUT=$SECONDS
        for B in $BASES; do
            if [ $((SECONDS - DEBUT)) -ge 60 ]; then ERR=$((ERR + 1)); continue; fi
            N=$(cd /tmp && PGOPTIONS="-c statement_timeout=30000" nice -n 19 $PSQL -XAtq -d "$B" 2>/dev/null <<'SQL'
SELECT CASE WHEN to_regclass('mail_message') IS NULL THEN -1 ELSE (
    SELECT count(*) FROM mail_message
    WHERE body ~* $$<script|javascript:|vbscript:|data:text/html|srcdoc|--!>|<!--->?|<[^>]*[\s/]on[a-z]+\s*=|<(iframe|object|embed|svg|math|base|form|template)\M$$
) END;
SQL
)
            case "$N" in
                -1) ;;
                ''|*[!0-9]*) ERR=$((ERR + 1)) ;;
                *) MSG=$((MSG + N)) ;;
            esac
        done
    fi
fi
echo "MSG;$MSG;$ERR;$RAISON"
# Journaux en dernier (étape la plus longue : en cas de délai dépassé, le reste est déjà relevé).
# Une seule lecture, à basse priorité (serveurs de production) : 500 derniers Mo des fichiers non compressés
# (journaux sans rotation de plusieurs Go), 500 premiers Mo des fichiers compressés des 31 derniers jours
# (1re rotation d'un journal de plusieurs Go)
FORT=0; FAIBLE=0
if [ -n "$FICHIERS" ]; then
    BAS="nice -n 19"
    command -v ionice >/dev/null && BAS="$BAS ionice -c3"
    TROUVE=$(for F in $FICHIERS; do
                 case "$F" in
                     *.gz) [ -n "$(find "$F" -mtime -31 2>/dev/null)" ] && zcat "$F" 2>/dev/null | head -c 500000000 ;;
                     *)    tail -c 500000000 "$F" 2>/dev/null ;;
                 esac
             done | $BAS env LC_ALL=C grep -aE "pg_sleep\(3\)|as z --|InvalidTextRepresentation|invalid input syntax for type integer")
    FORT=$(printf '%s\n' "$TROUVE" | grep -cE "pg_sleep\(3\)|as z --")
    # Erreur « texte à la place d'un nombre » comptée seulement si la valeur refusée contient du SQL
    # (erreurs ordinaires ignorées : NewId_…, datapoint_…, mot saisi, formule n8n non remplacée)
    FAIBLE=$(printf '%s\n' "$TROUVE" | grep -E "InvalidTextRepresentation|invalid input syntax for type integer" \
             | grep -ciE "select|union|sleep|cast|--")
fi
echo "LOGS;$FORT;$FAIBLE;$NB"
'''


def base_web(nom, ports):
    """Adresse web d'Odoo : https://nom, sinon http://nom:8069 si le port est ouvert, sinon None (pas de web)."""
    try:
        with socket.create_connection((nom, 443), timeout=5):
            return 'https://%s' % nom
    except OSError:
        pass
    if '8069' in ports[1]:
        return 'http://%s:8069' % nom
    return None


def fetch_https(base, path):
    """Retourne (content, http_code) ou (None, erreur) en cas d'erreur réseau."""
    req = urllib.request.Request('%s%s' % (base, path), headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, timeout=10, context=ssl_context) as resp:
            return resp.read().decode('utf-8', errors='replace'), resp.getcode()
    except urllib.error.HTTPError as e:
        return e.read().decode('utf-8', errors='replace'), e.code
    except Exception as e:
        return None, str(e)


def post_json(base, path):
    """POST JSON-RPC vide ; retourne (content, http_code) ou (None, erreur)."""
    req = urllib.request.Request('%s%s' % (base, path), data=b'{"jsonrpc":"2.0","method":"call","params":{}}',
                                 headers={'User-Agent': 'Mozilla/5.0', 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=10, context=ssl_context) as resp:
            return resp.read().decode('utf-8', errors='replace'), resp.getcode()
    except urllib.error.HTTPError as e:
        return e.read().decode('utf-8', errors='replace'), e.code
    except Exception as e:
        return None, str(e)


def get_db_manager_statut(nom):
    """Gestionnaire de bases : fermé par nginx (403/404), page affichée mais opérations bloquées
    par Odoo (list_db = False), ou ouvert."""
    content, http_code = fetch_https(nom, '/web/database/manager')
    if content is None:
        return WARN, 'ERREUR'
    if http_code in (403, 404):
        return OK, 'BLOQUÉ'
    liste, _code = post_json(nom, '/web/database/list')
    if 'disabled by the administrator' in content or 'has been disabled' in content \
            or (liste and ('blocked' in liste or 'AccessDenied' in liste)):
        return INFO, 'affiché'
    content_low = content.lower()
    if 'master password' in content_low and ('create database' in content_low or 'database_manager' in content_low):
        return KO, 'OUVERT !'
    return WARN, 'HTTP %s (?)' % http_code


def get_reset_password_statut(nom):
    """Page de réinitialisation du mot de passe accessible ou non."""
    content, http_code = fetch_https(nom, '/web/reset_password')
    if content is None:
        return WARN, 'ERREUR'
    content_low = content.lower()
    if 'oe_reset_password_form' in content_low:
        return KO, 'OUVERT !'
    if http_code in (403, 404) or 'not found' in content_low or 'oe_login_form' in content_low:
        return OK, 'BLOQUÉ'
    return WARN, 'HTTP %s (?)' % http_code


def get_signup_statut(nom):
    """Inscription publique (/web/signup) accessible ou non."""
    content, http_code = fetch_https(nom, '/web/signup')
    if content is None:
        return WARN, 'ERREUR'
    content_low = content.lower()
    if 'oe_signup_form' in content_low:
        return KO, 'OUVERT !'
    if http_code in (403, 404) or 'not found' in content_low or 'oe_login_form' in content_low:
        return OK, 'BLOQUÉ'
    return WARN, 'HTTP %s (?)' % http_code


def get_ports_statut(nom):
    """Ports 8069 et 8072 joignables depuis le poste."""
    ouverts = []
    for port in (8069, 8072):
        try:
            with socket.create_connection((nom, port), timeout=5):
                ouverts.append(str(port))
        except OSError:
            pass
    if ouverts:
        return KO, 'OUVERTS %s' % ','.join(ouverts)
    return OK, 'FERMÉS'


def odoo_par_ip(nom):
    """Odoo répond-il par l'adresse IP du serveur (pas de bloc default_server dans nginx) ?"""
    try:
        ip = socket.getaddrinfo(nom, 443, socket.AF_INET)[0][4][0]
    except OSError:
        return False
    if ip == nom:
        # accès SSH par IP : rien à comparer
        return False
    for base in ('https://%s' % ip, 'http://%s' % ip):
        content, http_code = fetch_https(base, '/web/login')
        if content and http_code == 200 and ('oe_login_form' in content or 'odoo' in content.lower()):
            return True
    return False


def get_acces_statut(nom, base, ports):
    """Accès directs : ports 8069/8072 (🔴), Odoo par l'adresse IP, XML-RPC ouvert (🟠)."""
    pbs, etat = [], OK
    if ports[0] == KO:
        pbs.append(ports[1].replace('OUVERTS ', ''))
        etat = KO
    if base and base.startswith('https://'):
        if odoo_par_ip(nom):
            pbs.append('IP')
            etat = etat if etat == KO else WARN
        content, http_code = fetch_https(base, '/xmlrpc/2/common')
        if content is not None and http_code not in (403, 404):
            pbs.append('xmlrpc')
            etat = etat if etat == KO else WARN
    if pbs:
        return etat, 'OUVERT %s' % ', '.join(pbs)
    return OK, 'FERMÉS'


def releve_ssh(acces_ssh):
    """Retourne (installations, journaux, erreur). Délai dépassé : ce qui a déjà été relevé est gardé
    (journaux lus en dernier), l'erreur n'est renvoyée que si aucune installation n'a été relevée."""
    try:
        res = subprocess.run(['ssh', '-o', 'ConnectTimeout=10', '-o', 'BatchMode=yes', acces_ssh, 'bash -s'],
                             input=PROGRAMME, capture_output=True, text=True, timeout=args.delai)
    except subprocess.TimeoutExpired as e:
        sortie = e.stdout or ''
        if isinstance(sortie, bytes):
            sortie = sortie.decode('utf-8', errors='replace')
        installs, logs = lire_releve(sortie)
        return installs, logs, 'délai dépassé (%d s)' % args.delai
    if res.returncode == 255:
        detail = res.stderr.strip().splitlines()[-1] if res.stderr.strip() else ''
        print('ERREUR SSH %s : %s' % (acces_ssh, detail), file=sys.stderr, flush=True)
        return [], None, 'ERREUR SSH'
    installs, logs = lire_releve(res.stdout)
    return installs, logs, None


def lire_releve(sortie):
    """Lignes INSTALL, ROT, UFW, MSG et LOGS du programme ; logs = None si aucune ligne ROT, UFW, MSG ou LOGS."""
    installs, logs = [], {}
    for ligne in sortie.splitlines():
        champs = ligne.strip().split(';')
        if champs[0] == 'INSTALL' and len(champs) == 8:
            installs.append({'dossier': champs[1], 'version': champs[2], 'date': champs[3],
                             'sqli': champs[4] == '1', 'xss2': champs[5] == '1', 'xss3': champs[6] == '1',
                             'libxml2': champs[7]})
        elif champs[0] == 'ROT' and len(champs) == 4:
            logs.update(rotation=champs[1], mo=int(champs[2] or 0), fichiers=int(champs[3] or 0))
        elif champs[0] == 'UFW' and len(champs) > 1:
            logs.setdefault('ufw', []).append(ligne.strip().split(';', 1)[1].strip())
        elif champs[0] == 'MSG' and len(champs) == 4:
            logs.update(msg=int(champs[1]) if champs[1] else None, msg_err=int(champs[2] or 0), msg_raison=champs[3])
        elif champs[0] == 'LOGS' and len(champs) == 4:
            logs.update(fort=int(champs[1] or 0), faible=int(champs[2] or 0), fichiers=int(champs[3] or 0))
    return installs, logs or None


def majeure(v):
    try:
        return int(v.split('.')[0].split('~')[-1].replace('saas', ''))
    except ValueError:
        return 0


def statut_date(date_str):
    """Vert si < 6 mois, orange si < 2 ans, rouge sinon."""
    try:
        d = datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        return WARN, date_str or '?'
    now = datetime.now()
    if d >= now - timedelta(days=182):
        return OK, date_str
    if d >= now - timedelta(days=730):
        return WARN, date_str
    return KO, date_str


def statut_sqli(inst):
    m = majeure(inst['version'])
    if m >= 17:
        return OK, 'non concerné'
    if inst['sqli']:
        return OK, 'patché'
    if m <= 12:
        return KO, 'pas de patch'
    return KO, 'à patcher'


def version_libxml2(v):
    try:
        return tuple(int(x) for x in v.split('.'))
    except ValueError:
        return None


def statut_xss(inst):
    if inst['xss2'] and inst['xss3']:
        return OK, 'corrigé'
    if inst['xss2']:
        return WARN, 'partiel (OCB 1378)'
    if majeure(inst['version']) >= 16:
        return KO, 'git pull'
    lx = version_libxml2(inst['libxml2'])
    if lx is None:
        return KO, 'libxml2 ?'
    if lx >= (2, 10, 0):
        return WARN, 'libxml2 %s' % inst['libxml2']
    return KO, 'libxml2 %s' % inst['libxml2']


def statut_rotation(logs):
    if logs is None or 'rotation' not in logs:
        return WARN, '?'
    if not logs['fichiers']:
        return WARN, 'aucun journal'
    if logs['rotation']:
        return OK, logs['rotation']
    return KO, 'aucune (%d Mo)' % logs['mo']


def statut_logs(logs):
    """Colonne Traces : motifs dans les journaux et messages piégés en base ; couleur la plus grave."""
    if logs is None:
        return WARN, '?'
    etats, textes = [], []
    if 'fichiers' in logs and not logs['fichiers']:
        etats.append(WARN); textes.append('aucun journal')
    elif 'fort' not in logs:
        etats.append(WARN); textes.append('journaux ?')
    elif logs['fort']:
        etats.append(KO); textes.append('%d forts, %d faibles' % (logs['fort'], logs['faible']))
    elif logs['faible']:
        etats.append(WARN); textes.append('%d faibles' % logs['faible'])
    msg = logs.get('msg')
    if logs.get('msg_raison') == 'arrete':
        etats.append(INFO); textes.append('PG arrêté')
    elif msg:
        etats.append(WARN); textes.append('%d msg' % msg)
    elif msg is None or logs.get('msg_err'):
        etats.append(WARN); textes.append('msg ?')
    if not textes:
        return OK, 'rien'
    etat = next(e for e in (KO, WARN, INFO) if e in etats)
    return etat, ', '.join(textes)


PORTS_WEB = {80, 443, 8069, 8072}


def pare_feu(logs):
    """ufw filtrant : actif, entrées refusées par défaut, et aucune règle ouverte à tous (« Anywhere ») sur un port
    web, sur tous les ports, une plage ou un profil d'application (en cas de doute : non filtrant)."""
    lignes = (logs or {}).get('ufw') or []
    if 'Status: active' not in lignes:
        return False
    if not any(l.startswith('Default:') and re.search(r'(deny|reject) \(incoming\)', l) for l in lignes):
        return False
    for l in lignes:
        champs = re.split(r'\s{2,}', l)  # « À  Action  De »
        if len(champs) != 3 or not champs[1].startswith(('ALLOW', 'LIMIT')) or not champs[2].startswith('Anywhere'):
            continue
        m = re.fullmatch(r'([\d,]+)(/(tcp|udp))?( \(v6\))?', champs[0])
        if not m or PORTS_WEB & {int(p) for p in m.group(1).split(',') if p}:
            return False
    return True


def attenue(statut):
    """Pare-feu filtrant : 🔴 et 🟠 passent en 🟡, avec « (pare-feu) »."""
    etat, texte = statut
    if etat in (KO, WARN):
        return INFO, '%s (pare-feu)' % texte
    return statut


def traiter(serveur):
    """Retourne la liste des lignes (une par installation Odoo) du serveur."""
    client       = serveur['partner_id'] and serveur['partner_id'][1] or ''
    nom          = serveur['name']
    service_name = serveur['service_id'] and serveur['service_id'][1] or ''
    acces_ssh    = serveur.get('acces_ssh')
    domaine      = acces_ssh.split('@', 1)[1] if acces_ssh and '@' in acces_ssh else nom
    ports = get_ports_statut(domaine)
    base  = base_web(domaine, ports)
    if base:
        http = {
            'bdd':    get_db_manager_statut(base),
            'reset':  get_reset_password_statut(base),
            'signup': get_signup_statut(base),
        }
    else:
        http = {k: (OK, 'pas de web') for k in ('bdd', 'reset', 'signup')}
    http['ports'] = get_acces_statut(domaine, base, ports)
    entete = {'client': client, 'serveur': nom, 'service': service_name, 'releve': MAINTENANT, 'echec': False}
    if not acces_ssh:
        installs, logs, erreur = [], None, 'SSH non configuré'
    else:
        installs, logs, erreur = releve_ssh(acces_ssh)
    if not installs:
        msg = (WARN, erreur or 'aucune installation /opt/odoo*')
        # serveur injoignable (ex. VPN non lancé) : la ligne déjà dans le relevé Markdown sera gardée
        entete['echec'] = bool(erreur and (erreur.startswith('ERREUR SSH') or erreur.startswith('délai')))
        return [dict(entete, **http, version=service_name, date=msg, sqli=msg, xss=msg,
                     logs=statut_logs(logs), rotation=statut_rotation(logs))]
    filtrant = pare_feu(logs)
    if filtrant:
        http = {k: attenue(v) for k, v in http.items()}
    lignes = []
    for inst in installs:
        v = inst['version']
        if len(installs) > 1:
            v += ' (%s)' % inst['dossier'].rstrip('/').split('/')[-1]
        sqli, xss = statut_sqli(inst), statut_xss(inst)
        if filtrant:
            sqli, xss = attenue(sqli), attenue(xss)
        lignes.append(dict(entete, **http, version=v, date=statut_date(inst['date']),
                           sqli=sqli, xss=xss, logs=statut_logs(logs),
                           rotation=statut_rotation(logs)))
    return lignes


COLONNES = [
    # (clé, titre terminal, largeur, titre Markdown)
    ('client',  'Client',        28, 'Client'),
    ('serveur', 'Serveur',       34, 'Serveur'),
    ('version', 'Version',       16, 'Version'),
    ('date',    'Sources',       14, 'Sources'),
    ('bdd',     'Gestion BDD',   23, 'Gestion des bases'),
    ('reset',   'Reset pwd',     20, 'Réinit. mot de passe'),
    ('signup',  'Inscription',   20, 'Inscription'),
    ('ports',   'Accès direct',  30, 'Accès direct'),
    ('sqli',    'SQLi',          27, 'SQLi (130028)'),
    ('xss',     'XSS',           29, 'XSS (130029)'),
    ('logs',    'Traces',        28, 'Traces'),
    ('rotation', 'Rotation',     20, 'Rotation des journaux'),
    ('releve',  'Relevé',        16, 'Relevé'),
]


def s(txt, lg=0):
    txt = str(txt or '')
    if lg > 0:
        txt = (txt + ' ' * 100)[:lg]
    return txt


def cellule_terminal(val, lg):
    if isinstance(val, tuple):
        # le rond occupe 2 colonnes à l'écran pour 1 caractère Python
        return s('%s %s' % (ROND[val[0]], val[1]), lg - 1)
    return s(val, lg)


def cellule_md(val):
    # même affichage que dans le terminal
    if isinstance(val, tuple):
        return '%s %s' % (ROND[val[0]], val[1].replace('|', '/'))
    return str(val or '').replace('|', '/')


def lignes_existantes(chemin, serveurs_releves):
    """Lignes du tableau de FICHIER à garder (serveurs non relevés cette fois), au format Markdown."""
    try:
        with open(chemin, encoding='utf-8') as f:
            texte = f.read()
    except OSError:
        return []
    garder = []
    for ligne in texte.splitlines():
        if not ligne.startswith('| ') or ligne.startswith('| Client |') or ligne.startswith('| Serveur |'):
            continue
        cellules = [c.strip() for c in ligne.strip().strip('|').split(' | ')]
        if '<br>' in cellules[0]:  # client et serveur dans la même cellule
            cellules = cellules[0].split('<br>', 1) + cellules[1:]
        if len(cellules) < 2 or cellules[1] in serveurs_releves:
            continue
        if len(cellules) == len(COLONNES) - 1:  # ancien format, sans la colonne Rotation (avant Relevé)
            cellules.insert(len(cellules) - 1, ROND[WARN] + ' ?')
        if len(cellules) == len(COLONNES):
            garder.append(cellules)
    return garder


SECTION_MANUELLE = '## À faire'


def section_manuelle(chemin):
    """Section « À faire » écrite à la main en fin de page : gardée telle quelle à chaque relevé."""
    try:
        with open(chemin, encoding='utf-8') as f:
            texte = f.read()
    except OSError:
        return ''
    i = texte.find('\n' + SECTION_MANUELLE + '\n')
    return texte[i + 1:].rstrip() if i >= 0 else ''


def ecrire_markdown(chemin, lignes, partiel, noms_serveurs):
    """partiel (relevé filtré) : les lignes des autres serveurs sont gardées.
    Serveur en échec SSH : son ancienne ligne est gardée si elle existe.
    Section « À faire » en fin de page : écrite à la main, gardée."""
    manuelle = section_manuelle(chemin)
    reussis = {l['serveur'] for l in lignes if not l['echec']}
    anciennes = lignes_existantes(chemin, reussis)
    if not partiel:
        # relevé complet : seules les anciennes lignes des serveurs en échec sont gardées
        anciennes = [c for c in anciennes if c[1] in noms_serveurs]
    gardees = {c[1] for c in anciennes}
    nouvelles = [[cellule_md(l[c[0]]) for c in COLONNES] for l in lignes
                 if not (l['echec'] and l['serveur'] in gardees)]
    nouvelles += anciennes
    nouvelles.sort(key=lambda c: (c[0].lower(), c[1].lower()))
    md = [
        '# Suivi de la sécurité des serveurs Odoo',
        '',
        '[← Sécuriser Odoo](README.md)',
        '',
        'Page écrite par `verif-update-odoo.py --markdown` (dépôt `is_gestion_odoo18`, `scripts-externes`) : '
        '**ne pas la modifier à la main** (sauf la section « À faire » en fin de page, gardée par le script), '
        'relancer le script (avec un filtre pour les serveurs derrière un VPN : '
        'seules leurs lignes sont remplacées). Date de chaque ligne : colonne « Relevé ». '
        'Comment vérifier et corriger chaque point : [Sécuriser Odoo](README.md#points-à-vérifier-sur-un-serveur), '
        '[CVE Odoo du 23/11/2026](../../cve/Odoo-2026-11-23.md).',
        '',
        # client et serveur dans la même cellule (« Client<br>serveur ») pour gagner une colonne
        '| Serveur | ' + ' | '.join(c[3] for c in COLONNES[2:]) + ' |',
        '|' + '---|' * (len(COLONNES) - 1),
    ]
    for cellules in nouvelles:
        md.append('| ' + ' | '.join(['%s<br>%s' % (cellules[0], cellules[1])] + cellules[2:]) + ' |')
    md += [
        '',
        '%d installation(s) Odoo.' % len(nouvelles),
        '',
        '## Lecture des colonnes',
        '',
        '| Colonne | Lecture |',
        '|---|---|',
        '| Sources | Date du dernier commit git (sinon de `release.py`) ; 🟠 plus de 6 mois, 🔴 plus de 2 ans |',
        '| Gestion des bases, réinit. mot de passe, inscription, accès direct | Testés depuis le poste ; 🟢 = bloqué ou fermé ; '
        '« pas de web » = ni HTTPS ni port 8069 ne répondent |',
        '| Gestion des bases | 🟢 BLOQUÉ = 403 ou 404 (fermé dans nginx) ; 🟡 affiché = opérations bloquées par Odoo '
        '(`list_db = False`), mais page encore affichée (pas fermée dans nginx) ; 🔴 OUVERT = gestionnaire utilisable |',
        '| Accès direct | 🔴 8069, 8072 = ports d\'Odoo joignables ; 🟠 IP = Odoo répond par l\'adresse IP (pas de bloc '
        '`default_server` dans nginx) ; 🟠 xmlrpc = `/xmlrpc` pas fermé dans nginx ([config nginx](../../linux/nginx.md#configuration-nginx)) |',
        '| « (pare-feu) » | 🟡 = 🔴 ou 🟠 atténué par ufw (actif, entrées refusées par défaut, aucun port web 80, 443, '
        '8069, 8072 ouvert à tous) ; le poste est une adresse autorisée, d\'où « OUVERT » ; failles encore atteignables '
        'depuis les adresses autorisées ; pare-feu autre qu\'ufw (iptables, OVH) non détecté |',
        '| SQLi | Patch de l\'avis dans `odoo/models.py` ; 17.0 et plus non concernés ; 12.0 et moins sans patch |',
        '| XSS | 16.0 et plus : correctif dans `odoo/tools/mail.py` (« stabilize » et « refine HTML normalization ») ; '
        '« partiel » = 16.0 à jour, second commit seulement dans la PR [OCA/OCB 1378](https://github.com/OCA/OCB/pull/1378). '
        '12.0 à 15.0 : 🟢 corrigé = report OCA/OCB ([1373](https://github.com/OCA/OCB/pull/1373) à '
        '[1376](https://github.com/OCA/OCB/pull/1376)) dans `odoo/tools/mail.py`. '
        'Sinon : version de libxml2 chargée par le Python d\'Odoo (🟠 ≥ 2.10 = atténué, 🔴 plus ancienne ou inconnue) |',
        '| Traces | Journaux : lignes du journal Odoo avec les motifs de l\'avis ; « forts » (`pg_sleep(3)`, `as z --`) = '
        'tentative quasi certaine ; « faibles » = erreur `InvalidTextRepresentation` dont la valeur refusée contient du SQL '
        '(`select`, `union`, `sleep`, `cast`, `--`), à regarder ; erreurs ordinaires non comptées. '
        'Base : « N msg » = messages (`mail_message`) avec du HTML piégé (`<script`, `javascript:`, `on…=`, `<iframe`, '
        'commentaires mal fermés…), toutes bases du serveur, faux positifs possibles (newsletter avec `<form>`, `<svg>`) : '
        'détail avec la requête de la [CVE Odoo du 23/11/2026](../../cve/Odoo-2026-11-23.md#traces-dattaque) ; '
        '« msg ? » = base non lue (pas d\'accès à PostgreSQL, plus de 30 s par base ou 60 s en tout) ; '
        '🟡 PG arrêté = PostgreSQL ne tourne pas (rien à lire) ; « journaux ? » = délai du relevé dépassé pendant '
        'la lecture des journaux (le reste de la ligne est relevé) |',
        '| Rotation des journaux | « logrotate » = fichier de `/etc/logrotate.d/` qui cite odoo ; « option Odoo » = '
        '`logrotate = True` dans la configuration d\'Odoo ; 🔴 aucune = taille du plus gros journal non compressé |',
        '',
        '## Corriger',
        '',
        'Exemples complets : [Odoo 13 avec nginx](../../epicerie-locavore-des-bourroches/odoo13-locavore.md) '
        '(Debian 10, tout en 🟢 sauf Sources), [Odoo 10 sans nginx](../../epicerie-locavore-des-bourroches/vps571502.md) '
        '(pare-feu ufw).',
        '',
        '| Colonne | Procédure |',
        '|---|---|',
        '| Sources | Ancienne Debian sans mises à jour : dépôts `archive.debian.org` et ELTS Freexian '
        '([exemple Debian 10](../../epicerie-locavore-des-bourroches/odoo13-locavore.md#mise-à-jour-du-25112026)) ; '
        'sources d\'Odoo : migration |',
        '| Gestion des bases | [Désactiver la gestion des bases](desactiver-gestion-des-bases.md) (`list_db = False`) et '
        '`/web/database` en 403 dans nginx ([config nginx](../../linux/nginx.md#configuration-nginx)) |',
        '| Réinit. mot de passe, inscription | [Page de connexion](page-de-connexion.md), '
        '[création de comptes](interdire-creation-comptes.md) ; Odoo 20 : module `is_interface_epuree` ([Sécuriser Odoo](README.md)) |',
        '| Accès direct | [Ports d\'Odoo](bloquer-ports-odoo.md) (`http_interface = 127.0.0.1`), '
        '[XML-RPC](bloquer-xmlrpc.md), bloc `default_server` ([config nginx](../../linux/nginx.md#configuration-nginx)) ; '
        'Odoo sans nginx : [pare-feu ufw](../../epicerie-locavore-des-bourroches/vps571502.md#pare-feu--accès-réservé-à-la-boutique-et-à-infosaône) |',
        '| SQLi, XSS | 16.0 à 20.0 : `git pull` ; 13.0 à 15.0 (12.0 pour XSS) : '
        '[Appliquer les correctifs](../../cve/Odoo-2026-11-23.md#appliquer-les-correctifs-130-à-150) ; '
        '10.0, 12.0 (SQLi) : pare-feu ou migration |',
        '| Rotation des journaux | [logrotate](../../linux/logrotate.md) |',
    ]
    if manuelle:
        md += ['', manuelle]
    with open(chemin, 'w', encoding='utf-8') as f:
        f.write('\n'.join(md) + '\n')


_domain = [
    ('active', '=', True),
    ('service_id.name', 'ilike', version if version else 'odoo'),
]
_fields = ['id', 'name', 'partner_id', 'acces_ssh', 'service_id']

serveurs = models.execute_kw(db, uid, password, 'is.serveur', 'search_read',
    [_domain],
    {
        'fields': _fields,
        'limit': 200,
        'order': 'partner_id,name',
    })
serveurs = [sv for sv in serveurs
            if not filtre
            or filtre in (sv['partner_id'] and sv['partner_id'][1] or '').lower()
            or filtre in sv['name'].lower()]

debut = time.time()
print('%d serveur(s) Odoo à relever, %d en parallèle...' % (len(serveurs), max(1, args.jobs)), file=sys.stderr, flush=True)
resultats = [None] * len(serveurs)
with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as ex:
    futures = {ex.submit(traiter, sv): i for i, sv in enumerate(serveurs)}
    for n, fut in enumerate(as_completed(futures), 1):
        i = futures[fut]
        try:
            resultats[i] = fut.result()
            etat = ', '.join('%s %s' % (l['version'], ROND[l['sqli'][0]]) for l in resultats[i])
        except Exception as e:
            resultats[i] = []
            etat = 'ERREUR : %s' % e
        print('[%*d/%d] %4.0f s  %s  %s' % (len(str(len(serveurs))), n, len(serveurs), time.time() - debut,
                                            s(serveurs[i]['name'], 40), etat),
              file=sys.stderr, flush=True)
        restants = [serveurs[j]['name'] for f, j in futures.items() if not f.done()]
        if 0 < len(restants) <= 3:
            print('         en cours : %s' % ', '.join(restants), file=sys.stderr, flush=True)
print(file=sys.stderr)
lignes = [l for r in resultats for l in r]

largeur = sum(c[2] + 1 for c in COLONNES)
print(' '.join(s(c[1], c[2]) for c in COLONNES))
print('-' * largeur)
for l in lignes:
    print(' '.join(cellule_terminal(l[c[0]], c[2]) for c in COLONNES))
print('-' * largeur)
print('%d serveur(s) Odoo, %d installation(s)' % (len(serveurs), len(lignes)))

if args.markdown:
    ecrire_markdown(args.markdown, lignes, bool(filtre or version), {sv['name'] for sv in serveurs})
    print('Relevé écrit dans %s' % args.markdown)
