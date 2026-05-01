"""
单元测试 for sbackup.i18n 模块
"""

import unittest
import os
import json
import tempfile
from sbackup import i18n


class TestI18n(unittest.TestCase):
    def setUp(self):
        """保存原始状态"""
        self._orig_locale = i18n._current_locale
        self._orig_trans = i18n._translations.copy()

    def tearDown(self):
        """恢复原始状态"""
        i18n._current_locale = self._orig_locale
        i18n._translations = self._orig_trans

    def test_set_locale_existing(self):
        """测试设置为存在的语言包"""
        i18n.set_locale("zh_CN")
        self.assertEqual(i18n._current_locale, "zh_CN")
        self.assertIn("cmd.add.success", i18n._translations)

    def test_set_locale_fallback(self):
        """测试设置不存在的语言包时回退到中文"""
        i18n.set_locale("nonexistent_lang")
        self.assertEqual(i18n._current_locale, "nonexistent_lang")
        self.assertIn("cmd.add.success", i18n._translations)

    def test_t_basic(self):
        """测试基础翻译获取"""
        i18n.set_locale("zh_CN")
        text = i18n.t("cmd.add.success", source="/a", dest="/b")
        self.assertIn("/a", text)
        self.assertIn("/b", text)

    def test_t_missing_key(self):
        """测试缺失键名时返回键名本身"""
        i18n.set_locale("zh_CN")
        text = i18n.t("this.key.does.not.exist")
        self.assertEqual(text, "this.key.does.not.exist")

    def test_t_no_kwargs(self):
        """测试无格式化参数时返回原文"""
        i18n.set_locale("en_US")
        text = i18n.t("cmd.all.empty")
        self.assertEqual(text, "No backup strategies configured.")

    def test_t_format_error(self):
        """测试格式化参数不匹配时返回原文"""
        i18n.set_locale("zh_CN")
        text = i18n.t("cmd.add.success", wrong_key="value")
        # 应返回未格式化的原文
        self.assertEqual(text, "备份策略添加成功: {source} -> {dest}")

    def test_language_switch_returns_correct_text(self):
        """测试切换语言后 t() 返回对应语言的文本"""
        i18n.set_locale("zh_CN")
        zh_text = i18n.t("cmd.all.empty")
        self.assertEqual(zh_text, "没有配置任何备份策略。")

        i18n.set_locale("en_US")
        en_text = i18n.t("cmd.all.empty")
        self.assertEqual(en_text, "No backup strategies configured.")

    def test_set_locale_corrupted_file_fallback(self):
        """测试语言包 JSON 损坏时回退到默认中文"""
        import shutil

        # 创建临时损坏的语言文件
        tmpdir = tempfile.mkdtemp()
        try:
            locales_dir = os.path.join(tmpdir, "locales")
            os.makedirs(locales_dir)
            # 创建损坏的 en_US.json
            with open(os.path.join(locales_dir, "en_US.json"), "w") as f:
                f.write("{corrupted!!!")
            # 创建正常的 zh_CN.json 作为回退
            with open(
                os.path.join(locales_dir, "zh_CN.json"), "w", encoding="utf-8"
            ) as f:
                json.dump({"test.key": "回退文本"}, f, ensure_ascii=False)

            # 使用 patch 模拟
            with unittest.mock.patch.object(
                i18n.os.path, "dirname", return_value=tmpdir
            ):
                i18n.set_locale("en_US")
                self.assertEqual(i18n.t("test.key"), "回退文本")
        finally:
            shutil.rmtree(tmpdir)

    def test_set_locale_both_corrupted(self):
        """测试所有语言包都损坏时 translations 为空"""
        import shutil

        tmpdir = tempfile.mkdtemp()
        try:
            locales_dir = os.path.join(tmpdir, "locales")
            os.makedirs(locales_dir)
            with open(os.path.join(locales_dir, "en_US.json"), "w") as f:
                f.write("{bad")
            with open(os.path.join(locales_dir, "zh_CN.json"), "w") as f:
                f.write("{bad")

            with unittest.mock.patch.object(
                i18n.os.path, "dirname", return_value=tmpdir
            ):
                i18n.set_locale("en_US")
                self.assertEqual(i18n._translations, {})
        finally:
            shutil.rmtree(tmpdir)


if __name__ == "__main__":
    unittest.main()
