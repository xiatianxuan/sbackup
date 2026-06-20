# Sbackup

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-GPL--3.0-green)](../../LICENSE)
[![PyPI](https://img.shields.io/pypi/v/sbackup-cli?color=blue)](https://pypi.org/project/sbackup-cli/)
[![Tests](https://img.shields.io/badge/tests-940%20passed-brightgreen)](../../.github/workflows/ci.yml)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)]()

> Herramienta ligera y eficiente para copias de seguridad de carpetas, con soporte de linea de comandos para gestionar tus estrategias de backup sin esfuerzo.

[English](../../README.md) | [Deutsch](README_de.md) | [Espanol](README_es.md) | [Francais](README_fr.md) | [Portugues](README_pt.md) | [Pycckuu](README_ru.md) | [日本語](README_ja.md) | [한국어](README_ko.md) | [中文](README_zh.md)

- [Introduccion](#introduccion)
- [Caracteristicas](#caracteristicas)
- [Inicio rapido](#inicio-rapido)
  - [Instalacion](#instalacion)
  - [Uso](#uso)
- [Archivo de configuracion](#archivo-de-configuracion)
  - [Ejemplo de configuracion](#ejemplo-de-configuracion)
- [Copia de seguridad remota por SFTP](#copia-de-seguridad-remota-por-sftp)
- [Copia de seguridad remota por WebDAV](#copia-de-seguridad-remota-por-webdav)
- [Principio de funcionamiento](#principio-de-funcionamiento)
- [Guia de desarrollo](#guia-de-desarrollo)
  - [Ejecutar pruebas](#ejecutar-pruebas)
  - [Estructura del codigo](#estructura-del-codigo)
- [Preguntas frecuentes](#preguntas-frecuentes)
- [Guia de contribucion](#guia-de-contribucion)
- [Licencia](#licencia)
- [Autor](#autor)

---

## Introduccion

Sbackup es una herramienta ligera de copias de seguridad de carpetas que permite agregar, eliminar y consultar estrategias de backup desde la linea de comandos. Se basa en la ultima fecha de modificacion de las carpetas para determinar si es necesario realizar una copia de seguridad, asegurando que tus datos permanezcan siempre actualizados.

## Caracteristicas

- **Copia de seguridad incremental**: Solo respalda las carpetas que han cambiado, ahorrando tiempo y espacio de almacenamiento.
- **Soporte de multiples formatos**: Compatible con siete formatos de empaquetado: ZIP, tar, tar.gz, tar.bz2, tar.xz, tar.zst y 7z. Tanto el formato global como el de cada entrada pueden configurarse de forma independiente.
- **Copia de seguridad remota por SFTP**: Basado en la biblioteca paramiko, soporta autenticacion por contrasena o clave privada SSH, con deteccion automatica de la clave privada predeterminada.
- **Copia de seguridad remota por WebDAV**: Basado en urllib de la biblioteca estandar, sin dependencias adicionales. Compatible con Jianguoyun, NextCloud y Synology.
- **Almacenamiento en la nube S3**: Basado en la biblioteca minio, compatible con todo almacenamiento compatible con S3 (AWS, MinIO, Alibaba Cloud OSS, etc.).
- **Backup paralelo a multiples destinos**: Copia simultanea a almacenamiento local y multiples destinos remotos, sin interferencias entre ellos.
- **Restauracion de backups**: Permite descomprimir y restaurar archivos de backup en el directorio especificado, con soporte de restauracion selectiva.
- **Limpieza de backups**: Eliminacion automatica de backups antiguos, con politicas por cantidad, tiempo o retencion diaria.
- **Cifrado de backups**: Soporta cifrado con contrasena en formato 7z mas cifrado PBKDF2 para todos los formatos.
- **Copia de seguridad programada**: Ejecucion automatica a intervalos definidos, con soporte de monitoreo de archivos en tiempo real (watchdog).
- **Historial de backups**: Registro de la fecha, tamano y suma de verificacion SHA256 de cada backup para facilitar el seguimiento.
- **Registro de auditoria**: Registro de todos los eventos de auditoria de operaciones de backup y restauracion.
- **Hooks pre/post**: Ejecucion de comandos personalizados antes y despues del backup.
- **Perfiles de configuracion**: Soporte para guardar, cambiar, importar y exportar multiples esquemas de configuracion.
- **Busqueda entre archivos**: Busqueda de nombres de archivo coincidentes en multiples archivos de backup.
- **Integridad de datos**: Generacion y verificacion de sumas de verificacion SHA256, codigos de correccion de errores Reed-Solomon.
- **Validacion de configuracion**: Verificacion automatica de la validez de los parametros de configuracion y deteccion de manipulaciones.
- **Cola de tareas**: Gestion de la cola de tareas de backup, con soporte para agregar, ejecutar y cancelar.
- **Benchmark de compresion**: Comparacion del rendimiento de compresion entre diferentes formatos y niveles.
- **Estimacion de espacio en disco**: Estimacion del tamano del backup por tipo de archivo y verificacion del espacio en el destino.
- **Internacionalizacion**: Soporte para nueve idiomas: chino, ingles, frances, espanol, ruso, aleman, japones, portugues y coreano.
- **Autocompletado de shell**: Soporte de autocompletado automatico para bash, zsh, fish y powershell.
- **Ligero y eficiente**: Tamano reducido, inicio rapido y bajo consumo de recursos.
- **Soporte multiplataforma**: Compatible con Windows, macOS y Linux.

## Inicio rapido

### Instalacion

#### Instalacion con pip

```bash
pip install sbackup-cli
```

Despues de la instalacion, usa el comando `sbackup` (el nombre del paquete en PyPI es `sbackup-cli`, el comando CLI es `sbackup`).

#### Instalacion desde el codigo fuente

```bash
git clone https://github.com/xiatianxuan/sbackup.git
cd sbackup
uv sync
```

### Uso

#### Sintaxis basica

```bash
uv run python main.py <command> [options]
```

#### Comandos disponibles

| Comando | Descripcion |
|---------|-------------|
| `add` | Agregar una estrategia de backup |
| `rm` / `remove` | Eliminar una estrategia de backup |
| `edit` | Editar una estrategia de backup existente |
| `all` | Ver todas las estrategias de backup |
| `save` | Ejecutar el backup |
| `watch` | Ejecutar backups programados |
| `restore` | Restaurar desde un archivo de backup |
| `info` | Ver detalles del archivo de backup |
| `diff` | Comparar diferencias entre el directorio origen y el backup |
| `verify` | Verificar la integridad del archivo de backup |
| `search` | Buscar archivos dentro de un backup |
| `xsearch` | Buscar entre multiples archivos de backup |
| `versions` | Ver el historial de versiones del backup |
| `sftp` | Gestion de backups remotos por SFTP |
| `webdav` | Gestion de backups remotos por WebDAV |
| `remote` | Gestion de archivos remotos (list/rm) |
| `task` | Gestion de la cola de tareas de backup |
| `audit` | Consulta del registro de auditoria |
| `hooks` | Ejecucion manual de hooks pre/post |
| `profile` | Gestion de perfiles de configuracion |
| `rotate` | Limpieza por rotacion de backups |
| `clean` | Limpieza de backups antiguos |
| `diskcheck` | Estimacion de espacio en disco |
| `benchmark` | Benchmark de formatos de compresion |
| `integrity` | Verificacion de integridad del directorio de backups |
| `dry-run` | Vista previa de la seleccion de archivos de backup |
| `export` / `import` | Exportar/importar estrategias de backup |
| `ignore` | Generar archivo .sbackupignore |
| `schedule` | Exportar configuracion de programacion |
| `webhook` | Configurar preajustes de webhook |
| `config` | Configuracion de cifrado/verificacion |
| `report` | Generar informe de backups |
| `completion` | Generar scripts de autocompletado de shell |
| `wizard` | Asistente de configuracion interactivo |
| `status` | Panel de estado del backup |
| `version` | Ver informacion de version |
| `help` | Ver ayuda |

#### Parametros globales

| Parametro | Descripcion |
|-----------|-------------|
| `--lang zh_CN` / `en_US` / `fr_FR` / `es_ES` / `ru_RU` / `de_DE` / `ja_JP` / `pt_BR` / `ko_KR` | Establecer el idioma de la interfaz (persistente en config.json) |
| `--format zip` / `tar` / `tar.gz` / `tar.bz2` / `tar.xz` / `tar.zst` / `7z` | Establecer el formato de empaquetado (persistente en config.json) |
| `--debug` | Activar el registro de depuracion |

#### Agregar una estrategia de backup

```bash
uv run python main.py add <source> <dest> [-i ignore_patterns]
```

Parametros:
- **source**: Ruta de la carpeta de origen a respaldar
- **dest**: Ruta de destino donde se almacenara el backup
- **-i, --ignore**: Nombres de archivos o carpetas a ignorar, separados por comas (por defecto: `.git,__pycache__`)
- **--format**: Formato de empaquetado a nivel de entrada (solo afecta a esta estrategia de backup; si no se especifica, se usa el formato global): `zip` / `tar` / `tar.gz` / `tar.bz2` / `tar.xz` / `tar.zst` / `7z`

Ejemplos:
```bash
# Agregar estrategia usando el formato global por defecto
uv run python main.py add F:/my_folder F:/backup -i node_modules,.git

# Especificar formato tar.gz para esta estrategia (cada backup de esta carpeta usara tar.gz)
uv run python main.py add F:/my_folder F:/backup --format tar.gz

# Especificar formato 7z (solo para esta carpeta)
uv run python main.py add F:/my_folder F:/backup --format 7z
```

#### Eliminar una estrategia de backup

```bash
uv run python main.py rm <path>
```

Parametros:
- **path**: Ruta de la carpeta de origen cuya estrategia de backup se va a eliminar

Ejemplo:
```bash
uv run python main.py rm F:/my_folder
```

#### Ver todas las estrategias de backup

```bash
uv run python main.py all
```

Muestra todas las estrategias de backup configuradas actualmente.

#### Ejecutar backup

```bash
# Usar formato por defecto (ZIP)
uv run python main.py save

# Usar formato tar.gz
uv run python main.py --format tar.gz save

# Conservar los 5 backups mas recientes, limpiando automaticamente los antiguos
uv run python main.py save --keep 5

# Usar formato 7z con cifrado
uv run python main.py --format 7z save --password mysecret

# Interfaz en ingles + formato tar.xz
uv run python main.py --lang en_US --format tar.xz save
```

**Parametros del comando save:**

| Parametro | Valor por defecto | Descripcion |
|-----------|-------------------|-------------|
| `--keep N` | `0` | Conservar los N backups mas recientes; 0 significa sin limpieza |
| `--password PASSWORD` | `""` | Contrasena de cifrado (solo formato 7z) |
| `--sftp` | `false` | Subir al servidor SFTP despues del backup |
| `--webdav` | `false` | Subir al servidor WebDAV despues del backup |

Segun la estrategia de backup configurada, respalda automaticamente las carpetas que hayan cambiado.

#### Backup programado

```bash
# Ejecutar backup cada 60 minutos
uv run python main.py watch --interval 60

# Backup cada 2 horas, conservando los 10 archivos mas recientes
uv run python main.py watch --interval 120 --keep 10

# Backup programado + cifrado 7z
uv run python main.py --format 7z watch --interval 60 --password mysecret
```

**Parametros del comando watch:**

| Parametro | Valor por defecto | Descripcion |
|-----------|-------------------|-------------|
| `--interval MINUTES` | `60` | Intervalo de backup (en minutos) |
| `--keep N` | `0` | Conservar los N backups mas recientes |
| `--password PASSWORD` | `""` | Contrasena de cifrado (solo formato 7z) |
| `--sftp` | `false` | Subir al servidor SFTP despues de cada backup |
| `--webdav` | `false` | Subir al servidor WebDAV despues de cada backup |

Pulsa `Ctrl+C` para detener el backup programado.

#### Restaurar backup

```bash
uv run python main.py restore <backup_file> <target_dir>
```

Parametros:
- **backup_file**: Ruta del archivo de backup (compatible con .zip / .tar / .tar.gz / .tar.bz2 / .tar.xz / .tar.zst / .7z)
- **target_dir**: Directorio de destino para la restauracion

Ejemplos:
```bash
uv run python main.py restore F:/backup/my_folder.tar.gz F:/restored
uv run python main.py restore F:/backup/my_folder.7z F:/restored
uv run python main.py restore F:/backup/my_folder.tar.zst F:/restored
```

#### Copia de seguridad remota por SFTP

```bash
# ============ Inicio rapido (recomendado) ============
# 1. Configurar SFTP (deteccion automatica de clave privada SSH, sin necesidad de especificar manualmente)
sbackup sftp config --host 192.168.1.100 --user admin --remote-path /backups

# 2. Probar conexion
sbackup sftp test

# 3. Ejecutar backup y subir
sbackup save --sftp

# ============ Metodos de autenticacion ============

# Metodo 1: Deteccion automatica de clave privada (recomendado)
# El sistema intenta automaticamente ~/.ssh/id_ed25519 -> id_rsa -> id_ecdsa
sbackup sftp config --host 192.168.1.100 --user admin

# Metodo 2: Autenticacion por contrasena
sbackup sftp config --host 192.168.1.100 --user admin --password secret

# Metodo 3: Especificar clave privada
sbackup sftp config --host 192.168.1.100 --user admin --key-file ~/.ssh/id_rsa

# Metodo 4: Clave privada + frase de paso (entrada interactiva)
sbackup sftp config --host 192.168.1.100 --user admin --key-file ~/.ssh/id_rsa

# Metodo 5: Clave privada + frase de paso (especificada en linea de comandos)
sbackup sftp config --host 192.168.1.100 --user admin --key-file ~/.ssh/id_rsa --key-passphrase mykeypass

# ============ Casos de uso ============

# Caso 1: Backup unico y subida
sbackup save --sftp

# Caso 2: Backup programado con subida automatica (cada 60 minutos)
sbackup watch --interval 60 --sftp

# Caso 3: Backup con formato especifico + subida
sbackup --format tar.gz save --sftp

# Caso 4: Backup cifrado + subida
sbackup --format 7z save --password mysecret --sftp

# Caso 5: Conservar los 5 backups mas recientes + subida
sbackup save --keep 5 --sftp

# ============ Uso avanzado ============

# Configuracion interactiva (introducir todos los parametros paso a paso)
sbackup sftp config

# Configuracion no interactiva (todos los parametros en la linea de comandos)
sbackup sftp config --host 192.168.1.100 --port 22 --user admin --password secret --remote-path /backups

# Probar conexion y ver registro detallado
sbackup --debug sftp test
```

**Subcomandos de sftp:**

| Subcomando | Descripcion | Ejemplo |
|------------|-------------|---------|
| `sftp config` | Configurar parametros de conexion SFTP (host/port/user/password/key_file/key_passphrase/remote_path) | `sbackup sftp config --host 192.168.1.100 --user admin` |
| `sftp test` | Probar si la conexion SFTP esta disponible | `sbackup sftp test` |

**Metodos de autenticacion:**

| Metodo | Parametros | Descripcion | Ejemplo |
|--------|------------|-------------|---------|
| **Deteccion automatica** | Sin parametros de autenticacion | Intenta automaticamente `~/.ssh/id_ed25519` -> `id_rsa` -> `id_ecdsa` (recomendado) | `sbackup sftp config --host ... --user ...` |
| Contrasena | `--password` | Acceso directo con contrasena | `sbackup sftp config --host ... --user ... --password secret` |
| Clave privada | `--key-file` | Acceso con clave privada SSH especificada | `sbackup sftp config --host ... --user ... --key-file ~/.ssh/id_rsa` |
| Clave privada + frase de paso | `--key-file` + `--key-passphrase` | Para claves privadas con frase de paso | `sbackup sftp config --host ... --user ... --key-file ~/.ssh/id_rsa --key-passphrase mypass` |

Formatos de clave privada compatibles: RSA, Ed25519, ECDSA.

**Soporte de rutas multiplataforma:**

| Plataforma | Ejemplo de ruta de clave privada | Descripcion |
|------------|----------------------------------|-------------|
| Linux/macOS | `~/.ssh/id_rsa` | Se expande automaticamente a `/home/user/.ssh/id_rsa` |
| Windows | `~/.ssh/id_rsa` | Se expande automaticamente a `C:\Users\username\.ssh\id_rsa` |
| Todas | Ruta absoluta | Se usa directamente la ruta completa |

La configuracion de SFTP se guarda en el campo `sftp` de `config.json` y admite parametros de linea de comandos o entrada interactiva.

#### Ver informacion de version

```bash
sbackup version
```

## Archivo de configuracion

Sbackup permite la personalizacion mediante el archivo `config.json`. El archivo de configuracion debe ubicarse en el directorio raiz del proyecto.

### Descripcion de las opciones de configuracion

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

| Opcion | Tipo | Valor por defecto | Descripcion |
|--------|------|-------------------|-------------|
| `compression_format` | string | `"ZIP"` | Formato de empaquetado. Valores posibles: `ZIP`, `TAR`, `TAR_GZ`, `TAR_BZ2`, `TAR_XZ`, `TAR_ZST`, `7Z` |
| `compression.algorithm` | string | `"ZIP_DEFLATED"` | Algoritmo de compresion ZIP. Valores posibles: `ZIP_DEFLATED`, `ZIP_STORED`, `ZIP_BZIP2`, `ZIP_LZMA` |
| `compression.level` | int | `6` | Nivel de compresion, rango 0-9 (0 = sin compresion, 9 = maxima compresion) |
| `skip_patterns` | list | `[".git", "__pycache__"]` | Patrones de archivos o carpetas a ignorar (compatible con comodines fnmatch y coincidencia de rutas) |
| `data_file` | string | Ruta predeterminada de la plataforma | Ruta del archivo de datos de estrategias de backup |
| `lang` | string | `"zh_CN"` | Idioma de la interfaz. Valores posibles: `zh_CN`, `en_US`, `fr_FR`, `es_ES`, `ru_RU`, `de_DE`, `ja_JP`, `pt_BR`, `ko_KR` |
| `password` | string | `""` | Contrasena de cifrado para 7z |
| `sftp.host` | string | `""` | Direccion del servidor SFTP |
| `sftp.port` | int | `22` | Puerto SFTP |
| `sftp.user` | string | `""` | Nombre de usuario SFTP |
| `sftp.password` | string | `""` | Contrasena SFTP (para autenticacion por contrasena) |
| `sftp.key_file` | string | `""` | Ruta del archivo de clave privada SSH (para autenticacion por clave privada, recomendado) |
| `sftp.key_passphrase` | string | `""` | Frase de paso de la clave privada (si aplica) |
| `sftp.remote_path` | string | `"/"` | Ruta de destino remoto |
| `sftp.enabled` | bool | `false` | Habilitar o deshabilitar SFTP |

### Ejemplo de configuracion

Usar formato tar.bz2 para backups con alta tasa de compresion:

```json
{
  "compression_format": "TAR_BZ2",
  "compression_level": 9,
  "skip_patterns": [".git", "__pycache__", "node_modules", "*.log"],
  "data_file": "backup_strategies.json",
  "lang": "es_ES"
}
```

### Comparacion de formatos de empaquetado

| Formato | Extension | Compresion | Velocidad | Dependencias | Caso de uso |
|---------|-----------|------------|-----------|--------------|-------------|
| ZIP | .zip | Media | Rapida | Biblioteca estandar | Uso general, mejor compatibilidad con Windows |
| tar | .tar | Ninguna | Muy rapida | Biblioteca estandar | Archivado puro, compresion externa |
| tar.gz | .tar.gz | Media | Rapida | Biblioteca estandar | Uso general en Linux/macOS |
| tar.bz2 | .tar.bz2 | Alta | Media | Biblioteca estandar | Archivado con alta compresion |
| tar.xz | .tar.xz | Maxima | Lenta | Biblioteca estandar | Archivado a largo plazo, sensible al espacio |
| tar.zst | .tar.zst | Media-alta | Muy rapida | zstandard | Casos modernos, equilibrio entre velocidad y compresion |
| 7z | .7z | Muy alta | Lenta | py7zr | Maxima compresion, soporte de cifrado |

#### Copia de seguridad remota por WebDAV

WebDAV es un protocolo de archivos basado en HTTP, compatible con los principales servicios en la nube como Jianguoyun, NextCloud y Synology. Utiliza `urllib` de la biblioteca estandar de Python, **sin dependencias adicionales**.

```bash
# ============ Inicio rapido ============
# 1. Configurar WebDAV
sbackup webdav config --url https://dav.jianguoyun.com/dav/ --user user@example.com --password secret

# 2. Probar conexion
sbackup webdav test

# 3. Ejecutar backup y subir
sbackup save --webdav

# ============ Casos de uso ============

# Caso 1: Backup unico y subida
sbackup save --webdav

# Caso 2: Backup programado con subida automatica (cada 60 minutos)
sbackup watch --interval 60 --webdav

# Caso 3: Especificar subdirectorio remoto
sbackup webdav config --url https://dav.jianguoyun.com/dav/ --user user@example.com --remote-path /backups/sbackup

# Caso 4: Subir simultaneamente a SFTP y WebDAV
sbackup save --sftp --webdav

# ============ Direcciones comunes de servicios WebDAV ============
# Jianguoyun: https://dav.jianguoyun.com/dav/
# NextCloud: https://your-server/remote.php/dav/files/username/
# Synology: https://your-synology:5006/webdav/
```

**Subcomandos de webdav:**

| Subcomando | Descripcion | Ejemplo |
|------------|-------------|---------|
| `webdav config` | Configurar parametros de conexion WebDAV (url/user/password/remote_path) | `sbackup webdav config --url ... --user ...` |
| `webdav test` | Probar si la conexion WebDAV esta disponible | `sbackup webdav test` |

| Parametro | Valor por defecto | Descripcion |
|-----------|-------------------|-------------|
| `--url URL` | `""` | Direccion del servidor WebDAV (ej. `https://dav.jianguoyun.com/dav/`) |
| `--user USER` | `""` | Nombre de usuario de WebDAV (normalmente un correo electronico) |
| `--password PASS` | `""` | Contrasena de WebDAV (para Jianguoyun, genera una contrasena de aplicacion en la configuracion) |
| `--remote-path PATH` | `/` | Ruta de destino remoto |

## Principio de funcionamiento

Sbackup implementa sus funciones de backup de la siguiente manera:

1. **Almacenamiento de estrategias**: Las estrategias de backup se almacenan en un archivo JSON que contiene las rutas de las carpetas, la ultima fecha de modificacion, las rutas de destino, los patrones de exclusion y el formato de empaquetado a nivel de entrada.
2. **Backup incremental**: Al comparar la ultima fecha de modificacion de las carpetas, solo se respaldan las carpetas que hayan cambiado.
3. **Compresion multi-formato**: Utiliza los modulos integrados `zipfile` y `tarfile` de Python, junto con las bibliotecas de terceros `zstandard` y `py7zr`, para soportar siete formatos de empaquetado.
4. **Formato a nivel de entrada**: Cada estrategia de backup puede especificar su propio formato de empaquetado (`add --format`), que tiene prioridad sobre la configuracion global `--format`. Si no se especifica, se usa el formato global por defecto.
5. **Limpieza de backups**: Despues de un backup exitoso, se escanea automaticamente el directorio de destino, se ordena por fecha de modificacion y se eliminan los archivos antiguos que excedan la cantidad de retencion.
6. **Cifrado**: El formato 7z soporta cifrado LZMA2, configurable mediante el parametro `--password` o en `config.json`.
7. **Backup programado**: El comando `watch` ejecuta backups en bucle a intervalos especificados; se sale de forma segura con `Ctrl+C`.
8. **Historial de backups**: Despues de cada backup se registra la marca de tiempo, el tamano del archivo y la cantidad de archivos, conservando los ultimos 100 registros.
9. **Backup remoto por SFTP**: Implementado con la biblioteca paramiko, soporta prueba de conexion, creacion automatica de directorios remotos y subida de archivos con barra de progreso.

### Formato del archivo de datos

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

Cada entrada de estrategia de backup es una lista de 4 elementos: `[mtime, target, skip_patterns, compression_format]`

| Campo | Descripcion |
|-------|-------------|
| `mtime` | Ultima fecha de modificacion de la carpeta de origen (para determinar si se necesita backup incremental) |
| `target` | Ruta de destino donde se almacenara el archivo de backup |
| `skip_patterns` | Lista de patrones de archivos/carpetas a ignorar |
| `compression_format` | Formato de empaquetado a nivel de entrada (cadena vacia = usar formato global por defecto) |

## Guia de desarrollo

### Ejecutar pruebas

```bash
uv run coverage run -m unittest discover -s tests -t . && uv run coverage report -m
```

### Estructura del codigo

```
sbackup/
├── main.py              # Punto de entrada del programa
├── sbackup/
│   ├── __init__.py      # Exportacion de funciones principales
│   ├── __main__.py      # Punto de entrada para python -m sbackup
│   ├── cli.py           # Analisis de argumentos CLI y distribucion de comandos (30+ comandos)
│   ├── config.py        # Carga de configuracion, cifrado, configuracion Webhook/SMTP
│   ├── auto_save.py     # Motor principal BackupManager
│   ├── compression.py   # Motor de compresion/descompresion de 7 formatos
│   ├── i18n.py          # Internacionalizacion (9 idiomas)
│   ├── sftp.py          # Cliente de backup remoto SFTP (paramiko)
│   ├── webdav.py        # Cliente de backup remoto WebDAV (sin dependencias)
│   ├── cloud_storage.py # Cliente de almacenamiento en la nube S3 (minio)
│   ├── multi_dest.py    # Backup paralelo a multiples destinos
│   ├── handlers.py      # Manejadores de comandos SFTP/WebDAV/Remote/Schedule
│   ├── hooks.py         # Ejecucion de hooks pre/post
│   ├── audit.py         # Sistema de registro de auditoria
│   ├── profile.py       # Gestion de perfiles de configuracion
│   ├── selective.py     # Restauracion selectiva
│   ├── cross_search.py  # Busqueda entre archivos
│   ├── integrity.py     # Sumas de verificacion SHA256
│   ├── rotation.py      # Politicas de rotacion de backups
│   ├── dryrun.py        # Vista previa de dry-run
│   ├── diskcheck.py     # Estimacion de espacio en disco
│   ├── task_queue.py    # Sistema de cola de tareas
│   ├── schema.py        # Validador de configuracion
│   ├── benchmark.py     # Benchmark de compresion
│   ├── chunked_backup.py# Backup incremental a nivel de bloque
│   ├── dedup.py         # Deduplicacion a nivel de archivo con SHA256
│   ├── export.py        # Exportacion de metadatos (CSV/JSON)
│   ├── monitor.py       # Monitoreo de sistema de archivos con watchdog
│   ├── lock.py          # Bloqueo de proceso multiplataforma
│   ├── retry.py         # Reintentos con retroceso exponencial
│   ├── ratelimiter.py   # Limitador de velocidad con cubeta de tokens
│   ├── keychain.py      # Integracion con el llavero del sistema
│   ├── parity.py        # Codigos de correccion de errores Reed-Solomon
│   ├── completion.py    # Autocompletado de shell
│   ├── wizard.py        # Asistente de configuracion interactivo
│   └── locales/         # Archivos de traduccion en 9 idiomas
└── tests/
    └── sbackup/
        └── test_*.py    # 30 archivos de prueba que cubren todos los modulos
```

### Agregar nuevas funcionalidades

1. Crear un nuevo archivo de modulo en el directorio `sbackup/`
2. Importar las funciones de la nueva funcionalidad en `sbackup/__init__.py`
3. Agregar la logica de manejo del nuevo comando en la funcion `run()`
4. Agregar el archivo de prueba correspondiente en el directorio `tests/`

## Preguntas frecuentes

### P: Que pasa si elimino accidentalmente el archivo de estrategias de backup?

R: Las estrategias de backup se almacenan en el archivo de datos. Si se elimina accidentalmente, puedes volver a agregar las estrategias ejecutando el comando `add` nuevamente.

### P: Como puedo modificar una estrategia de backup ya agregada?

R: Usa el comando `sbackup edit`: `sbackup edit <source> --dest <new_dest> --ignore <patterns> --format <fmt>`.

### P: Soporta backups remotos?

R: Si. Se ofrecen tres metodos de backup remoto:
- **SFTP**: Configurar con `sbackup sftp config`, subir con `sbackup save --sftp`
- **WebDAV**: Configurar con `sbackup webdav config`, subir con `sbackup save --webdav` (compatible con Jianguoyun, NextCloud, Synology)
- **Almacenamiento S3**: Configurar el campo `cloud` en `config.json`, subir con `sbackup save --cloud`
- Se pueden usar varios a la vez: `sbackup save --sftp --webdav --cloud`

### P: Cual es la diferencia entre tar.gz y ZIP?

R: tar.gz se usa mas comunmente en Linux/macOS y ofrece una tasa de compresion ligeramente superior; ZIP es mas universal en Windows y tiene la mejor compatibilidad. tar.bz2 y tar.xz ofrecen mayor compresion pero son mas lentos. tar.zst es un algoritmo moderno con velocidad excelente y buena compresion. 7z ofrece la mayor compresion y soporta cifrado.

### P: Como puedo cifrar un backup?

R: Usa el formato 7z y establece una contrasena: `uv run python main.py --format 7z save --password yourpassword`. La contrasena tambien puede escribirse en el campo `password` de `config.json`.

### P: Como puedo limpiar automaticamente los backups antiguos?

R: Usa el parametro `--keep`: `uv run python main.py save --keep 5` conserva solo los 5 backups mas recientes. Tambien funciona con backups programados: `uv run python main.py watch --interval 60 --keep 10`.

### P: Como puedo configurar backups programados?

R: Usa el comando `watch`: `uv run python main.py watch --interval 60` ejecuta un backup cada 60 minutos. Pulsa `Ctrl+C` para detener.

### P: Es seguro almacenar las contrasenas?

R: Las contrasenas de SFTP y de cifrado 7z en `config.json` se almacenan en **texto plano**. Asegurate de que los permisos de acceso al archivo `config.json` esten restringidos a usuarios de confianza (por ejemplo, `chmod 600 config.json`). No incluyas el archivo `config.json` con contrasenas en el sistema de control de versiones.

## Guia de contribucion

Se agradecen los Issues y Pull Requests.

1. Haz fork de este repositorio
2. Crea tu rama de funcionalidad (`git checkout -b feature/AmazingFeature`)
3. Realiza tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Sube a tu rama (`git push origin feature/AmazingFeature`)
5. Envia el Pull Request

### Estilo de codigo

Este proyecto sigue PEP 8 y Google Python Style Guide. Asegurate de que tu codigo:
- Use anotaciones de tipo
- Siga la convencion de docstrings de Google
- Pase todas las pruebas unitarias

## Licencia

Este proyecto esta licenciado bajo la licencia GNU GPL v3.0. Consulta el archivo [LICENSE](../../LICENSE) para mas detalles.

## Autor

**xiatianxuan** (CodeSeed)

- [Gitee](https://gitee.com/xiatianxuan)
- [Pagina personal](https://xnors-codeseed.pages.dev/)

## Agradecimientos especiales

- [Xnors Studio](https://xnors.github.io/)

## Contacto

Si tienes preguntas o sugerencias, envia un correo a: xiatianxuan2025@163.com

---

*Ultima actualizacion: 19 de junio de 2026*
