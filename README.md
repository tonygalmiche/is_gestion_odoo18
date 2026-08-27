# is_gestion_odoo18

Module Odoo 18 développé sur mesure pour **InfoSaône**, regroupant la
gestion commerciale et technique de l'activité (clients, affaires, temps
passé, serveurs, veille sécurité, facturation), accessible depuis le menu
**CRM**.

| Domaine | Description |
|---|---|
| Clients / Affaires | Gestion commerciale des affaires et clients |
| Suivi du temps | Import Google Calendar et reporting mensuel par client |
| Serveurs | Inventaire des VPS/serveurs managés, historique des actions |
| CVE | Veille en sécurité et suivi des vulnérabilités |
| Factures | Accès et statistiques de facturation |

## Dépendances

`base`, `account`, `l10n_fr`, `l10n_fr_account`, `is_pivot_cumul`,
`is_web_number_color`, `l10n_fr_einvoicing`

## Documentation

- **[DOCUMENTATION.md](DOCUMENTATION.md)** — référence complète : modèles,
  champs, wizard d'import Google Calendar, scripts externes
  d'administration des VPS, menus, droits d'accès.
- **[README_GOOGLE_CALENDAR.md](README_GOOGLE_CALENDAR.md)** — pas à pas
  pour configurer l'API Google Calendar (projet Google Cloud, credentials
  OAuth2) nécessaire à l'import du suivi du temps.
- **[facturation-electronique.md](facturation-electronique.md)** —
  contexte Factur-X/EN16931 : modules impliqués, ce que corrige
  `is_gestion_odoo18`, différence entre le cas actif (génération
  conforme sans envoi PDP) et le cas non installé (envoi effectif via une
  plateforme agréée).

## Scripts d'administration des VPS

Le dossier `scripts-externes/` contient des scripts Python (API XML-RPC
Odoo + SSH) pour administrer les serveurs en masse (mises à jour,
relevé système, vérifications de sécurité). Détail des scripts et de
leurs options dans [DOCUMENTATION.md](DOCUMENTATION.md#scripts-externes-scripts-externes).
