#!/usr/bin/python3
# -*- coding: utf-8 -*-

import xmlrpc.client
from config import URL, DB, USERNAME, PASSWORD


common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(URL))
uid    = common.authenticate(DB, USERNAME, PASSWORD, {})
models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(URL))


def s(txt, lg=0):
    txt = txt or ''
    if lg > 0:
        txt = (txt + ' ' * 100)[:lg]
    return txt


serveurs = models.execute_kw(DB, uid, PASSWORD, 'is.serveur', 'search_read',
    [[
        ('active', '=', True),
        ('date_debut_maintenance','!=',False),
    ]], {
        'fields': ['name', 'adresse_ip', 'partner_id', 'commentaire', 'acces_ssh', 'systeme_id'],
        'limit': 100,
        'order': 'systeme_id,partner_id',
    })

print(s('Système', 20), s('Client', 35), s('IP', 17), s('Accès SSH', 37), s('Commentaire', 50))
print('-' * 160)

for serveur in serveurs:
    client      = serveur['partner_id']  and serveur['partner_id'][1]  or ''
    systeme     = serveur['systeme_id']  and serveur['systeme_id'][1]  or ''
    commentaire = (serveur['commentaire'] or '').split('\n')[0]

    print(
        s(systeme, 20),
        s(client, 35),
        s(serveur['adresse_ip'], 17),
        s(serveur['acces_ssh'], 37),
        s(commentaire, 50),
    )
