# Sbackup

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-GPL--3.0-green)](../../LICENSE)
[![PyPI](https://img.shields.io/pypi/v/sbackup-cli?color=blue)](https://pypi.org/project/sbackup-cli/)
[![Tests](https://img.shields.io/badge/tests-940%20passed-brightgreen)](../../.github/workflows/ci.yml)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)]()

> 가볍고 효율적인 폴더 백업 도구로, CLI를 통해 백업 전략을 손쉽게 관리할 수 있습니다.

[English](../../README.md) | [Deutsch](README_de.md) | [Espanol](README_es.md) | [Francais](README_fr.md) | [Portugues](README_pt.md) | [Pycckuu](README_ru.md) | [日本語](README_ja.md) | [한국어](README_ko.md) | [中文](README_zh.md)

- [소개](#소개)
- [주요 기능](#주요-기능)
- [빠른 시작](#빠른-시작)
  - [설치](#설치)
  - [사용 방법](#사용-방법)
- [설정 파일](#설정-파일)
  - [설정 예시](#설정-예시)
- [SFTP 원격 백업](#sftp-원격-백업)
- [WebDAV 원격 백업](#webdav-원격-백업)
- [구현 원리](#구현-원리)
- [개발 가이드](#개발-가이드)
  - [테스트 실행](#테스트-실행)
  - [코드 구조](#코드-구조)
- [자주 묻는 질문](#자주-묻는-질문)
- [기여 가이드](#기여-가이드)
- [라이선스](#라이선스)
- [저자](#저자)

---

## 소개

Sbackup는 CLI를 통해 백업 전략을 추가, 삭제, 조회할 수 있는 가벼운 폴더 백업 도구입니다. 폴더의 최종 수정 시간을 기준으로 백업이 필요한지 판단하여 데이터를 항상 최신 상태로 유지합니다.

## 주요 기능

- **증분 백업**: 변경된 폴더만 백업하여 시간과 저장 공간을 절약
- **다중 포맷 지원**: ZIP, tar, tar.gz, tar.bz2, tar.xz, tar.zst, 7z 등 7가지 압축 포맷을 전략별 및 전역 수준에서 독립 지정 가능
- **SFTP 원격 백업**: paramiko 기반, 비밀번호/SSH 개인키 인증 및 기본 개인키 자동 감지 지원
- **WebDAV 원격 백업**: 표준 라이브러리 urllib 기반, 추가 의존성 없이 견과云/NextCloud/시놀로지 지원
- **S3 클라우드 저장소**: minio 기반, 모든 S3 호환 저장소(AWS/MinIO/Alibaba Cloud OSS 등) 지원
- **다중 대상 병렬 백업**: 로컬 + 여러 원격 대상에 동시에 백업, 상호 간섭 없음
- **백업 복원**: 백업 파일에서 지정 디렉토리로 압축 해제 및 복원, 선택적 복원 지원
- **백업 정리**: 오래된 백업 자동 삭제, 수량/시간/일별 보존 전략 지원
- **암호화 백업**: 7z 포맷 비밀번호 암호화 + 전체 포맷 PBKDF2 암호화
- **예약 백업**: 간격 기반 자동 실행, 실시간 파일 감시(watchdog) 지원
- **백업 이력**: 각 백업의 시간, 크기, SHA256 체크섬 기록으로 추적 용이
- **감사 로그**: 모든 백업/복원 작업의 감사 이벤트 기록
- **Pre/Post Hook**: 백업 전후 사용자 정의 명령 실행
- **설정 Profile**: 다중 설정 프로필의 저장, 전환, 가져오기/내보내기 지원
- **크로스 아카이브 검색**: 여러 백업 파일에서 일치하는 파일명 검색
- **데이터 무결성**: SHA256 체크섬 생성 및 검증, Reed-Solomon 오류 정정 코드
- **설정 검증**: 설정 매개변수 유효성 자동 검증, 변조 감지
- **작업 큐**: 백업 작업 큐 관리, 추가/실행/취소 지원
- **압축 벤치마크**: 다양한 포맷/레벨의 압축 성능 비교
- **디스크 공간 예측**: 파일 유형별 백업 크기 추정, 대상 공간 확인
- **국제화**: 한국어, 영어, 중국어, 프랑스어, 스페인어, 러시아어, 독일어, 일본어, 포르투갈어 9개 언어 지원
- **Shell 자동 완성**: bash/zsh/fish/powershell 자동 완성 지원
- **가볍고 효율적**: 작은 용량, 빠른 시작 속도, 낮은 리소스 사용량
- **크로스 플랫폼 지원**: Windows, macOS, Linux 지원

## 빠른 시작

### 설치

#### pip으로 설치

```bash
pip install sbackup-cli
```

설치 후 `sbackup` 명령을 사용합니다 (PyPI 패키지명: `sbackup-cli`, CLI 명령: `sbackup`).

#### 소스에서 설치

```bash
git clone https://github.com/xiatianxuan/sbackup.git
cd sbackup
uv sync
```

### 사용 방법

#### 기본 구문

```bash
uv run python main.py <command> [options]
```

#### 사용 가능한 명령

| 명령 | 설명 |
|------|------|
| `add` | 백업 전략 추가 |
| `rm` / `remove` | 백업 전략 삭제 |
| `edit` | 기존 백업 전략 편집 |
| `all` | 모든 백업 전략 조회 |
| `save` | 백업 실행 |
| `watch` | 예약 백업 실행 |
| `restore` | 백업 파일에서 복원 |
| `info` | 백업 파일 상세 정보 조회 |
| `diff` | 원본 디렉토리와 백업 간 차이 비교 |
| `verify` | 백업 파일 무결성 검증 |
| `search` | 백업 내 파일 검색 |
| `xsearch` | 여러 백업 아카이브에서 검색 |
| `versions` | 백업 버전 이력 조회 |
| `sftp` | SFTP 원격 백업 관리 |
| `webdav` | WebDAV 원격 백업 관리 |
| `remote` | 원격 파일 관리 (list/rm) |
| `task` | 백업 작업 큐 관리 |
| `audit` | 감사 로그 조회 |
| `hooks` | Pre/Post Hook 수동 실행 |
| `profile` | 설정 Profile 관리 |
| `rotate` | 백업 로테이션 정리 |
| `clean` | 오래된 백업 정리 |
| `diskcheck` | 디스크 공간 예측 |
| `benchmark` | 압축 포맷 벤치마크 |
| `integrity` | 백업 디렉토리 무결성 검증 |
| `dry-run` | 백업 파일 선택 미리보기 |
| `export` / `import` | 백업 전략 내보내기/가져오기 |
| `ignore` | .sbackupignore 파일 생성 |
| `schedule` | 예약 스케줄 설정 내보내기 |
| `webhook` | Webhook 프리셋 설정 |
| `config` | 암호화/검증 설정 |
| `report` | 백업 보고서 생성 |
| `completion` | Shell 자동 완성 스크립트 생성 |
| `wizard` | 대화형 설정 마법사 |
| `status` | 백업 상태 대시보드 |
| `version` | 버전 정보 조회 |
| `help` | 도움말 조회 |

#### 전역 매개변수

| 매개변수 | 설명 |
|----------|------|
| `--lang zh_CN` / `en_US` / `fr_FR` / `es_ES` / `ru_RU` / `de_DE` / `ja_JP` / `pt_BR` / `ko_KR` | 인터페이스 언어 설정 (config.json에 영구 저장) |
| `--format zip` / `tar` / `tar.gz` / `tar.bz2` / `tar.xz` / `tar.zst` / `7z` | 압축 포맷 설정 (config.json에 영구 저장) |
| `--debug` | 디버그 로그 활성화 |

#### 백업 전략 추가

```bash
uv run python main.py add <source> <dest> [-i ignore_patterns]
```

매개변수 설명:
- **source**: 백업할 원본 폴더 경로
- **dest**: 백업 파일 저장 대상 경로
- **-i, --ignore**: 무시할 파일 또는 폴더 이름, 쉼표로 구분 (기본값: `.git,__pycache__`)
- **--format**: 항목별 압축 포맷 (해당 백업 전략에만 적용, 미지정 시 전역 기본값 사용): `zip` / `tar` / `tar.gz` / `tar.bz2` / `tar.xz` / `tar.zst` / `7z`

예시:
```bash
# 전역 기본 포맷으로 전략 추가
uv run python main.py add F:/my_folder F:/backup -i node_modules,.git

# 해당 전략에 tar.gz 포맷 지정 (이 폴더 백업 시 항상 tar.gz 사용)
uv run python main.py add F:/my_folder F:/backup --format tar.gz

# 7z 포맷 지정 (해당 폴더만)
uv run python main.py add F:/my_folder F:/backup --format 7z
```

#### 백업 전략 삭제

```bash
uv run python main.py rm <path>
```

매개변수 설명:
- **path**: 백업 전략을 삭제할 원본 폴더 경로

예시:
```bash
uv run python main.py rm F:/my_folder
```

#### 모든 백업 전략 조회

```bash
uv run python main.py all
```

현재 설정된 모든 백업 전략을 표시합니다.

#### 백업 실행

```bash
# 기본 포맷(ZIP) 사용
uv run python main.py save

# tar.gz 포맷 사용
uv run python main.py --format tar.gz save

# 최근 5개 백업 파일 유지, 오래된 파일 자동 정리
uv run python main.py save --keep 5

# 7z 포맷으로 암호화
uv run python main.py --format 7z save --password mysecret

# 영어 인터페이스 + tar.xz 포맷
uv run python main.py --lang en_US --format tar.xz save
```

**save 명령 매개변수:**

| 매개변수 | 기본값 | 설명 |
|----------|--------|------|
| `--keep N` | `0` | 최근 N개 백업 파일 유지, 0이면 정리 안 함 |
| `--password PASSWORD` | `""` | 암호화 비밀번호 (7z 포맷만 지원) |
| `--sftp` | `false` | 백업 완료 후 SFTP 서버에 업로드 |
| `--webdav` | `false` | 백업 완료 후 WebDAV 서버에 업로드 |

백업 전략에 따라 변경된 폴더를 자동 백업합니다.

#### 예약 백업

```bash
# 60분마다 백업 실행
uv run python main.py watch --interval 60

# 2시간마다 백업, 최근 10개 파일 유지
uv run python main.py watch --interval 120 --keep 10

# 예약 백업 + 7z 암호화
uv run python main.py --format 7z watch --interval 60 --password mysecret
```

**watch 명령 매개변수:**

| 매개변수 | 기본값 | 설명 |
|----------|--------|------|
| `--interval MINUTES` | `60` | 백업 간격 (분) |
| `--keep N` | `0` | 최근 N개 백업 파일 유지 |
| `--password PASSWORD` | `""` | 암호화 비밀번호 (7z 포맷만 지원) |
| `--sftp` | `false` | 매 백업 후 SFTP 서버에 업로드 |
| `--webdav` | `false` | 매 백업 후 WebDAV 서버에 업로드 |

`Ctrl+C`를 눌러 예약 백업을 중지합니다.

#### 백업 복원

```bash
uv run python main.py restore <backup_file> <target_dir>
```

매개변수 설명:
- **backup_file**: 백업 파일 경로 (.zip / .tar / .tar.gz / .tar.bz2 / .tar.xz / .tar.zst / .7z 지원)
- **target_dir**: 복원 대상 디렉토리

예시:
```bash
uv run python main.py restore F:/backup/my_folder.tar.gz F:/restored
uv run python main.py restore F:/backup/my_folder.7z F:/restored
uv run python main.py restore F:/backup/my_folder.tar.zst F:/restored
```

#### SFTP 원격 백업

```bash
# ============ 빠른 시작 (권장) ============
# 1. SFTP 설정 (SSH 개인키 자동 감지, 수동 지정 불필요)
sbackup sftp config --host 192.168.1.100 --user admin --remote-path /backups

# 2. 연결 테스트
sbackup sftp test

# 3. 백업 실행 및 업로드
sbackup save --sftp

# ============ 인증 방식 ============

# 방식 1: 개인키 자동 감지 (권장)
# 시스템이 자동으로 ~/.ssh/id_ed25519 -> id_rsa -> id_ecdsa 순서로 시도
sbackup sftp config --host 192.168.1.100 --user admin

# 방식 2: 비밀번호 인증
sbackup sftp config --host 192.168.1.100 --user admin --password secret

# 방식 3: 개인키 지정
sbackup sftp config --host 192.168.1.100 --user admin --key-file ~/.ssh/id_rsa

# 방식 4: 개인키 + 패스프레이즈 (대화형 입력)
sbackup sftp config --host 192.168.1.100 --user admin --key-file ~/.ssh/id_rsa

# 방식 5: 개인키 + 패스프레이즈 (명령줄 지정)
sbackup sftp config --host 192.168.1.100 --user admin --key-file ~/.ssh/id_rsa --key-passphrase mykeypass

# ============ 사용 시나리오 ============

# 시나리오 1: 일회성 백업 및 업로드
sbackup save --sftp

# 시나리오 2: 예약 백업 및 자동 업로드 (60분마다)
sbackup watch --interval 60 --sftp

# 시나리오 3: 특정 포맷 백업 + 업로드
sbackup --format tar.gz save --sftp

# 시나리오 4: 암호화 백업 + 업로드
sbackup --format 7z save --password mysecret --sftp

# 시나리오 5: 최근 5개 백업 유지 + 업로드
sbackup save --keep 5 --sftp

# ============ 고급 사용법 ============

# 대화형 설정 (단계별로 모든 매개변수 입력)
sbackup sftp config

# 비대화형 설정 (모든 매개변수를 명령줄에서 지정)
sbackup sftp config --host 192.168.1.100 --port 22 --user admin --password secret --remote-path /backups

# 연결 테스트 및 상세 로그 확인
sbackup --debug sftp test
```

**sftp 하위 명령:**

| 하위 명령 | 설명 | 예시 |
|-----------|------|------|
| `sftp config` | SFTP 연결 매개변수 설정 (host/port/user/password/key_file/key_passphrase/remote_path) | `sbackup sftp config --host 192.168.1.100 --user admin` |
| `sftp test` | SFTP 연결 가능 여부 테스트 | `sbackup sftp test` |

**인증 방식:**

| 방식 | 매개변수 | 설명 | 예시 |
|------|----------|------|------|
| **자동 감지** | 인증 매개변수 미지정 | `~/.ssh/id_ed25519` -> `id_rsa` -> `id_ecdsa` 순서로 자동 시도 (권장) | `sbackup sftp config --host ... --user ...` |
| 비밀번호 인증 | `--password` | 비밀번호로 직접 로그인 | `sbackup sftp config --host ... --user ... --password secret` |
| 개인키 인증 | `--key-file` | 지정된 SSH 개인키로 로그인 | `sbackup sftp config --host ... --user ... --key-file ~/.ssh/id_rsa` |
| 개인키+패스프레이즈 | `--key-file` + `--key-passphrase` | 개인키에 패스프레이즈가 있는 경우 사용 | `sbackup sftp config --host ... --user ... --key-file ~/.ssh/id_rsa --key-passphrase mypass` |

지원되는 개인키 형식: RSA, Ed25519, ECDSA.

**크로스 플랫폼 경로 지원:**

| 플랫폼 | 개인키 경로 예시 | 설명 |
|--------|-----------------|------|
| Linux/macOS | `~/.ssh/id_rsa` | `/home/user/.ssh/id_rsa`로 자동 확장 |
| Windows | `~/.ssh/id_rsa` | `C:\Users\username\.ssh\id_rsa`로 자동 확장 |
| 전 플랫폼 | 절대 경로 | 전체 경로를 직접 사용 |

SFTP 설정은 `config.json`의 `sftp` 필드에 저장되며, 명령줄 매개변수 또는 대화형 입력으로 설정할 수 있습니다.

#### 버전 정보 조회

```bash
sbackup version
```

## 설정 파일

Sbackup는 `config.json` 파일을 통해 사용자 정의 설정을 지원합니다. 설정 파일은 프로젝트 루트 디렉토리에 배치해야 합니다.

### 설정 항목 설명

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

| 설정 항목 | 타입 | 기본값 | 설명 |
|-----------|------|--------|------|
| `compression_format` | string | `"ZIP"` | 압축 포맷, 가능한 값: `ZIP`, `TAR`, `TAR_GZ`, `TAR_BZ2`, `TAR_XZ`, `TAR_ZST`, `7Z` |
| `compression.algorithm` | string | `"ZIP_DEFLATED"` | ZIP 압축 알고리즘, 가능한 값: `ZIP_DEFLATED`, `ZIP_STORED`, `ZIP_BZIP2`, `ZIP_LZMA` |
| `compression.level` | int | `6` | 압축 레벨, 범위 0-9 (0: 압축 없음, 9: 최대 압축) |
| `skip_patterns` | list | `[".git", "__pycache__"]` | 무시할 파일 또는 폴더 패턴 (fnmatch 와일드카드 및 경로 매칭 지원) |
| `data_file` | string | 플랫폼 기본 경로 | 백업 전략 데이터 파일 저장 경로 |
| `lang` | string | `"zh_CN"` | 인터페이스 언어, 가능한 값: `zh_CN`, `en_US`, `fr_FR`, `es_ES`, `ru_RU`, `de_DE`, `ja_JP`, `pt_BR`, `ko_KR` |
| `password` | string | `""` | 7z 암호화 비밀번호 |
| `sftp.host` | string | `""` | SFTP 서버 주소 |
| `sftp.port` | int | `22` | SFTP 포트 |
| `sftp.user` | string | `""` | SFTP 사용자 이름 |
| `sftp.password` | string | `""` | SFTP 비밀번호 (비밀번호 인증 시 사용) |
| `sftp.key_file` | string | `""` | SSH 개인키 파일 경로 (개인키 인증 시 사용, 권장) |
| `sftp.key_passphrase` | string | `""` | 개인키 패스프레이즈 (있는 경우) |
| `sftp.remote_path` | string | `"/"` | 원격 대상 경로 |
| `sftp.enabled` | bool | `false` | SFTP 활성화 여부 |

### 설정 예시

tar.bz2 포맷으로 고압축률 백업:

```json
{
  "compression_format": "TAR_BZ2",
  "compression_level": 9,
  "skip_patterns": [".git", "__pycache__", "node_modules", "*.log"],
  "data_file": "backup_strategies.json",
  "lang": "zh_CN"
}
```

### 압축 포맷 비교

| 포맷 | 확장자 | 압축률 | 속도 | 의존성 | 적합한 시나리오 |
|------|--------|--------|------|--------|----------------|
| ZIP | .zip | 중간 | 빠름 | 표준 라이브러리 | 범용, Windows 호환성 최고 |
| tar | .tar | 없음 | 매우 빠름 | 표준 라이브러리 | 순수 아카이브, 외부 압축과 결합 |
| tar.gz | .tar.gz | 중간 | 빠름 | 표준 라이브러리 | Linux/macOS 범용 |
| tar.bz2 | .tar.bz2 | 높음 | 중간 | 표준 라이브러리 | 고압축률 아카이브 |
| tar.xz | .tar.xz | 최고 | 느림 | 표준 라이브러리 | 장기 아카이브, 공간 민감 |
| tar.zst | .tar.zst | 중상 | 매우 빠름 | zstandard | 현대 시나리오, 속도와 압축률 균형 |
| 7z | .7z | 매우 높음 | 느림 | py7zr | 최대 압축률, 암호화 지원 |

#### WebDAV 원격 백업

WebDAV는 HTTP 기반 파일 프로토콜로, 견과云, NextCloud, 시놀로지 등 주요 클라우드 스토리지를 지원합니다. Python 표준 라이브러리 `urllib`을 사용하여 **추가 의존성이 없습니다**.

```bash
# ============ 빠른 시작 ============
# 1. WebDAV 설정
sbackup webdav config --url https://dav.jianguoyun.com/dav/ --user user@example.com --password secret

# 2. 연결 테스트
sbackup webdav test

# 3. 백업 실행 및 업로드
sbackup save --webdav

# ============ 사용 시나리오 ============

# 시나리오 1: 일회성 백업 및 업로드
sbackup save --webdav

# 시나리오 2: 예약 백업 및 자동 업로드 (60분마다)
sbackup watch --interval 60 --webdav

# 시나리오 3: 원격 하위 디렉토리 지정
sbackup webdav config --url https://dav.jianguoyun.com/dav/ --user user@example.com --remote-path /backups/sbackup

# 시나리오 4: SFTP와 WebDAV에 동시 업로드
sbackup save --sftp --webdav

# ============ 일반 WebDAV 서비스 주소 ============
# 견과云: https://dav.jianguoyun.com/dav/
# NextCloud: https://your-server/remote.php/dav/files/username/
# 시놀로지: https://your-synology:5006/webdav/
```

**webdav 하위 명령:**

| 하위 명령 | 설명 | 예시 |
|-----------|------|------|
| `webdav config` | WebDAV 연결 매개변수 설정 (url/user/password/remote_path) | `sbackup webdav config --url ... --user ...` |
| `webdav test` | WebDAV 연결 가능 여부 테스트 | `sbackup webdav test` |

| 매개변수 | 기본값 | 설명 |
|----------|--------|------|
| `--url URL` | `""` | WebDAV 서버 주소 (예: `https://dav.jianguoyun.com/dav/`) |
| `--user USER` | `""` | WebDAV 사용자 이름 (일반적으로 이메일) |
| `--password PASS` | `""` | WebDAV 비밀번호 (견과云은 설정에서 앱 비밀번호를 생성해야 함) |
| `--remote-path PATH` | `/` | 원격 대상 경로 |

## 구현 원리

Sbackup는 다음과 같은 방식으로 백업 기능을 구현합니다:

1. **백업 전략 저장**: 백업 전략은 JSON 파일에 저장되며, 폴더 경로, 최종 수정 시간, 대상 경로, 무시 패턴, 항목별 압축 포맷을 포함합니다.
2. **증분 백업**: 폴더의 최종 수정 시간을 비교하여 변경된 폴더만 백업합니다.
3. **다중 포맷 압축**: Python 내장 `zipfile` 및 `tarfile` 모듈과 `zstandard`, `py7zr` 서드파티 라이브러리를 사용하여 7가지 압축 포맷을 지원합니다.
4. **항목별 포맷**: 각 백업 전략은 독립적인 압축 포맷을 지정할 수 있습니다 (`add --format`). 전역 `--format` 설정보다 우선하며, 미지정 시 전역 기본값을 사용합니다.
5. **백업 정리**: 백업 성공 후 대상 디렉토리를 자동 스캔하여 수정 시간순으로 정렬하고, 보존 수량을 초과하는 오래된 파일을 삭제합니다.
6. **암호화 백업**: 7z 포맷은 LZMA2 암호화를 지원하며, `--password` 매개변수 또는 `config.json` 설정을 통해 구성합니다.
7. **예약 백업**: `watch` 명령은 지정된 간격으로 루프에서 백업을 실행하며, `Ctrl+C`로 안전하게 종료합니다.
8. **백업 이력**: 매 백업 후 타임스탬프, 파일 크기, 파일 수를 기록하며, 최근 100개 기록을 유지합니다.
9. **SFTP 원격 백업**: paramiko 라이브러리 기반 SFTP 클라이언트를 구현하며, 연결 테스트, 원격 디렉토리 자동 생성, 진행 표시줄이 포함된 파일 업로드를 지원합니다.

### 데이터 파일 형식

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

각 백업 전략 항목은 4요소 리스트입니다: `[mtime, target, skip_patterns, compression_format]`

| 필드 | 설명 |
|------|------|
| `mtime` | 원본 폴더의 최종 수정 시간 (증분 백업 판단에 사용) |
| `target` | 백업 파일 저장 대상 경로 |
| `skip_patterns` | 무시할 파일/폴더 패턴 목록 |
| `compression_format` | 항목별 압축 포맷 (빈 문자열이면 전역 기본값 사용) |

## 개발 가이드

### 테스트 실행

```bash
uv run coverage run -m unittest discover -s tests -t . && uv run coverage report -m
```

### 코드 구조

```
sbackup/
├── main.py              # 프로그램 진입점
├── sbackup/
│   ├── __init__.py      # 핵심 함수 내보내기
│   ├── __main__.py      # python -m sbackup 진입점
│   ├── cli.py           # CLI 매개변수 파싱 및 명령 분배 (30+ 명령)
│   ├── config.py        # 설정 로드, 암호화, Webhook/SMTP 설정
│   ├── auto_save.py     # BackupManager 핵심 엔진
│   ├── compression.py   # 7가지 포맷 압축/해제 엔진
│   ├── i18n.py          # 국제화 (9개 언어)
│   ├── sftp.py          # SFTP 원격 백업 클라이언트 (paramiko)
│   ├── webdav.py        # WebDAV 원격 백업 클라이언트 (무의존성)
│   ├── cloud_storage.py # S3 클라우드 저장소 클라이언트 (minio)
│   ├── multi_dest.py    # 다중 대상 병렬 백업
│   ├── handlers.py      # SFTP/WebDAV/Remote/Schedule 명령 처리
│   ├── hooks.py         # Pre/Post Hook 실행
│   ├── audit.py         # 감사 로그 시스템
│   ├── profile.py       # 설정 Profile 관리
│   ├── selective.py     # 선택적 복원
│   ├── cross_search.py  # 크로스 아카이브 검색
│   ├── integrity.py     # SHA256 체크섬
│   ├── rotation.py      # 백업 로테이션 전략
│   ├── dryrun.py        # Dry-run 미리보기
│   ├── diskcheck.py     # 디스크 공간 예측
│   ├── task_queue.py    # 작업 큐 시스템
│   ├── schema.py        # 설정 검증기
│   ├── benchmark.py     # 압축 벤치마크
│   ├── chunked_backup.py# 블록 단위 증분 백업
│   ├── dedup.py         # 파일 단위 SHA256 중복 제거
│   ├── export.py        # 메타데이터 내보내기 (CSV/JSON)
│   ├── monitor.py       # watchdog 파일 시스템 감시
│   ├── lock.py          # 크로스 플랫폼 프로세스 잠금
│   ├── retry.py         # 지수 백오프 재시도
│   ├── ratelimiter.py   # 토큰 버킷 속도 제한기
│   ├── keychain.py      # 시스템 키체인 통합
│   ├── parity.py        # Reed-Solomon 오류 정정 코드
│   ├── completion.py    # Shell 자동 완성
│   ├── wizard.py        # 대화형 설정 마법사
│   └── locales/         # 9개 언어 번역 파일
└── tests/
    └── sbackup/
        └── test_*.py    # 30개 테스트 파일, 모든 모듈 커버
```

### 새 기능 추가

1. `sbackup/` 디렉토리에 새 모듈 파일을 생성합니다
2. `sbackup/__init__.py`에 새 기능의 함수를 임포트합니다
3. `run()` 함수에 새로운 CLI 명령 처리 로직을 추가합니다
4. `tests/` 디렉토리에 대응하는 테스트 파일을 추가합니다

## 자주 묻는 질문

### Q: 백업 전략 파일을 실수로 삭제하면 어떻게 하나요?

A: 백업 전략은 데이터 파일에 저장됩니다. 실수로 삭제한 경우 `add` 명령을 다시 실행하여 백업 전략을 다시 추가할 수 있습니다.

### Q: 이미 추가한 백업 전략을 어떻게 수정하나요?

A: `sbackup edit` 명령을 사용합니다: `sbackup edit <source> --dest <new_dest> --ignore <patterns> --format <fmt>`.

### Q: 원격 백업을 지원하나요?

A: 지원합니다! 세 가지 원격 백업 방식을 제공합니다:
- **SFTP**: `sbackup sftp config`로 설정, `sbackup save --sftp`로 업로드
- **WebDAV**: `sbackup webdav config`로 설정, `sbackup save --webdav`로 업로드 (견과云/NextCloud/시놀로지 지원)
- **S3 클라우드 저장소**: `config.json`에서 `cloud` 필드 설정, `sbackup save --cloud`로 업로드
- 동시에 여러 방식 사용 가능: `sbackup save --sftp --webdav --cloud`

### Q: tar.gz와 ZIP의 차이는 무엇인가요?

A: tar.gz는 Linux/macOS에서 더 일반적이며 압축률이 약간 높습니다. ZIP은 Windows에서 더 범용적이며 호환성이 가장 좋습니다. tar.bz2와 tar.xz는 더 높은 압축률을 제공하지만 속도가 느립니다. tar.zst는 현대 알고리즘으로 속도가 매우 빠르면서 압축률도 양호합니다. 7z는 압축률이 가장 높고 암호화를 지원합니다.

### Q: 백업을 어떻게 암호화하나요?

A: 7z 포맷을 사용하고 비밀번호를 설정합니다: `uv run python main.py --format 7z save --password yourpassword`. 비밀번호를 `config.json`의 `password` 필드에 작성할 수도 있습니다.

### Q: 오래된 백업을 어떻게 자동 정리하나요?

A: `--keep` 매개변수를 사용합니다: `uv run python main.py save --keep 5`로 최근 5개 백업 파일만 유지합니다. 예약 백업 시에도同样 지원합니다: `uv run python main.py watch --interval 60 --keep 10`.

### Q: 예약 백업을 어떻게 설정하나요?

A: `watch` 명령을 사용합니다: `uv run python main.py watch --interval 60`으로 60분마다 백업합니다. `Ctrl+C`로 중지합니다.

### Q: 비밀번호 저장이 안전한가요?

A: `config.json`에 저장된 SFTP 비밀번호와 7z 암호화 비밀번호는 **평문**으로 저장됩니다. `config.json` 파일의 접근 권한을 신뢰할 수 있는 사용자로만 제한하세요 (예: `chmod 600 config.json`). 비밀번호가 포함된 `config.json`을 버전控制系统에 커밋하지 마세요.

## 기여 가이드

Issue와 Pull Request를 환영합니다!

1. 이 저장소를 Fork합니다
2. 기능 브랜치를 생성합니다 (`git checkout -b feature/AmazingFeature`)
3. 변경사항을 커밋합니다 (`git commit -m 'Add some AmazingFeature'`)
4. 브랜치에 푸시합니다 (`git push origin feature/AmazingFeature`)
5. Pull Request를 제출합니다

### 코드 스타일

이 프로젝트는 PEP 8 및 Google Python Style Guide를 따릅니다. 다음을 준수하세요:
- 타입 어노테이션 사용
- Google 스타일 docstrings 준수
- 모든 단위 테스트 통과

## 라이선스

이 프로젝트는 GNU GPL v3.0 라이선스를 따릅니다. 자세한 내용은 [LICENSE](../../LICENSE) 파일을 참조하세요.

## 저자

**xiatianxuan** (CodeSeed)

- [Gitee](https://gitee.com/xiatianxuan)
- [홈페이지](https://xnors-codeseed.pages.dev/)

## 특별 감사

- [Xnors Studio](https://xnors.github.io/)

## 문의

질문이나 제안이 있으시면 이메일로 연락해 주세요: xiatianxuan2025@163.com

---

*최종 업데이트: 2026년 6월 19일*
