# -*- coding: utf-8 -*-
from odoo import fields, models, api
from odoo.exceptions import UserError
import json
import logging
from datetime import date, datetime, timedelta

_logger = logging.getLogger(__name__)

try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import Flow
    from googleapiclient.discovery import build
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False
    _logger.warning("Les bibliothèques Google API ne sont pas installées. Exécutez: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']


class IsImportGoogleCalendarWizard(models.TransientModel):
    _name = 'is.import.google.calendar.wizard'
    _description = 'Import Google Calendar'

    periode = fields.Selection([
        ('mois_courant', 'Mois en cours'),
        ('mois_precedent', 'Mois précédent'),
    ], string='Période', default='mois_precedent', required=True)
    date_debut = fields.Date(string='Date de début', required=True, default=lambda self: self._get_dates_periode('mois_precedent')[0])
    date_fin = fields.Date(string='Date de fin', required=True, default=lambda self: self._get_dates_periode('mois_precedent')[1])

    @api.model
    def _get_dates_periode(self, periode):
        today = date.today()
        if periode == 'mois_courant':
            debut = today.replace(day=1)
        else:
            mois_courant_debut = today.replace(day=1)
            fin_mois_precedent = mois_courant_debut - timedelta(days=1)
            debut = fin_mois_precedent.replace(day=1)
        if debut.month == 12:
            debut_mois_suivant = debut.replace(year=debut.year + 1, month=1, day=1)
        else:
            debut_mois_suivant = debut.replace(month=debut.month + 1, day=1)
        fin = debut_mois_suivant - timedelta(days=1)
        return debut, fin

    @api.onchange('periode')
    def _onchange_periode(self):
        if self.periode:
            self.date_debut, self.date_fin = self._get_dates_periode(self.periode)

    # Champs pour l'authentification OAuth
    state = fields.Selection([
        ('config', 'Configuration'),
        ('auth', 'Autorisation'),
        ('import', 'Import')
    ], default='config', string='État')
    auth_url = fields.Char(string='URL d\'autorisation', readonly=True)
    code_verifier = fields.Char(string='PKCE Code Verifier', readonly=True)

    def _get_redirect_uri(self):
        # Google refuse les redirect_uri en http:// non-loopback (erreur invalid_request).
        # On utilise donc une URL dédiée (ex: http://localhost:8069), différente de web.base.url,
        # paramétrable via le paramètre système is_gestion_odoo18.google_redirect_base_url.
        ir_config = self.env['ir.config_parameter'].sudo()
        base_url = ir_config.get_param('is_gestion_odoo18.google_redirect_base_url') \
            or ir_config.get_param('web.base.url')
        return f"{base_url}/google_calendar/callback"

    def _get_credentials(self):
        """Récupérer les credentials valides ou None"""
        company = self.env.company
        
        if not company.is_google_token_json:
            return None
            
        try:
            token_info = json.loads(company.is_google_token_json)
            creds = Credentials.from_authorized_user_info(token_info, SCOPES)
            
            if creds and creds.valid:
                return creds
            
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                company.sudo().write({
                    'is_google_token_json': creds.to_json()
                })
                return creds
        except Exception as e:
            _logger.warning(f"Erreur lors de la récupération des credentials: {e}")
        
        return None
    
    def action_import(self):
        """Vérifier les credentials et lancer l'import ou l'authentification"""
        self.ensure_one()
        
        if not GOOGLE_API_AVAILABLE:
            raise UserError("Les bibliothèques Google API ne sont pas installées.\n"
                          "Exécutez: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")
        
        company = self.env.company
        
        if not company.is_google_credentials_json:
            raise UserError("Veuillez configurer les credentials Google API dans la fiche société (onglet Google Calendar).")
        
        # Vérifier si on a déjà des credentials valides
        creds = self._get_credentials()
        
        if creds:
            # On a des credentials valides, lancer l'import directement
            return self._do_import(creds)
        else:
            # Pas de credentials, générer l'URL d'autorisation
            return self._generate_auth_url()
    
    def _generate_auth_url(self):
        """Générer l'URL d'autorisation OAuth"""
        company = self.env.company
        
        try:
            credentials_info = json.loads(company.is_google_credentials_json)
        except json.JSONDecodeError:
            raise UserError("Le JSON des credentials Google n'est pas valide.")
        
        try:
            flow = Flow.from_client_config(
                credentials_info,
                scopes=SCOPES,
                redirect_uri=self._get_redirect_uri()
            )
            auth_url, _ = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true',
                prompt='consent',
                state=f"{self.id}-{company.id}"
            )

            self.write({
                'state': 'auth',
                'auth_url': auth_url,
                'code_verifier': flow.code_verifier,
            })
            
            return {
                'type': 'ir.actions.act_window',
                'res_model': self._name,
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
            }
            
        except Exception as e:
            raise UserError(f"Erreur lors de la génération de l'URL d'autorisation: {e}")
    
    def _do_import(self, creds):
        """Effectuer l'import des événements de tous les calendriers"""
        try:
            service = build('calendar', 'v3', credentials=creds)
            
            # Formater les dates pour l'API (convertir Date en datetime)
            time_min = datetime.combine(self.date_debut, datetime.min.time()).isoformat() + 'Z'
            time_max = datetime.combine(self.date_fin, datetime.max.time()).isoformat() + 'Z'
            
            # Récupérer la configuration des calendriers depuis la société
            company = self.env.company
            calendar_config = {cfg.name: cfg.color for cfg in company.is_google_calendar_ids}
            calendar_filter = list(calendar_config.keys()) if calendar_config else []
            
            # Récupérer la liste de tous les calendriers
            calendar_list = service.calendarList().list().execute()
            calendars = calendar_list.get('items', [])
            
            events = []
            for calendar in calendars:
                calendar_id = calendar.get('id')
                calendar_name = calendar.get('summary', calendar_id)
                
                # Filtrer les calendriers si un filtre est défini
                if calendar_filter and calendar_name not in calendar_filter:
                    continue
                
                # Récupérer la couleur configurée ou 1 par défaut
                calendar_color = calendar_config.get(calendar_name, 1)
                
                try:
                    events_result = service.events().list(
                        calendarId=calendar_id,
                        timeMin=time_min,
                        timeMax=time_max,
                        singleEvents=True,
                        orderBy='startTime'
                    ).execute()
                    # Ajouter le nom du calendrier et la couleur à chaque événement
                    for event in events_result.get('items', []):
                        event['_calendar_name'] = calendar_name
                        event['_calendar_color'] = calendar_color
                        event['_calendar_id'] = calendar_id
                        events.append(event)
                except Exception as e:
                    _logger.warning(f"Erreur lors de la récupération du calendrier '{calendar_name}': {e}")
                    continue
            
        except Exception as e:
            raise UserError(f"Erreur lors de la récupération des événements: {e}")
        
        # Créer ou mettre à jour les enregistrements de suivi du temps
        suivi_temps_model = self.env['is.suivi.temps']
        created_ids = []
        updated_ids = []
        
        for event in events:
            google_event_id = event.get('id')
            start = event.get('start', {})
            end = event.get('end', {})
            
            start_str = start.get('dateTime', start.get('date'))
            end_str = end.get('dateTime', end.get('date'))
            
            if start_str and end_str:
                try:
                    if 'T' in start_str:
                        # Parse avec timezone puis convertir en UTC naive
                        date_debut = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                        date_fin = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
                        # Convertir en naive datetime (enlever le timezone)
                        date_debut = date_debut.replace(tzinfo=None)
                        date_fin = date_fin.replace(tzinfo=None)
                    else:
                        date_debut = datetime.strptime(start_str, '%Y-%m-%d')
                        date_fin = datetime.strptime(end_str, '%Y-%m-%d')
                    
                    # Parser la description pour extraire les informations
                    description_orig = event.get('summary', 'Sans titre')
                    suivi_temps_obj = suivi_temps_model.browse()  # Instance vide pour appeler la méthode
                    parsed_info = suivi_temps_obj.parse_description(description_orig)
                    
                    # Chercher le client par son code
                    partner_id = False
                    if parsed_info['code_client']:
                        partner = self.env['res.partner'].search([
                            ('is_code_client', '=ilike', parsed_info['code_client'])
                        ], limit=1)
                        if partner:
                            partner_id = partner.id
                    
                    vals = {
                        'date_debut': date_debut,
                        'date_fin': date_fin,
                        'description': description_orig,
                        'google_event_id': google_event_id,
                        'google_calendar_id': event.get('_calendar_id', ''),
                        'google_calendar_name': event.get('_calendar_name', ''),
                        'color': event.get('_calendar_color', 1),
                        'fait': parsed_info['fait'],
                        'partner_id': partner_id,
                        'temps_facturable': parsed_info['temps_facturable'],
                    }
                    
                    # Vérifier si l'événement existe déjà
                    existing = suivi_temps_model.search([('google_event_id', '=', google_event_id)], limit=1)
                    if existing:
                        existing.write(vals)
                        updated_ids.append(existing.id)
                    else:
                        record = suivi_temps_model.create(vals)
                        created_ids.append(record.id)
                    
                except Exception as e:
                    _logger.warning(f"Erreur lors de la création de l'événement '{event.get('summary', '')}': {e}")
                    continue
        
        # Générer les fiches de suivi du temps par client
        self._generate_client_summary(created_ids + updated_ids)
        
        # Afficher la vue liste avec les événements créés ou mis à jour
        all_ids = created_ids + updated_ids
        return {
            'type': 'ir.actions.act_window',
            'name': f'Événements importés ({len(created_ids)} créés, {len(updated_ids)} mis à jour)',
            'res_model': 'is.suivi.temps',
            'view_mode': 'list,form',
            'domain': [('id', 'in', all_ids)],
            'target': 'current',
        }
    
    def _generate_client_summary(self, suivi_temps_ids):
        """Générer ou mettre à jour les fiches de suivi du temps par client"""
        if not suivi_temps_ids:
            return
        
        suivi_temps_model = self.env['is.suivi.temps']
        suivi_temps_client_model = self.env['is.suivi.temps.client']
        
        # Récupérer tous les enregistrements importés pour identifier les clients et mois concernés
        suivi_temps_records = suivi_temps_model.browse(suivi_temps_ids)
        
        # Identifier les combinaisons (client, mois) concernées
        client_month_keys = set()
        for record in suivi_temps_records:
            if record.partner_id and record.date_debut:
                mois = record.date_debut.strftime('%Y-%m')
                client_month_keys.add((record.partner_id.id, mois))
        
        # Pour chaque combinaison (client, mois), récupérer TOUTES les tâches
        for partner_id, mois in client_month_keys:
            # Calculer les dates de début et fin du mois
            mois_debut = datetime.strptime(f"{mois}-01", '%Y-%m-%d')
            if mois_debut.month == 12:
                mois_fin = datetime(mois_debut.year + 1, 1, 1)
            else:
                mois_fin = datetime(mois_debut.year, mois_debut.month + 1, 1)
            
            # Rechercher toutes les tâches du client pour ce mois
            all_records = suivi_temps_model.search([
                ('partner_id', '=', partner_id),
                ('date_debut', '>=', mois_debut),
                ('date_debut', '<', mois_fin)
            ], order='date_debut')
            
            # Construire les données
            taches = []
            temps_facturable = 0.0
            temps_passe = 0.0
            
            for record in all_records:
                if record.description_simplifiee:
                    jour_mois = record.date_debut.strftime('%d/%m')
                    tache_formatee = f"{jour_mois} - {record.description_simplifiee}"
                    taches.append(tache_formatee)
                
                temps_facturable += record.temps_facturable or 0.0
                temps_passe += record.duree or 0.0
            
            # Créer la liste des tâches avec retour à la ligne
            taches_text = '\n'.join(taches)
            
            vals = {
                'partner_id': partner_id,
                'mois': mois,
                'taches_effectuees': taches_text,
                'temps_facturable': temps_facturable,
                'temps_passe': temps_passe,
            }
            
            # Vérifier si la fiche existe déjà
            existing = suivi_temps_client_model.search([
                ('partner_id', '=', partner_id),
                ('mois', '=', mois)
            ], limit=1)
            
            if existing:
                # Mettre à jour la fiche existante
                existing.write(vals)
            else:
                # Créer une nouvelle fiche
                suivi_temps_client_model.create(vals)
