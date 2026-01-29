# -*- coding: utf-8 -*-
from odoo import models, fields, api


class IsSuiviTemps(models.Model):
    _name = 'is.suivi.temps'
    _description = 'Suivi du temps'
    _order = 'date_debut desc'
    _rec_name = 'display_name'

    date_debut = fields.Datetime(string='Date de début', required=True, default=fields.Datetime.now)
    date_fin = fields.Datetime(string='Date de fin')
    description = fields.Text(string='Description')
    duree = fields.Float(string='Durée (HH:MM)', compute='_compute_duree', store=True, readonly=True)
    google_event_id = fields.Char(string='ID Google Calendar', index=True, copy=False)
    google_calendar_name = fields.Char(string='Calendrier', copy=False)
    color = fields.Integer(string='Couleur', default=1)

    def _compute_display_name(self):
        for record in self:
            if record.description:
                record.display_name = record.description[:50] if len(record.description) > 50 else record.description
            else:
                record.display_name = str(record.date_debut) if record.date_debut else 'Sans description'

    @api.depends('date_debut', 'date_fin')
    def _compute_duree(self):
        for record in self:
            if record.date_debut and record.date_fin:
                delta = record.date_fin - record.date_debut
                record.duree = delta.total_seconds() / 3600.0
            else:
                record.duree = 0.0
