#!/usr/bin/python3
# -*- coding: utf-8 -*-

import xmlrpc.client
import os
import sys
import argparse
import ssl
import urllib.request
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/../../../scripts-externes')
from config import URL as url, DB as db, USERNAME as username, PASSWORD as password

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode    = ssl.CERT_NONE

common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(url), context=ssl_context)
uid    = common.authenticate(db, username, password, {})
models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(url), context=ssl_context)

parser = argparse.ArgumentParser(description="Vérification des serveurs Odoo (port, version, sécurité, comptes...)")
parser.add_argument('filtre', nargs='?', default='', help='Filtre sur le nom du client ou du serveur')
parser.add_argument('--version', type=str, default='', help='Filtre sur la version de Odoo (Service), ex: odoo18')
args    = parser.parse_args()

filtre  = args.filtre.lower()
version = args.version.lower()


def s(txt, lg=0):
    txt = str(txt or '')
    if lg > 0:
        txt = (txt + ' ' * 100)[:lg]
    return txt


ROND_VERT   = '🟢'
ROND_ROUGE  = '🔴'
ROND_ORANGE = '🟠'


def sc(txt, lg=0):
    """Comme s(), mais compense la largeur visuelle des ronds de couleur (1 caractère Python = 2 colonnes à l'écran)."""
    return s(txt, lg - 1 if lg > 0 else lg)


def fetch_https(nom, path):
    """Retourne (content, http_code) ou (None, None) en cas d'erreur réseau."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request('https://%s%s' % (nom, path), headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            return resp.read().decode('utf-8', errors='replace'), resp.getcode()
    except urllib.error.HTTPError as e:
        return e.read().decode('utf-8', errors='replace'), e.code
    except Exception as e:
        return None, str(e)


def get_db_manager_statut(nom):
    """Vérifie si l'accès au gestionnaire de base de données Odoo est bloqué."""
    content, http_code = fetch_https(nom, '/web/database/manager')
    if content is None:
        return '%s ERREUR' % ROND_ORANGE
    if 'disabled by the administrator' in content or 'has been disabled' in content:
        return '%s BLOQUÉ' % ROND_VERT
    content_low = content.lower()
    if 'master password' in content_low and ('create database' in content_low or 'database_manager' in content_low):
        return '%s OUVERT !' % ROND_ROUGE
    return '%s HTTP %s (?)' % (ROND_ORANGE, http_code)


def get_reset_password_statut(nom):
    """Vérifie si la page de réinitialisation du mot de passe Odoo est accessible."""
    content, http_code = fetch_https(nom, '/web/reset_password')
    if content is None:
        return '%s ERREUR' % ROND_ORANGE
    content_low = content.lower()
    if 'oe_reset_password_form' in content_low:
        return '%s OUVERT !' % ROND_ROUGE
    if http_code in (403, 404) or 'not found' in content_low or 'oe_login_form' in content_low:
        return '%s BLOQUÉ' % ROND_VERT
    return '%s HTTP %s (?)' % (ROND_ORANGE, http_code)


def get_odoo_bin_date(acces_ssh):
    """Retourne la date de dernière modif de /opt/odooXX/odoo-bin (installation/MAJ Odoo)."""
    cmd = (
        "(ssh -o ConnectTimeout=10 -o BatchMode=yes %s "
        "'for d in /opt/odoo*/odoo-bin; do [ -f \"$d\" ] && date -r \"$d\" +%%Y-%%m-%%d && break; done') 2>&1"
        % acces_ssh
    )
    out = os.popen(cmd).read().strip()
    if not out:
        return 'N/A'
    ssh_error = next((l.strip() for l in out.splitlines()
                      if l.lower().startswith('ssh:')
                      or 'timed out' in l.lower()
                      or 'no route to host' in l.lower()
                      or 'connection refused' in l.lower()
                      or 'permission denied' in l.lower()), None)
    if ssh_error:
        return 'ERREUR SSH'
    return out.splitlines()[0].strip()


def format_date_maj(date_str):
    """Colore la date de MAJ Odoo : vert si < 6 mois, orange si < 2 ans, rouge sinon."""
    try:
        date_maj = datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        return '%s %s' % (ROND_ORANGE, date_str)
    now = datetime.now()
    if date_maj >= now - timedelta(days=182):
        return '%s %s' % (ROND_VERT, date_str)
    if date_maj >= now - timedelta(days=730):
        return '%s %s' % (ROND_ORANGE, date_str)
    return '%s %s' % (ROND_ROUGE, date_str)


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

print(s('Client', 35), s('Accès SSH', 40), s('Service', 10), s('Date MAJ Odoo', 16), s('Gestion BDD', 16), s('Reset Password', 16))
print('-' * 130)

nb = 0
for serveur in serveurs:
    client       = serveur['partner_id'] and serveur['partner_id'][1] or ''
    nom          = serveur['name']
    service_name = serveur['service_id'] and serveur['service_id'][1] or ''
    acces_ssh    = serveur.get('acces_ssh')

    if filtre and filtre not in client.lower() and filtre not in nom.lower():
        continue

    nb += 1
    domaine     = acces_ssh.split('@', 1)[1] if acces_ssh and '@' in acces_ssh else nom
    date_maj    = get_odoo_bin_date(acces_ssh) if acces_ssh else 'SSH non configuré'
    db_manager  = get_db_manager_statut(domaine)
    reset_pwd   = get_reset_password_statut(domaine)
    print(s(client, 35), s(acces_ssh, 40), s(service_name, 10), sc(format_date_maj(date_maj), 16), sc(db_manager, 16), sc(reset_pwd, 16))

print('-' * 130)
print('%d serveur(s) Odoo' % nb)
