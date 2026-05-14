#!/usr/bin/python3
# -*- coding: utf-8 -*-

import xmlrpc.client
import os
import sys
import argparse
import time
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/../../../scripts-externes')
from config import URL as url, DB as db, USERNAME as username, PASSWORD as password

common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(url))
uid    = common.authenticate(db, username, password, {})
models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(url))

parser = argparse.ArgumentParser(description='Vérification des mises à jour des VPS')
parser.add_argument('filtre',         nargs='?', default='', help='Filtre sur le nom du client ou du VPS')
parser.add_argument('--update',       action='store_true', help='Lancer apt-get update')
parser.add_argument('--dist-upgrade', action='store_true', help='Lancer apt-get dist-upgrade')
parser.add_argument('--reboot',       action='store_true', help='Redémarrer le serveur après le dist-upgrade (implique --dist-upgrade)')
parser.add_argument('--add-action',   action='store_true', help='Enregistrer l\'action dans Odoo (is.serveur.action)')
args    = parser.parse_args()

if not args.update and not args.dist_upgrade and not args.reboot:
    parser.print_help()
    sys.exit(0)

filtre     = args.filtre.lower()
do_update  = args.update
upgrade    = args.dist_upgrade or args.reboot
reboot     = args.reboot
add_action = args.add_action

if reboot:
    action_label = 'apt-get dist-upgrade + reboot'
elif upgrade:
    action_label = 'apt-get dist-upgrade'
elif do_update:
    action_label = 'apt-get update'
else:
    action_label = 'Vérification mises à jour'


def s(txt, lg=0):
    txt = str(txt or '')
    if lg > 0:
        txt = (txt + ' ' * 100)[:lg]
    return txt


serveurs = models.execute_kw(db, uid, password, 'is.serveur', 'search_read',
    [[('active', '=', True)]],
    {
        'fields': ['id', 'name', 'adresse_ip', 'partner_id', 'acces_ssh', 'systeme_id'],
        'limit': 200,
        'order': 'partner_id,name',
    })

print(s('Client', 30), s('SSH', 40), s('Paquets à mettre à jour', 0))
print('-' * 120)

for serveur in serveurs:
    if not serveur['acces_ssh']:
        continue

    acces_ssh = serveur['acces_ssh']
    client    = serveur['partner_id'] and serveur['partner_id'][1] or ''
    nom       = serveur['name']

    if filtre and filtre not in client.lower() and filtre not in nom.lower():
        continue

    # apt-get update puis liste des paquets upgradables
    # Les lignes de paquets contiennent toujours un '/' (ex: bash/bookworm ...)
    if do_update:
        cmd_upd = (
            "(ssh -o ConnectTimeout=60 -o BatchMode=yes %s "
            "'apt-get update -qq 2>/dev/null') 2>&1" % acces_ssh
        )
        os.popen(cmd_upd).read()
        cmd = (
            "(ssh -o ConnectTimeout=10 -o BatchMode=yes %s "
            "'apt list --upgradable 2>/dev/null') 2>&1" % acces_ssh
        )
    else:
        cmd = (
            "(ssh -o ConnectTimeout=60 -o BatchMode=yes %s "
            "'apt-get update -qq 2>/dev/null && apt list --upgradable 2>/dev/null') 2>&1" % acces_ssh
        )
    lines   = os.popen(cmd).read().splitlines()
    paquets = [l.strip() for l in lines if '/' in l]  # seules les vraies lignes de paquets

    commentaire_lines = []
    if not paquets:
        print(s(client, 30), s(acces_ssh, 40), 'OK - à jour')
        commentaire_lines.append('OK - à jour')
        if reboot:
            # Vérifier qu'aucun apt/dpkg n'est en cours via le verrou
            cmd_check = (
                "(ssh -o ConnectTimeout=10 -o BatchMode=yes %s "
                "\"fuser /var/lib/dpkg/lock-frontend /var/lib/apt/lists/lock 2>/dev/null\") 2>&1" % acces_ssh
            )
            pids = os.popen(cmd_check).read().strip()
            if pids:
                msg = 'REBOOT ANNULÉ : apt/dpkg en cours (pid %s)' % pids.replace('\n', ',')
                print(' ' * 62, '>>>', msg)
                commentaire_lines.append(msg)
            else:
                print(' ' * 62, '>>> Reboot en cours...')
                cmd_reboot = (
                    "(ssh -o ConnectTimeout=10 -o BatchMode=yes %s "
                    "'nohup reboot &>/dev/null &') 2>&1" % acces_ssh
                )
                os.popen(cmd_reboot).read()
                print(' ' * 62, '>>> Reboot lancé')
                commentaire_lines.append('Reboot lancé')
    else:
        print(s(client, 30), s(acces_ssh, 40), '%d paquet(s) à mettre à jour :' % len(paquets))
        commentaire_lines.append('%d paquet(s) à mettre à jour :' % len(paquets))
        for p in paquets:
            print(' ' * 62, p)
            commentaire_lines.append(p)
        if upgrade:
            print(' ' * 62, '>>> Lancement de apt-get dist-upgrade...')
            t0 = time.time()
            cmd_upgrade = (
                "(ssh -o ConnectTimeout=300 -o BatchMode=yes %s "
                "'DEBIAN_FRONTEND=noninteractive apt-get dist-upgrade -y 2>&1') 2>&1" % acces_ssh
            )
            out = os.popen(cmd_upgrade).read()
            for line in out.splitlines():
                print(' ' * 62, line)
            print(' ' * 62, '>>> Durée : %.1fs' % (time.time() - t0))
            # Vérification après upgrade
            cmd_verif = (
                "(ssh -o ConnectTimeout=10 -o BatchMode=yes %s "
                "'apt list --upgradable 2>/dev/null') 2>&1" % acces_ssh
            )
            reste = [l.strip() for l in os.popen(cmd_verif).read().splitlines() if '/' in l]
            if reste:
                commentaire_lines.append('ATTENTION : %d paquet(s) toujours en attente :' % len(reste))
                print(' ' * 62, '>>> ATTENTION : %d paquet(s) toujours en attente :' % len(reste))
                for p in reste:
                    print(' ' * 62, '  ', p)
                    commentaire_lines.append(p)
            else:
                print(' ' * 62, '>>> Upgrade terminé - serveur à jour')
                commentaire_lines.append('Upgrade terminé - serveur à jour')
            if reboot:
                print(' ' * 62, '>>> Reboot en cours...')
                cmd_reboot = (
                    "(ssh -o ConnectTimeout=10 -o BatchMode=yes %s "
                    "'nohup reboot &>/dev/null &') 2>&1" % acces_ssh
                )
                os.popen(cmd_reboot).read()
                print(' ' * 62, '>>> Reboot lancé')
                commentaire_lines.append('Reboot lancé')

    if add_action and commentaire_lines:
        today     = datetime.now().strftime('%Y-%m-%d')
        vals      = {
            'serveur_id': serveur['id'],
            'date_heure': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
            'action':     action_label,
            'commentaire': '\n'.join(commentaire_lines),
        }
        existants = models.execute_kw(db, uid, password, 'is.serveur.action', 'search',
            [[('serveur_id', '=', serveur['id']),
              ('date_heure', '>=', today + ' 00:00:00'),
              ('date_heure', '<=', today + ' 23:59:59')]])
        if existants:
            models.execute_kw(db, uid, password, 'is.serveur.action', 'write', [existants, vals])
        else:
            models.execute_kw(db, uid, password, 'is.serveur.action', 'create', [vals])
