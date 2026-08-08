# Trouver les CVE corrigées par une version de noyau Debian

Exemple utilisé : passage de `6.12.95+deb13-cloud-amd64` à `6.12.101+deb13-cloud-amd64` sur VPS OVH

## 1. Changelog Debian du paquet (le plus direct, mais piégeux)

`apt changelog linux-image-...` et `zcat /usr/share/doc/.../changelog.Debian.gz`
échouent souvent :
- sur les images cloud minimales, `/usr/share/doc/.../changelog.Debian.gz` n'est
  pas installé ;
- `apt changelog` résout vers le paquet `linux-signed-amd64` (méta-paquet de
  signature) dont le changelog n'existe pas sur ftp-master (404) ;
- le vrai contenu (et les CVE) se trouve dans le paquet **source** `linux`,
  pas dans `linux-image-*` ni `linux-signed-amd64`.

Commande fiable, testée en lecture seule sur un serveur (cherche automatiquement
la dernière version de changelog disponible sur ftp-master, car les versions les
plus récentes issues de `trixie-security` peuvent ne pas encore y être indexées) :

```bash
LATEST=$(curl -s "https://metadata.ftp-master.debian.org/changelogs/main/l/linux/" \
  | grep -oE 'linux_6\.12\.[0-9]+-1_changelog' | sort -t. -k3 -n -u | tail -1)

curl -s "https://metadata.ftp-master.debian.org/changelogs/main/l/linux/${LATEST}" \
  | grep -oE 'CVE-[0-9]{4}-[0-9]+' | sort -u
```

Pour une version précise (si son changelog est déjà indexé) :

```bash
curl -s "https://metadata.ftp-master.debian.org/changelogs/main/l/linux/linux_6.12.100-1_changelog" \
  | grep -oE 'CVE-[0-9]{4}-[0-9]+' | sort -u
```

Ne pas utiliser `apt-get source linux` pour ça : si les dépôts `backports` sont
activés, apt peut résoudre vers un paquet source `linux` totalement différent
(vu en test : version `7.1.3-1~bpo13+1`, 163 Mo, sans rapport avec le noyau
installé).

## 2. Debian Security Tracker (source officielle)

https://security-tracker.debian.org/tracker/source-package/linux

Liste toutes les CVE connues pour le paquet `linux`, avec la version qui corrige
chacune (ex: "fixed in 6.12.100-1"). Filtrer les CVE dont le "fixed version" se
situe entre l'ancienne et la nouvelle version installée.

## 3. debsecan (ligne de commande, scan local)

```bash
apt install debsecan
debsecan --suite trixie --format detail
```

Compare les paquets installés sur la machine aux CVE connues et indique
lesquelles sont corrigées ou encore ouvertes.

## 4. Suivi amont kernel.org

Utile pour le détail technique de chaque CVE, mais moins pertinent pour Debian
car les correctifs sont backportés indépendamment des releases stables amont.

## Contexte

Ce besoin est apparu suite à la vérification du serveur grafana12.infosaone.com,
qui était resté sur le noyau `6.12.95+deb13-cloud-amd64` du 16/07/2026 au
08/08/2026 faute de redémarrage après mise à jour (voir `/var/run/reboot-required.pkgs`
qui listait les noyaux 6.12.96 à 6.12.101 installés mais non actifs).
