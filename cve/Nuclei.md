# Nuclei

**Nuclei** est un scanner de vulnérabilités open source développé par **ProjectDiscovery**. Il utilise des templates YAML pour tester des cibles HTTP, DNS, TCP, etc. Complémentaire à vulnx : vulnx *identifie* les CVE applicables à un produit, nuclei *vérifie* si votre instance est réellement vulnérable.

- Dépôt officiel : https://github.com/projectdiscovery/nuclei
- Bibliothèque de templates : https://cloud.projectdiscovery.io/library

---

## Installation

### Via Docker (recommandé, sans installation)

```bash
docker pull projectdiscovery/nuclei:latest
```

Alias shell pratique à ajouter dans `~/.bashrc` :

```bash
alias nuclei='docker run --rm --network host projectdiscovery/nuclei'
```

### Via Go (installation native)

```bash
go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest
```

### Mise à jour des templates

```bash
nuclei -update-templates
```

---

## Utilisation de base

### Scanner une CVE précise

```bash
# Vérifier si une instance est vulnérable à une CVE spécifique
nuclei -u http://localhost:8069 -id CVE-2023-1434
```

### Scanner toutes les CVE d'un produit

```bash
# Toutes les CVE Odoo connues (templates passifs)
nuclei -u http://localhost:8069 -tags odoo

# Filtrer par sévérité
nuclei -u http://localhost:8069 -tags odoo -severity critical,high
```

### Exporter les résultats

```bash
# Rapport JSON
nuclei -u http://localhost:8069 -tags odoo -json -o rapport-odoo.json

# Rapport Markdown
nuclei -u http://localhost:8069 -tags odoo -markdown-export ./rapports/
```

---

## Workflow vulnx + nuclei

1. **vulnx** : identifier les CVE applicables au produit
```bash
vulnx search "odoo && is_kev:true" --limit 0
```

2. **nuclei** : vérifier si votre instance est réellement vulnérable
```bash
nuclei -u http://localhost:8069 -id CVE-2023-1434
```

3. **Appliquer les correctifs** selon les résultats

---

## Niveaux de risque des templates

| Type de template | Risque | Exemple |
|-----------------|--------|---------|
| `cve` | Faible — requêtes passives | CVE-2023-1434 |
| `misconfig` | Faible — observation de config | headers manquants |
| `default-logins` | Modéré — tentatives de login | admin/admin |
| `sqli`, `lfi`, `rce` | Élevé — payloads actifs | injection SQL |
| `fuzzing` | Très élevé — scan bruteforce | à éviter en prod |

---

## Utilisation sur une instance de production

### Ce qui est sûr

```bash
# ✅ CVE précise, depuis le réseau interne
nuclei -u http://localhost:8069 -id CVE-2023-1434

# ✅ Toutes les CVE Odoo, sévérités ciblées
nuclei -u http://localhost:8069 -tags odoo -severity low,medium,high,critical
```

### Ce qui est à éviter en production

```bash
# ⚠️ Auto-scan agressif (centaines de requêtes)
nuclei -u http://odoo-prod.example.com -as

# ⚠️ Templates de fuzzing (payloads actifs)
nuclei -u http://odoo-prod.example.com -tags fuzzing

# ⚠️ Scan depuis l'extérieur (risque de blocage IP / déclenchement WAF)
nuclei -u https://odoo-prod.example.com -tags odoo
```

### Bonnes pratiques

- Toujours scanner d'abord sur un environnement de **staging** (clone de la prod)
- Préférer scanner depuis **localhost** ou le réseau interne
- Utiliser `-id CVE-XXXX-XXXX` plutôt qu'un scan large en production
- Vérifier le contenu du template avant exécution : https://cloud.projectdiscovery.io/library

---

## Exemple complet : vérifier CVE-2023-1434 sur une instance Odoo

### 1. Lancer le scan

```bash
nuclei -u https://votre-domaine-odoo.com -id CVE-2023-1434
```

Résultat attendu si **non vulnérable** :
```
[INF] Scan completed in 312ms. No results found.
```

### 2. Valider le template en cas de warning

Si vous voyez `[WRN] Found 1 templates with runtime error` :

```bash
nuclei -u https://votre-domaine-odoo.com -id CVE-2023-1434 -validate
```

Résultat attendu :
```
[INF] All templates validated successfully
```
→ Le template est valide, le warning était un incident réseau transitoire.

### 3. Voir le détail de la requête envoyée

```bash
nuclei -u https://votre-domaine-odoo.com -id CVE-2023-1434 -v
```

Nuclei envoie une requête de ce type :
```
GET /web/set_profiling?profile=0&collectors=<script>alert(document.domain)</script>
```
Le template injecte un payload XSS dans le paramètre `collectors` de l'endpoint `/web/set_profiling` et vérifie si Odoo le reflète avec un mauvais `Content-Type`. Si rien ne matche → **non vulnérable**.

### Warning récurrent : `engines 'ruby' not available`

```
[WRN] Could not parse template CVE-2024-9487.yaml: engines 'ruby' not available on host
```

Ce warning est **sans rapport** avec le scan en cours — le template CVE-2024-9487 nécessite Ruby qui n'est pas installé. Il apparaît à chaque exécution de nuclei. Pour l'ignorer :

```bash
# Exclure explicitement le template problématique
nuclei -u https://votre-domaine-odoo.com -id CVE-2023-1434 -exclude-id CVE-2024-9487
```

---

## Mitigation sans mise à jour possible (ex. CVE-2023-1434 sur Odoo < 16)

Si la migration vers Odoo 16+ n'est pas possible, appliquer au niveau **nginx** :

```nginx
# Dans le bloc location du reverse proxy Odoo
add_header X-Content-Type-Options "nosniff" always;
add_header Content-Security-Policy "default-src 'self'" always;

# Restreindre l'accès à l'API aux IP de confiance
location /web/dataset/ {
    allow 10.0.0.0/8;
    allow 192.168.0.0/16;
    deny all;
    proxy_pass http://odoo;
}
```

Le header `X-Content-Type-Options: nosniff` empêche le navigateur de deviner le Content-Type et neutralise l'essentiel du vecteur d'attaque.

---

## Différence KEV CISA vs KEV VulnCheck

vulnx affiche deux sources pour le champ KEV :

| Source | Signification |
|--------|--------------|
| `KEV: ✔ (CISA)` | Exploitation confirmée par la CISA — patch **immédiat** |
| `KEV: ✔ (VULNCHECK)` | Exploitation détectée par VulnCheck (honeypots, dark web) — CISA non confirmé |
| `KEV: ✘` | Aucune exploitation active connue |

Une CVE absente du NVD (status RESERVED) peut quand même apparaître dans vulnx si VulnCheck l'a intégrée indépendamment (ex. CVE-2023-1434).
