#!/usr/bin/python3
# -*- coding: utf-8 -*-

import argparse
import xmlrpc.client
import socket
import subprocess
from config import URL, DB, USERNAME, PASSWORD

parser = argparse.ArgumentParser(description='Scan des ports des VPS')
parser.add_argument('filtre', nargs='?', default='', help='Filtre sur le nom du VPS (contient)')
args = parser.parse_args()


#PORTS   = [22, 25, 53, 80, 443, 5355, 5432, 8069, 8072]
PORTS   = [25, 5432, 8069, 8072]
TIMEOUT = 5  # secondes


def scan_ports(ip):
    """Retourne la liste des ports TCP accessibles depuis l'extérieur."""
    ouverts = []
    for port in PORTS:
        try:
            with socket.create_connection((ip, port), timeout=TIMEOUT):
                ouverts.append(port)
        except (socket.timeout, ConnectionRefusedError, OSError):
            pass
    return ouverts


def s(txt, lg=0):
    txt = str(txt) if txt else ''
    if lg > 0:
        txt = (txt + ' ' * 100)[:lg]
    return txt


common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(URL))
uid    = common.authenticate(DB, USERNAME, PASSWORD, {})
models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(URL))

domain = [('active', '=', True)]
if args.filtre:
    domain.append(('name', 'ilike', args.filtre))

serveurs = models.execute_kw(DB, uid, PASSWORD, 'is.serveur', 'search_read',
    [domain], {
        'fields': ['name', 'adresse_ip', 'partner_id', 'commentaire', 'acces_ssh'],
        'limit': 100,
        'order': 'partner_id',
    })

def ports_ssh(acces_ssh):
    """Via SSH : liste les ports en écoute sur une interface réseau (hors localhost)."""
    if not acces_ssh:
        return ''
    cmd = (
        "ssh -o ConnectTimeout=5 -o BatchMode=yes -o StrictHostKeyChecking=no "
        "%s \"ss -tlnp 2>/dev/null | awk 'NR>1 && !/127\\.0\\.0\\.1:|\\[::1\\]:/ && /[0-9]/ {print \\$4}' "
        "| awk -F: '{print \\$NF}' | sort -n | uniq\"" % acces_ssh
    )
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        ports = [p.strip() for p in result.stdout.splitlines() if p.strip()]
        return ', '.join(ports)
    except subprocess.TimeoutExpired:
        return 'timeout'
    except Exception as e:
        return str(e)


print(s('Nom', 40), s('Client', 28), s('IP', 17), s('Scan externe', 35), s('Ports SS (ss via SSH)', 55))
print('-' * 180)

for serveur in serveurs:
    ip        = serveur['adresse_ip'] or ''
    nom       = serveur['name']       or ''
    client    = serveur['partner_id'] and serveur['partner_id'][1] or ''
    acces_ssh = serveur['acces_ssh']  or ''

    if not ip:
        continue

    print(s(nom, 40), s(client, 28), s(ip, 17), '...', end='\r', flush=True)

    ports     = scan_ports(ip)
    ports_str = ', '.join(str(p) for p in ports) if ports else '—'
    ssh_ports = ports_ssh(acces_ssh)

    print(s(nom, 40), s(client, 28), s(ip, 17), s(ports_str, 35), s(ssh_ports or '—', 55))
