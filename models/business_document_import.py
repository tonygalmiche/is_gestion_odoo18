# -*- coding: utf-8 -*-
from odoo import models
from odoo.osv import expression


class BusinessDocumentImport(models.AbstractModel):
    _inherit = "business.document.import"

    def _match_product(self, product_dict, chatter_msg, seller=False, raise_exception=True):
        """Ajoute un dernier recours de matching par désignation (nom de
        l'article) quand le code-barres, la référence interne et le code
        fournisseur n'ont rien donné. Utile pour les fournisseurs (ex.
        opérateurs télécom) qui ne renseignent aucun identifiant produit
        dans leurs factures électroniques."""
        ppo = self.env["product.product"]
        self._strip_cleanup_dict(product_dict)
        product = self._direct_match(product_dict, ppo)
        if product:
            return product
        product = self._match_product_search(product_dict)
        if product:
            return product
        if seller and product_dict.get("code"):
            sinfo = self.env["product.supplierinfo"].search(
                expression.AND(
                    [
                        self._match_company_domain(),
                        [
                            ("partner_id", "=", seller.id),
                            ("product_code", "=", product_dict["code"]),
                        ],
                    ]
                ),
                limit=1,
            )
            if sinfo and len(sinfo.product_tmpl_id.product_variant_ids) == 1:
                return sinfo.product_tmpl_id.product_variant_id
        name = product_dict.get("name")
        if name:
            product = ppo.search(
                expression.AND(
                    [self._match_company_domain(), [("name", "=ilike", name)]]
                ),
                limit=1,
            )
            if product:
                return product
        self.user_error_wrap(
            "_match_product",
            product_dict,
            self.env._(
                "Odoo couldn't find any product corresponding to the "
                "following information extracted from the business document:\n"
                "Barcode: %(barcode)s\n"
                "Product code: %(product_code)s\n"
                "Designation: %(name)s\n"
                "Supplier: %(supplier)s\n",
                barcode=product_dict.get("barcode") or "",
                product_code=product_dict.get("code") or "",
                name=product_dict.get("name") or "",
                supplier=seller and seller.display_name or "",
            ),
            chatter_msg,
            raise_exception,
        )
        return None
