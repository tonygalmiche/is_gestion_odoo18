# -*- coding: utf-8 -*-
from odoo import api, fields, models  # type: ignore


class IsCve(models.Model):
    _name = 'is.cve'
    _description = "CVE - Vulnérabilité"
    _order = 'score_gravite desc, cve_id desc'

    cve_id             = fields.Char("CVE ID", required=True, index=True)
    name               = fields.Char("Nom de la vulnérabilité", index=True)
    state              = fields.Selection([
            ('creation'     , 'Création'),
            ('analyse'      , 'Analysé'),
            ('traite'       , 'Traité'),
            ('non_concerne' , 'Non concerné'),
        ], "État", index=True, default='creation', group_expand='_group_expand_states')
    severity           = fields.Selection([
            ('critical', 'Critical'),
            ('high'    , 'High'),
            ('medium'  , 'Medium'),
            ('low'     , 'Low'),
            ('info'    , 'Info'),
        ], "Sévérité", index=True)
    vuln_status        = fields.Char("Statut")
    cvss_score         = fields.Float("Score CVSS", digits=(4, 1))
    cvss_metrics       = fields.Char("Métriques CVSS")
    epss_score         = fields.Float("Score EPSS", digits=(8, 6))
    epss_percentile    = fields.Float("Percentile EPSS", digits=(8, 6))
    age_in_days        = fields.Integer("Âge (jours)")
    ntps               = fields.Integer("NTPS")
    assignee           = fields.Char("Assigné à")
    vendor             = fields.Char("Éditeur")
    product            = fields.Char("Produit")
    vulnerability_type = fields.Char("Type de vulnérabilité")
    requirement_type   = fields.Char("Type de prérequis")
    requirements       = fields.Text("Prérequis")
    cwe_ids            = fields.Char("CWE")
    exposure_hosts     = fields.Integer("Exposition (hôtes)")
    h1_rank            = fields.Integer("Rang HackerOne")
    is_patch_available = fields.Boolean("Patch disponible")
    is_remote          = fields.Boolean("Exploitation distante")
    is_auth            = fields.Boolean("Authentification requise")
    is_kev             = fields.Boolean("KEV (CISA)")
    is_poc             = fields.Boolean("PoC disponible")
    is_template        = fields.Boolean("Template Nuclei")
    cve_created_at     = fields.Datetime("Créé le (CVE)")
    cve_updated_at     = fields.Datetime("Mis à jour le (CVE)")
    analyse            = fields.Text("Analyse")
    description        = fields.Text("Description")
    impact             = fields.Text("Impact")
    remediation        = fields.Text("Remédiation")
    json_detail        = fields.Text("Détail JSON complet")
    score_gravite      = fields.Float("Score de gravité", compute='_compute_score_gravite', store=True, digits=(5, 1))

    @api.depends('cvss_score', 'epss_score', 'is_kev', 'is_poc', 'is_patch_available', 'is_remote')
    def _compute_score_gravite(self):
        for rec in self:
            score  = (rec.cvss_score / 10.0) * 50.0
            score += rec.epss_score * 20.0
            score += 20.0 if rec.is_kev else 0.0
            score += 10.0 if rec.is_poc else 0.0
            score += 5.0  if not rec.is_patch_available else 0.0
            score += 5.0  if rec.is_remote else 0.0
            rec.score_gravite = min(round(score, 1), 100.0)

    @api.model
    def _group_expand_states(self, states, domain):
        return [key for key, _val in type(self).state.selection]
