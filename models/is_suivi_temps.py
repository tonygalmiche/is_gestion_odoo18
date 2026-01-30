# -*- coding: utf-8 -*-
from odoo import models, fields, api
import re


class IsSuiviTemps(models.Model):
    _name = 'is.suivi.temps'
    _description = 'Suivi du temps'
    _order = 'date_debut desc'
    _rec_name = 'display_name'

    date_debut = fields.Datetime(string='Date de début', required=True, default=fields.Datetime.now)
    date_fin = fields.Datetime(string='Date de fin')
    description = fields.Text(string='Description')
    description_simplifiee = fields.Char(string='Description simplifiée', compute='_compute_description_simplifiee', store=True)
    duree = fields.Float(string='Durée (HH:MM)', compute='_compute_duree', store=True, readonly=True)
    google_event_id = fields.Char(string='ID Google Calendar', index=True, copy=False)
    google_calendar_id = fields.Char(string='ID Calendrier Google', copy=False, help="Identifiant du calendrier Google")
    google_calendar_name = fields.Char(string='Calendrier', copy=False)
    google_calendar_url = fields.Char(string='URL Google Calendar', compute='_compute_google_calendar_url', readonly=True)
    color = fields.Integer(string='Couleur', default=1)
    
    # Nouveaux champs
    fait = fields.Boolean(string='Fait', default=False, help="Indique si la tâche est terminée (FAIT : au début de la description)")
    partner_id = fields.Many2one('res.partner', string='Client', help="Client identifié par son code dans la description")
    temps_facturable = fields.Float(string='Temps facturable (H)', help="Temps prévu à facturer extrait de la description (ex: 4H)")


    def _compute_display_name(self):
        for record in self:
            if record.description:
                record.display_name = record.description[:50] if len(record.description) > 50 else record.description
            else:
                record.display_name = str(record.date_debut) if record.date_debut else 'Sans description'

    @api.depends('google_event_id', 'google_calendar_id')
    def _compute_google_calendar_url(self):
        """Générer l'URL vers l'événement dans Google Calendar"""
        for record in self:
            if record.google_event_id and record.google_calendar_id:
                # Google Calendar utilise un encodage base64 de "event_id calendar_id"
                import base64
                combined = f"{record.google_event_id} {record.google_calendar_id}"
                encoded = base64.b64encode(combined.encode('utf-8')).decode('utf-8')
                record.google_calendar_url = f"https://calendar.google.com/calendar/u/0/r/eventedit/{encoded}"
            else:
                record.google_calendar_url = False

    def action_open_google_calendar(self):
        """Ouvrir l'événement dans Google Calendar"""
        self.ensure_one()
        if self.google_calendar_url:
            return {
                'type': 'ir.actions.act_url',
                'url': self.google_calendar_url,
                'target': 'new',
            }

    @api.depends('date_debut', 'date_fin')
    def _compute_duree(self):
        for record in self:
            if record.date_debut and record.date_fin:
                delta = record.date_fin - record.date_debut
                record.duree = delta.total_seconds() / 3600.0
            else:
                record.duree = 0.0

    @api.depends('description', 'partner_id')
    def _compute_description_simplifiee(self):
        """Nettoie la description pour enlever FAIT : et le code client, mais garde le temps passé"""
        for record in self:
            if not record.description:
                record.description_simplifiee = ''
                continue
                
            desc = record.description
            
            # Enlever "FAIT : " au début
            desc = re.sub(r'^FAIT\s*:\s*', '', desc, flags=re.IGNORECASE).strip()
            
            # Si un client est trouvé, enlever son code (ex: "PG : ")
            if record.partner_id and record.partner_id.is_code_client:
                pattern = r'^' + re.escape(record.partner_id.is_code_client) + r'\s*:\s*'
                desc = re.sub(pattern, '', desc, flags=re.IGNORECASE).strip()
            
            record.description_simplifiee = desc

    def parse_description(self, description):
        """
        Parse la description pour extraire les informations:
        - FAIT : indique que la tâche est faite
        - Code client (ex: PG :)
        - Temps facturable (ex: (4H))
        
        Retourne un dict avec: fait, code_client, temps_facturable
        """
        if not description:
            return {'fait': False, 'code_client': None, 'temps_facturable': 0.0}
        
        result = {
            'fait': False,
            'code_client': None,
            'temps_facturable': 0.0
        }
        
        # Vérifier si la description commence par "FAIT :"
        if re.match(r'^FAIT\s*:', description, flags=re.IGNORECASE):
            result['fait'] = True
        
        # Extraire le code client (format: "XX :" après éventuellement "FAIT :")
        # On cherche 1 à 20 caractères (lettres, chiffres, tirets, underscores, espaces) suivis de " :"
        desc_sans_fait = re.sub(r'^FAIT\s*:\s*', '', description, flags=re.IGNORECASE).strip()
        match_code = re.match(r'^([\w\s-]{1,20}?)\s*:\s*', desc_sans_fait, flags=re.IGNORECASE)
        if match_code:
            result['code_client'] = match_code.group(1).strip().upper()
        
        # Extraire le temps facturable (format: (XXH) ou (XXh) à la fin)
        match_temps = re.search(r'\(([\d.,]+)\s*[Hh]\s*(?:\d+)?\)\s*$', description)
        if match_temps:
            try:
                temps_str = match_temps.group(1).replace(',', '.')
                result['temps_facturable'] = float(temps_str)
            except ValueError:
                pass
        
        return result

