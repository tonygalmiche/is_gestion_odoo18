# Configuration de l'API Google Calendar pour Odoo

Ce document explique comment configurer l'API Google Calendar pour permettre l'import des événements dans le module "Suivi du temps".

## Étape 1 : Créer un projet Google Cloud

1. Accédez à la [Console Google Cloud](https://console.cloud.google.com/)
2. Cliquez sur **Sélectionner un projet** en haut de la page
3. Cliquez sur **Nouveau projet**
4. Donnez un nom à votre projet (ex: "Odoo Calendar Import")
5. Cliquez sur **Créer**

## Étape 2 : Activer l'API Google Calendar

1. Dans le menu de gauche, allez dans **APIs et services** > **Bibliothèque**
2. Recherchez "Google Calendar API"
3. Cliquez sur **Google Calendar API**
4. Cliquez sur **Activer**

## Étape 3 : Configurer l'écran de consentement OAuth

1. Allez dans **APIs et services** > **Écran de consentement OAuth**
2. Sélectionnez **Externe** (ou **Interne** si vous avez Google Workspace)
3. Cliquez sur **Créer**
4. Remplissez les informations requises :
   - **Nom de l'application** : Odoo Calendar Import
   - **E-mail d'assistance utilisateur** : votre email
   - **E-mail du développeur** : votre email
5. Cliquez sur **Enregistrer et continuer**
6. Dans **Champs d'application**, cliquez sur **Ajouter ou supprimer des champs d'application**
7. Recherchez et sélectionnez : `https://www.googleapis.com/auth/calendar.readonly`
8. Cliquez sur **Mettre à jour** puis **Enregistrer et continuer**
9. Dans **Utilisateurs de test**, ajoutez votre adresse email Google
10. Cliquez sur **Enregistrer et continuer**

## Étape 4 : Créer les identifiants OAuth 2.0

Depuis 2023, Google a déprécié le flux "hors bande" (OOB, copier-coller manuel du code) et bloque désormais les URI de redirection en `http://` non-loopback (erreur `invalid_request` / `invalid_grant`). Il faut donc utiliser un vrai `redirect_uri`, servi en **HTTPS**, pointant vers un contrôleur Odoo dédié.

> ⚠️ Interface Google mise à jour : la console s'appelle maintenant **"Google Auth Platform"**. L'étape "Externe/Interne" est devenue l'onglet **Audience** (Type d'utilisateur + Utilisateurs de test), et le scope se configure dans l'onglet **Accès aux données** (ajoutez uniquement `.../auth/calendar.readonly`, pas besoin de `calendar.calendarlist`).

1. Dans le menu **Google Auth Platform**, allez dans **Clients**
2. Cliquez sur **Créer des identifiants** > **ID client OAuth**
3. Sélectionnez **Application Web** comme type d'application (et non "Application de bureau")
4. Donnez un nom (ex: "Odoo Calendar Import")
5. Dans **URI de redirection autorisés**, ajoutez :
   ```
   https://gestion-odoo18.com/google_calendar/callback
   ```
   **Important** : depuis 2025, Google exige que le nom de domaine se termine par un vrai TLD public reconnu (`.com`, `.org`, ...) pour un client "Application Web" — un simple nom d'hôte local comme `gestion-odoo18` (sans point) est refusé ("Redirection non valide : l'URI doit se terminer par une extension de domaine public"). D'où l'usage d'un nom de domaine fictif comme `gestion-odoo18.com` : il n'a pas besoin d'être réellement enregistré/possédé (l'app OAuth reste en mode "Test"), Google ne vérifie que le format du TLD. **Évitez cependant un sous-domaine d'un vrai domaine de production** (ex: `infosaone.com`) : s'il envoie un header HSTS avec `includeSubDomains`, le navigateur bloquera alors le certificat auto-signé sans possibilité de contournement. Préférez un nom totalement inventé, jamais utilisé en HTTPS ailleurs. Ce nom n'a besoin d'exister que dans le `/etc/hosts` de vos postes clients (voir étape 5 bis) — **ne l'ajoutez jamais dans une vraie zone DNS publique**.
6. Cliquez sur **Créer**
7. **Important** : Cliquez sur **Télécharger JSON** pour récupérer le fichier de credentials

## Étape 5 : Configurer Odoo

1. Ouvrez le fichier JSON téléchargé avec un éditeur de texte
2. Copiez tout le contenu du fichier
3. Dans Odoo, allez dans **Paramètres** > **Sociétés** > Votre société
4. Collez le contenu JSON dans le champ **"Google Calendar Credentials (JSON)"**
5. Enregistrez
6. Allez dans **Paramètres** > **Technique** > **Paramètres système**, créez (ou vérifiez) le paramètre :
   - Clé : `is_gestion_odoo18.google_redirect_base_url`
   - Valeur : `https://gestion-odoo18.com`

   Ce paramètre permet d'utiliser une URL différente de `web.base.url` pour la redirection OAuth (utile si `web.base.url` n'est pas en HTTPS).

## Étape 5 bis : Servir Odoo en HTTPS localement (nginx)

Google refuse tout `redirect_uri` en HTTP simple qui n'est pas littéralement `localhost`/`127.0.0.1` (et l'exception loopback n'est de toute façon valable que pour le type de client "Application de bureau", pas "Application Web"). Il faut donc servir l'adresse en HTTPS, même avec un certificat auto-signé (Google ne vérifie jamais ce certificat : seul votre navigateur le charge, il affichera juste un avertissement à accepter une fois).

Comme Google exige aussi un nom de domaine avec un vrai TLD public (voir étape 4), on utilise un nom de domaine fictif non lié à un vrai domaine de prod (ex: `gestion-odoo18.com`), résolu uniquement en local via `/etc/hosts` sur chaque poste client :

```
# Sur chaque poste client (pas sur un DNS public !) :
<IP_DE_LA_VM_ODOO> gestion-odoo18.com
```

Sur le serveur (nginx déjà en frontal du port 8069) :

```bash
# 1. Générer un certificat auto-signé (10 ans, CN = nom d'hôte utilisé)
mkdir -p /etc/ssl/nginx
openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
  -keyout /etc/ssl/nginx/gestion-odoo18.com.key \
  -out /etc/ssl/nginx/gestion-odoo18.com.crt \
  -subj "/CN=gestion-odoo18.com"
```

Ajouter un bloc `server` dans `/etc/nginx/sites-available/default` (à côté du bloc existant sur le port 80) :

```nginx
server {
  listen 443 ssl;
  server_name gestion-odoo18.com;

  ssl_certificate /etc/ssl/nginx/gestion-odoo18.com.crt;
  ssl_certificate_key /etc/ssl/nginx/gestion-odoo18.com.key;

  proxy_read_timeout 720s;
  proxy_connect_timeout 720s;
  proxy_send_timeout 720s;

  location /websocket {
    proxy_pass http://odoochat;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $connection_upgrade;
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Real-IP $remote_addr;
  }

  location / {
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_redirect off;
    proxy_pass http://odoo;
  }
}
```

Puis recharger nginx :

```bash
sudo nginx -t && sudo systemctl reload nginx
```

Vérifiez que `gestion-odoo18.com` pointe bien vers ce serveur dans le `/etc/hosts` (jamais dans un DNS public) de chaque poste client qui doit s'y connecter, puis visitez `https://gestion-odoo18.com` une première fois pour accepter l'avertissement de certificat auto-signé.

## Étape 6 : Installer les dépendances Python

### Sur Debian 12 (Bookworm) avec un environnement virtuel

Debian 12 utilise un Python "externally managed", il faut donc utiliser un environnement virtuel (venv) pour Odoo.

#### 1. Installer les paquets nécessaires

```bash
sudo apt update
sudo apt install python3-full python3-venv python3-pip
```

#### 2. Créer l'environnement virtuel pour Odoo

```bash
# Aller dans le dossier ou placer le venv
cd /opt/odoo18

# Créer le venv
python3 -m venv venv

# Activer le venv
source venv/bin/activate
```

#### 3. Installer les dépendances Odoo

```bash
# Avec le venv activé
pip install --upgrade pip
pip install -r requirements.txt
```

#### 4. Installer les dépendances Google Calendar

```bash
# Toujours avec le venv activé
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

#### 5. Lancer Odoo avec le venv

```bash
# Méthode 1 : Activer le venv puis lancer Odoo
source /home/tony/Documents/Développement/dev_odoo/18.0/0-odoo18/venv/bin/activate
./odoo-bin -c /chemin/vers/odoo.conf

# Méthode 2 : Utiliser directement le Python du venv
/home/tony/Documents/Développement/dev_odoo/18.0/0-odoo18/venv/bin/python odoo-bin -c /chemin/vers/odoo.conf
```

#### Script de démarrage (optionnel)

Créez un script `start_odoo.sh` pour faciliter le démarrage :

```bash
#!/bin/bash
cd /home/tony/Documents/Développement/dev_odoo/18.0/0-odoo18
source venv/bin/activate
./odoo-bin -c /chemin/vers/odoo.conf "$@"
```

Puis rendez-le exécutable :

```bash
chmod +x start_odoo.sh
```

### Vérifier l'installation

Pour vérifier que les modules Google sont bien installés :

```bash
source /home/tony/Documents/Développement/dev_odoo/18.0/0-odoo18/venv/bin/activate
python -c "from google.oauth2.credentials import Credentials; print('OK')"
```

## Étape 7 : Première utilisation

1. Allez dans le menu **CRM** > **Suivi du temps**
2. Cliquez sur le bouton **Import Google Calendar**
3. Sélectionnez les dates de début et de fin
4. Cliquez sur **Importer**
5. **Première fois uniquement** : un lien d'autorisation Google s'affiche dans l'assistant
6. Cliquez sur ce lien (ouvre un nouvel onglet), connectez-vous avec votre compte Google et autorisez l'accès
7. Une page de confirmation s'affiche ("Autorisation réussie") : fermez cet onglet et revenez sur l'onglet Odoo
8. Cliquez sur **Continuer l'import** : les événements sont importés

Les fois suivantes, le token est réutilisé automatiquement (et rafraîchi si besoin) : un simple clic sur **Importer** suffit.

## Structure du fichier JSON credentials

Le fichier JSON téléchargé ressemble à ceci :

```json
{
  "web": {
    "client_id": "XXXXX.apps.googleusercontent.com",
    "project_id": "votre-projet",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_secret": "XXXXX",
    "redirect_uris": ["https://gestion-odoo18.com/google_calendar/callback"]
  }
}
```

## Dépannage

### Erreur "Les bibliothèques Google API ne sont pas installées"
Installez les dépendances Python avec la commande mentionnée à l'étape 6.

### Erreur "Le JSON des credentials Google n'est pas valide"
Vérifiez que vous avez copié tout le contenu du fichier JSON, sans modification.

### Écran Google "Accès bloqué : erreur d'autorisation" / `invalid_request`
Google refuse les `redirect_uri` en `http://` non-loopback. Vérifiez que :
- Le paramètre système `is_gestion_odoo18.google_redirect_base_url` commence bien par `https://`
- nginx sert bien ce nom d'hôte en HTTPS (voir Étape 5 bis)
- L'URI exacte (`https://gestion-odoo18.com/google_calendar/callback`) est bien déclarée dans **Google Auth Platform** > **Clients**

### "Redirection non valide : l'URI doit se terminer par une extension de domaine public"
Un nom d'hôte sans point (ex: `gestion-odoo18`) n'est plus accepté par Google pour un client "Application Web". Utilisez un nom de domaine avec un vrai TLD, même fictif et non enregistré (ex: `gestion-odoo18.com`), résolu localement via `/etc/hosts` — voir Étape 4 et Étape 5 bis.

### "Connexion bloquée : problème de sécurité potentiel" (`MOZILLA_PKIX_ERROR_SELF_SIGNED_CERT`) sans possibilité de continuer
Le domaine choisi est un sous-domaine d'un vrai domaine de production qui envoie un header `Strict-Transport-Security: includeSubDomains` (HSTS). Le navigateur bloque alors tout certificat auto-signé sans option de contournement, même via "Avancé". Utilisez un nom de domaine totalement fictif, jamais utilisé en HTTPS ailleurs (ex: `gestion-odoo18.com`), plutôt qu'un sous-domaine de votre domaine de production.

### `nginx` répond en `502 Bad Gateway`
Odoo n'est pas démarré (ou pas encore prêt) derrière nginx. Vérifiez qu'il écoute sur le port 8069 dans la VM (`ss -tlnp | grep 8069`) et démarrez-le si besoin.

### La page reste bloquée sur "La connexion a échoué" malgré une config HTTP correcte
Si le nom d'hôte utilise un vrai domaine public (ex: `infosaone.com`), Firefox peut forcer un passage en HTTPS (mode "HTTPS-Only" ou préchargement HSTS) même si seul le port 80 est configuré. Terminez la configuration HTTPS (Étape 5 bis) plutôt que de désactiver ce mode.

### Erreur `invalid_grant` lors de la validation
Le code d'autorisation a expiré ou a déjà été utilisé (ne peut servir qu'une seule fois, quelques minutes). Relancez l'assistant depuis le début (**Importer** régénère un nouveau lien) sans réutiliser un ancien lien/onglet.

### Erreur lors de l'autorisation OAuth
- Assurez-vous que votre email est ajouté comme utilisateur de test dans l'onglet **Audience** de Google Auth Platform
- Vérifiez que l'API Google Calendar est bien activée et que le scope `.../auth/calendar.readonly` est ajouté dans l'onglet **Accès aux données**
- Si l'application est en mode "Test", seuls les utilisateurs de test peuvent l'utiliser

## Notes de sécurité

- Les credentials et tokens sont stockés dans la base de données Odoo
- Le token d'accès est automatiquement rafraîchi quand il expire
- Seul l'accès en lecture seule au calendrier est demandé (`calendar.readonly`)
- Le certificat HTTPS auto-signé n'est vérifié par aucun serveur Google : il ne sert qu'à faire transiter la redirection du navigateur vers Odoo
