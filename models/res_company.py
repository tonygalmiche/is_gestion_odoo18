# -*- coding: utf-8 -*-
from odoo import fields, models # type: ignore

class ResCompany(models.Model):
    _inherit = 'res.company'

    is_num_formation = fields.Char("Numéro de déclaration d'activité de formation")

