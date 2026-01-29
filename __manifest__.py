# -*- coding: utf-8 -*-
{
    "name"      : "Module Gestion Odoo 18 pour InfoSaône",
    "version"   : "18.0.1.0.0",
    "author"    : "InfoSaône / Tony Galmiche",
    "maintainer": "InfoSaône",
    "website"   : "http://www.infosaone.com",
    "category"  : "InfoSaône",
    "description": """
Module Gestion Odoo 18 pour InfoSaône 
===================================================
""",
    "maintainer" : "InfoSaône",
    "website"    : "http://www.infosaone.com",
    "depends"    : [
        "base",
        "account",
        "l10n_fr",
        "l10n_fr_account",
        #"account_edi_ubl_cii",
    ],
    "data" : [
        "security/ir.model.access.csv",
        "views/is_affaire_view.xml",
        "views/is_serveur_view.xml",
        "views/is_suivi_temps_view.xml",
        "wizards/is_import_google_calendar_wizard_view.xml",
        "views/res_partner_view.xml",
        "views/res_company_view.xml",
        "views/account_move_view.xml",
        "views/menu.xml",
        "report/report_templates.xml",
        "report/report_invoice.xml",
    ],
    "installable": True,
    "application": True,
    "license": "LGPL-3",
}
