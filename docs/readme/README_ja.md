# Sbackup

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-GPL--3.0-green)](../../LICENSE)
[![PyPI](https://img.shields.io/pypi/v/sbackup-cli?color=blue)](https://pypi.org/project/sbackup-cli/)
[![Tests](https://img.shields.io/badge/tests-940%20passed-brightgreen)](../../.github/workflows/ci.yml)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)]()

> 軽量で高効率なフォルダバックアップツール。コマンドラインでバックアップ戦略を簡単に管理できます。

[English](../../README.md) | [Deutsch](README_de.md) | [Espanol](README_es.md) | [Francais](README_fr.md) | [Portugues](README_pt.md) | [Pycckuu](README_ru.md) | [日本語](README_ja.md) | [한국어](README_ko.md) | [中文](README_zh.md)

- [はじめに](#はじめに)
- [機能一覧](#機能一覧)
- [クイックスタート](#クイックスタート)
  - [インストール](#インストール)
  - [使い方](#使い方)
- [設定ファイル](#設定ファイル)
  - [設定例](#設定例)
- [SFTP リモートバックアップ](#sftp-リモートバックアップ)
- [WebDAV リモートバックアップ](#webdav-リモートバックアップ)
- [仕組み](#仕組み)
- [開発ガイド](#開発ガイド)
  - [テスト実行](#テスト実行)
  - [コード構造](#コード構造)
- [よくある質問](#よくある質問)
- [コントリビューションガイド](#コントリビューションガイド)
- [ライセンス](#ライセンス)
- [著者](#著者)

---

## はじめに

Sbackup は軽量なフォルダバックアップツールです。コマンドラインからバックアップ戦略の追加、削除、表示が可能です。フォルダの最終更新日時を基にバックアップが必要かどうかを判断し、データを常に最新の状態に保ちます。

## 機能一覧

- **増分バックアップ**: 変更されたフォルダのみをバックアップし、時間とストレージを節約
- **多形式対応**: ZIP、tar、tar.gz、tar.bz2、tar.xz、tar.zst、7z の 7 種類のアーカイブ形式に対応。グローバルおよびエントリ単位で個別に指定可能
- **SFTP リモートバックアップ**: paramiko ベース。パスワード/SSH 秘密鍵認証、デフォルト秘密鍵の自動検出に対応
- **WebDAV リモートバックアップ**: Python 標準ライブラリ urllib ベース。追加依存なし。Jianguoyun/NextCloud/Synology 対応
- **S3 クラウドストレージ**: minio ベース。すべての S3 互換ストレージ（AWS/MinIO/Alibaba Cloud OSS 等）に対応
- **マルチターゲット並列バックアップ**: ローカルと複数のリモートターゲットへ同時にバックアップ。互いに影響しない
- **バックアップ復元**: バックアップファイルからの解凍・復元に対応。選択的な復元も可能
- **バックアップクリーンアップ**: 古いバックアップの自動削除。数量/日数/日別保持ポリシーに対応
- **暗号化バックアップ**: 7z 形式のパスワード暗号化と全形式 PBKDF2 暗号化に対応
- **定期バックアップ**: 指定間隔での自動実行。リアルタイムファイル監視（watchdog）に対応
- **バックアップ履歴**: 各バックアップの時刻、サイズ、SHA256 チェックサムを記録し、追跡を容易に
- **監査ログ**: すべてのバックアップ/復元操作の監査イベントを記録
- **Pre/Post Hook**: バックアップ前後にカスタムコマンドを実行
- **設定 Profile**: 複数の設定プロファイルの保存、切替、インポート/エクスポート
- **クロスアーカイブ検索**: 複数のバックアップファイルにわたるファイル名検索
- **データ整合性**: SHA256 チェックサムの生成と検証、Reed-Solomon 誤り訂正符号
- **設定バリデーション**: 設定パラメータの自動検証、改ざん検出
- **タスクキュー**: バックアップタスクキューの管理。追加、実行、キャンセルに対応
- **圧縮ベンチマーク**: 異なる形式/圧縮レベルのパフォーマンス比較
- **ディスク容量見積もり**: ファイルタイプ別のバックアップサイズ見積もり、ターゲット空き容量チェック
- **国際化**: 中国語、英語、フランス語、スペイン語、ロシア語、ドイツ語、日本語、ポルトガル語、韓国語の 9 言語に対応
- **Shell 補完**: bash/zsh/fish/powershell での自動補完に対応
- **軽量高効率**: 小さなサイズ、高速起動、リソース消費が低い
- **クロスプラットフォーム対応**: Windows、macOS、Linux に対応

## クイックスタート

### インストール

#### pip でのインストール

```bash
pip install sbackup-cli
```

インストール後、`sbackup` コマンドが使用可能になります（PyPI パッケージ名は `sbackup-cli`、CLI コマンドは `sbackup`）。

#### ソースからのインストール

```bash
git clone https://github.com/xiatianxuan/sbackup.git
cd sbackup
uv sync
```

### 使い方

#### 基本構文

```bash
uv run python main.py <command> [options]
```

#### 利用可能なコマンド

| コマンド | 説明 |
|----------|------|
| `add` | バックアップ戦略を追加 |
| `rm` / `remove` | バックアップ戦略を削除 |
| `edit` | 既存のバックアップ戦略を編集 |
| `all` | すべてのバックアップ戦略を表示 |
| `save` | バックアップを実行 |
| `watch` | 定期バックアップを実行 |
| `restore` | バックアップファイルから復元 |
| `info` | バックアップファイルの詳細を表示 |
| `diff` | ソースディレクトリとバックアップの差分を比較 |
| `verify` | バックアップファイルの整合性を検証 |
| `search` | バックアップ内をファイル検索 |
| `xsearch` | 複数のバックアップアーカイブを横断検索 |
| `versions` | バックアップバージョン履歴を表示 |
| `sftp` | SFTP リモートバックアップ管理 |
| `webdav` | WebDAV リモートバックアップ管理 |
| `remote` | リモートファイル管理（list/rm） |
| `task` | バックアップタスクキュー管理 |
| `audit` | 監査ログ照会 |
| `hooks` | Pre/Post Hook を手動実行 |
| `profile` | 設定 Profile 管理 |
| `rotate` | バックアップローテーションクリーンアップ |
| `clean` | 古いバックアップをクリーンアップ |
| `diskcheck` | ディスク容量見積もり |
| `benchmark` | 圧縮形式ベンチマーク |
| `integrity` | バックアップディレクトリ整合性検証 |
| `dry-run` | バックアップファイル選択のプレビュー |
| `export` / `import` | バックアップ戦略のエクスポート/インポート |
| `ignore` | .sbackupignore ファイルを生成 |
| `schedule` | 定期スケジュール設定をエクスポート |
| `webhook` | Webhook プリセットを設定 |
| `config` | 暗号化/検証の設定 |
| `report` | バックアップレポートを生成 |
| `completion` | Shell 補完スクリプトを生成 |
| `wizard` | インタラクティブ設定ウィザード |
| `status` | バックアップステータスダッシュボード |
| `version` | バージョン情報を表示 |
| `help` | ヘルプを表示 |

#### グローバルオプション

| オプション | 説明 |
|-----------|------|
| `--lang zh_CN` / `en_US` / `fr_FR` / `es_ES` / `ru_RU` / `de_DE` / `ja_JP` / `pt_BR` / `ko_KR` | UI 言語を設定（config.json に永続化） |
| `--format zip` / `tar` / `tar.gz` / `tar.bz2` / `tar.xz` / `tar.zst` / `7z` | アーカイブ形式を設定（config.json に永続化） |
| `--debug` | デバッグログを有効化 |

#### バックアップ戦略の追加

```bash
uv run python main.py add <source> <dest> [-i ignore_patterns]
```

パラメータ説明:
- **source**: バックアップ対象のソースフォルダパス
- **dest**: バックアップファイルの保存先パス
- **-i, --ignore**: 無視するファイルまたはフォルダ名（カンマ区切り。デフォルト: `.git,__pycache__`）
- **--format**: エントリ単位のアーカイブ形式（このバックアップ戦略のみに適用。未指定時はグローバルデフォルトを使用）: `zip` / `tar` / `tar.gz` / `tar.bz2` / `tar.xz` / `tar.zst` / `7z`

例:
```bash
# グローバルデフォルト形式で戦略を追加
uv run python main.py add F:/my_folder F:/backup -i node_modules,.git

# この戦略に tar.gz 形式を指定（このフォルダのバックアップは常に tar.gz）
uv run python main.py add F:/my_folder F:/backup --format tar.gz

# 7z 形式を指定（このフォルダのみ）
uv run python main.py add F:/my_folder F:/backup --format 7z
```

#### バックアップ戦略の削除

```bash
uv run python main.py rm <path>
```

パラメータ説明:
- **path**: バックアップ戦略を削除するソースフォルダのパス

例:
```bash
uv run python main.py rm F:/my_folder
```

#### すべてのバックアップ戦略を表示

```bash
uv run python main.py all
```

現在設定されているすべてのバックアップ戦略を表示します。

#### バックアップの実行

```bash
# デフォルト形式（ZIP）を使用
uv run python main.py save

# tar.gz 形式を使用
uv run python main.py --format tar.gz save

# 直近 5 件のバックアップを保持し、古いものを自動クリーンアップ
uv run python main.py save --keep 5

# 7z 形式で暗号化
uv run python main.py --format 7z save --password mysecret

# 英語 UI + tar.xz 形式
uv run python main.py --lang en_US --format tar.xz save
```

**save コマンドのオプション:**

| オプション | デフォルト値 | 説明 |
|-----------|-------------|------|
| `--keep N` | `0` | 直近 N 件のバックアップファイルを保持。0 はクリーンアップなし |
| `--password PASSWORD` | `""` | 暗号化パスワード（7z 形式のみ対応） |
| `--sftp` | `false` | バックアップ完了後に SFTP サーバーへアップロード |
| `--webdav` | `false` | バックアップ完了後に WebDAV サーバーへアップロード |

バックアップ戦略に基づき、変更されたフォルダを自動的にバックアップします。

#### 定期バックアップ

```bash
# 60 分ごとにバックアップを実行
uv run python main.py watch --interval 60

# 2 時間ごとにバックアップ、直近 10 ファイルを保持
uv run python main.py watch --interval 120 --keep 10

# 定期バックアップ + 7z 暗号化
uv run python main.py --format 7z watch --interval 60 --password mysecret
```

**watch コマンドのオプション:**

| オプション | デフォルト値 | 説明 |
|-----------|-------------|------|
| `--interval MINUTES` | `60` | バックアップ間隔（分） |
| `--keep N` | `0` | 直近 N 件のバックアップファイルを保持 |
| `--password PASSWORD` | `""` | 暗号化パスワード（7z 形式のみ対応） |
| `--sftp` | `false` | バックアップ後に SFTP サーバーへアップロード |
| `--webdav` | `false` | バックアップ後に WebDAV サーバーへアップロード |

`Ctrl+C` で定期バックアップを停止できます。

#### バックアップの復元

```bash
uv run python main.py restore <backup_file> <target_dir>
```

パラメータ説明:
- **backup_file**: バックアップファイルのパス（.zip / .tar / .tar.gz / .tar.bz2 / .tar.xz / .tar.zst / .7z 対応）
- **target_dir**: 復元先ディレクトリ

例:
```bash
uv run python main.py restore F:/backup/my_folder.tar.gz F:/restored
uv run python main.py restore F:/backup/my_folder.7z F:/restored
uv run python main.py restore F:/backup/my_folder.tar.zst F:/restored
```

#### SFTP リモートバックアップ

```bash
# ============ クイックスタート（推奨） ============
# 1. SFTP を設定（SSH 秘密鍵を自動検出、手動指定不要）
sbackup sftp config --host 192.168.1.100 --user admin --remote-path /backups

# 2. 接続テスト
sbackup sftp test

# 3. バックアップ実行とアップロード
sbackup save --sftp

# ============ 認証方式 ============

# 方式 1: 秘密鍵の自動検出（推奨）
# ~/.ssh/id_ed25519 → id_rsa → id_ecdsa を自動的に試行
sbackup sftp config --host 192.168.1.100 --user admin

# 方式 2: パスワード認証
sbackup sftp config --host 192.168.1.100 --user admin --password secret

# 方式 3: 秘密鍵を指定
sbackup sftp config --host 192.168.1.100 --user admin --key-file ~/.ssh/id_rsa

# 方式 4: 秘密鍵 + パスフレーズ（対話的入力）
sbackup sftp config --host 192.168.1.100 --user admin --key-file ~/.ssh/id_rsa

# 方式 5: 秘密鍵 + パスフレーズ（コマンドラインで指定）
sbackup sftp config --host 192.168.1.100 --user admin --key-file ~/.ssh/id_rsa --key-passphrase mykeypass

# ============ 使用シーン ============

# シーン 1: 1 回限りのバックアップとアップロード
sbackup save --sftp

# シーン 2: 定期バックアップと自動アップロード（60 分ごと）
sbackup watch --interval 60 --sftp

# シーン 3: 形式を指定してバックアップ + アップロード
sbackup --format tar.gz save --sftp

# シーン 4: 暗号化バックアップ + アップロード
sbackup --format 7z save --password mysecret --sftp

# シーン 5: 直近 5 件を保持 + アップロード
sbackup save --keep 5 --sftp

# ============ 高度な使い方 ============

# インタラクティブ設定（すべてのパラメータを順に入力）
sbackup sftp config

# 非インタラクティブ設定（すべてのパラメータをコマンドラインで指定）
sbackup sftp config --host 192.168.1.100 --port 22 --user admin --password secret --remote-path /backups

# 接続テストと詳細ログ表示
sbackup --debug sftp test
```

**sftp サブコマンド:**

| サブコマンド | 説明 | 例 |
|-------------|------|-----|
| `sftp config` | SFTP 接続パラメータを設定（host/port/user/password/key_file/key_passphrase/remote_path） | `sbackup sftp config --host 192.168.1.100 --user admin` |
| `sftp test` | SFTP 接続のテスト | `sbackup sftp test` |

**認証方式:**

| 方式 | パラメータ | 説明 | 例 |
|------|-----------|------|-----|
| **自動検出** | 認証パラメータを指定しない | `~/.ssh/id_ed25519` → `id_rsa` → `id_ecdsa` を自動的に試行（推奨） | `sbackup sftp config --host ... --user ...` |
| パスワード認証 | `--password` | パスワードで直接ログイン | `sbackup sftp config --host ... --user ... --password secret` |
| 秘密鍵認証 | `--key-file` | 指定した SSH 秘密鍵でログイン | `sbackup sftp config --host ... --user ... --key-file ~/.ssh/id_rsa` |
| 秘密鍵+パスフレーズ | `--key-file` + `--key-passphrase` | 秘密鍵にパスフレーズがある場合に使用 | `sbackup sftp config --host ... --user ... --key-file ~/.ssh/id_rsa --key-passphrase mypass` |

対応する秘密鍵形式: RSA、Ed25519、ECDSA。

**クロスプラットフォームパス対応:**

| プラットフォーム | 秘密鍵パスの例 | 説明 |
|-----------------|----------------|------|
| Linux/macOS | `~/.ssh/id_rsa` | `/home/user/.ssh/id_rsa` に自動展開 |
| Windows | `~/.ssh/id_rsa` | `C:\Users\username\.ssh\id_rsa` に自動展開 |
| 全プラットフォーム | 絶対パス | 完全なパスを直接使用 |

SFTP 設定は `config.json` の `sftp` フィールドに保存されます。コマンドライン引数または対話的入力で設定できます。

#### バージョン情報の表示

```bash
sbackup version
```

## 設定ファイル

Sbackup は `config.json` ファイルによるカスタマイズ設定に対応しています。設定ファイルはプロジェクトルートディレクトリに配置してください。

### 設定項目の説明

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

| 設定項目 | 型 | デフォルト値 | 説明 |
|---------|-----|------------|------|
| `compression_format` | string | `"ZIP"` | アーカイブ形式。選択肢: `ZIP`, `TAR`, `TAR_GZ`, `TAR_BZ2`, `TAR_XZ`, `TAR_ZST`, `7Z` |
| `compression.algorithm` | string | `"ZIP_DEFLATED"` | ZIP 圧縮アルゴリズム。選択肢: `ZIP_DEFLATED`, `ZIP_STORED`, `ZIP_BZIP2`, `ZIP_LZMA` |
| `compression.level` | int | `6` | 圧縮レベル（0-9）。0 は無圧縮、9 が最高圧縮 |
| `skip_patterns` | list | `[".git", "__pycache__"]` | 無視するファイルまたはフォルダのパターン（fnmatch ワイルドカードとパスマッチに対応） |
| `data_file` | string | プラットフォームのデフォルトパス | バックアップ戦略データファイルの保存先 |
| `lang` | string | `"zh_CN"` | UI 言語。選択肢: `zh_CN`, `en_US`, `fr_FR`, `es_ES`, `ru_RU`, `de_DE`, `ja_JP`, `pt_BR`, `ko_KR` |
| `password` | string | `""` | 7z 暗号化パスワード |
| `sftp.host` | string | `""` | SFTP サーバーアドレス |
| `sftp.port` | int | `22` | SFTP ポート |
| `sftp.user` | string | `""` | SFTP ユーザー名 |
| `sftp.password` | string | `""` | SFTP パスワード（パスワード認証時に使用） |
| `sftp.key_file` | string | `""` | SSH 秘密鍵ファイルのパス（秘密鍵認証時に使用。推奨） |
| `sftp.key_passphrase` | string | `""` | 秘密鍵のパスフレーズ（必要な場合） |
| `sftp.remote_path` | string | `"/"` | リモートターゲットパス |
| `sftp.enabled` | bool | `false` | SFTP を有効にするか |

### 設定例

tar.bz2 形式で高圧縮率バックアップを行う場合:

```json
{
  "compression_format": "TAR_BZ2",
  "compression_level": 9,
  "skip_patterns": [".git", "__pycache__", "node_modules", "*.log"],
  "data_file": "backup_strategies.json",
  "lang": "zh_CN"
}
```

### アーカイブ形式の比較

| 形式 | 拡張子 | 圧縮率 | 速度 | 依存関係 | 適用シーン |
|------|--------|--------|------|---------|-----------|
| ZIP | .zip | 中 | 高速 | 標準ライブラリ | 汎用。Windows での互換性が最も高い |
| tar | .tar | なし | 超高速 | 標準ライブラリ | アーカイブのみ。外部圧縮と組み合わせ |
| tar.gz | .tar.gz | 中 | 高速 | 標準ライブラリ | Linux/macOS で一般的 |
| tar.bz2 | .tar.bz2 | 高 | 中 | 標準ライブラリ | 高圧縮率アーカイブ |
| tar.xz | .tar.xz | 最高 | 低速 | 標準ライブラリ | 長期保存。容量制限が厳しい場合 |
| tar.zst | .tar.zst | 中高 | 超高速 | zstandard | モダンな用途。速度と圧縮率のバランス |
| 7z | .7z | 極高 | 低速 | py7zr | 最高圧縮率。暗号化対応 |

#### WebDAV リモートバックアップ

WebDAV は HTTP ベースのファイルプロトコルで、Jianguoyun（坚果云）、NextCloud、Synology（群晖）などの主要クラウドストレージに対応しています。Python 標準ライブラリ `urllib` を使用するため、**追加の依存は不要**です。

```bash
# ============ クイックスタート ============
# 1. WebDAV を設定
sbackup webdav config --url https://dav.jianguoyun.com/dav/ --user user@example.com --password secret

# 2. 接続テスト
sbackup webdav test

# 3. バックアップ実行とアップロード
sbackup save --webdav

# ============ 使用シーン ============

# シーン 1: 1 回限りのバックアップとアップロード
sbackup save --webdav

# シーン 2: 定期バックアップと自動アップロード（60 分ごと）
sbackup watch --interval 60 --webdav

# シーン 3: リモートサブディレクトリを指定
sbackup webdav config --url https://dav.jianguoyun.com/dav/ --user user@example.com --remote-path /backups/sbackup

# シーン 4: SFTP と WebDAV へ同時にアップロード
sbackup save --sftp --webdav

# ============ 主要な WebDAV サービスのアドレス ============
# 坚果云: https://dav.jianguoyun.com/dav/
# NextCloud: https://your-server/remote.php/dav/files/username/
# 群晖: https://your-synology:5006/webdav/
```

**webdav サブコマンド:**

| サブコマンド | 説明 | 例 |
|-------------|------|-----|
| `webdav config` | WebDAV 接続パラメータを設定（url/user/password/remote_path） | `sbackup webdav config --url ... --user ...` |
| `webdav test` | WebDAV 接続のテスト | `sbackup webdav test` |

| パラメータ | デフォルト値 | 説明 |
|-----------|-------------|------|
| `--url URL` | `""` | WebDAV サーバーアドレス（例: `https://dav.jianguoyun.com/dav/`） |
| `--user USER` | `""` | WebDAV ユーザー名（通常はメールアドレス） |
| `--password PASS` | `""` | WebDAV パスワード（Jianguoyun では設定画面でアプリパスワードを生成） |
| `--remote-path PATH` | `/` | リモートターゲットパス |

## 仕組み

Sbackup は以下の方法でバックアップ機能を実現しています。

1. **バックアップ戦略の保存**: バックアップ戦略は JSON ファイルに保存されます。フォルダパス、最終更新日時、ターゲットパス、無視パターン、エントリ単位のアーカイブ形式を含みます。
2. **増分バックアップ**: フォルダの最終更新日時を比較し、変更されたフォルダのみをバックアップします。
3. **マルチ形式圧縮**: Python 組み込みの `zipfile` および `tarfile` モジュールに加え、`zstandard` と `py7zr` のサードパーティライブラリを使用し、7 種類のアーカイブ形式に対応しています。
4. **エントリ単位の形式**: 各バックアップ戦略は個別のアーカイブ形式を指定できます（`add --format`）。グローバルの `--format` 設定より優先されます。未指定の場合はグローバルデフォルトを使用します。
5. **バックアップクリーンアップ**: バックアップ成功後、ターゲットディレクトリをスキャンし、更新日時順にソートして、保持数を超える古いファイルを削除します。
6. **暗号化バックアップ**: 7z 形式は LZMA2 暗号化に対応。`--password` パラメータまたは `config.json` で設定します。
7. **定期バックアップ**: `watch` コマンドは指定された間隔でバックアップをループ実行します。`Ctrl+C` で安全に終了できます。
8. **バックアップ履歴**: 各バックアップ後にタイムスタンプ、ファイルサイズ、ファイル数を記録し、直近 100 件のレコードを保持します。
9. **SFTP リモートバックアップ**: paramiko ベースの SFTP クライアントを実装。接続テスト、リモートディレクトリの自動作成、プログレスバー付きファイルアップロードに対応。

### データファイルの形式

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

各バックアップ戦略エントリは 4 要素のリストです: `[mtime, target, skip_patterns, compression_format]`

| フィールド | 説明 |
|-----------|------|
| `mtime` | ソースフォルダの最終更新日時（増分バックアップの判定に使用） |
| `target` | バックアップファイルの保存先パス |
| `skip_patterns` | 無視するファイル/フォルダパターンのリスト |
| `compression_format` | エントリ単位のアーカイブ形式（空文字列はグローバルデフォルトを使用） |

## 開発ガイド

### テスト実行

```bash
uv run coverage run -m unittest discover -s tests -t . && uv run coverage report -m
```

### コード構造

```
sbackup/
├── main.py              # プログラムエントリポイント
├── sbackup/
│   ├── __init__.py      # コア関数をエクスポート
│   ├── __main__.py      # python -m sbackup エントリポイント
│   ├── cli.py           # CLI 引数解析とコマンドディスパッチ（30 以上のコマンド）
│   ├── config.py        # 設定読み込み、暗号化、Webhook/SMTP 設定
│   ├── auto_save.py     # BackupManager コアエンジン
│   ├── compression.py   # 7 形式の圧縮/解凍エンジン
│   ├── i18n.py          # 国際化（9 言語）
│   ├── sftp.py          # SFTP リモートバックアップクライアント（paramiko）
│   ├── webdav.py        # WebDAV リモートバックアップクライアント（依存なし）
│   ├── cloud_storage.py # S3 クラウドストレージクライアント（minio）
│   ├── multi_dest.py    # マルチターゲット並列バックアップ
│   ├── handlers.py      # SFTP/WebDAV/Remote/Schedule コマンドハンドラ
│   ├── hooks.py         # Pre/Post Hook 実行
│   ├── audit.py         # 監査ログシステム
│   ├── profile.py       # 設定 Profile 管理
│   ├── selective.py     # 選択的復元
│   ├── cross_search.py  # クロスアーカイブ検索
│   ├── integrity.py     # SHA256 チェックサム
│   ├── rotation.py      # バックアップローテーションポリシー
│   ├── dryrun.py        # Dry-run プレビュー
│   ├── diskcheck.py     # ディスク容量見積もり
│   ├── task_queue.py    # タスクキューシステム
│   ├── schema.py        # 設定バリデーター
│   ├── benchmark.py     # 圧縮ベンチマーク
│   ├── chunked_backup.py# ブロックレベル増分バックアップ
│   ├── dedup.py         # ファイルレベル SHA256 重複排除
│   ├── export.py        # メタデータエクスポート（CSV/JSON）
│   ├── monitor.py       # watchdog ファイルシステム監視
│   ├── lock.py          # クロスプラットフォームプロセスロック
│   ├── retry.py         # 指数バックオフリトライ
│   ├── ratelimiter.py   # トークンバケットレートリミッター
│   ├── keychain.py      # システムキーチェーン統合
│   ├── parity.py        # Reed-Solomon 誤り訂正符号
│   ├── completion.py    # Shell 自動補完
│   ├── wizard.py        # インタラクティブ設定ウィザード
│   └── locales/         # 9 言語の翻訳ファイル
└── tests/
    └── sbackup/
        └── test_*.py    # 30 個のテストファイル。すべてのモジュールをカバー
```

### 新機能の追加

1. `sbackup/` ディレクトリに新しいモジュールファイルを作成
2. `sbackup/__init__.py` で新機能の関数をインポート
3. `run()` 関数に新しいコマンドラインコマンドの処理ロジックを追加
4. `tests/` ディレクトリに対応するテストファイルを追加

## よくある質問

### Q: バックアップ戦略ファイルを誤って削除してしまいました。どうすればよいですか？

A: バックアップ戦略はデータファイルに保存されています。誤って削除した場合は、`add` コマンドを再実行してバックアップ戦略を再追加してください。

### Q: 追加済みのバックアップ戦略を変更するにはどうすればよいですか？

A: `sbackup edit` コマンドを使用してください: `sbackup edit <source> --dest <new_dest> --ignore <patterns> --format <fmt>`。

### Q: リモートバックアップは対応していますか？

A: 対応しています。3 種類のリモートバックアップ方式があります:
- **SFTP**: `sbackup sftp config` で設定、`sbackup save --sftp` でアップロード
- **WebDAV**: `sbackup webdav config` で設定、`sbackup save --webdav` でアップロード（Jianguoyun/NextCloud/Synology 対応）
- **S3 クラウドストレージ**: `config.json` の `cloud` フィールドで設定、`sbackup save --cloud` でアップロード
- 複数を同時に有効化可能: `sbackup save --sftp --webdav --cloud`

### Q: tar.gz と ZIP の違いは何ですか？

A: tar.gz は Linux/macOS で一般的に使用され、圧縮率がやや高いです。ZIP は Windows で汎用的で互換性が最も高いです。tar.bz2 と tar.xz はさらに高い圧縮率を持ちますが速度は遅くなります。tar.zst はモダンなアルゴリズムで、高速かつ良好な圧縮率を備えています。7z は最高の圧縮率を持ち、暗号化にも対応しています。

### Q: バックアップを暗号化するにはどうすればよいですか？

A: 7z 形式を使用しパスワードを設定してください: `uv run python main.py --format 7z save --password yourpassword`。パスワードは `config.json` の `password` フィールドに記載することもできます。

### Q: 古いバックアップを自動的にクリーンアップするにはどうすればよいですか？

A: `--keep` パラメータを使用してください: `uv run python main.py save --keep 5` で直近 5 件のバックアップファイルのみを保持します。定期バックアップ時も同様に対応しています: `uv run python main.py watch --interval 60 --keep 10`。

### Q: 定期バックアップを設定するにはどうすればよいですか？

A: `watch` コマンドを使用してください: `uv run python main.py watch --interval 60` で 60 分ごとにバックアップを実行します。`Ctrl+C` で停止できます。

### Q: パスワードの保存は安全ですか？

A: `config.json` に保存される SFTP パスワードと 7z 暗号化パスワードは**プレーンテキスト**で保存されます。`config.json` ファイルへのアクセス権限を信頼できるユーザーのみに制限してください（例: `chmod 600 config.json`）。パスワードを含む `config.json` をバージョン管理システムにコミ밋しないでください。

## コントリビューションガイド

Issue と Pull Request の提出を歓迎します。

1. 本リポジトリを Fork
2. 機能ブランチを作成 (`git checkout -b feature/AmazingFeature`)
3. 変更をコミット (`git commit -m 'Add some AmazingFeature'`)
4. ブランチにプッシュ (`git push origin feature/AmazingFeature`)
5. Pull Request を提出

### コードスタイル

本プロジェクトは PEP 8 および Google Python Style Guide に準拠しています。以下の点を確認してください:
- 型アノテーションを使用すること
- Google スタイルの docstrings に従うこと
- すべての単体テストに合格すること

## ライセンス

本プロジェクトは GNU GPL v3.0 ライセンスの下で提供されています。詳細は [LICENSE](../../LICENSE) ファイルを参照してください。

## 著者

**xiatianxuan** (CodeSeed)

- [Gitee](https://gitee.com/xiatianxuan)
- [個人ページ](https://xnors-codeseed.pages.dev/)

## 謝辞

- [Xnors Studio](https://xnors.github.io/)

## お問い合わせ

ご質問やご提案がございましたら、以下のメールアドレスまでお問い合わせください: xiatianxuan2025@163.com

---

*最終更新: 2026年6月19日*
