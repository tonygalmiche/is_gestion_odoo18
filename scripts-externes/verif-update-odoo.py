#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""Suivi de la sécurité des serveurs Odoo (is.serveur dont le service contient « odoo »), lecture seule.

Depuis le poste (HTTPS et ports) :
  - gestionnaire de bases, réinitialisation du mot de passe, inscription publique (/web/signup) ;
  - ports 8069 et 8072 joignables de l'extérieur.
Par SSH (une connexion par serveur, commandes en lecture seule), pour chaque installation /opt/odoo* :
  - version et date des sources (dernier commit git, sinon date de release.py) ;
  - CVE-2026-130028 (injection SQL, ≤ 16) : patch de l'avis présent dans odoo/models.py ;
  - CVE-2026-130029 (XSS) : correctif présent dans odoo/tools/mail.py (16.0 et plus, 2 commits :
    « stabilize » et « refine HTML normalization », le second absent d'Odoo 16.0, PR OCA/OCB 1378),
    sinon version de libxml2 chargée par le Python d'Odoo (≥ 2.10 : atténué) ;
  - journaux Odoo : lignes avec les motifs d'attaque de l'avis (forts : pg_sleep, « as z -- » ;
    faibles : InvalidTextRepresentation, aussi produits par des erreurs ordinaires) ; 500 derniers Mo
    des fichiers non compressés et fichiers compressés des 31 derniers jours, à basse priorité.

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

OK, KO, WARN = 'ok', 'ko', 'warn'
ROND     = {OK: '🟢', KO: '🔴', WARN: '🟠'}
ICONE_MD = {OK: '✅', KO: '❌', WARN: '⚠️'}

# Programme envoyé par SSH (bash -s), lecture seule.
# Sortie : « INSTALL;dossier;version;date;sqli;xss_stabilize;xss_refine;libxml2 » par installation,
#          puis « LOGS;forts;faibles;nb_fichiers ».
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
        X2=0; grep -qF "serialized.replace(b'--!>'" "${S}odoo/tools/mail.py" 2>/dev/null && X2=1
        X3=0; grep -qF '</?o:[^<>\n]*?>' "${S}odoo/tools/mail.py" 2>/dev/null && X3=1
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
FORT=0; FAIBLE=0; NB=0
if [ -n "$FICHIERS" ]; then
    NB=$(echo "$FICHIERS" | wc -l)
    # Une seule lecture des journaux, à basse priorité (serveurs de production) : 500 derniers Mo des fichiers
    # non compressés (journaux sans rotation de plusieurs Go), fichiers compressés des 31 derniers jours
    BAS="nice -n 19"
    command -v ionice >/dev/null && BAS="$BAS ionice -c3"
    TROUVE=$(for F in $FICHIERS; do
                 case "$F" in
                     *.gz) [ -n "$(find "$F" -mtime -31 2>/dev/null)" ] && zcat "$F" 2>/dev/null ;;
                     *)    tail -c 500000000 "$F" 2>/dev/null ;;
                 esac
             done | $BAS env LC_ALL=C grep -aE "pg_sleep\(3\)|as z --|InvalidTextRepresentation|invalid input syntax for type integer")
    FORT=$(printf '%s\n' "$TROUVE" | grep -cE "pg_sleep\(3\)|as z --")
    FAIBLE=$(printf '%s\n' "$TROUVE" | grep -cE "InvalidTextRepresentation|invalid input syntax for type integer")
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


def get_db_manager_statut(nom):
    """Gestionnaire de bases Odoo bloqué ou non."""
    content, http_code = fetch_https(nom, '/web/database/manager')
    if content is None:
        return WARN, 'ERREUR'
    if 'disabled by the administrator' in content or 'has been disabled' in content or http_code in (403, 404):
        return OK, 'BLOQUÉ'
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


def releve_ssh(acces_ssh):
    """Retourne (installations, journaux, erreur)."""
    try:
        res = subprocess.run(['ssh', '-o', 'ConnectTimeout=10', '-o', 'BatchMode=yes', acces_ssh, 'bash -s'],
                             input=PROGRAMME, capture_output=True, text=True, timeout=args.delai)
    except subprocess.TimeoutExpired:
        return [], None, 'délai dépassé (%d s)' % args.delai
    if res.returncode == 255:
        detail = res.stderr.strip().splitlines()[-1] if res.stderr.strip() else ''
        print('ERREUR SSH %s : %s' % (acces_ssh, detail), file=sys.stderr, flush=True)
        return [], None, 'ERREUR SSH'
    installs, logs = [], None
    for ligne in res.stdout.splitlines():
        champs = ligne.strip().split(';')
        if champs[0] == 'INSTALL' and len(champs) == 8:
            installs.append({'dossier': champs[1], 'version': champs[2], 'date': champs[3],
                             'sqli': champs[4] == '1', 'xss2': champs[5] == '1', 'xss3': champs[6] == '1',
                             'libxml2': champs[7]})
        elif champs[0] == 'LOGS' and len(champs) == 4:
            logs = {'fort': int(champs[1] or 0), 'faible': int(champs[2] or 0), 'fichiers': int(champs[3] or 0)}
    return installs, logs, None


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


def statut_logs(logs):
    if logs is None:
        return WARN, '?'
    if not logs['fichiers']:
        return WARN, 'aucun journal'
    if logs['fort']:
        return KO, '%d forts, %d faibles' % (logs['fort'], logs['faible'])
    if logs['faible']:
        return WARN, '%d faibles' % logs['faible']
    return OK, 'rien'


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
    http['ports'] = ports
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
                     logs=statut_logs(logs))]
    lignes = []
    for inst in installs:
        v = inst['version']
        if len(installs) > 1:
            v += ' (%s)' % inst['dossier'].rstrip('/').split('/')[-1]
        lignes.append(dict(entete, **http, version=v, date=statut_date(inst['date']),
                           sqli=statut_sqli(inst), xss=statut_xss(inst), logs=statut_logs(logs)))
    return lignes


COLONNES = [
    # (clé, titre terminal, largeur, titre Markdown)
    ('client',  'Client',        28, 'Client'),
    ('serveur', 'Serveur',       34, 'Serveur'),
    ('version', 'Version',       16, 'Version'),
    ('date',    'Sources',       14, 'Sources'),
    ('bdd',     'Gestion BDD',   15, 'Gestion des bases'),
    ('reset',   'Reset pwd',     15, 'Réinit. mot de passe'),
    ('signup',  'Inscription',   15, 'Inscription'),
    ('ports',   'Ports',         20, 'Ports 8069, 8072'),
    ('sqli',    'SQLi',          16, 'SQLi (130028)'),
    ('xss',     'XSS',           22, 'XSS (130029)'),
    ('logs',    'Journaux',      22, 'Journaux'),
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
    if isinstance(val, tuple):
        if val[0] == OK and val[1] in ('BLOQUÉ', 'FERMÉS', 'rien'):
            return ICONE_MD[OK]
        return '%s %s' % (ICONE_MD[val[0]], val[1].replace('|', '/'))
    return str(val or '').replace('|', '/')


def lignes_existantes(chemin, serveurs_releves):
    """Lignes du tableau de FICHIER à garder (serveurs non relevés cette fois), au format Markdown."""
    try:
        with open(chemin, encoding='utf-8') as f:
            texte = f.read()
    except OSError:
        return []
    m = re.search(r'Relevé du (\d\d/\d\d/\d{4} \d\d:\d\d)', texte)
    date_ancienne = m.group(1) if m else ''
    garder = []
    for ligne in texte.splitlines():
        if not ligne.startswith('| ') or ligne.startswith('| Client |') or ligne.startswith('| Serveur |'):
            continue
        cellules = [c.strip() for c in ligne.strip().strip('|').split(' | ')]
        if '<br>' in cellules[0]:  # client et serveur dans la même cellule
            cellules = cellules[0].split('<br>', 1) + cellules[1:]
        if len(cellules) < 2 or cellules[1] in serveurs_releves:
            continue
        if len(cellules) == len(COLONNES) - 1:  # ancien format, sans la colonne Relevé
            cellules.append(date_ancienne)
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
        '| Sources | Date du dernier commit git (sinon de `release.py`) ; ⚠️ plus de 6 mois, ❌ plus de 2 ans |',
        '| Gestion des bases, réinit. mot de passe, inscription, ports | Testés depuis le poste ; ✅ = bloqué ou fermé ; '
        '« pas de web » = ni HTTPS ni port 8069 ne répondent |',
        '| SQLi | Patch de l\'avis dans `odoo/models.py` ; 17.0 et plus non concernés ; 12.0 et moins sans patch |',
        '| XSS | 16.0 et plus : correctif dans `odoo/tools/mail.py` (« stabilize » et « refine HTML normalization ») ; '
        '« partiel » = 16.0 à jour, second commit seulement dans la PR [OCA/OCB 1378](https://github.com/OCA/OCB/pull/1378). '
        'Avant 16.0 : version de libxml2 chargée par le Python d\'Odoo (⚠️ ≥ 2.10 = atténué, ❌ plus ancienne ou inconnue) |',
        '| Journaux | Lignes du journal Odoo avec les motifs de l\'avis ; « forts » (`pg_sleep(3)`, `as z --`) = tentative '
        'quasi certaine ; « faibles » (`InvalidTextRepresentation`) = aussi des erreurs ordinaires, à regarder |',
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
