#!/usr/bin/python3
# -*- coding: utf-8 -*-

import xmlrpc.client
import os
import sys
import argparse
import time
import urllib.request
import ssl
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
parser.add_argument('--dirty-frag',   action='store_true', help='Vérifier/appliquer la mitigation DirtyFrag (CVE-2026-43284/43500)')
parser.add_argument('--get-system',            action='store_true', help='Récupérer le système, la version, le noyau et sa date de mise à jour')
parser.add_argument('--get-database-manager',  action='store_true', help='Vérifier si l\'accès au gestionnaire de base de données Odoo est bloqué')
parser.add_argument('--get-reset-password',    action='store_true', help='Vérifier si la page de réinitialisation du mot de passe Odoo est accessible')
parser.add_argument('--add-action',            action='store_true', help='Enregistrer l\'action dans Odoo (is.serveur.action)')
parser.add_argument('--script',                type=str, help='Copier et exécuter un script local sur les serveurs (ex: CIFSwitch.sh)')
args    = parser.parse_args()

if not args.update and not args.dist_upgrade and not args.reboot and not args.dirty_frag and not args.get_system and not args.get_database_manager and not args.get_reset_password and not args.script:
    parser.print_help()
    sys.exit(0)

filtre          = args.filtre.lower()
do_update       = args.update
upgrade         = args.dist_upgrade or args.reboot
reboot          = args.reboot
dirty_frag      = args.dirty_frag
get_system      = args.get_system
get_db_manager    = args.get_database_manager
get_reset_passwd  = args.get_reset_password
add_action        = args.add_action
script_path       = args.script

if reboot:
    action_label = 'apt-get dist-upgrade + reboot'
elif upgrade:
    action_label = 'apt-get dist-upgrade'
elif do_update:
    action_label = 'apt-get update'
elif dirty_frag:
    action_label = 'Mitigation DirtyFrag'
elif get_system:
    action_label = 'Récupération info système'
elif get_db_manager:
    action_label = 'Vérification gestionnaire BDD'
elif get_reset_passwd:
    action_label = 'Vérification reset password'
elif script_path:
    action_label = 'Exécution script : %s' % script_path
else:
    action_label = 'Vérification mises à jour'


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


def s(txt, lg=0):
    txt = str(txt or '')
    if lg > 0:
        txt = (txt + ' ' * 100)[:lg]
    return txt


def save_action(serveur_id, label, lines):
    """Crée ou met à jour une is.serveur.action pour aujourd'hui (même serveur + même action)."""
    if not add_action or not lines:
        return
    today = datetime.now().strftime('%Y-%m-%d')
    vals  = {
        'serveur_id': serveur_id,
        'date_heure': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
        'action':     label,
        'commentaire': '\n'.join(lines),
    }
    existants = models.execute_kw(db, uid, password, 'is.serveur.action', 'search',
        [[('serveur_id', '=', serveur_id),
          ('action',     '=', label),
          ('date_heure', '>=', today + ' 00:00:00'),
          ('date_heure', '<=', today + ' 23:59:59')]])
    if existants:
        models.execute_kw(db, uid, password, 'is.serveur.action', 'write', [existants, vals])
    else:
        models.execute_kw(db, uid, password, 'is.serveur.action', 'create', [vals])


# Définir le domain et fields par défaut
_domain = [
    ('active', '=', True),
    ('upgrade_auto', '=', True),
    ('date_debut_maintenance', '!=', False),
]
_fields = ['id', 'name', 'adresse_ip', 'partner_id', 'acces_ssh', 'systeme_id']

# Modifier le domain et fields selon les options
if get_db_manager or get_reset_passwd:
    _domain.append(('service_id.name', 'ilike', 'odoo'))


serveurs = models.execute_kw(db, uid, password, 'is.serveur', 'search_read',
    [_domain],
    {
        'fields': _fields,
        'limit': 200,
        'order': 'service_id,partner_id,name' if (get_db_manager or get_reset_passwd) else ('partner_id,name' if not script_path else 'partner_id,name'),
    })

# Vérifier que le script local existe si --script est fourni
if script_path and not os.path.isfile(script_path):
    print("ERREUR : Le script '%s' n'existe pas" % script_path)
    sys.exit(1)

script_basename = os.path.basename(script_path) if script_path else None

print(s('Client', 30), s('SSH', 40), s('Résultat', 0))
print('-' * 120)

for serveur in serveurs:
    client = serveur['partner_id'] and serveur['partner_id'][1] or ''
    nom    = serveur['name']

    if filtre and filtre not in client.lower() and filtre not in nom.lower():
        continue

    # --- Vérification URL Odoo (database manager / reset password) ---
    if get_db_manager or get_reset_passwd:
        service_name = serveur.get('service_id') and serveur['service_id'][1] or ''
        if get_db_manager:
            path = '/web/database/manager'
        else:
            path = '/web/reset_password'
        content, http_code = fetch_https(nom, path)
        if content is None:
            print(s(client, 30), s(nom, 40), '[%s] ERREUR : %s' % (service_name, http_code))
            continue
        if get_db_manager:
            if 'disabled by the administrator' in content or 'has been disabled' in content:
                statut = 'BLOQUÉ (disabled by administrator)'
            elif 'database' in content.lower() and 'manager' in content.lower():
                statut = 'OUVERT - accès non protégé !'
            else:
                statut = 'Réponse HTTP %s (contenu inattendu)' % http_code
        else:
            if http_code in (403, 404) or 'not found' in content.lower():
                statut = 'BLOQUÉ (HTTP %s)' % http_code
            elif 'reset' in content.lower() and 'password' in content.lower():
                statut = 'OUVERT - accès non protégé !'
            else:
                statut = 'Réponse HTTP %s (contenu inattendu)' % http_code
        print(s(client, 30), s(nom, 40), '[%s] %s' % (service_name, statut))
        save_action(serveur['id'], action_label, [statut])
        continue

    # --- Exécution d'un script ---
    if script_path:
        if not serveur.get('acces_ssh'):
            print(s(client, 30), s(nom, 40), 'SSH non configuré')
            continue
        
        acces_ssh = serveur['acces_ssh']
        commentaire_lines = []
        remote_path = '/tmp/%s' % script_basename
        
        # Copier et exécuter le script
        cmd_scp = 'scp -o ConnectTimeout=10 -o BatchMode=yes "%s" "%s:%s" 2>&1' % (script_path, acces_ssh, remote_path)
        scp_out = os.popen(cmd_scp).read().strip()
        
        if 'ssh:' in scp_out.lower() or 'permission denied' in scp_out.lower() or 'no such' in scp_out.lower():
            print(s(client, 30), s(acces_ssh, 40), 'ERREUR SCP : %s' % scp_out)
            save_action(serveur['id'], action_label, ['ERREUR SCP : %s' % scp_out])
            continue
        
        cmd_exec = 'ssh -o ConnectTimeout=30 -o BatchMode=yes %s "bash %s; rm %s" 2>&1' % (acces_ssh, remote_path, remote_path)
        exec_out = os.popen(cmd_exec).read().strip()
        
        if not exec_out:
            print(s(client, 30), s(acces_ssh, 40), 'Pas de résultat')
            commentaire_lines.append('Pas de résultat')
        else:
            # Afficher seulement la première ligne du résultat
            result_line = exec_out.splitlines()[0] if exec_out.splitlines() else 'Pas de résultat'
            print(s(client, 30), s(acces_ssh, 40), result_line)
            commentaire_lines.append(result_line)
        
        save_action(serveur['id'], action_label, commentaire_lines)
        continue

    if not serveur.get('acces_ssh'):
        continue

    acces_ssh = serveur['acces_ssh']

    # --- Récupération info système ---
    if get_system:
        cmd_sys = (
            "(ssh -o ConnectTimeout=10 -o BatchMode=yes %s "
            "'echo SYS:$(lsb_release -si 2>/dev/null); "
            "echo VER:$(lsb_release -sc 2>/dev/null); "
            "echo KER:$(uname -r); "
            "echo KDT:$(date -r /boot/vmlinuz-$(uname -r) +%%Y-%%m-%%d 2>/dev/null)') 2>&1" % acces_ssh
        )
        out = os.popen(cmd_sys).read().strip()
        infos = {}
        for line in out.splitlines():
            if ':' in line:
                key, _, val = line.partition(':')
                infos[key.strip()] = val.strip()
        sys_name   = infos.get('SYS', 'N/A')
        sys_ver    = infos.get('VER', 'N/A')
        kernel     = infos.get('KER', 'N/A')
        kernel_dt  = infos.get('KDT', 'N/A')
        ssh_error  = next((l.strip() for l in out.splitlines()
                           if l.lower().startswith('ssh:')
                           or 'timed out' in l.lower()
                           or 'no route to host' in l.lower()
                           or 'connection refused' in l.lower()
                           or 'permission denied' in l.lower()), None)
        if ssh_error:
            print(s(client, 30), s(acces_ssh, 40), 'ERREUR SSH : %s' % ssh_error)
        else:
            kernel_str   = '%s(%s)' % (kernel, kernel_dt) if kernel_dt and kernel_dt != 'N/A' else kernel
            info_systeme = '%s %s - noyau: %s' % (sys_name, sys_ver, kernel_str)
            print(s(client, 30), s(acces_ssh, 40),
                  '%-10s %-12s  noyau: %s' % (sys_name, sys_ver, kernel_str))
            models.execute_kw(db, uid, password, 'is.serveur', 'write',
                              [[serveur['id']], {'info_systeme': info_systeme}])
            save_action(serveur['id'], action_label, [info_systeme])
        continue

    # --- DirtyFrag (CVE-2026-43284 / CVE-2026-43500) ---
    # Élévation de privilèges locale (LPE) dans le noyau Linux via algif_aead.
    # Mitigation : bloquer le chargement des modules esp4, esp6 et rxrpc via modprobe,
    # décharger ces modules s'ils sont déjà en mémoire, puis vider le page cache
    # pour éliminer toute page potentiellement corrompue.
    # Ref : https://github.com/V4bel/dirtyfrag
    if dirty_frag:
        commentaire_lines = []
        cmd_check = (
            "(ssh -o ConnectTimeout=10 -o BatchMode=yes %s "
            "'test -f /etc/modprobe.d/dirtyfrag.conf && echo OK || echo ABSENT') 2>&1" % acces_ssh
        )
        etat = os.popen(cmd_check).read().strip()
        if etat not in ('OK', 'ABSENT'):
            print(s(client, 30), s(acces_ssh, 40), 'ERREUR SSH : %s' % (etat or 'pas de réponse'))
            continue
        if etat == 'OK':
            print(s(client, 30), s(acces_ssh, 40), 'DirtyFrag : mitigation déjà appliquée')
            commentaire_lines.append('Mitigation déjà présente')
        else:
            print(s(client, 30), s(acces_ssh, 40), 'DirtyFrag : application de la mitigation...')
            cmd_fix = (
                "(ssh -o ConnectTimeout=30 -o BatchMode=yes %s "
                "\"sh -c \\\"printf 'install esp4 /bin/false\\\\ninstall esp6 /bin/false\\\\ninstall rxrpc /bin/false\\\\n' "
                "> /etc/modprobe.d/dirtyfrag.conf; rmmod esp4 esp6 rxrpc 2>/dev/null; "
                "echo 3 | tee /proc/sys/vm/drop_caches > /dev/null; true\\\"\") 2>&1" % acces_ssh
            )
            out = os.popen(cmd_fix).read().strip()
            # Vérifier que le fichier a bien été créé
            cmd_verif = (
                "(ssh -o ConnectTimeout=10 -o BatchMode=yes %s "
                "'test -f /etc/modprobe.d/dirtyfrag.conf && echo OK || echo ECHEC') 2>&1" % acces_ssh
            )
            verif = os.popen(cmd_verif).read().strip()
            if verif == 'OK':
                print(' ' * 62, '>>> Mitigation appliquée avec succès')
                commentaire_lines.append('Mitigation appliquée')
            else:
                print(' ' * 62, '>>> ECHEC application mitigation')
                if out:
                    print(' ' * 62, out)
                commentaire_lines.append('ECHEC mitigation')
                if out:
                    commentaire_lines.append(out)
        save_action(serveur['id'], action_label, commentaire_lines)
        continue

    # --- apt update / upgrade ---
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

    # Détecter les erreurs SSH (connexion refusée, timeout, etc.)
    ssh_error = next((l.strip() for l in lines if l.lower().startswith('ssh:')
                      or 'timed out' in l.lower()
                      or 'no route to host' in l.lower()
                      or 'connection refused' in l.lower()
                      or 'permission denied' in l.lower()), None)
    if ssh_error:
        print(s(client, 30), s(acces_ssh, 40), 'ERREUR SSH : %s' % ssh_error)
        save_action(serveur['id'], action_label, ['ERREUR SSH : %s' % ssh_error])
        continue

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

    save_action(serveur['id'], action_label, commentaire_lines)
