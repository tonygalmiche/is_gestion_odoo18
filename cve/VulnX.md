# VulnX

**VulnX** (anciennement cvemap) est un outil en ligne de commande développé par **ProjectDiscovery** pour explorer et filtrer la base de données des CVE (vulnérabilités connues). Il agrège les données du NVD (NIST), CISA KEV, EPSS, GitHub (PoC) et Nuclei.

- Dépôt officiel : https://github.com/projectdiscovery/cvemap
- Image Docker : https://hub.docker.com/r/projectdiscovery/vulnx

## Installation

### 1. Supprimer l'ancienne image officielle (si déjà utilisée)

```bash
docker rm $(docker ps -a --filter "name=vulnx" -q)
docker rmi projectdiscovery/vulnx:v1
```

### 2. Construire l'image locale (Debian Trixie + Go)

```bash
docker compose build
```

---

## Clé API (optionnelle mais recommandée)

Sans clé API, les requêtes sont limitées à **10/minute**. Créer une clé gratuite sur https://cloud.projectdiscovery.io/ puis créer un fichier `.env` :

```
PDCP_API_KEY=votre_clé_ici
```

## Alias shell (recommandé)

Pour éviter de taper `docker compose run --rm` à chaque commande, ajoutez cet alias dans `~/.bashrc` :

```bash
alias vulnx='docker compose -f ~/Documents/Développement/Docker/VulnX/docker-compose.yml run --rm vulnx'
```

Rechargez le shell :

```bash
source ~/.bashrc
```

## Utilisation

### Afficher l'aide

```bash
vulnx --help
```

### Afficher les statistiques globales des CVE

```bash
vulnx
```

### Rechercher les CVE d'un produit

```bash
vulnx search odoo
vulnx search "mongodb || react"
```

### Obtenir le détail d'une CVE

```bash
vulnx id cve-2025-14847
```

### Filtres de recherche avancés

```bash
# CVE sur odoo critiques avec PoC, publiées à partir de 2020
vulnx search "odoo cvss_score:>8.0 && cve_created_at:>=2020 && is_poc:true" --limit 50

# CVE sur odoo dans le catalogue KEV (exploitées activement confirmées par la CISA)
vulnx search "odoo && is_kev:true" --limit 0

# CVE dans le catalogue KEV (exploitées activement)
vulnx search "is_kev:true"

# Toutes les CVE critiques (CVSS >= 9.0)
vulnx search "cvss_score:>=9.0" --limit 0

# Toutes les CVE High (CVSS 7.0 à 8.9)
vulnx search "cvss_score:>=7.0 && cvss_score:<9.0" --limit 0

# CVE publiées aujourd'hui ou hier
vulnx search "age_in_days:<=1" --limit 0

# CVE d'un éditeur spécifique
vulnx search "affected_products.vendor:microsoft"

# CVE avec score EPSS (probabilité d'exploitation dans les 30 prochains jours)
# Score > 50% : exploitation très probable
vulnx search "epss_score:>=0.50" --limit 0
# Score > 30% : exploitation probable
vulnx search "epss_score:>=0.30" --limit 0
# Score > 10% : risque modéré
vulnx search "epss_score:>=0.10" --limit 0
# Combiné : Critical + EPSS élevé (les plus urgentes à patcher)
vulnx search "cvss_score:>=9.0 && epss_score:>=0.30" --limit 0
```

### Exporter en JSON

```bash
vulnx search "is_kev:true" --json
vulnx search "cvss_score:>9.0" --output /output/critiques.json
```

### Lister les filtres disponibles (79 filtres)

```bash
vulnx filters
```

## Options principales

| Option | Description |
|--------|-------------|
| `search <produit>` | Rechercher des CVE par produit |
| `id <CVE-ID>` | Détail d'une CVE spécifique |
| `filters` | Lister les 79 filtres disponibles |
| `--limit N` | Limiter les résultats (0 = tous) |
| `--json` | Sortie au format JSON |
| `--output <fichier>` | Exporter dans un fichier |
| `--silent` | Supprimer les logs de progression |

## Résultats

Les fichiers exportés sont sauvegardés dans le dossier `./output/`.

## Mise à jour

L'image est construite avec `@latest` au moment du build. Si vulnx affiche `(outdated)`, reconstruire sans cache pour récupérer la dernière version :

```bash
docker compose build --no-cache
docker image prune -f
```

### Alternative : installation native avec Go (sans sudo)

En installant Go directement sur la machine, `vulnx` se met à jour automatiquement à chaque réinstallation, sans rebuild Docker.

Le paquet `golang-go` de Debian Bookworm est en version 1.19 (trop ancienne), mais la version 1.23 est disponible via les backports. Deux options :

**Option 1 : via les backports Debian (recommandé)**

```bash
# Activer les backports (nécessite su)
su -c "echo 'deb http://deb.debian.org/debian bookworm-backports main' >> /etc/apt/sources.list"
su -c "apt update"
su -c "apt install -y -t bookworm-backports golang-go"
```

**Option 2 : installation manuelle depuis go.dev**

```bash
cd ~
wget https://go.dev/dl/go1.24.3.linux-amd64.tar.gz
tar -xzf go1.24.3.linux-amd64.tar.gz
rm go1.24.3.linux-amd64.tar.gz
```

Ajouter Go et les binaires au PATH dans `~/.bashrc` :

```bash
echo 'export PATH=$PATH:~/go/bin' >> ~/.bashrc
source ~/.bashrc
```

Vérifier l'installation :

```bash
go version
```

Installer / mettre à jour vulnx :

```bash
wget https://github.com/projectdiscovery/vulnx/releases/download/v2.0.1/vulnx_2.0.1_linux_amd64.zip
unzip vulnx_2.0.1_linux_amd64.zip vulnx -d ~/go/bin/
rm vulnx_2.0.1_linux_amd64.zip
```

Le binaire `vulnx` est alors disponible directement dans le terminal sans Docker.
