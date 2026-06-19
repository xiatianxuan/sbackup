# Sbackup

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-GPL--3.0-green)](../../LICENSE)
[![PyPI](https://img.shields.io/pypi/v/sbackup-cli?color=blue)](https://pypi.org/project/sbackup-cli/)
[![Tests](https://img.shields.io/badge/tests-940%20passed-brightgreen)](../../.github/workflows/ci.yml)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)]()

> Outil de sauvegarde de dossiers léger et efficace, fonctionnant en ligne de commande, pour gérer vos stratégies de sauvegarde en toute simplicité.

[English](../../README.md) | [Deutsch](README_de.md) | [Espanol](README_es.md) | [Francais](README_fr.md) | [Portugues](README_pt.md) | [Pycckuu](README_ru.md) | [日本語](README_ja.md) | [한국어](README_ko.md) | [中文](README_zh.md)

- [Introduction](#introduction)
- [Fonctionnalites](#fonctionnalites)
- [Demarrage rapide](#demarrage-rapide)
  - [Installation](#installation)
  - [Utilisation](#utilisation)
- [Fichier de configuration](#fichier-de-configuration)
  - [Exemple de configuration](#exemple-de-configuration)
- [Sauvegarde SFTP distante](#sauvegarde-sftp-distante)
- [Sauvegarde WebDAV distante](#sauvegarde-webdav-distante)
- [Principe de fonctionnement](#principe-de-fonctionnement)
- [Guide de developpement](#guide-de-developpement)
  - [Executer les tests](#executer-les-tests)
  - [Structure du code](#structure-du-code)
- [Questions frequentes](#questions-frequentes)
- [Guide de contribution](#guide-de-contribution)
- [Licence](#licence)
- [Auteur](#auteur)

---

## Introduction

Sbackup est un outil de sauvegarde de dossiers léger qui permet d'ajouter, supprimer et consulter des stratégies de sauvegarde via la ligne de commande. Il se base sur la date de dernière modification des dossiers pour déterminer si une sauvegarde est nécessaire, garantissant ainsi que vos données sont toujours à jour.

## Fonctionnalites

- **Sauvegarde incrémentielle** : ne sauvegarde que les dossiers modifiés, économisant temps et espace de stockage
- **Multi-format** : prend en charge sept formats d'archivage — ZIP, tar, tar.gz, tar.bz2, tar.xz, tar.zst, 7z — configurables globalement ou par entrée
- **Sauvegarde SFTP distante** : basée sur la bibliothèque paramiko, authentification par mot de passe ou clé SSH privée, détection automatique de la clé par défaut
- **Sauvegarde WebDAV distante** : basée sur la bibliothèque standard urllib, sans aucune dépendance supplémentaire, compatible avec Jianguoyun / NextCloud / Synology
- **Stockage cloud S3** : basé sur la bibliothèque minio, compatible avec tous les stockages S3 (AWS / MinIO / Alibaba Cloud OSS, etc.)
- **Sauvegarde multi-destinations en parallèle** : sauvegarde simultanée vers le local et plusieurs destinations distantes, sans interférence mutuelle
- **Restauration de sauvegarde** : extraction et restauration depuis un fichier de sauvegarde vers un répertoire cible, avec restauration sélective possible
- **Nettoyage de sauvegardes** : suppression automatique des anciennes sauvegardes, avec stratégies par nombre / durée / conservation quotidienne
- **Sauvegarde chiffrée** : chiffrement par mot de passe pour le format 7z + chiffrement PBKDF2 pour tous les formats
- **Sauvegarde planifiée** : exécution automatique à intervalles réguliers, surveillance en temps réel des fichiers (watchdog)
- **Historique de sauvegarde** : enregistrement de l'heure, de la taille et de la somme de contrôle SHA256 de chaque sauvegarde, pour un suivi facile
- **Journal d'audit** : enregistrement des événements d'audit pour toutes les opérations de sauvegarde et de restauration
- **Hooks Pre/Post** : exécution de commandes personnalisées avant et après la sauvegarde
- **Profils de configuration** : sauvegarde, basculement, import/export de plusieurs jeux de configuration
- **Recherche inter-archives** : recherche de noms de fichiers correspondants dans plusieurs fichiers de sauvegarde
- **Intégrité des données** : génération et vérification de sommes de contrôle SHA256, codes correcteurs d'erreurs Reed-Solomon
- **Validation de configuration** : vérification automatique de la validité des paramètres, détection des modifications non autorisées
- **File d'attente de tâches** : gestion de la file d'attente des tâches de sauvegarde, avec ajout, exécution et annulation
- **Benchmark de compression** : comparaison des performances de compression selon les différents formats et niveaux
- **Estimation d'espace disque** : estimation de la taille de sauvegarde par type de fichier, vérification de l'espace disponible sur la destination
- **Internationalisation** : support de neuf langues — chinois, anglais, français, espagnol, russe, allemand, japonais, portugais, coréen
- **Complétion shell** : auto-complétion pour bash / zsh / fish / powershell
- **Léger et efficace** : faible encombrement, démarrage rapide, consommation de ressources minimale
- **Multiplateforme** : compatible avec Windows, macOS et Linux

## Demarrage rapide

### Installation

#### Installation via pip

```bash
pip install sbackup-cli
```

Après l'installation, utilisez la commande `sbackup` (le nom du paquet PyPI est `sbackup-cli`, la commande CLI est `sbackup`).

#### Installation depuis les sources

```bash
git clone https://github.com/xiatianxuan/sbackup.git
cd sbackup
uv sync
```

### Utilisation

#### Syntaxe de base

```bash
uv run python main.py <commande> [options]
```

#### Commandes disponibles

| Commande | Description |
|----------|-------------|
| `add` | Ajouter une stratégie de sauvegarde |
| `rm` / `remove` | Supprimer une stratégie de sauvegarde |
| `edit` | Modifier une stratégie de sauvegarde existante |
| `all` | Afficher toutes les stratégies de sauvegarde |
| `save` | Exécuter la sauvegarde |
| `watch` | Sauvegarde planifiée à intervalles réguliers |
| `restore` | Restaurer depuis un fichier de sauvegarde |
| `info` | Afficher les détails d'un fichier de sauvegarde |
| `diff` | Comparer les différences entre le répertoire source et la sauvegarde |
| `verify` | Vérifier l'intégrité d'un fichier de sauvegarde |
| `search` | Rechercher des fichiers dans une sauvegarde |
| `xsearch` | Rechercher dans plusieurs archives de sauvegarde |
| `versions` | Afficher l'historique des versions de sauvegarde |
| `sftp` | Gestion des sauvegardes SFTP distantes |
| `webdav` | Gestion des sauvegardes WebDAV distantes |
| `remote` | Gestion des fichiers distants (list/rm) |
| `task` | Gestion de la file d'attente des tâches |
| `audit` | Consultation du journal d'audit |
| `hooks` | Exécution manuelle des hooks Pre/Post |
| `profile` | Gestion des profils de configuration |
| `rotate` | Rotation et nettoyage des sauvegardes |
| `clean` | Nettoyage des anciennes sauvegardes |
| `diskcheck` | Estimation de l'espace disque |
| `benchmark` | Benchmark des formats de compression |
| `integrity` | Vérification d'intégrité du répertoire de sauvegarde |
| `dry-run` | Aperçu de la sélection des fichiers de sauvegarde |
| `export` / `import` | Exporter / Importer les stratégies de sauvegarde |
| `ignore` | Générer un fichier .sbackupignore |
| `schedule` | Exporter la configuration de planification |
| `webhook` | Configurer des préréglages de webhook |
| `config` | Configuration du chiffrement / validation |
| `report` | Générer un rapport de sauvegarde |
| `completion` | Générer les scripts de complétion shell |
| `wizard` | Assistant de configuration interactif |
| `status` | Tableau de bord de l'état des sauvegardes |
| `version` | Afficher les informations de version |
| `help` | Afficher l'aide |

#### Paramètres globaux

| Paramètre | Description |
|-----------|-------------|
| `--lang zh_CN` / `en_US` / `fr_FR` / `es_ES` / `ru_RU` / `de_DE` / `ja_JP` / `pt_BR` / `ko_KR` | Définir la langue de l'interface (persisté dans config.json) |
| `--format zip` / `tar` / `tar.gz` / `tar.bz2` / `tar.xz` / `tar.zst` / `7z` | Définir le format d'archivage (persisté dans config.json) |
| `--debug` | Activer le journal de débogage |

#### Ajouter une stratégie de sauvegarde

```bash
uv run python main.py add <source> <dest> [-i ignore_patterns]
```

Description des paramètres :
- **source** : chemin du dossier source à sauvegarder
- **dest** : chemin de destination pour le fichier de sauvegarde
- **-i, --ignore** : noms de fichiers ou dossiers à ignorer, séparés par des virgules (par défaut : `.git,__pycache__`)
- **--format** : format d'archivage au niveau de l'entrée (s'applique uniquement à cette stratégie, utilise la valeur globale par défaut si non spécifié) : `zip` / `tar` / `tar.gz` / `tar.bz2` / `tar.xz` / `tar.zst` / `7z`

Exemples :
```bash
# Ajouter une stratégie avec le format par défaut global
uv run python main.py add F:/my_folder F:/backup -i node_modules,.git

# Spécifier le format tar.gz pour cette stratégie (chaque sauvegarde de ce dossier utilisera tar.gz)
uv run python main.py add F:/my_folder F:/backup --format tar.gz

# Spécifier le format 7z (uniquement pour ce dossier)
uv run python main.py add F:/my_folder F:/backup --format 7z
```

#### Supprimer une stratégie de sauvegarde

```bash
uv run python main.py rm <path>
```

Description des paramètres :
- **path** : chemin du dossier source dont la stratégie de sauvegarde doit être supprimée

Exemple :
```bash
uv run python main.py rm F:/my_folder
```

#### Afficher toutes les stratégies de sauvegarde

```bash
uv run python main.py all
```

Affiche toutes les stratégies de sauvegarde actuellement configurées.

#### Exécuter la sauvegarde

```bash
# Utiliser le format par défaut (ZIP)
uv run python main.py save

# Utiliser le format tar.gz
uv run python main.py --format tar.gz save

# Conserver les 5 derniers fichiers de sauvegarde, nettoyer automatiquement les anciens
uv run python main.py save --keep 5

# Utiliser le format 7z avec chiffrement
uv run python main.py --format 7z save --password mysecret

# Interface en anglais + format tar.xz
uv run python main.py --lang en_US --format tar.xz save
```

**Paramètres de la commande save :**

| Paramètre | Valeur par défaut | Description |
|-----------|-------------------|-------------|
| `--keep N` | `0` | Conserver les N fichiers de sauvegarde les plus récents, 0 signifie aucun nettoyage |
| `--password PASSWORD` | `""` | Mot de passe de chiffrement (uniquement pour le format 7z) |
| `--sftp` | `false` | Télécharger vers le serveur SFTP après la sauvegarde |
| `--webdav` | `false` | Télécharger vers le serveur WebDAV après la sauvegarde |

Sauvegarde automatiquement les dossiers modifiés selon les stratégies configurées.

#### Sauvegarde planifiée

```bash
# Exécuter la sauvegarde toutes les 60 minutes
uv run python main.py watch --interval 60

# Sauvegarder toutes les 2 heures, conserver les 10 derniers fichiers
uv run python main.py watch --interval 120 --keep 10

# Sauvegarde planifiée + chiffrement 7z
uv run python main.py --format 7z watch --interval 60 --password mysecret
```

**Paramètres de la commande watch :**

| Paramètre | Valeur par défaut | Description |
|-----------|-------------------|-------------|
| `--interval MINUTES` | `60` | Intervalle de sauvegarde (en minutes) |
| `--keep N` | `0` | Conserver les N fichiers de sauvegarde les plus récents |
| `--password PASSWORD` | `""` | Mot de passe de chiffrement (uniquement pour le format 7z) |
| `--sftp` | `false` | Télécharger vers le serveur SFTP après chaque sauvegarde |
| `--webdav` | `false` | Télécharger vers le serveur WebDAV après chaque sauvegarde |

Appuyez sur `Ctrl+C` pour arrêter la sauvegarde planifiée.

#### Restaurer une sauvegarde

```bash
uv run python main.py restore <backup_file> <target_dir>
```

Description des paramètres :
- **backup_file** : chemin du fichier de sauvegarde (compatible .zip / .tar / .tar.gz / .tar.bz2 / .tar.xz / .tar.zst / .7z)
- **target_dir** : répertoire cible de la restauration

Exemples :
```bash
uv run python main.py restore F:/backup/my_folder.tar.gz F:/restored
uv run python main.py restore F:/backup/my_folder.7z F:/restored
uv run python main.py restore F:/backup/my_folder.tar.zst F:/restored
```

#### Sauvegarde SFTP distante

```bash
# ============ Demarrage rapide (recommande) ============
# 1. Configurer le SFTP (détection automatique de la clé SSH privée, aucune spécification manuelle nécessaire)
sbackup sftp config --host 192.168.1.100 --user admin --remote-path /backups

# 2. Tester la connexion
sbackup sftp test

# 3. Exécuter la sauvegarde et télécharger
sbackup save --sftp

# ============ Modes d'authentification ============

# Mode 1 : Détection automatique de la clé privée (recommandé)
# Le système tente automatiquement ~/.ssh/id_ed25519 → id_rsa → id_ecdsa
sbackup sftp config --host 192.168.1.100 --user admin

# Mode 2 : Authentification par mot de passe
sbackup sftp config --host 192.168.1.100 --user admin --password secret

# Mode 3 : Spécifier une clé privée
sbackup sftp config --host 192.168.1.100 --user admin --key-file ~/.ssh/id_rsa

# Mode 4 : Clé privée + phrase secrète (saisie interactive)
sbackup sftp config --host 192.168.1.100 --user admin --key-file ~/.ssh/id_rsa

# Mode 5 : Clé privée + phrase secrète (spécifiée en ligne de commande)
sbackup sftp config --host 192.168.1.100 --user admin --key-file ~/.ssh/id_rsa --key-passphrase mykeypass

# ============ Scenarios d'utilisation ============

# Scénario 1 : Sauvegarde unique avec téléchargement
sbackup save --sftp

# Scénario 2 : Sauvegarde planifiée avec téléchargement automatique (toutes les 60 minutes)
sbackup watch --interval 60 --sftp

# Scénario 3 : Sauvegarde dans un format spécifié + téléchargement
sbackup --format tar.gz save --sftp

# Scénario 4 : Sauvegarde chiffrée + téléchargement
sbackup --format 7z save --password mysecret --sftp

# Scénario 5 : Conserver les 5 dernières sauvegardes + téléchargement
sbackup save --keep 5 --sftp

# ============ Utilisation avancee ============

# Configuration interactive (saisie de tous les paramètres étape par étape)
sbackup sftp config

# Configuration non interactive (tous les paramètres spécifiés en ligne de commande)
sbackup sftp config --host 192.168.1.100 --port 22 --user admin --password secret --remote-path /backups

# Tester la connexion avec journal détaillé
sbackup --debug sftp test
```

**Sous-commandes sftp :**

| Sous-commande | Description | Exemple |
|---------------|-------------|---------|
| `sftp config` | Configurer les paramètres de connexion SFTP (host/port/user/password/key_file/key_passphrase/remote_path) | `sbackup sftp config --host 192.168.1.100 --user admin` |
| `sftp test` | Tester si la connexion SFTP est disponible | `sbackup sftp test` |

**Modes d'authentification :**

| Mode | Paramètres | Description | Exemple |
|------|------------|-------------|---------|
| **Détection automatique** | Aucun paramètre d'authentification | Tente automatiquement `~/.ssh/id_ed25519` → `id_rsa` → `id_ecdsa` (recommandé) | `sbackup sftp config --host ... --user ...` |
| Mot de passe | `--password` | Connexion directe par mot de passe | `sbackup sftp config --host ... --user ... --password secret` |
| Clé privée | `--key-file` | Connexion avec une clé SSH privée spécifiée | `sbackup sftp config --host ... --user ... --key-file ~/.ssh/id_rsa` |
| Clé privée + phrase | `--key-file` + `--key-passphrase` | Lorsque la clé privée est protégée par une phrase secrète | `sbackup sftp config --host ... --user ... --key-file ~/.ssh/id_rsa --key-passphrase mypass` |

Formats de clés privées pris en charge : RSA, Ed25519, ECDSA.

**Support des chemins multiplateforme :**

| Plateforme | Exemple de chemin de clé privée | Description |
|------------|--------------------------------|-------------|
| Linux/macOS | `~/.ssh/id_rsa` | Développement automatiquement en `/home/user/.ssh/id_rsa` |
| Windows | `~/.ssh/id_rsa` | Développement automatiquement en `C:\Users\username\.ssh\id_rsa` |
| Toutes plateformes | Chemin absolu | Utilisation directe du chemin complet |

La configuration SFTP est enregistrée dans le champ `sftp` du fichier `config.json`, configurable via les paramètres de ligne de commande ou en mode interactif.

#### Afficher les informations de version

```bash
sbackup version
```

## Fichier de configuration

Sbackup prend en charge la personnalisation via un fichier `config.json`. Le fichier de configuration doit être placé à la racine du projet.

### Description des paramètres de configuration

```json
{
  "compression_format": "ZIP",
  "compression": {
    "algorithm": "ZIP_DEFLATED",
    "level": 6
  },
  "skip_patterns": [".git", "__pycache__"],
  "data_file": "sbackup.json",
  "lang": "zh_CN",
  "password": "",
  "sftp": {
    "host": "",
    "port": 22,
    "user": "",
    "password": "",
    "key_file": "",
    "key_passphrase": "",
    "remote_path": "/",
    "enabled": false
  }
}
```

| Paramètre | Type | Valeur par défaut | Description |
|-----------|------|-------------------|-------------|
| `compression_format` | string | `"ZIP"` | Format d'archivage, valeurs possibles : `ZIP`, `TAR`, `TAR_GZ`, `TAR_BZ2`, `TAR_XZ`, `TAR_ZST`, `7Z` |
| `compression.algorithm` | string | `"ZIP_DEFLATED"` | Algorithme de compression ZIP, valeurs possibles : `ZIP_DEFLATED`, `ZIP_STORED`, `ZIP_BZIP2`, `ZIP_LZMA` |
| `compression.level` | int | `6` | Niveau de compression, de 0 à 9 (0 = pas de compression, 9 = compression maximale) |
| `skip_patterns` | list | `[".git", "__pycache__"]` | Motifs de fichiers ou dossiers à ignorer (supporte les jokers fnmatch et la correspondance de chemins) |
| `data_file` | string | Chemin par défaut de la plateforme | Chemin du fichier de données des stratégies de sauvegarde |
| `lang` | string | `"zh_CN"` | Langue de l'interface, valeurs possibles : `zh_CN`, `en_US`, `fr_FR`, `es_ES`, `ru_RU`, `de_DE`, `ja_JP`, `pt_BR`, `ko_KR` |
| `password` | string | `""` | Mot de passe de chiffrement 7z |
| `sftp.host` | string | `""` | Adresse du serveur SFTP |
| `sftp.port` | int | `22` | Port SFTP |
| `sftp.user` | string | `""` | Nom d'utilisateur SFTP |
| `sftp.password` | string | `""` | Mot de passe SFTP (utilisé pour l'authentification par mot de passe) |
| `sftp.key_file` | string | `""` | Chemin du fichier de clé SSH privée (utilisé pour l'authentification par clé, recommandé) |
| `sftp.key_passphrase` | string | `""` | Phrase secrète de la clé privée (le cas échéant) |
| `sftp.remote_path` | string | `"/"` | Chemin de destination distant |
| `sftp.enabled` | bool | `false` | Activer ou non le SFTP |

### Exemple de configuration

Utiliser le format tar.bz2 pour une sauvegarde à taux de compression élevé :

```json
{
  "compression_format": "TAR_BZ2",
  "compression_level": 9,
  "skip_patterns": [".git", "__pycache__", "node_modules", "*.log"],
  "data_file": "backup_strategies.json",
  "lang": "zh_CN"
}
```

### Comparaison des formats d'archivage

| Format | Extension | Taux de compression | Vitesse | Dépendance | Cas d'utilisation |
|--------|-----------|---------------------|---------|------------|-------------------|
| ZIP | .zip | Moyen | Rapide | Bibliothèque standard | Universel, meilleure compatibilité sous Windows |
| tar | .tar | Aucun | Très rapide | Bibliothèque standard | Archivage pur, à combiner avec une compression externe |
| tar.gz | .tar.gz | Moyen | Rapide | Bibliothèque standard | Courant sous Linux/macOS |
| tar.bz2 | .tar.bz2 | Élevé | Moyen | Bibliothèque standard | Archivage à taux de compression élevé |
| tar.xz | .tar.xz | Le plus élevé | Lent | Bibliothèque standard | Archivage à long terme, espace limité |
| tar.zst | .tar.zst | Moyen-élevé | Très rapide | zstandard | Usage moderne, bon équilibre vitesse/compression |
| 7z | .7z | Très élevé | Lent | py7zr | Compression maximale, support du chiffrement |

#### Sauvegarde WebDAV distante

WebDAV est un protocole de fichiers basé sur HTTP, compatible avec les principaux services cloud comme Jianguoyun, NextCloud et Synology. Utilise la bibliothèque standard Python `urllib`, **sans aucune dépendance supplémentaire**.

```bash
# ============ Demarrage rapide ============
# 1. Configurer le WebDAV
sbackup webdav config --url https://dav.jianguoyun.com/dav/ --user user@example.com --password secret

# 2. Tester la connexion
sbackup webdav test

# 3. Exécuter la sauvegarde et télécharger
sbackup save --webdav

# ============ Scenarios d'utilisation ============

# Scénario 1 : Sauvegarde unique avec téléchargement
sbackup save --webdav

# Scénario 2 : Sauvegarde planifiée avec téléchargement automatique (toutes les 60 minutes)
sbackup watch --interval 60 --webdav

# Scénario 3 : Spécifier un sous-répertoire distant
sbackup webdav config --url https://dav.jianguoyun.com/dav/ --user user@example.com --remote-path /backups/sbackup

# Scénario 4 : Télécharger simultanément vers SFTP et WebDAV
sbackup save --sftp --webdav

# ============ Adresses de services WebDAV courants ============
# Jianguoyun: https://dav.jianguoyun.com/dav/
# NextCloud: https://your-server/remote.php/dav/files/username/
# Synology: https://your-synology:5006/webdav/
```

**Sous-commandes webdav :**

| Sous-commande | Description | Exemple |
|---------------|-------------|---------|
| `webdav config` | Configurer les paramètres de connexion WebDAV (url/user/password/remote_path) | `sbackup webdav config --url ... --user ...` |
| `webdav test` | Tester si la connexion WebDAV est disponible | `sbackup webdav test` |

| Paramètre | Valeur par défaut | Description |
|-----------|-------------------|-------------|
| `--url URL` | `""` | Adresse du serveur WebDAV (par ex. `https://dav.jianguoyun.com/dav/`) |
| `--user USER` | `""` | Nom d'utilisateur WebDAV (généralement une adresse e-mail) |
| `--password PASS` | `""` | Mot de passe WebDAV (pour Jianguoyun, générez un mot de passe d'application dans les paramètres) |
| `--remote-path PATH` | `/` | Chemin de destination distant |

## Principe de fonctionnement

Sbackup implémente les fonctionnalités de sauvegarde de la manière suivante :

1. **Stockage des stratégies** : les stratégies de sauvegarde sont enregistrées dans un fichier JSON, contenant les chemins des dossiers, les dates de dernière modification, les chemins de destination, les motifs d'exclusion et les formats d'archivage par entrée.
2. **Sauvegarde incrémentielle** : en comparant les dates de dernière modification des dossiers, seuls les dossiers modifiés sont sauvegardés.
3. **Compression multi-format** : utilisation des modules Python intégrés `zipfile` et `tarfile`, ainsi que des bibliothèques tierces `zstandard` et `py7zr`, pour prendre en charge sept formats d'archivage.
4. **Format par entrée** : chaque stratégie de sauvegarde peut spécifier un format d'archivage indépendant (`add --format`), prioritaire sur le paramètre global `--format` ; la valeur globale est utilisée si aucune n'est spécifiée.
5. **Nettoyage des sauvegardes** : après une sauvegarde réussie, le répertoire cible est analysé, trié par date de modification, et les fichiers dépassant le nombre de rétention sont supprimés.
6. **Sauvegarde chiffrée** : le format 7z supporte le chiffrement LZMA2, configurable via le paramètre `--password` ou le fichier `config.json`.
7. **Sauvegarde planifiée** : la commande `watch` exécute la sauvegarde en boucle à l'intervalle spécifié, arrêt sécurisé avec `Ctrl+C`.
8. **Historique de sauvegarde** : après chaque sauvegarde, l'horodatage, la taille du fichier et le nombre de fichiers sont enregistrés, avec conservation des 100 dernières entrées.
9. **Sauvegarde SFTP distante** : implémentation d'un client SFTP basée sur la bibliothèque paramiko, avec test de connexion, création automatique de répertoires distants et upload avec barre de progression.

### Format du fichier de données

```json
{
  "/path/to/source/folder": [
    1719235200.0,
    "/path/to/target/folder",
    [".git", "__pycache__"],
    ""
  ],
  "/path/to/another/folder": [
    1719235200.0,
    "/path/to/another/target",
    [".git"],
    "TAR_GZ"
  ],
  "_history": [
    {
      "time": "2026-05-01T12:00:00",
      "source": "/path/to/source/folder",
      "size_mb": 12.5,
      "files_count": 150
    }
  ]
}
```

Chaque entrée de stratégie de sauvegarde est une liste de 4 éléments : `[mtime, target, skip_patterns, compression_format]`

| Champ | Description |
|-------|-------------|
| `mtime` | Date de dernière modification du dossier source (utilisée pour la décision de sauvegarde incrémentielle) |
| `target` | Chemin de destination pour le fichier de sauvegarde |
| `skip_patterns` | Liste des motifs de fichiers/dossiers à ignorer |
| `compression_format` | Format d'archivage au niveau de l'entrée (chaîne vide = utilisation de la valeur globale par défaut) |

## Guide de developpement

### Executer les tests

```bash
uv run coverage run -m unittest discover -s tests -t . && uv run coverage report -m
```

### Structure du code

```
sbackup/
├── main.py              # Point d'entrée du programme
├── sbackup/
│   ├── __init__.py      # Export des fonctions principales
│   ├── __main__.py      # Point d'entrée python -m sbackup
│   ├── cli.py           # Analyse des arguments CLI et dispatch des commandes (30+ commandes)
│   ├── config.py        # Chargement de la configuration, chiffrement, configuration Webhook/SMTP
│   ├── auto_save.py     # Moteur principal BackupManager
│   ├── compression.py   # Moteur de compression/décompression pour 7 formats
│   ├── i18n.py          # Internationalisation (9 langues)
│   ├── sftp.py          # Client de sauvegarde SFTP distant (paramiko)
│   ├── webdav.py        # Client de sauvegarde WebDAV distant (sans dépendance)
│   ├── cloud_storage.py # Client de stockage cloud S3 (minio)
│   ├── multi_dest.py    # Sauvegarde multi-destinations en parallèle
│   ├── handlers.py      # Gestionnaires de commandes SFTP/WebDAV/Remote/Schedule
│   ├── hooks.py         # Exécution des hooks Pre/Post
│   ├── audit.py         # Système de journal d'audit
│   ├── profile.py       # Gestion des profils de configuration
│   ├── selective.py     # Restauration sélective
│   ├── cross_search.py  # Recherche inter-archives
│   ├── integrity.py     # Sommes de contrôle SHA256
│   ├── rotation.py      # Stratégies de rotation des sauvegardes
│   ├── dryrun.py        # Aperçu en mode dry-run
│   ├── diskcheck.py     # Estimation de l'espace disque
│   ├── task_queue.py    # Système de file d'attente de tâches
│   ├── schema.py        # Validateur de configuration
│   ├── benchmark.py     # Benchmark de compression
│   ├── chunked_backup.py# Sauvegarde incrémentielle par blocs
│   ├── dedup.py         # Dédoublonnage par fichier SHA256
│   ├── export.py        # Export des métadonnées (CSV/JSON)
│   ├── monitor.py       # Surveillance du système de fichiers (watchdog)
│   ├── lock.py          # Verrouillage de processus multiplateforme
│   ├── retry.py         # Réessai avec backoff exponentiel
│   ├── ratelimiter.py   # Limiteur de débit par jeton
│   ├── keychain.py      # Intégration du trousseau système
│   ├── parity.py        # Codes correcteurs d'erreurs Reed-Solomon
│   ├── completion.py    # Auto-complétion shell
│   ├── wizard.py        # Assistant de configuration interactif
│   └── locales/         # Fichiers de traduction pour 9 langues
└── tests/
    └── sbackup/
        └── test_*.py    # 30 fichiers de test couvrant tous les modules
```

### Ajouter une nouvelle fonctionnalité

1. Créer un nouveau fichier module dans le répertoire `sbackup/`
2. Importer les fonctions de la nouvelle fonctionnalité dans `sbackup/__init__.py`
3. Ajouter la logique de gestion de la nouvelle commande dans la fonction `run()`
4. Ajouter le fichier de test correspondant dans le répertoire `tests/`

## Questions frequentes

### Q : Que faire si le fichier de stratégie de sauvegarde est supprimé par erreur ?

R : Les stratégies de sauvegarde sont stockées dans le fichier de données. En cas de suppression accidentelle, vous pouvez les recréer en réexécutant la commande `add`.

### Q : Comment modifier une stratégie de sauvegarde déjà ajoutée ?

R : Utilisez la commande `sbackup edit` : `sbackup edit <source> --dest <new_dest> --ignore <patterns> --format <fmt>`.

### Q : La sauvegarde distante est-elle prise en charge ?

R : Oui ! Trois méthodes de sauvegarde distante sont disponibles :
- **SFTP** : configuration avec `sbackup sftp config`, téléchargement avec `sbackup save --sftp`
- **WebDAV** : configuration avec `sbackup webdav config`, téléchargement avec `sbackup save --webdav` (compatible Jianguoyun / NextCloud / Synology)
- **Stockage cloud S3** : configurer le champ `cloud` dans `config.json`, téléchargement avec `sbackup save --cloud`
- Activation simultanée de plusieurs méthodes : `sbackup save --sftp --webdav --cloud`

### Q : Quelle est la différence entre tar.gz et ZIP ?

R : tar.gz est plus courant sous Linux/macOS avec un taux de compression légèrement supérieur ; ZIP est plus universel sous Windows avec la meilleure compatibilité. tar.bz2 et tar.xz offrent des taux de compression plus élevés mais sont plus lents. tar.zst est un algorithme moderne, extrêmement rapide avec un bon taux de compression. 7z offre le taux de compression le plus élevé et supporte le chiffrement.

### Q : Comment chiffrer une sauvegarde ?

R : Utilisez le format 7z avec un mot de passe : `uv run python main.py --format 7z save --password yourpassword`. Le mot de passe peut également être enregistré dans le champ `password` du fichier `config.json`.

### Q : Comment nettoyer automatiquement les anciennes sauvegardes ?

R : Utilisez le paramètre `--keep` : `uv run python main.py save --keep 5` ne conserve que les 5 fichiers de sauvegarde les plus récents. La sauvegarde planifiée le supporte également : `uv run python main.py watch --interval 60 --keep 10`.

### Q : Comment configurer une sauvegarde planifiée ?

R : Utilisez la commande `watch` : `uv run python main.py watch --interval 60` pour sauvegarder toutes les 60 minutes. Appuyez sur `Ctrl+C` pour arrêter.

### Q : Le stockage des mots de passe est-il sécurisé ?

R : Les mots de passe SFTP et de chiffrement 7z dans `config.json` sont stockés en **clair**. Veuillez vous assurer que l'accès au fichier `config.json` est limité aux utilisateurs de confiance (par exemple, `chmod 600 config.json`). Ne commitez pas un fichier `config.json` contenant des mots de passe dans un système de contrôle de version.

## Guide de contribution

Les Issues et Pull Requests sont les bienvenus !

1. Forker ce dépôt
2. Créer votre branche de fonctionnalité (`git checkout -b feature/AmazingFeature`)
3. Valider vos modifications (`git commit -m 'Add some AmazingFeature'`)
4. Pousser vers la branche (`git push origin feature/AmazingFeature`)
5. Soumettre une Pull Request

### Style de code

Ce projet suit les conventions PEP 8 et le Google Python Style Guide. Veuillez vous assurer que votre code :
- Utilise des annotations de type
- Suit les docstrings au format Google
- Passe tous les tests unitaires

## Licence

Ce projet est sous licence GNU GPL v3.0. Pour plus de détails, consultez le fichier [LICENSE](../../LICENSE).

## Auteur

**xiatianxuan** (CodeSeed)

- [Gitee](https://gitee.com/xiatianxuan)
- [Page personnelle](https://xnors-codeseed.pages.dev/)

## Remerciements

- [Xnors Studio](https://xnors.github.io/)

## Nous contacter

Pour toute question ou suggestion, envoyez un e-mail à : xiatianxuan2025@163.com

---

*Dernière mise à jour : 19 juin 2026*
