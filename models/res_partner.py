# -*- coding: utf-8 -*-
from odoo import fields, models  # type: ignore

class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_effectif              = fields.Integer("Effectif")
    is_activite              = fields.Char("Activité")
    is_dirigeant             = fields.Char("Dirigeant")
    is_contact               = fields.Char("Contact principal")
    is_derniere_intervention = fields.Text("Commentaire dernière intervention")
    is_siren                 = fields.Char("SIREN")
    is_forme_juridique       = fields.Char("Forme juridique")
    is_date_debut_activite   = fields.Date("Date de début d'activité")
    is_categorie             = fields.Char("Catégorie")
    is_dynacase_id           = fields.Integer("Id Dynacase")
    is_code_client           = fields.Char("Code client", help="Code client utilisé dans Google Calendar pour identifier le client")






