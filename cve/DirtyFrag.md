# Dirty Frag — Faille Linux critique (mai 2026)

## Identité
| Champ | Détail |
|---|---|
| CVEs | CVE-2026-43284 (esp4/esp6) · CVE-2026-43500 (rxrpc) |
| Découvert par | Hyunwoo Kim |
| Divulgué | 7-8 mai 2026 (embargo rompu par un tiers) |
| PoC public | https://github.com/V4bel/dirtyfrag |
| Sources | [BleepingComputer](https://www.bleepingcomputer.com/news/security/new-linux-dirty-frag-zero-day-with-poc-exploit-gives-root-privileges/) · [Microsoft](https://www.microsoft.com/en-us/security/blog/2026/05/08/active-attack-dirty-frag-linux-vulnerability-expands-post-compromise-risk/) |

## Nature
Élévation de privilèges locale (**LPE**) dans le noyau Linux — un utilisateur non privilégié obtient les droits **root** avec une seule commande.

Enchaîne deux vulnérabilités dans l'interface cryptographique `algif_aead` (introduites ~2017) :
- **xfrm-ESP Page-Cache Write** — modules esp4/esp6 (CVE-2026-43284)
- **RxRPC Page-Cache Write** — module rxrpc (CVE-2026-43500)

Même famille que **Dirty Pipe** et **Copy Fail**, mais **sans race condition** → très fiable, taux de succès élevé, pas de kernel panic en cas d'échec.

## Distributions affectées
Ubuntu · RHEL · CentOS Stream · AlmaLinux · Rocky Linux · Fedora · Debian · openSUSE · SUSE · OpenShift

## Conditions d'exploitation
Accès local préalable requis (pas d'exploitation distante directe). Vecteurs courants :
- Compte SSH compromis
- Web shell sur application exposée
- Évasion de conteneur
- Compte de service faiblement privilégié

## Mitigation immédiate
> ⚠️ Casse les VPN IPsec et les systèmes de fichiers AFS distribués (RxRPC/AFS)

```bash
sh -c "printf 'install esp4 /bin/false\ninstall esp6 /bin/false\ninstall rxrpc /bin/false\n' > /etc/modprobe.d/dirtyfrag.conf; rmmod esp4 esp6 rxrpc 2>/dev/null; true"
```

Vider le cache page si exploitation suspectée :
```bash
echo 3 | tee /proc/sys/vm/drop_caches
```

## Correctifs
- **CVE-2026-43284** : patch publié le 8 mai 2026 (Linux Kernel Organization) → mettre à jour le noyau dès disponibilité distro
- **CVE-2026-43500** : pas de patch disponible au 8 mai 2026

### Debian
Patch disponible sur **Bullseye**, **Bookworm** et **Trixie**.

**Vérifier si le patch est déjà installé :**
```bash
# Version du noyau actuellement en cours d'exécution
uname -r
# → 6.12.85+deb13-cloud-amd64  (Trixie, vérifié le 13/05/2026)

# Vérifier si une mise à jour du noyau est disponible
apt update && apt list --upgradable 2>/dev/null | grep linux-image

# Vérifier si les CVE sont corrigées dans le noyau installé (via changelog)
apt-get changelog linux-image-$(uname -r) 2>/dev/null | grep -i "CVE-2026-43284\|CVE-2026-43500"
```

> ⚠️ **Résultat 13/05/2026 — Trixie `cloud-amd64`** : système à jour (`Tous les paquets sont à jour`), mais le changelog ne contient aucune des deux CVE → **patch non encore livré** dans la variante `linux-image-cloud-amd64` à cette date. La mitigation par `modprobe` reste nécessaire.
>
> **État mitigation** : modules `esp4`/`esp6`/`rxrpc` **non chargés** + `/etc/modprobe.d/dirtyfrag.conf` **présent et actif** → ✅ mitigation appliquée le 13/05/2026.
>
> **Note** : le fichier `/etc/modprobe.d/dirtyfrag.conf` peut être conservé même après l'installation du patch kernel — ces modules sont inutiles sur un serveur standard et leur blocage constitue une mesure de défense en profondeur contre de futures variantes.
> Sur un serveur **OpenVPN** (TUN/TAP), `esp4`/`esp6` ne sont pas utilisés → la mitigation est applicable sans impact. Sur un serveur **IPsec**, la mitigation casse les tunnels → privilégier l'attente du patch kernel et vérifier que les modules ne sont pas chargés (`lsmod | grep -E "^esp4|^esp6|^rxrpc"`)

**Vérifier si les modules vulnérables sont chargés :**
```bash
lsmod | grep -E "^esp4|^esp6|^rxrpc"
# Aucune sortie = modules non chargés = pas exposé
```

**Appliquer le patch si disponible :**
```bash
apt update && apt upgrade linux-image-$(uname -r)
# puis redémarrer pour activer le nouveau noyau
reboot
```
