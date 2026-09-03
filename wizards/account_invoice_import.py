# -*- coding: utf-8 -*-
from odoo import api, models


class AccountInvoiceImport(models.TransientModel):
    _inherit = "account.invoice.import"

    @api.model
    def _pre_process_parsed_inv(self, parsed_inv, company):
        """Propage la désignation de chaque ligne (line['name']) dans le
        dict 'product' de la ligne, pour permettre à business.document.import
        de tenter un matching produit par désignation en dernier recours
        (voir models/business_document_import.py)."""
        parsed_inv = super()._pre_process_parsed_inv(parsed_inv, company)
        for line in parsed_inv.get("lines") or []:
            if isinstance(line, dict) and line.get("name"):
                line.setdefault("product", {})
                line["product"].setdefault("name", line["name"])
        return parsed_inv
