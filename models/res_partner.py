# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta
from odoo import fields, models  # type: ignore

class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_effectif              = fields.Integer("Effectif")
    is_activite              = fields.Char("Activité")
    is_dirigeant             = fields.Char("Dirigeant")
    is_contact               = fields.Char("Contact principal")
    is_date_debut_maintenance = fields.Date("Date début contrat de maintenance")
    is_derniere_intervention  = fields.Text("Commentaire dernière intervention")
    is_siren                 = fields.Char("SIREN (ne plus utiliser)")
    is_forme_juridique       = fields.Char("Forme juridique")
    is_date_debut_activite   = fields.Date("Date de début d'activité")
    is_categorie             = fields.Char("Catégorie")
    is_dynacase_id           = fields.Integer("Id Dynacase")
    is_code_client           = fields.Char("Code client", help="Code client utilisé dans Google Calendar pour identifier le client")
    is_ca_12_mois            = fields.Monetary("CA des 12 derniers mois", currency_field='currency_id', help="Chiffre d'affaires HT facturé sur les 12 derniers mois glissants (actualisé par tâche planifiée)")
    is_ca_24_mois            = fields.Monetary("CA des 24 derniers mois", currency_field='currency_id', help="Chiffre d'affaires HT facturé sur les 24 derniers mois glissants (actualisé par tâche planifiée)")


    def _calculer_ca_glissant(self, field_name, nb_mois):
        date_debut = fields.Date.context_today(self) - relativedelta(months=nb_mois)
        self.search([]).write({field_name: 0})
        resultats = self.env['account.move'].sudo()._read_group(
            domain=[
                ('move_type', 'in', ('out_invoice', 'out_refund')),
                ('state', '=', 'posted'),
                ('invoice_date', '>=', date_debut),
            ],
            groupby=['partner_id'],
            aggregates=['amount_untaxed_signed:sum'],
        )
        for partner, montant in resultats:
            if partner:
                partner[field_name] = montant


    def _cron_calculer_ca_12_mois(self):
        """Recalcule les champs is_ca_12_mois et is_ca_24_mois de tous les partenaires facturés."""
        self._calculer_ca_glissant('is_ca_12_mois', 12)
        self._calculer_ca_glissant('is_ca_24_mois', 24)






