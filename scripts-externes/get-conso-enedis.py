#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Récupération de la consommation électrique ENEDIS via l'API Data Connect.
Voir get-conso-enedis.md pour la documentation complète.
"""

import argparse
import csv
import json
import os
import sys
import threading
import time
import urllib.parse
import webbrowser
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests

sys.path.insert(0, os.path.dirname(__file__))
import config

# ---------------------------------------------------------------------------
# Constantes API ENEDIS
# ---------------------------------------------------------------------------
AUTH_URL    = "https://mon-compte-particulier.enedis.fr/dataconnect/v1/oauth2/authorize"
TOKEN_URL   = "https://mon-compte-particulier.enedis.fr/dataconnect/v1/oauth2/token"
API_BASE    = "https://conso.prm.enedis.fr/api/metering_data/v5"
TOKEN_FILE  = os.path.join(os.path.dirname(__file__), "enedis_tokens.json")

# ---------------------------------------------------------------------------
# Gestion des tokens OAuth2
# ---------------------------------------------------------------------------

def _load_tokens() -> dict:
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_tokens(tokens: dict) -> None:
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        json.dump(tokens, f, indent=2)
    os.chmod(TOKEN_FILE, 0o600)  # lecture/écriture propriétaire uniquement


def _is_expired(tokens: dict) -> bool:
    expires_at = tokens.get("expires_at", 0)
    return time.time() >= expires_at - 60  # 60 s de marge


def _refresh_access_token(tokens: dict) -> dict:
    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type":    "refresh_token",
            "refresh_token": tokens["refresh_token"],
            "client_id":     config.ENEDIS_CLIENT_ID,
            "client_secret": config.ENEDIS_CLIENT_SECRET,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    data["expires_at"] = time.time() + data.get("expires_in", 3600)
    _save_tokens(data)
    return data


# ---------------------------------------------------------------------------
# Serveur local pour capturer le callback OAuth2
# ---------------------------------------------------------------------------

_auth_code: str | None = None
_auth_error: str | None = None


class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global _auth_code, _auth_error
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if "code" in params:
            _auth_code = params["code"][0]
            body = b"<h2>Autorisation ENEDIS accord\xc3\xa9e !</h2><p>Vous pouvez fermer cet onglet.</p>"
        elif "error" in params:
            _auth_error = params.get("error_description", params["error"])[0]
            body = b"<h2>Erreur d'autorisation.</h2><p>Vous pouvez fermer cet onglet.</p>"
        else:
            body = b"<h2>Callback re\xc3\xa7u.</h2>"

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # noqa: silence les logs HTTP
        pass


def _authorize() -> dict:
    """Lance le flux OAuth2 et retourne les tokens."""
    global _auth_code, _auth_error
    _auth_code = None
    _auth_error = None

    parsed = urllib.parse.urlparse(config.ENEDIS_REDIRECT_URI)
    port = parsed.port or 7777

    server = HTTPServer(("localhost", port), _CallbackHandler)
    thread = threading.Thread(target=server.handle_request)
    thread.daemon = True
    thread.start()

    params = {
        "client_id":     config.ENEDIS_CLIENT_ID,
        "response_type": "code",
        "redirect_uri":  config.ENEDIS_REDIRECT_URI,
        "duration":      "P1Y",  # token valide 1 an
    }
    url = AUTH_URL + "?" + urllib.parse.urlencode(params)

    print("Ouverture du navigateur pour l'autorisation ENEDIS…")
    webbrowser.open(url)

    thread.join(timeout=120)

    if _auth_error:
        raise RuntimeError(f"Erreur d'autorisation ENEDIS : {_auth_error}")
    if not _auth_code:
        raise RuntimeError("Aucun code reçu dans le délai imparti (2 min).")

    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type":   "authorization_code",
            "code":         _auth_code,
            "redirect_uri": config.ENEDIS_REDIRECT_URI,
            "client_id":    config.ENEDIS_CLIENT_ID,
            "client_secret": config.ENEDIS_CLIENT_SECRET,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    data["expires_at"] = time.time() + data.get("expires_in", 3600)
    _save_tokens(data)
    print("Tokens sauvegardés.")
    return data


def get_tokens() -> dict:
    """Retourne un access_token valide (autorisation ou rafraîchissement)."""
    tokens = _load_tokens()
    if not tokens:
        return _authorize()
    if _is_expired(tokens):
        if "refresh_token" in tokens:
            print("Renouvellement du token…")
            return _refresh_access_token(tokens)
        return _authorize()
    return tokens


# ---------------------------------------------------------------------------
# Appels API ENEDIS
# ---------------------------------------------------------------------------

def _api_get(endpoint: str, params: dict, access_token: str) -> dict:
    resp = requests.get(
        f"{API_BASE}/{endpoint}",
        headers={"Authorization": f"Bearer {access_token}"},
        params=params,
        timeout=30,
    )
    if resp.status_code == 401:
        raise PermissionError("Token invalide ou expiré (401).")
    resp.raise_for_status()
    return resp.json()


def get_daily_consumption(start: date, end: date, access_token: str) -> list[dict]:
    """Retourne la consommation journalière en kWh."""
    data = _api_get(
        "daily_consumption",
        {
            "usage_point_id": config.ENEDIS_PDL,
            "start":          start.isoformat(),
            "end":            end.isoformat(),
        },
        access_token,
    )
    meter_readings = (
        data.get("meter_reading", {})
            .get("interval_reading", [])
    )
    return meter_readings  # [{"date": "2026-01-01", "value": "12.345"}, …]


def get_load_curve(start: date, end: date, access_token: str) -> list[dict]:
    """Retourne la courbe de charge (pas 30 min) en Wh."""
    data = _api_get(
        "consumption_load_curve",
        {
            "usage_point_id": config.ENEDIS_PDL,
            "start":          start.isoformat(),
            "end":            end.isoformat(),
        },
        access_token,
    )
    return (
        data.get("meter_reading", {})
            .get("interval_reading", [])
    )


# ---------------------------------------------------------------------------
# Affichage
# ---------------------------------------------------------------------------

def _display_table(readings: list[dict], titre: str) -> None:
    if not readings:
        print("Aucune donnée disponible.")
        return

    print(f"\n{'─' * 40}")
    print(f"  {titre}")
    print(f"{'─' * 40}")
    total = 0.0
    for r in readings:
        val = float(r.get("value", 0))
        total += val
        print(f"  {r['date']}   {val:>10.3f}")
    print(f"{'─' * 40}")
    print(f"  TOTAL          {total:>10.3f}")
    print(f"{'─' * 40}\n")


def _export_csv(readings: list[dict], filepath: str) -> None:
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "value"])
        writer.writeheader()
        writer.writerows(readings)
    print(f"Export CSV : {filepath}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    today = date.today()
    parser = argparse.ArgumentParser(
        description="Récupère la consommation électrique ENEDIS."
    )
    parser.add_argument(
        "--debut",
        default=(today - timedelta(days=30)).isoformat(),
        help="Date de début AAAA-MM-JJ (défaut : J-30)",
    )
    parser.add_argument(
        "--fin",
        default=today.isoformat(),
        help="Date de fin AAAA-MM-JJ (défaut : aujourd'hui)",
    )
    parser.add_argument(
        "--type",
        choices=["daily", "load_curve"],
        default="daily",
        help="Type de données (défaut : daily)",
    )
    parser.add_argument(
        "--csv",
        metavar="FICHIER",
        help="Exporte les résultats dans un fichier CSV",
    )
    parser.add_argument(
        "--reauth",
        action="store_true",
        help="Force une nouvelle autorisation (efface les tokens existants)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    try:
        debut = date.fromisoformat(args.debut)
        fin   = date.fromisoformat(args.fin)
    except ValueError as e:
        sys.exit(f"Format de date invalide : {e}")

    if debut > fin:
        sys.exit("La date de début doit être antérieure à la date de fin.")

    if args.reauth and os.path.exists(TOKEN_FILE):
        os.remove(TOKEN_FILE)
        print("Tokens supprimés, nouvelle autorisation requise.")

    tokens = get_tokens()
    access_token = tokens["access_token"]

    print(f"PDL : {config.ENEDIS_PDL}")
    print(f"Période : {debut} → {fin}")

    if args.type == "daily":
        readings = get_daily_consumption(debut, fin, access_token)
        titre = "Consommation journalière (kWh)"
    else:
        readings = get_load_curve(debut, fin, access_token)
        titre = "Courbe de charge (Wh, pas 30 min)"

    _display_table(readings, titre)

    if args.csv:
        _export_csv(readings, args.csv)


if __name__ == "__main__":
    main()
