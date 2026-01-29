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

1. Allez dans **APIs et services** > **Identifiants**
2. Cliquez sur **Créer des identifiants** > **ID client OAuth**
3. Sélectionnez **Application de bureau** comme type d'application
4. Donnez un nom (ex: "Odoo Desktop Client")
5. Cliquez sur **Créer**
6. **Important** : Cliquez sur **Télécharger JSON** pour récupérer le fichier de credentials

## Étape 5 : Configurer Odoo

1. Ouvrez le fichier JSON téléchargé avec un éditeur de texte
2. Copiez tout le contenu du fichier
3. Dans Odoo, allez dans **Paramètres** > **Sociétés** > Votre société
4. Collez le contenu JSON dans le champ **"Google Calendar Credentials (JSON)"**
5. Enregistrez

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
5. **Première fois uniquement** : Une fenêtre de navigateur s'ouvrira pour vous demander d'autoriser l'application
6. Connectez-vous avec votre compte Google et autorisez l'accès
7. Les événements seront importés

## Structure du fichier JSON credentials

Le fichier JSON téléchargé ressemble à ceci :

```json
{
  "installed": {
    "client_id": "XXXXX.apps.googleusercontent.com",
    "project_id": "votre-projet",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_secret": "XXXXX",
    "redirect_uris": ["http://localhost"]
  }
}
```

## Dépannage

### Erreur "Les bibliothèques Google API ne sont pas installées"
Installez les dépendances Python avec la commande mentionnée à l'étape 6.

### Erreur "Le JSON des credentials Google n'est pas valide"
Vérifiez que vous avez copié tout le contenu du fichier JSON, sans modification.

### Erreur lors de l'autorisation OAuth
- Assurez-vous que votre email est ajouté comme utilisateur de test dans la console Google Cloud
- Vérifiez que l'API Google Calendar est bien activée
- Si l'application est en mode "Test", seuls les utilisateurs de test peuvent l'utiliser

### Le navigateur ne s'ouvre pas pour l'autorisation
Assurez-vous que le port 8090 n'est pas utilisé par une autre application.

## Notes de sécurité

- Les credentials et tokens sont stockés dans la base de données Odoo
- Le token d'accès est automatiquement rafraîchi quand il expire
- Seul l'accès en lecture seule au calendrier est demandé (`calendar.readonly`)
