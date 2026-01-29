# -*- coding: utf-8 -*-
from odoo import fields, models


class IsGoogleCalendarConfig(models.Model):
    _name = 'is.google.calendar.config'
    _description = 'Configuration des calendriers Google'
    _order = 'name'

    name = fields.Char(string='Nom du calendrier', required=True, help="Nom exact du calendrier tel qu'il apparaît dans Google Calendar")
    company_id = fields.Many2one('res.company', string='Société', required=True, ondelete='cascade')
    color = fields.Integer(string='Couleur', default=1, help="Couleur pour l'affichage dans la vue calendrier (1-11)")
