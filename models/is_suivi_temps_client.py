# -*- coding: utf-8 -*-
from odoo import models, fields, api


class IsSuiviTempsClient(models.Model):
    _name = 'is.suivi.temps.client'
    _description = 'Suivi du temps par client'
    _order = 'mois desc, partner_id'
    _rec_name = 'display_name'

    mois              = fields.Char(string='Mois', required=True, index=True, help="Format YYYY-MM")
    partner_id        = fields.Many2one('res.partner', string='Client', required=True, index=True, ondelete='cascade')
    taches_effectuees = fields.Text(string='Tâches effectuées', help="Liste des tâches effectuées pour ce client ce mois-ci")
    temps_facturable  = fields.Float(string='Temps facturable (H)', help="Total du temps facturable pour ce client ce mois-ci")
    temps_passe       = fields.Float(string='Temps passé (H)', help="Total du temps passé pour ce client ce mois-ci")
    temps_facture     = fields.Float(string='Temps facturé (H)', help="Temps réellement facturé")
    commentaire       = fields.Text(string='Commentaire', help="Commentaires libres sur le suivi du temps pour ce client ce mois-ci")
    
    _sql_constraints = [
        ('mois_partner_unique', 'UNIQUE(mois, partner_id)', 'Un enregistrement par client et par mois existe déjà !')
    ]

    @api.depends('mois', 'partner_id')
    def _compute_display_name(self):
        for record in self:
            if record.partner_id and record.mois:
                record.display_name = f"{record.partner_id.name} - {record.mois}"
            else:
                record.display_name = record.mois or 'Nouveau'

    def action_view_taches(self):
        """Ouvrir la liste des tâches pour ce client et ce mois"""
        self.ensure_one()
        
        # Calculer les dates de début et fin du mois
        from datetime import datetime
        mois_debut = datetime.strptime(f"{self.mois}-01", '%Y-%m-%d')
        if mois_debut.month == 12:
            mois_fin = datetime(mois_debut.year + 1, 1, 1)
        else:
            mois_fin = datetime(mois_debut.year, mois_debut.month + 1, 1)
        
        return {
            'type': 'ir.actions.act_window',
            'name': f"Tâches - {self.partner_id.name} - {self.mois}",
            'res_model': 'is.suivi.temps',
            'view_mode': 'list,form',
            'domain': [
                ('partner_id', '=', self.partner_id.id),
                ('date_debut', '>=', mois_debut),
                ('date_debut', '<', mois_fin)
            ],
            'context': {'default_partner_id': self.partner_id.id},
        }
