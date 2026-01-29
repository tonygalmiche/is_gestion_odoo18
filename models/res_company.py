# -*- coding: utf-8 -*-
from odoo import fields, models # type: ignore

class ResCompany(models.Model):
    _inherit = 'res.company'

    is_num_formation = fields.Char("Numéro de déclaration d'activité de formation")
    is_google_credentials_json = fields.Text("Google Calendar Credentials (JSON)", help="Collez ici le contenu du fichier JSON des credentials téléchargé depuis Google Cloud Console")
    is_google_token_json = fields.Text("Google Calendar Token (JSON)", readonly=True, help="Token d'accès généré automatiquement après l'autorisation OAuth")
    is_google_calendar_ids = fields.One2many('is.google.calendar.config', 'company_id', string='Calendriers à importer')

