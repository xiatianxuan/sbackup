# Sbackup

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-GPL--3.0-green)](../../LICENSE)
[![PyPI](https://img.shields.io/pypi/v/sbackup-cli?color=blue)](https://pypi.org/project/sbackup-cli/)
[![Tests](https://img.shields.io/badge/tests-940%20passed-brightgreen)](../../.github/workflows/ci.yml)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)]()

> Ferramenta leve e eficiente para backup de pastas via linha de comando, ajudando você a gerenciar facilmente suas estratégias de backup.

[English](../../README.md) | [Deutsch](README_de.md) | [Espanol](README_es.md) | [Francais](README_fr.md) | [Portugues](README_pt.md) | [Pycckuu](README_ru.md) | [日本語](README_ja.md) | [한국어](README_ko.md) | [中文](README_zh.md)

- [Introducao](#introducao)
- [Recursos](#recursos)
- [Inicio Rapido](#inicio-rapido)
  - [Instalacao](#instalacao)
  - [Como Usar](#como-usar)
- [Arquivo de Configuracao](#arquivo-de-configuracao)
  - [Exemplo de Configuracao](#exemplo-de-configuracao)
- [Backup Remoto via SFTP](#backup-remoto-via-sftp)
- [Backup Remoto via WebDAV](#backup-remoto-via-webdav)
- [Como Funciona](#como-funciona)
- [Guia de Desenvolvimento](#guia-de-desenvolvimento)
  - [Executando Testes](#executando-testes)
  - [Estrutura do Codigo](#estrutura-do-codigo)
- [Perguntas Frequentes](#perguntas-frequentes)
- [Guia de Contribuicao](#guia-de-contribuicao)
- [Licenca](#licenca)
- [Autor](#autor)

---

## Introducao

Sbackup e uma ferramenta leve de backup de pastas que permite adicionar, remover e visualizar estrategias de backup via linha de comando. Ela utiliza a data de ultima modificacao da pasta para decidir se o backup precisa ser realizado, garantindo que seus dados estejam sempre atualizados.

## Recursos

- **Backup incremental**: faz backup apenas das pastas que foram alteradas, economizando tempo e espaco de armazenamento
- **Suporte a multiplos formatos**: suporta ZIP, tar, tar.gz, tar.bz2, tar.xz, tar.zst e 7z, com configuracao global e por entrada
- **Backup remoto via SFTP**: baseado na biblioteca paramiko, suporta autenticacao por senha/chave SSH com deteccao automatica de chave padrao
- **Backup remoto via WebDAV**: baseado na biblioteca padrao urllib, zero dependencias extras, compativel com JianguoCloud/NextCloud/Synology
- **Armazenamento em nuvem S3**: baseado na biblioteca minio, suporta todos os armazenamentos compativeis com S3 (AWS/MinIO/Alibaba Cloud OSS, etc.)
- **Backup paralelo para multiplos destinos**: faz backup simultaneamente para local + multiplos destinos remotos, sem interferencia entre eles
- **Restauracao de backup**: suporta descompactacao e restauracao de arquivos de backup para um diretorio especificado, com restauracao seletiva
- **Limpeza de backups**: remove backups antigos automaticamente, com politicas de retencao por quantidade/tempo/diaria
- **Backup criptografado**: suporta criptografia por senha no formato 7z + criptografia PBKDF2 para todos os formatos
- **Backup agendado**: execucao automatica em intervalos definidos, com monitoramento de arquivos em tempo real (watchdog)
- **Historico de backups**: registra o tempo, tamanho e checksum SHA256 de cada backup para rastreabilidade
- **Log de auditoria**: registra eventos de auditoria de todas as operacoes de backup/restauracao
- **Pre/Post Hook**: executa comandos personalizados antes e depois do backup
- **Perfis de configuracao**: suporta salvamento, alternancia, importacao e exportacao de multiplos perfis de configuracao
- **Busca entre arquivos**: busca nomes de arquivos correspondentes em multiplos arquivos de backup
- **Integridade dos dados**: geracao e verificacao de checksum SHA256, codigos de correcao de erros Reed-Solomon
- **Validacao de configuracao**: validacao automatica dos parametros de configuracao, deteccao de adulteracao
- **Fila de tarefas**: gerencia a fila de tarefas de backup, com suporte a adicao, execucao e cancelamento
- **Benchmark de compressao**: compara o desempenho de compressao entre diferentes formatos/niveis
- **Estimativa de espaco em disco**: estima o tamanho do backup por tipo de arquivo e verifica o espaco no destino
- **Internacionalizacao**: suporta chines, ingles, frances, espanhol, russo, alemao, japones, portugues e coreano
- **Autocompletar no shell**: suporta autocompletar em bash/zsh/fish/powershell
- **Leve e eficiente**: tamanho pequeno, inicializacao rapida, baixo consumo de recursos
- **Suporte multiplataforma**: suporta Windows, macOS e Linux

## Inicio Rapido

### Instalacao

#### Instalando via pip

```bash
pip install sbackup-cli
```

Apos a instalacao, use o comando `sbackup` (nome do pacote PyPI e `sbackup-cli`, comando CLI e `sbackup`).

#### Instalando a partir do codigo-fonte

```bash
git clone https://github.com/xiatianxuan/sbackup.git
cd sbackup
uv sync
```

### Como Usar

#### Sintaxe basica

```bash
uv run python main.py <comando> [opcoes]
```

#### Comandos disponiveis

| Comando | Descricao |
|---------|-----------|
| `add` | Adiciona uma estrategia de backup |
| `rm` / `remove` | Remove uma estrategia de backup |
| `edit` | Edita uma estrategia de backup existente |
| `all` | Exibe todas as estrategias de backup |
| `save` | Executa o backup |
| `watch` | Executa backups agendados |
| `restore` | Restaura a partir de um arquivo de backup |
| `info` | Exibe detalhes do arquivo de backup |
| `diff` | Compara diferencas entre o diretorio de origem e o backup |
| `verify` | Verifica a integridade do arquivo de backup |
| `search` | Busca arquivos no backup |
| `xsearch` | Busca entre multiplos arquivos de backup |
| `versions` | Exibe o historico de versoes do backup |
| `sftp` | Gerenciamento de backup remoto via SFTP |
| `webdav` | Gerenciamento de backup remoto via WebDAV |
| `remote` | Gerenciamento de arquivos remotos (list/rm) |
| `task` | Gerenciamento da fila de tarefas de backup |
| `audit` | Consulta de logs de auditoria |
| `hooks` | Executa Pre/Post Hook manualmente |
| `profile` | Gerenciamento de perfis de configuracao |
| `rotate` | Limpeza por rotacao de backups |
| `clean` | Limpa backups antigos |
| `diskcheck` | Estimativa de espaco em disco |
| `benchmark` | Benchmark de formatos de compressao |
| `integrity` | Verificacao de integridade do diretorio de backup |
| `dry-run` | Visualizacao previa da selecao de arquivos de backup |
| `export` / `import` | Exporta/importa estrategias de backup |
| `ignore` | Gera arquivo .sbackupignore |
| `schedule` | Exporta configuracao de agendamento |
| `webhook` | Configura predefinicoes de Webhook |
| `config` | Configuracao de criptografia/validacao |
| `report` | Gera relatorio de backup |
| `completion` | Gera scripts de autocompletar para shells |
| `wizard` | Assistente de configuracao interativo |
| `status` | Painel de status do backup |
| `version` | Exibe informacoes de versao |
| `help` | Exibe ajuda |

#### Parametros globais

| Parametro | Descricao |
|-----------|-----------|
| `--lang zh_CN` / `en_US` / `fr_FR` / `es_ES` / `ru_RU` / `de_DE` / `ja_JP` / `pt_BR` / `ko_KR` | Define o idioma da interface (persistido no config.json) |
| `--format zip` / `tar` / `tar.gz` / `tar.bz2` / `tar.xz` / `tar.zst` / `7z` | Define o formato de empacotamento (persistido no config.json) |
| `--debug` | Ativa logs de depuracao |

#### Adicionando uma estrategia de backup

```bash
uv run python main.py add <origem> <destino> [-i padroes_ignorados]
```

Parametros:
- **origem**: caminho da pasta de origem para backup
- **destino**: caminho onde os arquivos de backup serao armazenados
- **-i, --ignore**: nomes de arquivos ou pastas a serem ignorados, separados por virgula (padrao: `.git,__pycache__`)
- **--format**: formato de empacotamento por entrada (apenas para esta estrategia de backup, usa o padrao global se nao especificado): `zip` / `tar` / `tar.gz` / `tar.bz2` / `tar.xz` / `tar.zst` / `7z`

Exemplos:
```bash
# Adiciona estrategia usando o formato padrao global
uv run python main.py add F:/minha_pasta F:/backup -i node_modules,.git

# Define formato tar.gz para esta estrategia (cada backup desta pasta usara tar.gz)
uv run python main.py add F:/minha_pasta F:/backup --format tar.gz

# Define formato 7z (apenas para esta pasta)
uv run python main.py add F:/minha_pasta F:/backup --format 7z
```

#### Removendo uma estrategia de backup

```bash
uv run python main.py rm <caminho>
```

Parametros:
- **caminho**: caminho da pasta de origem da estrategia de backup a ser removida

Exemplo:
```bash
uv run python main.py rm F:/minha_pasta
```

#### Visualizando todas as estrategias de backup

```bash
uv run python main.py all
```

Exibe todas as estrategias de backup configuradas atualmente.

#### Executando o backup

```bash
# Usa o formato padrao (ZIP)
uv run python main.py save

# Usa formato tar.gz
uv run python main.py --format tar.gz save

# Mantem os 5 backups mais recentes, limpa automaticamente os antigos
uv run python main.py save --keep 5

# Usa formato 7z com criptografia
uv run python main.py --format 7z save --password mysecret

# Interface em ingles + formato tar.xz
uv run python main.py --lang en_US --format tar.xz save
```

**Parametros do comando save:**

| Parametro | Padrao | Descricao |
|-----------|--------|-----------|
| `--keep N` | `0` | Mantem os N backups mais recentes, 0 significa sem limpeza |
| `--password SENHA` | `""` | Senha de criptografia (apenas formato 7z) |
| `--sftp` | `false` | Envia para servidor SFTP apos o backup |
| `--webdav` | `false` | Envia para servidor WebDAV apos o backup |

De acordo com a estrategia de backup, faz backup automaticamente das pastas que foram alteradas.

#### Backup agendado

```bash
# Executa backup a cada 60 minutos
uv run python main.py watch --interval 60

# Backup a cada 2 horas, mantem os 10 arquivos mais recentes
uv run python main.py watch --interval 120 --keep 10

# Backup agendado + criptografia 7z
uv run python main.py --format 7z watch --interval 60 --password mysecret
```

**Parametros do comando watch:**

| Parametro | Padrao | Descricao |
|-----------|--------|-----------|
| `--interval MINUTOS` | `60` | Intervalo entre backups (em minutos) |
| `--keep N` | `0` | Mantem os N backups mais recentes |
| `--password SENHA` | `""` | Senha de criptografia (apenas formato 7z) |
| `--sftp` | `false` | Envia para servidor SFTP apos cada backup |
| `--webdav` | `false` | Envia para servidor WebDAV apos cada backup |

Pressione `Ctrl+C` para parar o backup agendado.

#### Restaurando backup

```bash
uv run python main.py restore <arquivo_backup> <diretorio_destino>
```

Parametros:
- **arquivo_backup**: caminho do arquivo de backup (suporta .zip / .tar / .tar.gz / .tar.bz2 / .tar.xz / .tar.zst / .7z)
- **diretorio_destino**: diretorio de destino para restauracao

Exemplos:
```bash
uv run python main.py restore F:/backup/minha_pasta.tar.gz F:/restaurado
uv run python main.py restore F:/backup/minha_pasta.7z F:/restaurado
uv run python main.py restore F:/backup/minha_pasta.tar.zst F:/restaurado
```

#### Backup remoto via SFTP

```bash
# ============ Inicio rapido (recomendado) ============
# 1. Configura SFTP (deteccao automatica de chave SSH, sem necessidade de especificar manualmente)
sbackup sftp config --host 192.168.1.100 --user admin --remote-path /backups

# 2. Testa a conexao
sbackup sftp test

# 3. Executa backup e envia
sbackup save --sftp

# ============ Metodos de autenticacao ============

# Metodo 1: Deteccao automatica de chave privada (recomendado)
# O sistema tenta automaticamente ~/.ssh/id_ed25519 -> id_rsa -> id_ecdsa
sbackup sftp config --host 192.168.1.100 --user admin

# Metodo 2: Autenticacao por senha
sbackup sftp config --host 192.168.1.100 --user admin --password secret

# Metodo 3: Especificar chave privada
sbackup sftp config --host 192.168.1.100 --user admin --key-file ~/.ssh/id_rsa

# Metodo 4: Chave privada + frase secreta (entrada interativa)
sbackup sftp config --host 192.168.1.100 --user admin --key-file ~/.ssh/id_rsa

# Metodo 5: Chave privada + frase secreta (especificada na linha de comando)
sbackup sftp config --host 192.168.1.100 --user admin --key-file ~/.ssh/id_rsa --key-passphrase mykeypass

# ============ Cenarios de uso ============

# Cenario 1: Backup unico e envio
sbackup save --sftp

# Cenario 2: Backup agendado com envio automatico (a cada 60 minutos)
sbackup watch --interval 60 --sftp

# Cenario 3: Backup com formato especifico + envio
sbackup --format tar.gz save --sftp

# Cenario 4: Backup criptografado + envio
sbackup --format 7z save --password mysecret --sftp

# Cenario 5: Manter os 5 backups mais recentes + envio
sbackup save --keep 5 --sftp

# ============ Uso avancado ============

# Configuracao interativa (insere todos os parametros passo a passo)
sbackup sftp config

# Configuracao nao interativa (todos os parametros na linha de comando)
sbackup sftp config --host 192.168.1.100 --port 22 --user admin --password secret --remote-path /backups

# Testa conexao e exibe log detalhado
sbackup --debug sftp test
```

**Subcomandos sftp:**

| Subcomando | Descricao | Exemplo |
|------------|-----------|---------|
| `sftp config` | Configura parametros de conexao SFTP (host/port/user/password/key_file/key_passphrase/remote_path) | `sbackup sftp config --host 192.168.1.100 --user admin` |
| `sftp test` | Testa se a conexao SFTP esta disponivel | `sbackup sftp test` |

**Metodos de autenticacao:**

| Metodo | Parametros | Descricao | Exemplo |
|--------|------------|-----------|---------|
| **Deteccao automatica** | Sem parametros de autenticacao | Tenta automaticamente `~/.ssh/id_ed25519` -> `id_rsa` -> `id_ecdsa` (recomendado) | `sbackup sftp config --host ... --user ...` |
| Senha | `--password` | Login direto com senha | `sbackup sftp config --host ... --user ... --password secret` |
| Chave privada | `--key-file` | Login com chave SSH especifica | `sbackup sftp config --host ... --user ... --key-file ~/.ssh/id_rsa` |
| Chave privada+frase | `--key-file` + `--key-passphrase` | Usado quando a chave privada possui frase secreta | `sbackup sftp config --host ... --user ... --key-file ~/.ssh/id_rsa --key-passphrase mypass` |

Formatos de chave privada suportados: RSA, Ed25519, ECDSA.

**Suporte a caminhos multiplataforma:**

| Plataforma | Exemplo de caminho da chave privada | Descricao |
|------------|-------------------------------------|-----------|
| Linux/macOS | `~/.ssh/id_rsa` | Expande automaticamente para `/home/usuario/.ssh/id_rsa` |
| Windows | `~/.ssh/id_rsa` | Expande automaticamente para `C:\Users\usuario\.ssh\id_rsa` |
| Todas | Caminho absoluto | Usa o caminho completo diretamente |

A configuracao SFTP e salva no campo `sftp` do `config.json`, suportando parametros via linha de comando ou entrada interativa.

#### Visualizando informacoes de versao

```bash
sbackup version
```

## Arquivo de Configuracao

Sbackup suporta configuracao personalizada atraves do arquivo `config.json`. O arquivo de configuracao deve ser colocado no diretorio raiz do projeto.

### Descricao das configuracoes

```json
{
  "compression_format": "ZIP",
  "compression": {
    "algorithm": "ZIP_DEFLATED",
    "level": 6
  },
  "skip_patterns": [".git", "__pycache__"],
  "data_file": "sbackup.json",
  "lang": "pt_BR",
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

| Configuracao | Tipo | Padrao | Descricao |
|--------------|------|--------|-----------|
| `compression_format` | string | `"ZIP"` | Formato de empacotamento, valores validos: `ZIP`, `TAR`, `TAR_GZ`, `TAR_BZ2`, `TAR_XZ`, `TAR_ZST`, `7Z` |
| `compression.algorithm` | string | `"ZIP_DEFLATED"` | Algoritmo de compressao ZIP, valores validos: `ZIP_DEFLATED`, `ZIP_STORED`, `ZIP_BZIP2`, `ZIP_LZMA` |
| `compression.level` | int | `6` | Nivel de compressao, intervalo 0-9 (0 = sem compressao, 9 = compressao maxima) |
| `skip_patterns` | list | `[".git", "__pycache__"]` | Padroes de arquivos ou pastas a serem ignorados (suporta curingas fnmatch e correspondencia de caminhos) |
| `data_file` | string | Caminho padrao da plataforma | Caminho do arquivo de dados das estrategias de backup |
| `lang` | string | `"pt_BR"` | Idioma da interface, valores validos: `zh_CN`, `en_US`, `fr_FR`, `es_ES`, `ru_RU`, `de_DE`, `ja_JP`, `pt_BR`, `ko_KR` |
| `password` | string | `""` | Senha de criptografia 7z |
| `sftp.host` | string | `""` | Endereco do servidor SFTP |
| `sftp.port` | int | `22` | Porta SFTP |
| `sftp.user` | string | `""` | Nome de usuario SFTP |
| `sftp.password` | string | `""` | Senha SFTP (usada na autenticacao por senha) |
| `sftp.key_file` | string | `""` | Caminho do arquivo de chave SSH privada (usado na autenticacao por chave, recomendado) |
| `sftp.key_passphrase` | string | `""` | Frase secreta da chave privada (se houver) |
| `sftp.remote_path` | string | `"/"` | Caminho do destino remoto |
| `sftp.enabled` | bool | `false` | Habilita ou desabilita SFTP |

### Exemplo de configuracao

Usando formato tar.bz2 para backup com alta taxa de compressao:

```json
{
  "compression_format": "TAR_BZ2",
  "compression_level": 9,
  "skip_patterns": [".git", "__pycache__", "node_modules", "*.log"],
  "data_file": "estrategias_backup.json",
  "lang": "pt_BR"
}
```

### Comparacao de formatos de empacotamento

| Formato | Extensao | Taxa de compressao | Velocidade | Dependencia | Cenario de uso |
|---------|----------|-------------------|------------|-------------|----------------|
| ZIP | .zip | Media | Rapida | Biblioteca padrao | Uso geral, melhor compatibilidade com Windows |
| tar | .tar | Nenhuma | Muito rapida | Biblioteca padrao | Apenas arquivamento, combina com compressao externa |
| tar.gz | .tar.gz | Media | Rapida | Biblioteca padrao | Uso geral em Linux/macOS |
| tar.bz2 | .tar.bz2 | Alta | Media | Biblioteca padrao | Arquivamento com alta taxa de compressao |
| tar.xz | .tar.xz | Muito alta | Lenta | Biblioteca padrao | Arquivamento de longo prazo, sensivel a espaco |
| tar.zst | .tar.zst | Media-alta | Muito rapida | zstandard | Cenarios modernos, equilibrio entre velocidade e compressao |
| 7z | .7z | Extremamente alta | Lenta | py7zr | Maior taxa de compressao, suporta criptografia |

#### Backup remoto via WebDAV

WebDAV e um protocolo de arquivos baseado em HTTP, compativel com JianguoCloud, NextCloud, Synology e outros servicos de armazenamento em nuvem. Usa a biblioteca padrao `urllib` do Python, **zero dependencias extras**.

```bash
# ============ Inicio rapido ============
# 1. Configura WebDAV
sbackup webdav config --url https://dav.jianguoyun.com/dav/ --user usuario@exemplo.com --password secret

# 2. Testa a conexao
sbackup webdav test

# 3. Executa backup e envia
sbackup save --webdav

# ============ Cenarios de uso ============

# Cenario 1: Backup unico e envio
sbackup save --webdav

# Cenario 2: Backup agendado com envio automatico (a cada 60 minutos)
sbackup watch --interval 60 --webdav

# Cenario 3: Especificar subdiretorio remoto
sbackup webdav config --url https://dav.jianguoyun.com/dav/ --user usuario@exemplo.com --remote-path /backups/sbackup

# Cenario 4: Enviar simultaneamente para SFTP e WebDAV
sbackup save --sftp --webdav

# ============ Enderecos comuns de servicos WebDAV ============
# JianguoCloud: https://dav.jianguoyun.com/dav/
# NextCloud: https://seu-servidor/remote.php/dav/files/usuario/
# Synology: https://seu-synology:5006/webdav/
```

**Subcomandos webdav:**

| Subcomando | Descricao | Exemplo |
|------------|-----------|---------|
| `webdav config` | Configura parametros de conexao WebDAV (url/user/password/remote_path) | `sbackup webdav config --url ... --user ...` |
| `webdav test` | Testa se a conexao WebDAV esta disponivel | `sbackup webdav test` |

| Parametro | Padrao | Descricao |
|-----------|--------|-----------|
| `--url URL` | `""` | Endereco do servidor WebDAV (ex: `https://dav.jianguoyun.com/dav/`) |
| `--user USUARIO` | `""` | Nome de usuario WebDAV (geralmente o e-mail) |
| `--password SENHA` | `""` | Senha WebDAV (JianguoCloud requer geracao de senha de aplicativo nas configuracoes) |
| `--remote-path CAMINHO` | `/` | Caminho do destino remoto |

## Como Funciona

Sbackup implementa as funcionalidades de backup da seguinte forma:

1. **Armazenamento de estrategias**: as estrategias de backup sao armazenadas em um arquivo JSON, contendo caminhos de pastas, data de ultima modificacao, caminhos de destino, padroes de ignorancia e formato de empacotamento por entrada.
2. **Backup incremental**: comparando a data de ultima modificacao das pastas, faz backup apenas das pastas que foram alteradas.
3. **Compressao multi-formato**: usa os modulos `zipfile` e `tarfile` integrados do Python, alem das bibliotecas `zstandard` e `py7zr`, suportando 7 formatos de empacotamento.
4. **Formato por entrada**: cada estrategia de backup pode ter seu proprio formato de empacotamento (`add --format`), com prioridade sobre a configuracao global `--format`; quando nao especificado, usa o padrao global.
5. **Limpeza de backups**: apos o backup ser bem-sucedido, escaneia automaticamente o diretorio de destino, ordena por data de modificacao e remove arquivos antigos que excedem a quantidade de retencao.
6. **Backup criptografado**: o formato 7z suporta criptografia LZMA2, atraves do parametro `--password` ou configuracao no `config.json`.
7. **Backup agendado**: o comando `watch` executa backups em loop com intervalos especificados, `Ctrl+C` para saida segura.
8. **Historico de backups**: apos cada backup, registra timestamp, tamanho do arquivo e contagem de arquivos, mantendo os ultimos 100 registros.
9. **Backup remoto via SFTP**: implementa o cliente SFTP baseado na biblioteca paramiko, com suporte a teste de conexao, criacao automatica de diretorios remotos e upload de arquivos com barra de progresso.

### Formato do arquivo de dados

```json
{
  "/caminho/para/pasta/de/origem": [
    1719235200.0,
    "/caminho/para/pasta/de/destino",
    [".git", "__pycache__"],
    ""
  ],
  "/caminho/para/outra/pasta": [
    1719235200.0,
    "/caminho/para/outro/destino",
    [".git"],
    "TAR_GZ"
  ],
  "_history": [
    {
      "time": "2026-05-01T12:00:00",
      "source": "/caminho/para/pasta/de/origem",
      "size_mb": 12.5,
      "files_count": 150
    }
  ]
}
```

Cada entrada de estrategia de backup e uma lista de 4 elementos: `[mtime, destino, padroes_ignorados, formato_compressao]`

| Campo | Descricao |
|-------|-----------|
| `mtime` | Data de ultima modificacao da pasta de origem (usada para decisao de backup incremental) |
| `destino` | Caminho de destino onde os arquivos de backup serao armazenados |
| `padroes_ignorados` | Lista de padroes de arquivos/pastas a serem ignorados |
| `formato_compressao` | Formato de empacotamento por entrada (string vazia significa usar o padrao global) |

## Guia de Desenvolvimento

### Executando testes

```bash
uv run coverage run -m unittest discover -s tests -t . && uv run coverage report -m
```

### Estrutura do codigo

```
sbackup/
├── main.py              # Ponto de entrada do programa
├── sbackup/
│   ├── __init__.py      # Exporta funcoes principais
│   ├── __main__.py      # Ponto de entrada python -m sbackup
│   ├── cli.py           # Analise de argumentos CLI e distribuicao de comandos (30+ comandos)
│   ├── config.py        # Carregamento de configuracao, criptografia, configuracao Webhook/SMTP
│   ├── auto_save.py     # Motor principal BackupManager
│   ├── compression.py   # Motor de compressao/descompressao para 7 formatos
│   ├── i18n.py          # Internacionalizacao (9 idiomas)
│   ├── sftp.py          # Cliente SFTP de backup remoto (paramiko)
│   ├── webdav.py        # Cliente WebDAV de backup remoto (zero dependencias)
│   ├── cloud_storage.py # Cliente S3 de armazenamento em nuvem (minio)
│   ├── multi_dest.py    # Backup paralelo para multiplos destinos
│   ├── handlers.py      # Manipuladores de comandos SFTP/WebDAV/Remote/Schedule
│   ├── hooks.py         # Execucao de Pre/Post Hook
│   ├── audit.py         # Sistema de log de auditoria
│   ├── profile.py       # Gerenciamento de perfis de configuracao
│   ├── selective.py     # Restauracao seletiva
│   ├── cross_search.py  # Busca entre arquivos
│   ├── integrity.py     # Checksum SHA256
│   ├── rotation.py      # Estrategia de rotacao de backups
│   ├── dryrun.py        # Visualizacao previa de dry-run
│   ├── diskcheck.py     # Estimativa de espaco em disco
│   ├── task_queue.py    # Sistema de fila de tarefas
│   ├── schema.py        # Validador de configuracao
│   ├── benchmark.py     # Benchmark de compressao
│   ├── chunked_backup.py# Backup incremental por blocos
│   ├── dedup.py         # Deduplicacao por SHA256 no nivel de arquivo
│   ├── export.py        # Exportacao de metadados (CSV/JSON)
│   ├── monitor.py       # Monitoramento de sistema de arquivos com watchdog
│   ├── lock.py          # Bloqueio de processo multiplataforma
│   ├── retry.py         | Retry com backoff exponencial
│   ├── ratelimiter.py   # Limitador de taxa por balde de tokens
│   ├── keychain.py      # Integracao com chaveiro do sistema
│   ├── parity.py        # Codigos de correcao de erros Reed-Solomon
│   ├── completion.py    # Autocompletar para shells
│   ├── wizard.py        # Assistente de configuracao interativo
│   └── locales/         # Arquivos de traducao para 9 idiomas
└── tests/
    └── sbackup/
        └── test_*.py    # 30 arquivos de teste cobrindo todos os modulos
```

### Adicionando novas funcionalidades

1. Crie um novo arquivo de modulo no diretorio `sbackup/`
2. Importe as funcoes da nova funcionalidade em `sbackup/__init__.py`
3. Adicione a logica de manipulacao do novo comando na funcao `run()`
4. Adicione o arquivo de teste correspondente no diretorio `tests/`

## Perguntas Frequentes

### P: E se o arquivo de estrategias de backup for deletado acidentalmente?

R: As estrategias de backup sao armazenadas no arquivo de dados. Se forem deletadas acidentalmente, voce pode reexecutar o comando `add` para adicionar as estrategias novamente.

### P: Como modificar uma estrategia de backup ja adicionada?

R: Use o comando `sbackup edit`: `sbackup edit <origem> --dest <novo_destino> --ignore <padroes> --format <fmt>`.

### P: Suporta backup remoto?

R: Sim! Sao fornecidos tres metodos de backup remoto:
- **SFTP**: `sbackup sftp config` para configurar, `sbackup save --sftp` para enviar
- **WebDAV**: `sbackup webdav config` para configurar, `sbackup save --webdav` para enviar (compativel com JianguoCloud/NextCloud/Synology)
- **Armazenamento em nuvem S3**: configure o campo `cloud` no `config.json`, `sbackup save --cloud` para enviar
- Pode usar varios simultaneamente: `sbackup save --sftp --webdav --cloud`

### P: Qual a diferenca entre tar.gz e ZIP?

R: tar.gz e mais usado em Linux/macOS, com taxa de compressao ligeiramente superior; ZIP e mais universal em Windows, com melhor compatibilidade. tar.bz2 e tar.xz oferecem maior taxa de compressao, mas sao mais lentos. tar.zst e um algoritmo moderno, muito rapido com boa taxa de compressao. 7z tem a maior taxa de compressao e suporta criptografia.

### P: Como criptografar o backup?

R: Use o formato 7z e defina uma senha: `uv run python main.py --format 7z save --password suasenha`. A senha tambem pode ser gravada no campo `password` do `config.json`.

### P: Como limpar backups antigos automaticamente?

R: Use o parametro `--keep`: `uv run python main.py save --keep 5` mantem apenas os 5 backups mais recentes. O backup agendado tambem suporta: `uv run python main.py watch --interval 60 --keep 10`.

### P: Como configurar backup agendado?

R: Use o comando `watch`: `uv run python main.py watch --interval 60` executa backup a cada 60 minutos. Pressione `Ctrl+C` para parar.

### P: O armazenamento de senhas e seguro?

R: As senhas SFTP e de criptografia 7z no `config.json` sao armazenadas em **texto plano**. Certifique-se de que as permissoes de acesso ao arquivo `config.json` sejam restritas a usuarios confiaveis (por exemplo, `chmod 600 config.json`). Nao envie o `config.json` com senhas para o sistema de controle de versao.

## Guia de Contribuicao

Contribuicoes com Issues e Pull Requests sao bem-vindas!

1. Fork este repositorio
2. Crie sua branch de funcionalidade (`git checkout -b feature/SuaFuncionalidade`)
3. Faca seus commits (`git commit -m 'Adiciona SuaFuncionalidade'`)
4. Envie para a branch (`git push origin feature/SuaFuncionalidade`)
5. Abra um Pull Request

### Estilo de codigo

Este projeto segue o PEP 8 e o Google Python Style Guide. Certifique-se de que seu codigo:
- Use anotacoes de tipo
- Siga docstrings no estilo Google
- Passe em todos os testes unitarios

## Licenca

Este projeto esta licenciado sob a GNU GPL v3.0. Consulte o arquivo [LICENSE](../../LICENSE) para mais detalhes.

## Autor

**xiatianxuan** (CodeSeed)

- [Gitee](https://gitee.com/xiatianxuan)
- [Pagina pessoal](https://xnors-codeseed.pages.dev/)

## Agradecimentos especiais

- [Xnors Studio](https://xnors.github.io/)

## Contato

Se tiver duvidas ou sugestoes, envie um e-mail para: xiatianxuan2025@163.com

---

*Ultima atualizacao: 19 de junho de 2026*
