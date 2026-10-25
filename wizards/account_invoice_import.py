# -*- coding: utf-8 -*-
from odoo import api, models


class AccountInvoiceImport(models.TransientModel):
    _inherit = "account.invoice.import"

    @api.model
    def _match_product(self, line_dict, parsed_inv, import_config):
        """Ajoute un dernier recours de matching par désignation (nom de
        l'article, BT-153) quand le code-barres, la référence interne et le
        code fournisseur n'ont rien donné. Utile pour les fournisseurs (ex.
        opérateurs télécom) qui ne renseignent aucun identifiant produit
        dans leurs factures électroniques."""
        product = super()._match_product(line_dict, parsed_inv, import_config)
        name = line_dict.get("BT-153")
        if product or not name:
            return product
        product = self.env["product.product"].search(
            [
                ("company_id", "in", (False, import_config["company"].id)),
                ("name", "=ilike", name.strip()),
            ],
            limit=1,
        )
        if product:
            self._info_log(
                import_config,
                f"Invoice line {line_dict['BT-126']}: product "
                f"{product.display_name} matched via item name (BT-153)",
            )
            return product
        return None
