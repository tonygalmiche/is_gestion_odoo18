#!/usr/bin/python3
# -*- coding: utf-8 -*-

import xmlrpc.client
import os
import sys
import argparse
import time
import urllib.request
import ssl
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/../../../scripts-externes')
from config import URL as url, DB as db, USERNAME as username, PASSWORD as password

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode    = ssl.CERT_NONE

common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(url), context=ssl_context)
uid    = common.authenticate(db, username, password, {})
models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(url), context=ssl_context)

# ServerProxy partage une seule connexion HTTP : un seul appel XML-RPC à la fois entre les threads
odoo_lock = threading.Lock()

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
parser.add_argument('--script',                type=str, help='Copier et exécuter un script local sur les serveurs (ex: script/CIFSwitch.sh, script/fail2ban-ip-bannies.sh)')
parser.add_argument('--jobs',                  type=int, default=10, help='Nombre de serveurs traités en parallèle (défaut: 10). --dist-upgrade et --reboot restent séquentiels')
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
    with odoo_lock:
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


def nom_client(serveur):
    return serveur['partner_id'] and serveur['partner_id'][1] or ''


def traiter(serveur, direct=False):
    """Traite un serveur. En mode direct, affiche au fil de l'eau ; sinon retourne les lignes à afficher."""
    sortie = []

    def p(*a):
        if direct:
            print(*a, flush=True)
        else:
            sortie.append(' '.join(str(x) for x in a))

    client = nom_client(serveur)
    nom    = serveur['name']

    # --- Vérification URL Odoo (database manager / reset password) ---
    if get_db_manager or get_reset_passwd:
        service_name = serveur.get('service_id') and serveur['service_id'][1] or ''
        if get_db_manager:
            path = '/web/database/manager'
        else:
            path = '/web/reset_password'
        content, http_code = fetch_https(nom, path)
        if content is None:
            p(s(client, 30), s(nom, 40), '[%s] ERREUR : %s' % (service_name, http_code))
            return sortie
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
        p(s(client, 30), s(nom, 40), '[%s] %s' % (service_name, statut))
        save_action(serveur['id'], action_label, [statut])
        return sortie

    # --- Exécution d'un script ---
    if script_path:
        if not serveur.get('acces_ssh'):
            p(s(client, 30), s(nom, 40), 'SSH non configuré')
            return sortie
        
        acces_ssh = serveur['acces_ssh']
        commentaire_lines = []
        remote_path = '/tmp/%s' % script_basename
        
        # Copier et exécuter le script
        cmd_scp = 'scp -o ConnectTimeout=10 -o BatchMode=yes "%s" "%s:%s" 2>&1' % (script_path, acces_ssh, remote_path)
        scp_out = os.popen(cmd_scp).read().strip()
        
        if 'ssh:' in scp_out.lower() or 'permission denied' in scp_out.lower() or 'no such' in scp_out.lower():
            p(s(client, 30), s(acces_ssh, 40), 'ERREUR SCP : %s' % scp_out)
            save_action(serveur['id'], action_label, ['ERREUR SCP : %s' % scp_out])
            return sortie
        
        cmd_exec = 'ssh -o ConnectTimeout=30 -o BatchMode=yes %s "bash %s; rm %s" 2>&1' % (acces_ssh, remote_path, remote_path)
        exec_out = os.popen(cmd_exec).read().strip()
        
        if not exec_out:
            p(s(client, 30), s(acces_ssh, 40), 'Pas de résultat')
            commentaire_lines.append('Pas de résultat')
        else:
            # Afficher seulement la première ligne du résultat
            result_line = exec_out.splitlines()[0] if exec_out.splitlines() else 'Pas de résultat'
            p(s(client, 30), s(acces_ssh, 40), result_line)
            commentaire_lines.append(result_line)
        
        save_action(serveur['id'], action_label, commentaire_lines)
        return sortie

    if not serveur.get('acces_ssh'):
        return sortie

    acces_ssh = serveur['acces_ssh']

    # --- Récupération info système ---
    if get_system:
        cmd_sys = (
            "(ssh -o ConnectTimeout=10 -o BatchMode=yes %s "
            "'echo SYS:$(lsb_release -si 2>/dev/null); "
            "echo VER:$(lsb_release -sc 2>/dev/null); "
            "echo KER:$(uname -r); "
            "echo KDT:$(date -r /boot/vmlinuz-$(uname -r) +%%Y-%%m-%%d 2>/dev/null); "
            "echo UPT:$(uptime -p 2>/dev/null)') 2>&1" % acces_ssh
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
        uptime_str = infos.get('UPT', 'N/A')
        ssh_error  = next((l.strip() for l in out.splitlines()
                           if l.lower().startswith('ssh:')
                           or 'timed out' in l.lower()
                           or 'no route to host' in l.lower()
                           or 'connection refused' in l.lower()
                           or 'permission denied' in l.lower()), None)
        if ssh_error:
            p(s(client, 30), s(acces_ssh, 40), 'ERREUR SSH : %s' % ssh_error)
        else:
            kernel_str   = '%s(%s)' % (kernel, kernel_dt) if kernel_dt and kernel_dt != 'N/A' else kernel
            info_systeme = '%s %s - noyau: %s - uptime: %s' % (sys_name, sys_ver, kernel_str, uptime_str)
            p(s(client, 30), s(acces_ssh, 40),
                  '%-10s %-12s  noyau: %s  uptime: %s' % (sys_name, sys_ver, kernel_str, uptime_str))
            with odoo_lock:
                models.execute_kw(db, uid, password, 'is.serveur', 'write',
                                  [[serveur['id']], {'info_systeme': info_systeme}])
            save_action(serveur['id'], action_label, [info_systeme])
        return sortie

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
            p(s(client, 30), s(acces_ssh, 40), 'ERREUR SSH : %s' % (etat or 'pas de réponse'))
            return sortie
        if etat == 'OK':
            p(s(client, 30), s(acces_ssh, 40), 'DirtyFrag : mitigation déjà appliquée')
            commentaire_lines.append('Mitigation déjà présente')
        else:
            p(s(client, 30), s(acces_ssh, 40), 'DirtyFrag : application de la mitigation...')
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
                p(' ' * 62, '>>> Mitigation appliquée avec succès')
                commentaire_lines.append('Mitigation appliquée')
            else:
                p(' ' * 62, '>>> ECHEC application mitigation')
                if out:
                    p(' ' * 62, out)
                commentaire_lines.append('ECHEC mitigation')
                if out:
                    commentaire_lines.append(out)
        save_action(serveur['id'], action_label, commentaire_lines)
        return sortie

    # --- apt update / upgrade ---
    # Simulation (--simulate : n'installe rien) de ce que ferait réellement dist-upgrade :
    # exclut les paquets en phasage Ubuntu et en hold, contrairement à 'apt list --upgradable'.
    # Seules les lignes 'Inst ' (non traduites) correspondent à des paquets à installer.
    if do_update:
        cmd_upd = (
            "(ssh -o ConnectTimeout=15 -o BatchMode=yes %s "
            "'apt-get update -qq 2>/dev/null') 2>&1" % acces_ssh
        )
        os.popen(cmd_upd).read()
        cmd = (
            "(ssh -o ConnectTimeout=10 -o BatchMode=yes %s "
            "'apt-get --simulate dist-upgrade 2>/dev/null') 2>&1" % acces_ssh
        )
    else:
        cmd = (
            "(ssh -o ConnectTimeout=15 -o BatchMode=yes %s "
            "'apt-get update -qq 2>/dev/null && apt-get --simulate dist-upgrade 2>/dev/null') 2>&1" % acces_ssh
        )
    lines   = os.popen(cmd).read().splitlines()
    paquets = [l.strip()[5:] for l in lines if l.startswith('Inst ')]  # seules les vraies lignes de paquets

    # Détecter les erreurs SSH (connexion refusée, timeout, etc.)
    ssh_error = next((l.strip() for l in lines if l.lower().startswith('ssh:')
                      or 'timed out' in l.lower()
                      or 'no route to host' in l.lower()
                      or 'connection refused' in l.lower()
                      or 'permission denied' in l.lower()), None)
    if ssh_error:
        p(s(client, 30), s(acces_ssh, 40), 'ERREUR SSH : %s' % ssh_error)
        save_action(serveur['id'], action_label, ['ERREUR SSH : %s' % ssh_error])
        return sortie

    commentaire_lines = []
    if not paquets:
        p(s(client, 30), s(acces_ssh, 40), 'OK - à jour')
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
                p(' ' * 62, '>>>', msg)
                commentaire_lines.append(msg)
            else:
                p(' ' * 62, '>>> Reboot en cours...')
                cmd_reboot = (
                    "(ssh -o ConnectTimeout=10 -o BatchMode=yes %s "
                    "'nohup reboot &>/dev/null &') 2>&1" % acces_ssh
                )
                os.popen(cmd_reboot).read()
                p(' ' * 62, '>>> Reboot lancé')
                commentaire_lines.append('Reboot lancé')
    else:
        p(s(client, 30), s(acces_ssh, 40), '%d paquet(s) à mettre à jour' % len(paquets))
        commentaire_lines.append('%d paquet(s) à mettre à jour :' % len(paquets))
        commentaire_lines.extend(paquets)
        if upgrade:
            p(' ' * 62, '>>> Lancement de apt-get dist-upgrade...')
            t0 = time.time()
            cmd_upgrade = (
                "(ssh -o ConnectTimeout=300 -o BatchMode=yes %s "
                "'DEBIAN_FRONTEND=noninteractive apt-get dist-upgrade -y 2>&1') 2>&1" % acces_ssh
            )
            out = os.popen(cmd_upgrade).read()
            for line in out.splitlines():
                p(' ' * 62, line)
            p(' ' * 62, '>>> Durée : %.1fs' % (time.time() - t0))
            # Vérification après upgrade
            cmd_verif = (
                "(ssh -o ConnectTimeout=10 -o BatchMode=yes %s "
                "'apt-get --simulate dist-upgrade 2>/dev/null') 2>&1" % acces_ssh
            )
            reste = [l.strip()[5:] for l in os.popen(cmd_verif).read().splitlines() if l.startswith('Inst ')]
            if reste:
                commentaire_lines.append('ATTENTION : %d paquet(s) toujours en attente :' % len(reste))
                p(' ' * 62, '>>> ATTENTION : %d paquet(s) toujours en attente' % len(reste))
                commentaire_lines.extend(reste)
            else:
                p(' ' * 62, '>>> Upgrade terminé - serveur à jour')
                commentaire_lines.append('Upgrade terminé - serveur à jour')
            if reboot:
                p(' ' * 62, '>>> Reboot en cours...')
                cmd_reboot = (
                    "(ssh -o ConnectTimeout=10 -o BatchMode=yes %s "
                    "'nohup reboot &>/dev/null &') 2>&1" % acces_ssh
                )
                os.popen(cmd_reboot).read()
                p(' ' * 62, '>>> Reboot lancé')
                commentaire_lines.append('Reboot lancé')

    save_action(serveur['id'], action_label, commentaire_lines)
    return sortie


a_traiter = [sv for sv in serveurs
             if not filtre or filtre in nom_client(sv).lower() or filtre in sv['name'].lower()]

# dist-upgrade / reboot : séquentiel pour suivre l'upgrade en direct et pouvoir interrompre
jobs = 1 if upgrade else max(1, args.jobs)
if jobs == 1:
    for serveur in a_traiter:
        traiter(serveur, direct=True)
else:
    with ThreadPoolExecutor(max_workers=jobs) as executor:
        # map() rend les résultats dans l'ordre de la liste, dès qu'ils sont disponibles
        for lignes in executor.map(traiter, a_traiter):
            for ligne in lignes:
                print(ligne, flush=True)
