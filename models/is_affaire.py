# -*- coding: utf-8 -*-
from odoo import api, fields, models  # type: ignore


class IsAffaire(models.Model):
    _name = 'is.affaire'
    _description = "Affaire"
    _order = 'name desc'

    name               = fields.Char("Affaire", readonly=True, index=True)
    intitule           = fields.Char("Intitulé de l'affaire", required=True, index=True)
    partner_id         = fields.Many2one('res.partner', "Client", required=True, index=True, domain=[('is_company','=',True)])
    date_debut         = fields.Date("Date de début", default=fields.Date.today())
    date_fin           = fields.Date("Date de fin")
    ca_previsionnel    = fields.Float("CA prévisionnel", digits=(14,2))
    frais_previsionnel = fields.Float("Frais prévisionnel", digits=(14,2))
    commentaire        = fields.Text("Commentaire")
    facture_ids        = fields.One2many('account.move', 'is_affaire_id', 'Factures')
    state              = fields.Selection([
            ('devis'     , 'Devis'),
            ('abandonnee', 'Abandonnée'),
            ('active'    , 'Active'),
            ('soldee'    , 'Soldée'),
        ], "État", index=True, default='active')


    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['name'] = self.env['ir.sequence'].next_by_code('is.affaire')
        return super().create(vals_list)


    def name_get(self):
        result = []
        for obj in self:
            result.append((obj.id, '['+str(obj.name)+'] '+str(obj.intitule)+' ('+obj.partner_id.name+')'))
        return result


    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        ids = []
        if name:
            ids = self._search(['|','|',('name', 'ilike', name),('intitule', 'ilike', name),('partner_id.name', 'ilike', name)] + args, limit=limit, access_rights_uid=name_get_uid)
        else:
            ids = self._search(args, limit=limit, access_rights_uid=name_get_uid)
        return self.browse(ids).name_get()


