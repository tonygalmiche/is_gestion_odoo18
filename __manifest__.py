# -*- coding: utf-8 -*-
{
    'name'     : 'Module Gestion Odoo 18 pour InfoSaône',
    'version'  : '0.1',
    'author'   : 'InfoSaône',
    'category' : 'InfoSaône',
    'description': """
Module Gestion Odoo 18 pour InfoSaône 
===================================================
""",
    'maintainer' : 'InfoSaône',
    'website'    : 'http://www.infosaone.com',
    'depends'    : [
        'base',
        'account',
        'l10n_fr',
        'l10n_fr_account',
    ],
    'data' : [
        'security/ir.model.access.csv',
        'views/is_affaire_view.xml',
        'views/is_serveur_view.xml',
        'views/res_partner_view.xml',
        'views/res_company_view.xml',
        'views/account_move_view.xml',
        'views/menu.xml',
        'report/report_templates.xml',
        'report/report_invoice.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
