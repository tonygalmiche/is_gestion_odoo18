# -*- coding: utf-8 -*-
import re
from datetime import datetime
from odoo import api, fields, models, _  # type: ignore
from odoo.exceptions import UserError  # type: ignore

class IsServeur(models.Model):
    _name = 'is.serveur'
    _inherit=['mail.thread']
    _description = "Serveur"
    _order = 'name'

    name                = fields.Char("Nom du serveur"                , required=True, index=True, tracking=True)
    partner_id          = fields.Many2one('res.partner', "Client"     , required=True, tracking=True)
    fournisseur_id      = fields.Many2one('res.partner', "Fournisseur", required=True, tracking=True)
    adresse_ip          = fields.Char("Adresse IP", required=True, tracking=True)
    date_creation       = fields.Date("Date de création", tracking=True)
    date_fin            = fields.Date("Date fin abonnement", tracking=True)
    renouvellement_auto = fields.Selection([
            ('oui', 'Oui'),
            ('non', 'Non'),
        ], "Renouvellement auto", tracking=True)
    service_id          = fields.Many2one('is.service', "Service", required=True, tracking=True)
    acces_ssh           = fields.Char("Accès SSH", tracking=True)
    mot_de_passe        = fields.Char("Mot de passe")
    systeme_id          = fields.Many2one('is.systeme', "Système", required=True, tracking=True)
    info_systeme        = fields.Char("Info système", tracking=True)
    type_vps_id         = fields.Many2one('is.type.vps', "Type de VPS", tracking=True)
    commentaire         = fields.Text("Commentaire")
    grafana             = fields.Boolean("Grafana", default=False, tracking=True)
    sauvegarde          = fields.Boolean("Vérification sauvegarde", default=True, tracking=True)
    active              = fields.Boolean("Actif"  , default=True, tracking=True)
    action_ids             = fields.One2many('is.serveur.action', 'serveur_id', "Actions")
    upgrade_auto           = fields.Boolean("Upgrade automatique autorisé", default=True, tracking=True)
    date_debut_maintenance = fields.Date("Date maintenance", help="Date début contrat maintenance", related='partner_id.is_date_debut_maintenance', store=True)
    nb_actions          = fields.Integer("Nb actions", compute='_compute_nb_actions', store=True)

    @api.depends('action_ids')
    def _compute_nb_actions(self):
        for rec in self:
            rec.nb_actions = len(rec.action_ids)

    def action_open_actions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Actions',
            'res_model': 'is.serveur.action',
            'view_mode': 'list,form',
            'domain': [('serveur_id', '=', self.id)],
            'context': {'default_serveur_id': self.id},
        }

    def action_import_commentaire(self):
        self.ensure_one()
        if not self.commentaire:
            raise UserError(_("Le commentaire est vide."))
        pattern = re.compile(r'^(\d{2}/\d{2}/\d{4})\s*:\s*(.+)$')
        created = 0
        remaining_lines = []
        for line in self.commentaire.splitlines():
            m = pattern.match(line.strip())
            if m:
                date_str, action_text = m.group(1), m.group(2).strip()
                date_heure = datetime.strptime(date_str + ' 08:00', '%d/%m/%Y %H:%M')
                self.env['is.serveur.action'].create({
                    'serveur_id': self.id,
                    'date_heure': date_heure,
                    'action': action_text,
                })
                created += 1
            else:
                remaining_lines.append(line)
        self.commentaire = '\n'.join(remaining_lines).strip() or False
        # if not created:
        #     raise UserError(_("Aucune ligne avec une date (JJ/MM/AAAA) trouvée dans le commentaire."))
        # return {
        #     'type': 'ir.actions.client',
        #     'tag': 'display_notification',
        #     'params': {
        #         'title': _("Import terminé"),
        #         'message': _("%d action(s) créée(s).") % created,
        #         'type': 'success',
        #     },
        # }


class IsServeurAction(models.Model):
    _name = 'is.serveur.action'
    _description = "Actions sur les serveurs"
    _order = 'date_heure desc'

    serveur_id  = fields.Many2one('is.serveur', "Serveur", required=True, ondelete='cascade')
    partner_id  = fields.Many2one('res.partner', "Client",   related='serveur_id.partner_id', store=True)
    service_id  = fields.Many2one('is.service',  "Service",  related='serveur_id.service_id',  store=True)
    systeme_id  = fields.Many2one('is.systeme',  "Système",  related='serveur_id.systeme_id',  store=True)
    date_heure  = fields.Datetime("Date", required=True, default=fields.Datetime.now)
    action      = fields.Char("Action", required=True)
    commentaire = fields.Text("Commentaire")


class IsSysteme(models.Model):
    _name = 'is.systeme'
    _description = "Système"
    _order = 'name'

    name = fields.Char("Système", required=True, index=True)


class IsTypeVPS(models.Model):
    _name = 'is.type.vps'
    _description = "Type de VPS"
    _order = 'name'

    name = fields.Char("Type de VPS", required=True, index=True)


class IsService(models.Model):
    _name = 'is.service'
    _description = "Service"
    _order = 'name'

    name = fields.Char("Service", required=True, index=True)
