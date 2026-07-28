# -*- coding: utf-8 -*-
import json
import logging

from markupsafe import escape
from odoo import http
from odoo.http import request

try:
    from google_auth_oauthlib.flow import Flow
except ImportError:
    Flow = None

_logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']


class GoogleCalendarController(http.Controller):

    def _html_page(self, title, message):
        return request.make_response(
            f"<html><head><meta charset='utf-8'/></head><body style='font-family:sans-serif;text-align:center;margin-top:80px;'>"
            f"<h2>{title}</h2><p>{message}</p></body></html>",
            headers=[('Content-Type', 'text/html; charset=utf-8')]
        )

    @http.route('/google_calendar/callback', type='http', auth='public', csrf=False)
    def google_calendar_callback(self, code=None, state=None, error=None, **kwargs):
        if error:
            return self._html_page("Autorisation refusée", escape(error))

        if not code or not state or '-' not in state:
            return self._html_page("Requête invalide", "Le code ou l'état de la requête est manquant.")

        wizard_id, company_id = state.split('-', 1)
        company = request.env['res.company'].sudo().browse(int(company_id))
        wizard = request.env['is.import.google.calendar.wizard'].sudo().browse(int(wizard_id))

        if not company.exists() or not company.is_google_credentials_json:
            return self._html_page("Erreur", "Société ou configuration Google introuvable.")

        if not wizard.exists():
            return self._html_page("Erreur", "L'assistant d'import n'existe plus. Relancez l'import depuis Odoo.")

        ir_config = request.env['ir.config_parameter'].sudo()
        base_url = ir_config.get_param('is_gestion_odoo18.google_redirect_base_url') \
            or ir_config.get_param('web.base.url')

        try:
            credentials_info = json.loads(company.is_google_credentials_json)
            flow = Flow.from_client_config(
                credentials_info,
                scopes=SCOPES,
                redirect_uri=f"{base_url}/google_calendar/callback",
            )
            flow.fetch_token(code=code, code_verifier=wizard.code_verifier)
            creds = flow.credentials
            company.sudo().write({'is_google_token_json': creds.to_json()})
        except Exception as e:
            _logger.warning("Erreur lors de la validation du code Google Calendar: %s", e)
            return self._html_page(
                "Erreur lors de la validation du code",
                f"{escape(str(e))}<br/>Vous pouvez fermer cette page et relancer l'autorisation depuis Odoo."
            )

        return self._html_page(
            "Autorisation réussie",
            "Vous pouvez fermer cette page et retourner sur Odoo pour cliquer sur \"Importer\"."
        )
