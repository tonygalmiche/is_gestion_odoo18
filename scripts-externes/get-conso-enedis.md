# get-conso-enedis.py

Script Python pour récupérer la consommation électrique via l'**API officielle ENEDIS Data Connect**.

---

## Important : qui peut souscrire à l'API Data Connect ?

L'API Data Connect est **gratuite**, mais réservée aux **personnes morales** (entreprises, associations, collectivités).
ENEDIS demande un justificatif lors de la souscription :

| Type d'entité | Justificatif accepté |
|---|---|
| SARL / SAS / EURL… | Extrait Kbis de moins de 3 mois |
| Association loi 1901 | Récépissé de déclaration en préfecture |
| Collectivité | Cachet officiel |

> Un particulier **ne peut pas** souscrire directement. Si vous avez une société (même une SARL de développement informatique), utilisez-la — **l'accès reste gratuit**, ENEDIS ne facture pas l'API.

Le Kbis est téléchargeable gratuitement sur [infogreffe.fr](https://www.infogreffe.fr).

---

## Prérequis

### 1. Souscrire à Data Connect sur datahub-enedis.fr

1. Aller sur [https://datahub-enedis.fr/](https://datahub-enedis.fr/) → **Services API** → **Data Connect** → **Souscrire**
2. Renseigner le formulaire en 3 étapes :
   - **Type entité** : `Autre` (si SARL de développement, choisir `Entreprise`)
   - **Nom commercial** : nom de votre société ou libellé descriptif
   - **Forme juridique** : `SARL` (ou autre selon votre cas)
   - **Justificatif** : joindre votre Kbis (moins de 3 mois)
   - **Redirect URI** : `http://localhost:7777/callback` ← valeur exacte obligatoire
   - **Scopes** : `daily_consumption`, `consumption_load_curve`
3. Après validation par ENEDIS, récupérer le `client_id` et le `client_secret` dans votre espace

### 2. Renseigner les paramètres dans `config.py`

### 2. Renseigner les paramètres dans `config.py`

```python
ENEDIS_CLIENT_ID     = 'votre_client_id'
ENEDIS_CLIENT_SECRET = 'votre_client_secret'
ENEDIS_PDL           = '12345678901234'   # Numéro PDL à 14 chiffres (sur votre facture)
ENEDIS_REDIRECT_URI  = 'http://localhost:7777/callback'
```

Le **numéro PDL** (Point De Livraison) se trouve sur votre facture d'électricité ou dans votre espace client ENEDIS.

### 3. Installer les dépendances Python

```bash
pip install requests
```

---

## Comment fonctionne l'authentification OAuth2

ENEDIS utilise le protocole **OAuth2** avec un flux d'autorisation par code. Voici ce qui se passe lors du premier lancement :

```
┌──────────────────────────────────────────────────────────────────┐
│  1. Le script démarre un mini serveur HTTP sur localhost:7777    │
│                          ↓                                       │
│  2. Le script ouvre votre navigateur sur la page ENEDIS          │
│                          ↓                                       │
│  3. Vous vous connectez à votre espace client ENEDIS             │
│     et autorisez l'accès à vos données                           │
│                          ↓                                       │
│  4. ENEDIS redirige VOTRE navigateur vers :                      │
│     http://localhost:7777/callback?code=XXXXXX                   │
│                          ↓                                       │
│  5. C'est votre navigateur local qui contacte localhost:7777     │
│     (ENEDIS ne se connecte JAMAIS directement à votre machine)   │
│                          ↓                                       │
│  6. Le script récupère le code, ferme le mini serveur            │
│     et l'échange contre un access_token + refresh_token          │
│                          ↓                                       │
│  7. Les tokens sont sauvegardés localement (enedis_tokens.json)  │
└──────────────────────────────────────────────────────────────────┘
```

> **Le port 7777 n'a pas besoin d'être accessible depuis internet.**
> La redirection se fait uniquement dans votre navigateur local, sur votre propre machine.
> C'est la technique standard pour les applications de bureau/CLI, définie par la [RFC 8252](https://datatracker.ietf.org/doc/html/rfc8252).

### Renouvellement automatique du token

Après le premier lancement, les tokens sont sauvegardés dans `enedis_tokens.json`. Le script les réutilise automatiquement et les renouvelle via le `refresh_token` sans demander une nouvelle autorisation.

---

## Automatisation (cron nocturne)

Le script est conçu pour tourner **sans intervention** après le premier lancement :

```
1er lancement (une seule fois, manuellement) :
  → ouvre le navigateur, vous vous connectez à votre espace ENEDIS
  → autorisez l'accès → tokens sauvegardés dans enedis_tokens.json
  → durée du token : 1 an (duration=P1Y)

Tous les lancements suivants (cron de nuit) :
  → aucun navigateur, aucune intervention humaine
  → le refresh_token est utilisé automatiquement
  → fonctionne en arrière-plan
```

### Exemple de cron (toutes les nuits à 2h)

```bash
crontab -e
# Ajouter la ligne suivante :
0 2 * * * /usr/bin/python3 /chemin/vers/get-conso-enedis.py --csv /var/data/conso-$(date +\%Y-\%m-\%d).csv
```

---

## Utilisation

```bash
# Consommation des 30 derniers jours (par défaut)
python3 get-conso-enedis.py

# Consommation sur une période précise
python3 get-conso-enedis.py --debut 2026-01-01 --fin 2026-01-31

# Export CSV
python3 get-conso-enedis.py --csv conso.csv
```

---

## Données récupérées

| Endpoint API | Description |
|---|---|
| `daily_consumption` | Consommation journalière en kWh |
| `consumption_load_curve` | Courbe de charge par pas de 30 min |
| `daily_consumption_max_power` | Puissance maximale atteinte par jour (kVA) |

---

## Fichiers générés

| Fichier | Description |
|---|---|
| `enedis_tokens.json` | Tokens OAuth2 (ne pas partager ni versionner) |
| `conso_AAAA-MM.csv` | Export CSV optionnel de la consommation |

> Ajouter `enedis_tokens.json` au `.gitignore` pour ne pas exposer vos tokens.
