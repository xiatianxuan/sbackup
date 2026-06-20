"""
单元测试 for sbackup.schema 模块（配置校验/校验和）
"""

import os
import tempfile
import shutil
import unittest

from sbackup.config import Config
from sbackup.schema import (
    ConfigValidator,
    ValidationError,
    get_config_checksum,
    validate_config_file,
)


class TestValidationError(unittest.TestCase):
    """测试 ValidationError 数据类"""

    def test_default_severity(self):
        err = ValidationError(field="test", message="msg")
        self.assertEqual(err.severity, "error")

    def test_custom_severity(self):
        err = ValidationError(field="test", message="msg", severity="warning")
        self.assertEqual(err.severity, "warning")


class TestCompressionValidation(unittest.TestCase):
    """测试压缩格式校验"""

    def test_valid_format_zip(self):
        config = Config(compression_format="ZIP")
        is_valid, errors, warnings = validate_config_file(config)
        self.assertTrue(is_valid)
        self.assertFalse(any(e.field == "compression_format" for e in errors))

    def test_valid_format_tar(self):
        config = Config(compression_format="TAR")
        is_valid, errors, _ = validate_config_file(config)
        self.assertTrue(is_valid)
        self.assertFalse(any(e.field == "compression_format" for e in errors))

    def test_valid_all_formats(self):
        for fmt in ["ZIP", "TAR", "GZ", "BZ2", "XZ", "ZST", "7Z"]:
            config = Config(compression_format=fmt)
            is_valid, errors, _ = validate_config_file(config)
            self.assertTrue(is_valid, f"Format {fmt} should be valid")
            self.assertFalse(any(e.field == "compression_format" for e in errors))

    def test_invalid_format(self):
        config = Config(compression_format="INVALID")
        is_valid, errors, _ = validate_config_file(config)
        self.assertFalse(is_valid)
        self.assertTrue(any(e.field == "compression_format" for e in errors))

    def test_invalid_format_case_insensitive(self):
        config = Config(compression_format="zip")
        is_valid, errors, _ = validate_config_file(config)
        # Should pass because validate_all uppercases the format
        self.assertTrue(is_valid)


class TestSFTPValidation(unittest.TestCase):
    """测试 SFTP 配置校验"""

    def test_sftp_disabled_skips_validation(self):
        config = Config(sftp_enabled=False, sftp_host="", sftp_user="")
        is_valid, errors, _ = validate_config_file(config)
        self.assertTrue(is_valid)

    def test_sftp_enabled_empty_host(self):
        config = Config(sftp_enabled=True, sftp_host="", sftp_user="test")
        is_valid, errors, _ = validate_config_file(config)
        self.assertFalse(is_valid)
        self.assertTrue(any(e.field == "sftp_host" for e in errors))

    def test_sftp_enabled_empty_user(self):
        config = Config(sftp_enabled=True, sftp_host="example.com", sftp_user="")
        is_valid, errors, _ = validate_config_file(config)
        self.assertFalse(is_valid)
        self.assertTrue(any(e.field == "sftp_user" for e in errors))

    def test_sftp_port_out_of_range(self):
        config = Config(
            sftp_enabled=True, sftp_host="example.com", sftp_user="u", sftp_port=0
        )
        is_valid, errors, _ = validate_config_file(config)
        self.assertFalse(is_valid)
        self.assertTrue(any(e.field == "sftp_port" for e in errors))

    def test_sftp_port_too_high(self):
        config = Config(
            sftp_enabled=True, sftp_host="example.com", sftp_user="u", sftp_port=70000
        )
        is_valid, errors, _ = validate_config_file(config)
        self.assertFalse(is_valid)
        self.assertTrue(any(e.field == "sftp_port" for e in errors))

    def test_sftp_valid_port(self):
        config = Config(
            sftp_enabled=True, sftp_host="example.com", sftp_user="u", sftp_port=22
        )
        is_valid, errors, _ = validate_config_file(config)
        # No sftp-related errors for valid config
        sftp_errors = [e for e in errors if e.field.startswith("sftp")]
        self.assertFalse(sftp_errors)

    def test_sftp_key_file_not_found(self):
        config = Config(
            sftp_enabled=True,
            sftp_host="example.com",
            sftp_user="u",
            sftp_key_file="/nonexistent/path/key.pem",
        )
        _, _, warnings = validate_config_file(config)
        self.assertTrue(any(w.field == "sftp_key_file" for w in warnings))


class TestWebDAVValidation(unittest.TestCase):
    """测试 WebDAV 配置校验"""

    def test_webdav_disabled_skips_validation(self):
        config = Config(webdav_enabled=False, webdav_url="")
        is_valid, errors, _ = validate_config_file(config)
        self.assertTrue(is_valid)

    def test_webdav_enabled_empty_url(self):
        config = Config(webdav_enabled=True, webdav_url="")
        is_valid, errors, _ = validate_config_file(config)
        self.assertFalse(is_valid)
        self.assertTrue(any(e.field == "webdav_url" for e in errors))

    def test_webdav_invalid_url_no_scheme(self):
        config = Config(webdav_enabled=True, webdav_url="example.com/dav")
        is_valid, errors, _ = validate_config_file(config)
        self.assertFalse(is_valid)
        self.assertTrue(any(e.field == "webdav_url" for e in errors))

    def test_webdav_invalid_url_ftp(self):
        config = Config(webdav_enabled=True, webdav_url="ftp://example.com/dav")
        is_valid, errors, _ = validate_config_file(config)
        self.assertFalse(is_valid)
        self.assertTrue(any(e.field == "webdav_url" for e in errors))

    def test_webdav_valid_http(self):
        config = Config(webdav_enabled=True, webdav_url="http://example.com/dav")
        is_valid, errors, _ = validate_config_file(config)
        webdav_errors = [e for e in errors if e.field == "webdav_url"]
        self.assertFalse(webdav_errors)

    def test_webdav_valid_https(self):
        config = Config(
            webdav_enabled=True, webdav_url="https://dav.jianguoyun.com/dav/"
        )
        is_valid, errors, _ = validate_config_file(config)
        webdav_errors = [e for e in errors if e.field == "webdav_url"]
        self.assertFalse(webdav_errors)

    def test_webdav_malformed_url_with_spaces(self):
        config = Config(webdav_enabled=True, webdav_url="http://exam ple.com/dav")
        is_valid, errors, _ = validate_config_file(config)
        self.assertFalse(is_valid)
        self.assertTrue(any(e.field == "webdav_url" for e in errors))


class TestCloudValidation(unittest.TestCase):
    """测试云存储配置校验"""

    def test_cloud_disabled_skips_validation(self):
        config = Config(cloud_enabled=False)
        is_valid, errors, _ = validate_config_file(config)
        self.assertTrue(is_valid)

    def test_cloud_enabled_empty_endpoint(self):
        config = Config(
            cloud_enabled=True,
            cloud_bucket="b",
            cloud_access_key="a",
            cloud_secret_key="s",
        )
        is_valid, errors, _ = validate_config_file(config)
        self.assertFalse(is_valid)
        self.assertTrue(any(e.field == "cloud_endpoint" for e in errors))

    def test_cloud_enabled_empty_bucket(self):
        config = Config(
            cloud_enabled=True,
            cloud_endpoint="e",
            cloud_access_key="a",
            cloud_secret_key="s",
        )
        is_valid, errors, _ = validate_config_file(config)
        self.assertFalse(is_valid)
        self.assertTrue(any(e.field == "cloud_bucket" for e in errors))

    def test_cloud_enabled_empty_access_key(self):
        config = Config(
            cloud_enabled=True,
            cloud_endpoint="e",
            cloud_bucket="b",
            cloud_secret_key="s",
        )
        is_valid, errors, _ = validate_config_file(config)
        self.assertFalse(is_valid)
        self.assertTrue(any(e.field == "cloud_access_key" for e in errors))

    def test_cloud_enabled_empty_secret_key(self):
        config = Config(
            cloud_enabled=True,
            cloud_endpoint="e",
            cloud_bucket="b",
            cloud_access_key="a",
        )
        is_valid, errors, _ = validate_config_file(config)
        self.assertFalse(is_valid)
        self.assertTrue(any(e.field == "cloud_secret_key" for e in errors))

    def test_cloud_all_fields_filled(self):
        config = Config(
            cloud_enabled=True,
            cloud_endpoint="https://s3.amazonaws.com",
            cloud_bucket="my-bucket",
            cloud_access_key="AKIA...",
            cloud_secret_key="secret",
        )
        is_valid, errors, _ = validate_config_file(config)
        cloud_errors = [e for e in errors if e.field.startswith("cloud")]
        self.assertFalse(cloud_errors)


class TestSMTPValidation(unittest.TestCase):
    """测试 SMTP 配置校验"""

    def test_smtp_disabled_skips_validation(self):
        config = Config(smtp_enabled=False)
        is_valid, errors, _ = validate_config_file(config)
        self.assertTrue(is_valid)

    def test_smtp_enabled_empty_host(self):
        config = Config(smtp_enabled=True, smtp_host="")
        is_valid, errors, _ = validate_config_file(config)
        self.assertFalse(is_valid)
        self.assertTrue(any(e.field == "smtp_host" for e in errors))

    def test_smtp_port_out_of_range(self):
        config = Config(smtp_enabled=True, smtp_host="smtp.example.com", smtp_port=0)
        is_valid, errors, _ = validate_config_file(config)
        self.assertFalse(is_valid)
        self.assertTrue(any(e.field == "smtp_port" for e in errors))

    def test_smtp_port_too_high(self):
        config = Config(
            smtp_enabled=True, smtp_host="smtp.example.com", smtp_port=99999
        )
        is_valid, errors, _ = validate_config_file(config)
        self.assertFalse(is_valid)
        self.assertTrue(any(e.field == "smtp_port" for e in errors))

    def test_smtp_valid_config(self):
        config = Config(smtp_enabled=True, smtp_host="smtp.example.com", smtp_port=587)
        is_valid, errors, _ = validate_config_file(config)
        smtp_errors = [e for e in errors if e.field.startswith("smtp")]
        self.assertFalse(smtp_errors)


class TestWebhookValidation(unittest.TestCase):
    """测试 Webhook URL 校验"""

    def test_empty_webhook_list(self):
        config = Config(webhook_urls=[])
        is_valid, errors, _ = validate_config_file(config)
        self.assertTrue(is_valid)

    def test_valid_webhook_urls(self):
        config = Config(
            webhook_urls=["https://example.com/hook", "http://localhost:8080/notify"]
        )
        is_valid, errors, _ = validate_config_file(config)
        webhook_errors = [e for e in errors if e.field == "webhook_urls"]
        self.assertFalse(webhook_errors)

    def test_invalid_webhook_url(self):
        config = Config(webhook_urls=["not-a-url"])
        is_valid, errors, _ = validate_config_file(config)
        self.assertFalse(is_valid)
        self.assertTrue(any(e.field == "webhook_urls" for e in errors))

    def test_ftp_webhook_url_rejected(self):
        config = Config(webhook_urls=["ftp://example.com/hook"])
        is_valid, errors, _ = validate_config_file(config)
        self.assertFalse(is_valid)
        self.assertTrue(any(e.field == "webhook_urls" for e in errors))


class TestPasswordValidation(unittest.TestCase):
    """测试密码配置校验"""

    def test_empty_password_no_warning(self):
        config = Config(password="")
        _, _, warnings = validate_config_file(config)
        self.assertFalse(any(w.field == "password" for w in warnings))

    def test_plaintext_password_warning(self):
        config = Config(password="mysecret")
        _, _, warnings = validate_config_file(config)
        self.assertTrue(any(w.field == "password" for w in warnings))

    def test_encrypted_password_no_warning(self):
        config = Config(password="enc:someencryptedvalue")
        _, _, warnings = validate_config_file(config)
        self.assertFalse(any(w.field == "password" for w in warnings))


class TestPathsValidation(unittest.TestCase):
    """测试路径配置校验"""

    def test_existing_folder_no_warning(self):
        config = Config(folder_path=tempfile.gettempdir())
        _, _, warnings = validate_config_file(config)
        self.assertFalse(any(w.field == "folder_path" for w in warnings))

    def test_nonexistent_folder_warning(self):
        config = Config(folder_path="/nonexistent/folder/path")
        _, _, warnings = validate_config_file(config)
        self.assertTrue(any(w.field == "folder_path" for w in warnings))

    def test_zipfile_path_nonexistent_parent_warning(self):
        config = Config(zipfile_path="/nonexistent/dir/backup.zip")
        _, _, warnings = validate_config_file(config)
        self.assertTrue(any(w.field == "zipfile_path" for w in warnings))

    def test_zipfile_path_valid_parent_no_warning(self):
        tmpdir = tempfile.mkdtemp()
        try:
            zipfile_path = os.path.join(tmpdir, "backup.zip")
            config = Config(zipfile_path=zipfile_path)
            _, _, warnings = validate_config_file(config)
            self.assertFalse(any(w.field == "zipfile_path" for w in warnings))
        finally:
            shutil.rmtree(tmpdir)


class TestNetworkValidation(unittest.TestCase):
    """测试网络配置校验"""

    def test_valid_ip_sftp(self):
        config = Config(
            sftp_enabled=True, sftp_host="192.168.1.1", sftp_user="u", sftp_port=22
        )
        _, errors, _ = validate_config_file(config)
        network_errors = [e for e in errors if e.field == "sftp_host"]
        self.assertFalse(network_errors)

    def test_invalid_port_for_ip(self):
        config = Config(
            sftp_enabled=True, sftp_host="192.168.1.1", sftp_user="u", sftp_port=0
        )
        _, errors, _ = validate_config_file(config)
        self.assertTrue(any(e.field == "sftp_host" for e in errors))

    def test_domain_host_skips_port_check(self):
        # Non-IP host should not trigger port range error via network validation
        config = Config(smtp_enabled=True, smtp_host="smtp.example.com", smtp_port=25)
        _, errors, _ = validate_config_file(config)
        network_errors = [e for e in errors if e.field == "smtp_host"]
        self.assertFalse(network_errors)

    def test_malformed_host_warning(self):
        config = Config(
            sftp_enabled=True, sftp_host="invalid host!", sftp_user="u", sftp_port=22
        )
        _, _, warnings = validate_config_file(config)
        self.assertTrue(any(w.field == "sftp_host" for w in warnings))


class TestIntegrityChecksum(unittest.TestCase):
    """测试配置校验和"""

    def test_checksum_consistency(self):
        config = Config(
            folder_path="/test",
            compression_format="ZIP",
            sftp_host="example.com",
        )
        checksum1 = get_config_checksum(config)
        checksum2 = get_config_checksum(config)
        self.assertEqual(checksum1, checksum2)

    def test_checksum_changes_with_field(self):
        config1 = Config(folder_path="/test")
        config2 = Config(folder_path="/different")
        self.assertNotEqual(get_config_checksum(config1), get_config_checksum(config2))

    def test_checksum_excludes_internal_fields(self):
        """校验和不应受 _encrypted/_key_salt/_config_checksum 影响"""
        config = Config(folder_path="/test")
        config._encrypted = True
        config._key_salt = "some_salt"
        config._config_checksum = "old_checksum"
        checksum_with = get_config_checksum(config)
        # Reset internal fields
        config._encrypted = False
        config._key_salt = ""
        config._config_checksum = ""
        checksum_without = get_config_checksum(config)
        self.assertEqual(checksum_with, checksum_without)

    def test_validate_all_updates_checksum(self):
        config = Config(compression_format="ZIP")
        validator = ConfigValidator(config)
        old_checksum = getattr(config, "_config_checksum", None)
        validator.validate_all()
        # After validate_all, the config's _config_checksum should be updated
        self.assertIsNotNone(config._config_checksum)
        self.assertNotEqual(old_checksum, config._config_checksum)
        # Running again should produce same checksum
        validator2 = ConfigValidator(config)
        validator2.validate_all()
        self.assertEqual(config._config_checksum, get_config_checksum(config))


class TestValidateConfigFile(unittest.TestCase):
    """测试 validate_config_file 完整校验"""

    def test_all_valid_config(self):
        tmpdir = tempfile.mkdtemp()
        try:
            config = Config(
                folder_path=tmpdir,
                compression_format="ZIP",
                zipfile_path=os.path.join(tmpdir, "backup.zip"),
            )
            is_valid, errors, warnings = validate_config_file(config)
            self.assertTrue(is_valid)
            self.assertEqual(len(errors), 0)
        finally:
            shutil.rmtree(tmpdir)

    def test_multiple_errors(self):
        config = Config(
            sftp_enabled=True,
            sftp_host="",
            sftp_user="",
            sftp_port=99999,
            compression_format="BAD",
        )
        is_valid, errors, warnings = validate_config_file(config)
        self.assertFalse(is_valid)
        self.assertGreaterEqual(len(errors), 4)

    def test_errors_and_warnings_coexist(self):
        config = Config(
            folder_path="/nonexistent/path",
            password="plaintext_pass",
            compression_format="ZIP",
        )
        is_valid, errors, warnings = validate_config_file(config)
        # folder_path warning + password warning, no errors
        self.assertTrue(is_valid)
        self.assertGreater(len(warnings), 0)


class TestSecurityScenarios(unittest.TestCase):
    """安全场景测试"""

    def test_malformed_url(self):
        """畸形 URL 应被拒绝"""
        config = Config(webdav_enabled=True, webdav_url="javascript:alert(1)")
        is_valid, errors, _ = validate_config_file(config)
        self.assertFalse(is_valid)
        self.assertTrue(any(e.field == "webdav_url" for e in errors))

    def test_url_with_newline_injection(self):
        """包含换行符的 URL 应被拒绝"""
        config = Config(
            webdav_enabled=True, webdav_url="http://example.com/path\nEvil-Header: true"
        )
        is_valid, errors, _ = validate_config_file(config)
        self.assertFalse(is_valid)

    def test_empty_required_fields(self):
        """空的必填字段应产生错误"""
        config = Config(
            sftp_enabled=True,
            webdav_enabled=True,
            cloud_enabled=True,
            smtp_enabled=True,
        )
        is_valid, errors, _ = validate_config_file(config)
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)

    def test_extreme_port_values(self):
        """极端端口值应被拒绝"""
        for port in [0, -1, 65536, 99999]:
            config = Config(
                sftp_enabled=True,
                sftp_host="192.168.1.1",
                sftp_user="u",
                sftp_port=port,
            )
            is_valid, errors, _ = validate_config_file(config)
            self.assertFalse(is_valid, f"Port {port} should be invalid")

    def test_port_boundary_values(self):
        """边界端口值 1 和 65535 应该合法"""
        for port in [1, 65535]:
            config = Config(
                sftp_enabled=True,
                sftp_host="192.168.1.1",
                sftp_user="u",
                sftp_port=port,
            )
            _, errors, _ = validate_config_file(config)
            port_errors = [e for e in errors if e.field == "sftp_port"]
            self.assertFalse(port_errors, f"Port {port} should be valid")


if __name__ == "__main__":
    unittest.main()
