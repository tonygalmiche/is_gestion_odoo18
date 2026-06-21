# Module is_gestion_odoo18 — Documentation

**Auteur** : InfoSaône / Tony Galmiche  
**Version** : 18.0.1.0.0  
**Licence** : LGPL-3  
**Dépendances** : `base`, `account`, `l10n_fr`, `l10n_fr_account`

---

## Vue d'ensemble

Module Odoo 18 développé sur mesure pour InfoSaône. Il regroupe cinq domaines fonctionnels accessibles depuis le menu principal **CRM** :

| Domaine | Description |
|---|---|
| Clients / Affaires | Gestion commerciale des affaires et clients |
| Suivi du temps | Import Google Calendar et reporting mensuel |
| Serveurs | Inventaire des VPS/serveurs managés |
| CVE | Veille en sécurité et suivi des vulnérabilités |
| Factures | Accès et statistiques de facturation |

---

## Structure du module

```
is_gestion_odoo18/
├── models/
│   ├── is_affaire.py             # Modèle Affaire
│   ├── is_serveur.py             # Modèle Serveur + actions
│   ├── is_cve.py                 # Modèle CVE
│   ├── is_suivi_temps.py         # Suivi du temps (événements)
│   ├── is_suivi_temps_client.py  # Synthèse mensuelle par client
│   ├── is_google_calendar_config.py  # Config calendriers par société
│   ├── account_move.py           # Extension factures
│   ├── res_partner.py            # Extension partenaires
│   └── res_company.py            # Extension société
├── wizards/
│   └── is_import_google_calendar_wizard.py  # Import OAuth2 Google Calendar
├── views/                        # Vues XML
├── report/                       # Rapport de facturation personnalisé
├── security/ir.model.access.csv  # Droits d'accès
├── scripts-externes/             # Scripts Python d'administration VPS
└── cve/                          # Fichiers de documentation CVE
```

---

## Modèles

### `is.affaire` — Affaire

Gestion des affaires commerciales avec numérotation automatique (séquence `is.affaire`).

| Champ | Type | Description |
|---|---|---|
| `name` | Char | Numéro d'affaire (auto, lecture seule) |
| `intitule` | Char | Intitulé de l'affaire (obligatoire) |
| `partner_id` | Many2one `res.partner` | Client (sociétés uniquement) |
| `date_debut` | Date | Date de début (défaut : aujourd'hui) |
| `date_fin` | Date | Date de fin |
| `ca_previsionnel` | Float | CA prévisionnel (€) |
| `frais_previsionnel` | Float | Frais prévisionnels (€) |
| `commentaire` | Text | Commentaire libre |
| `facture_ids` | One2many `account.move` | Factures liées |
| `state` | Selection | État : `devis` / `abandonnee` / `active` / `soldee` |

La méthode `name_get()` affiche `[N° affaire] Intitulé (Client)`. La recherche (`_name_search`) porte sur le numéro, l'intitulé et le nom du client.

---

### `is.serveur` — Serveur

Inventaire des serveurs/VPS avec suivi chatter (`mail.thread`).

| Champ | Type | Description |
|---|---|---|
| `name` | Char | Nom du serveur |
| `partner_id` | Many2one `res.partner` | Client |
| `fournisseur_id` | Many2one `res.partner` | Fournisseur hébergement |
| `adresse_ip` | Char | Adresse IP |
| `date_creation` | Date | Date de création |
| `date_fin` | Date | Fin d'abonnement |
| `renouvellement_auto` | Selection | Renouvellement automatique oui/non |
| `service_id` | Many2one `is.service` | Service (Odoo, Web, Mail…) |
| `acces_ssh` | Char | Chaîne de connexion SSH |
| `mot_de_passe` | Char | Mot de passe (non tracké) |
| `systeme_id` | Many2one `is.systeme` | Système d'exploitation |
| `info_systeme` | Char | Infos OS/noyau (mis à jour par script) |
| `type_vps_id` | Many2one `is.type.vps` | Type de VPS |
| `grafana` | Boolean | Présence sur Grafana |
| `sauvegarde` | Boolean | Vérification sauvegarde active |
| `active` | Boolean | Serveur actif (archivage standard) |
| `upgrade_auto` | Boolean | Mise à jour automatique autorisée |
| `date_debut_maintenance` | Date | Date contrat maintenance (relié au client) |
| `action_ids` | One2many `is.serveur.action` | Historique des actions |
| `nb_actions` | Integer | Nombre d'actions (calculé) |

**Actions disponibles :**
- `action_open_actions()` : ouvre la liste des actions liées
- `action_import_commentaire()` : parse le champ `commentaire` pour créer des `is.serveur.action` à partir des lignes au format `JJ/MM/AAAA : texte`

#### `is.serveur.action` — Actions sur les serveurs

Historique horodaté des opérations effectuées sur un serveur (mise à jour, reboot, script…).

| Champ | Type | Description |
|---|---|---|
| `serveur_id` | Many2one `is.serveur` | Serveur (cascade) |
| `partner_id` | Many2one `res.partner` | Client (relié) |
| `service_id` | Many2one `is.service` | Service (relié) |
| `systeme_id` | Many2one `is.systeme` | Système (relié) |
| `date_heure` | Datetime | Date/heure de l'action |
| `action` | Char | Libellé de l'action |
| `commentaire` | Text | Détail / résultat |

#### Modèles de référence

- **`is.systeme`** : liste des OS (Ubuntu, Debian…)
- **`is.type.vps`** : types de VPS (KVM, LXC…)
- **`is.service`** : services hébergés (Odoo, Web, Mail…)

---

### `is.cve` — Vulnérabilité (CVE)

Suivi des vulnérabilités de sécurité avec calcul automatique d'un score de gravité composite.

| Champ | Type | Description |
|---|---|---|
| `cve_id` | Char | Identifiant CVE (ex : CVE-2024-12368) |
| `name` | Char | Nom de la vulnérabilité |
| `state` | Selection | État : `creation` / `analyse` / `traite` / `non_concerne` |
| `severity` | Selection | Sévérité : critical / high / medium / low / info |
| `cvss_score` | Float | Score CVSS (0–10) |
| `epss_score` | Float | Score EPSS (probabilité d'exploitation) |
| `epss_percentile` | Float | Percentile EPSS |
| `is_kev` | Boolean | Répertoriée dans la liste KEV de la CISA |
| `is_poc` | Boolean | PoC (proof-of-concept) disponible |
| `is_patch_available` | Boolean | Correctif disponible |
| `is_remote` | Boolean | Exploitation distante possible |
| `is_template` | Boolean | Template Nuclei disponible |
| `is_auth` | Boolean | Authentification requise |
| `score_gravite` | Float | Score de gravité composite calculé (0–100) |
| `analyse` | Text | Analyse interne |
| `description` | Text | Description de la vulnérabilité |
| `impact` | Text | Impact |
| `remediation` | Text | Remédiation |
| `json_detail` | Text | Données JSON brutes de l'outil de scan |

**Formule du score de gravité** (`_compute_score_gravite`) :

```
score = (cvss_score / 10) × 50
      + epss_score × 20
      + 20 si KEV
      + 10 si PoC disponible
      + 5  si pas de patch
      + 5  si exploitation distante
score = min(score, 100)
```

Les colonnes Kanban sont toujours affichées (même vides) grâce à `_group_expand_states`.

---

### `is.suivi.temps` — Suivi du temps

Enregistrements de temps importés depuis Google Calendar.

| Champ | Type | Description |
|---|---|---|
| `date_debut` | Datetime | Début de l'événement |
| `date_fin` | Datetime | Fin de l'événement |
| `duree` | Float | Durée calculée en heures |
| `description` | Text | Titre/description de l'événement Google |
| `description_simplifiee` | Char | Description nettoyée (sans préfixes FAIT/code client) |
| `fait` | Boolean | Tâche marquée FAIT dans la description |
| `partner_id` | Many2one `res.partner` | Client identifié par son code |
| `temps_facturable` | Float | Temps facturable extrait de la description (ex : `(4H)`) |
| `google_event_id` | Char | ID événement Google (clé de déduplication) |
| `google_calendar_id` | Char | ID du calendrier Google |
| `google_calendar_name` | Char | Nom du calendrier |
| `google_calendar_url` | Char | URL calculée vers l'événement dans Google Calendar |
| `color` | Integer | Couleur (par calendrier) |

**Parsing de la description** (`parse_description`) :
La description des événements Google respecte la convention :
```
[FAIT :] [CODE_CLIENT :] Libellé de la tâche [(XH)]
```
- `FAIT :` → champ `fait = True`
- `CODE_CLIENT :` → recherche du partenaire par `is_code_client`
- `(4H)` en fin de ligne → champ `temps_facturable`

---

### `is.suivi.temps.client` — Synthèse mensuelle par client

Récapitulatif automatique du temps passé par client et par mois (généré à l'import).

| Champ | Type | Description |
|---|---|---|
| `mois` | Char | Mois au format `YYYY-MM` (unique par client) |
| `partner_id` | Many2one `res.partner` | Client |
| `taches_effectuees` | Text | Liste des tâches du mois |
| `temps_facturable` | Float | Total temps facturable (H) |
| `temps_passe` | Float | Total temps passé (H) |
| `temps_facture` | Float | Temps facturé (à saisir manuellement) |
| `commentaire` | Text | Commentaire libre |

Contrainte unique : une seule fiche par couple `(mois, partner_id)`.  
`action_view_taches()` ouvre la liste des événements du client pour le mois concerné.

---

### `is.google.calendar.config` — Configuration des calendriers

Configure les calendriers Google à importer par société.

| Champ | Type | Description |
|---|---|---|
| `name` | Char | Nom exact du calendrier dans Google Calendar |
| `company_id` | Many2one `res.company` | Société |
| `color` | Integer | Couleur d'affichage (1–11) |

---

### Extensions des modèles standard

#### `account.move` (Factures)

| Champ ajouté | Type | Description |
|---|---|---|
| `is_affaire_id` | Many2one `is.affaire` | Affaire liée |
| `is_date_paiement` | Date | Date de paiement |
| `is_amount_untaxed_percent` | Float | Total HT (calculé) |

#### `account.move.line` (Lignes de factures)

| Champ ajouté | Type | Description |
|---|---|---|
| `is_account_invoice_line_id` | Integer | Lien de migration depuis l'ancienne table |

#### `res.partner` (Partenaires)

| Champ ajouté | Type | Description |
|---|---|---|
| `is_effectif` | Integer | Effectif de l'entreprise |
| `is_activite` | Char | Secteur d'activité |
| `is_dirigeant` | Char | Nom du dirigeant |
| `is_contact` | Char | Contact principal |
| `is_date_debut_maintenance` | Date | Date début contrat de maintenance |
| `is_derniere_intervention` | Text | Commentaire dernière intervention |
| `is_siren` | Char | Numéro SIREN |
| `is_forme_juridique` | Char | Forme juridique |
| `is_date_debut_activite` | Date | Date de début d'activité |
| `is_categorie` | Char | Catégorie interne |
| `is_dynacase_id` | Integer | ID dans l'ancien logiciel Dynacase |
| `is_code_client` | Char | Code court utilisé dans Google Calendar |

#### `res.company` (Société)

| Champ ajouté | Type | Description |
|---|---|---|
| `is_num_formation` | Char | Numéro de déclaration d'activité de formation |
| `is_google_credentials_json` | Text | JSON des credentials OAuth2 Google |
| `is_google_token_json` | Text | JSON du token OAuth2 (auto-généré) |
| `is_google_calendar_ids` | One2many `is.google.calendar.config` | Calendriers à importer |

---

## Wizard : Import Google Calendar

**Modèle** : `is.import.google.calendar.wizard`

Importe les événements Google Calendar dans `is.suivi.temps` via l'API Google Calendar v3 (OAuth2).

### Prérequis

```bash
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

### Flux d'authentification

```
Lancer l'import
    │
    ├─ Token valide → import direct
    │
    └─ Pas de token
           │
           ├─ Générer URL d'autorisation OAuth2 (affichée à l'utilisateur)
           │
           └─ Saisir le code → valider → sauvegarder le token → import
```

### Déroulement de l'import (`_do_import`)

1. Connexion à l'API Google Calendar
2. Récupération de tous les calendriers de la société (filtrés par `is.google.calendar.config`)
3. Pour chaque événement dans la période sélectionnée :
   - Parsing de la description (FAIT, code client, temps facturable)
   - Recherche du partenaire par `is_code_client`
   - Création ou mise à jour de `is.suivi.temps` (déduplication par `google_event_id`)
4. Génération automatique des synthèses `is.suivi.temps.client` (`_generate_client_summary`)

### Configuration dans Odoo

Dans la fiche société (onglet *Google Calendar*) :
1. Coller le contenu du fichier JSON téléchargé depuis Google Cloud Console
2. Ajouter les calendriers à importer (nom exact)
3. Lancer l'import depuis *CRM > Suivi du temps > Import Google Calendar*

---

## Scripts externes (`scripts-externes/`)

Ces scripts Python utilisent l'API XML-RPC d'Odoo pour administrer les VPS en masse.

### `config.py`

Centralise les paramètres de connexion Odoo (URL, base de données, identifiants).

### `liste-vps.py`

Affiche en console la liste des serveurs actifs sous contrat de maintenance.

```bash
python3 liste-vps.py
```

### `verif-update-vps.py`

Script principal d'administration des VPS. Se connecte en SSH sur chaque serveur éligible.

```bash
python3 verif-update-vps.py [filtre] [options]
```

| Option | Description |
|---|---|
| `--update` | `apt-get update` puis liste les paquets à mettre à jour |
| `--dist-upgrade` | `apt-get dist-upgrade` |
| `--reboot` | `dist-upgrade` puis reboot |
| `--dirty-frag` | Applique la mitigation CVE-2026-43284/43500 (DirtyFrag) |
| `--get-system` | Récupère OS, version et noyau (met à jour `info_systeme` dans Odoo) |
| `--get-database-manager` | Vérifie si `/web/database/manager` est exposé sur les serveurs Odoo |
| `--get-reset-password` | Vérifie si `/web/reset_password` est exposé |
| `--add-action` | Enregistre le résultat dans `is.serveur.action` |
| `--script <fichier>` | Copie et exécute un script bash local sur les serveurs |

Seuls les serveurs avec `active=True`, `upgrade_auto=True` et un contrat de maintenance sont traités.

### `scan-ports-vps.py`

Scan des ports ouverts sur les VPS.

### `get-conso-enedis.py`

Récupère la consommation électrique via l'API Enedis Data Connect (credentials à configurer dans `config.py`).

### `vulnx/import-cve-avec-vulnx.py`

Import de CVE dans `is.cve` à partir des résultats de l'outil VulnX/Nuclei.

---

## Menu et navigation

**Menu principal : CRM**

```
CRM
├── Clients
├── Affaires
├── Suivi du temps
│   ├── Suivi du temps
│   ├── Suivi par client
│   └── Import Google Calendar
├── Serveurs
│   ├── Serveurs
│   ├── Actions sur les serveurs
│   ├── Systèmes          [référentiel]
│   ├── Types de VPS      [référentiel]
│   └── Services          [référentiel]
├── CVE
└── Factures
    ├── Factures
    ├── Lignes de factures
    └── Statistiques
        ├── Factures par client et par mois
        └── Factures par client et par an
```

---

## Droits d'accès

Tous les modèles du module accordent les droits complets (lecture, écriture, création, suppression) au groupe `base.group_user` (utilisateurs internes).

---

## Rapport de facturation

Un rapport de facture personnalisé remplace le rapport standard Odoo (`report/report_invoice.xml`). Il inclut des templates partagés (`report/report_templates.xml`) et des assets CSS/SCSS (`static/src/scss/style.scss`).
