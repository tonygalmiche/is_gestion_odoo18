# -*- coding: utf-8 -*-
import base64
import io
import logging
from odoo import api, fields, models  # type: ignore

_logger = logging.getLogger(__name__)

# # Importer la bibliothèque facturx pour générer un PDF/A-3 conforme
# try:
#     from facturx import generate_from_binary
#     FACTURX_LIB_AVAILABLE = True
# except ImportError:
#     FACTURX_LIB_AVAILABLE = False
#     _logger.warning("La bibliothèque 'facturx' n'est pas installée. Installez-la avec: pip install facturx")


class AccountMove(models.Model):
    _inherit = "account.move"

    is_affaire_id             = fields.Many2one('is.affaire', 'Affaire')
    is_date_paiement          = fields.Date('Date paiement')
    is_amount_untaxed_percent = fields.Float(compute='_compute_amount_untaxed_percent', string='Total HT(%)')


    def _compute_amount_untaxed_percent(self, field_names=None):
        res = {}
        for obj in self:
            res[obj.id] = {}
            res[obj.id]['is_amount_untaxed_percent'] = obj.amount_untaxed
            for k, v in res[obj.id].items():
                setattr(obj, k, v)
        return res


    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        """
            Inherit read_group to calculate the sum of the non-stored fields, as it is not automatically done anymore through the XML.
        """
        res = super(AccountMove, self).read_group(domain, fields, groupby, offset=offset, limit=limit, orderby=orderby, lazy=lazy)
        for idx, item in enumerate(res):
            res[idx]['is_amount_untaxed_percent']=123
        return res


    def calculer_tva(self):
        for obj in self:
            obj.compute_taxes()


    def acceder_facture_action(self, vals):
        for obj in self:

            res= {
                'name': 'Facture',
                'view_mode': 'form',
                'view_type': 'form',
                'res_model': 'account.invoice',
                'res_id': obj.id,
                'type': 'ir.actions.act_window',
                'view_id': self.env.ref('account.invoice_form').id,
                'domain': [('type','=','out_invoice')],
            }
            return res


    # def action_generate_facturx_pdf(self):
    #     """Génère le PDF Factur-X conforme PDF/A-3 en utilisant la bibliothèque facturx."""
    #     self.ensure_one()
        
    #     if not FACTURX_LIB_AVAILABLE:
    #         raise models.ValidationError(
    #             "La bibliothèque 'facturx' n'est pas installée.\n"
    #             "Installez-la avec: pip install facturx"
    #         )
        
    #     _logger.info("=== Génération Factur-X pour la facture %s ===", self.name)
        
    #     # Générer le XML Factur-X via le module standard account_edi_ubl_cii
    #     cii_builder = self.env['account.edi.xml.cii']
    #     xml_content, errors = cii_builder._export_invoice(self)
        
    #     if errors:
    #         _logger.error("Erreurs lors de la génération du XML Factur-X: %s", errors)
    #         raise models.ValidationError("\n".join(errors))
        
    #     _logger.info("=== XML Factur-X généré ===")
    #     _logger.info("Contenu XML:\n%s", xml_content.decode('utf-8') if xml_content else "VIDE")
        
    #     # Générer le PDF via le rapport standard
    #     report = self.env.ref('account.account_invoices')
    #     _logger.info("Génération du PDF avec le rapport: %s", report.report_name)
        
    #     pdf_content, content_type = report.with_context(force_report_rendering=True)._render_qweb_pdf(
    #         report.report_name, res_ids=self.ids
    #     )
    #     _logger.info("PDF généré, taille: %d octets", len(pdf_content))
        
    #     # Utiliser la bibliothèque facturx pour générer un PDF/A-3 conforme
    #     # avec le XML Factur-X intégré correctement
    #     pdf_metadata = {
    #         'author': self.company_id.name,
    #         'keywords': f"Factur-X, Invoice, {self.name}",
    #         'title': f"Facture {self.name}",
    #         'subject': f"Facture {self.name} - {self.partner_id.name}",
    #     }
        
    #     # Langue du partenaire pour les métadonnées
    #     lang = self.partner_id.lang.replace('_', '-') if self.partner_id.lang else 'fr-FR'
        
    #     # Générer le PDF Factur-X conforme PDF/A-3
    #     pdf_facturx_content = generate_from_binary(
    #         pdf_content,
    #         xml_content,
    #         flavor='factur-x',
    #         level='extended',
    #         check_xsd=False,  # Déjà validé par Odoo
    #         pdf_metadata=pdf_metadata,
    #         lang=lang,
    #     )
        
    #     _logger.info("PDF Factur-X PDF/A-3 généré, taille finale: %d octets", len(pdf_facturx_content))
        
    #     # Créer ou mettre à jour la pièce jointe
    #     filename = f"{self.name.replace('/', '_')}_facturx.pdf"
    #     attachment = self.env['ir.attachment'].search([
    #         ('res_model', '=', 'account.move'),
    #         ('res_id', '=', self.id),
    #         ('name', '=', filename),
    #     ], limit=1)
        
    #     attachment_vals = {
    #         'name': filename,
    #         'type': 'binary',
    #         'datas': base64.b64encode(pdf_facturx_content),
    #         'res_model': 'account.move',
    #         'res_id': self.id,
    #         'mimetype': 'application/pdf',
    #     }
        
    #     if attachment:
    #         attachment.write(attachment_vals)
    #     else:
    #         attachment = self.env['ir.attachment'].create(attachment_vals)
        
    #     # Retourner l'action pour télécharger le fichier
    #     return {
    #         'type': 'ir.actions.act_url',
    #         'url': f'/web/content/{attachment.id}?download=true',
    #         'target': 'new',
    #     }


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    is_account_invoice_line_id = fields.Integer('Lien entre account_invoice_line et account_move_line pour la migration', index=True)

