# -*- coding: utf-8 -*-
from odoo import fields, models  # type: ignore

class IsServeur(models.Model):
    _name = 'is.serveur'
    _inherit=['mail.thread']
    _description = "Serveur"
    _order = 'name'

    name                = fields.Char("Nom du serveur"                , required=True, index=True)
    partner_id          = fields.Many2one('res.partner', "Client"     , required=True)
    fournisseur_id      = fields.Many2one('res.partner', "Fournisseur", required=True)
    adresse_ip          = fields.Char("Adresse IP", required=True)
    date_creation       = fields.Date("Date de création")
    date_fin            = fields.Date("Date fin abonnement")
    renouvellement_auto = fields.Selection([
            ('oui', 'Oui'),
            ('non', 'Non'),
        ], "Renouvellement auto")
    service_id          = fields.Many2one('is.service', "Service", required=True)
    acces_ssh           = fields.Char("Accès SSH")
    mot_de_passe        = fields.Char("Mot de passe")
    systeme_id          = fields.Many2one('is.systeme', "Système", required=True)
    type_vps_id         = fields.Many2one('is.type.vps', "Type de VPS")
    commentaire         = fields.Text("Commentaire")
    grafana             = fields.Boolean("Grafana", default=False)
    sauvegarde          = fields.Boolean("Vérification sauvegarde", default=True)
    active              = fields.Boolean("Actif"  , default=True)


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
