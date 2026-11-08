# -*- coding: utf-8 -*-
import re
from odoo import api, fields, models, _  # type: ignore
from odoo.exceptions import ValidationError  # type: ignore


class IsLogiciel(models.Model):
    _name = 'is.logiciel'
    _description = "Logiciel à surveiller (CVE)"
    _order = 'sequence, name'

    name      = fields.Char("Logiciel", required=True, index=True)
    sequence  = fields.Integer("Séquence", default=10)
    script    = fields.Char("Script", required=True,
                            help="Script du dossier scripts-externes/logiciels/ exécuté sur le serveur par verif-update-vps.py --get-logiciels")
    parametre = fields.Char("Paramètre", help="Paramètres du script séparés par des espaces (ex. pour paquet.sh : noms de paquets Debian, * accepté)")
    active    = fields.Boolean("Actif", default=True)

    @api.constrains('script')
    def _check_script(self):
        for rec in self:
            if not re.fullmatch(r'[a-z0-9_-]+\.sh', rec.script or ''):
                raise ValidationError(_("Le script doit être un simple nom de fichier .sh du dossier scripts-externes/logiciels/ (ex. paquet.sh)."))


class IsServeurLogiciel(models.Model):
    _name = 'is.serveur.logiciel'
    _description = "Version d'un logiciel sur un serveur"
    _order = 'logiciel_id, serveur_id, version'

    serveur_id     = fields.Many2one('is.serveur', "Serveur", required=True, index=True, ondelete='cascade')
    logiciel_id    = fields.Many2one('is.logiciel', "Logiciel", required=True, index=True, ondelete='cascade')
    version        = fields.Char("Version", index=True)
    version_paquet = fields.Char("Version paquet")
    date_releve    = fields.Datetime("Date du relevé")
    partner_id     = fields.Many2one('res.partner', "Client",  related='serveur_id.partner_id', store=True)
    service_id     = fields.Many2one('is.service',  "Service", related='serveur_id.service_id', store=True)
    systeme_id     = fields.Many2one('is.systeme',  "Système", related='serveur_id.systeme_id', store=True)
