import json
import os
import logging

logger = logging.getLogger(__name__)

_current_locale = "zh_CN"
_translations = {}

# 初始化默认语言包
_default_file = os.path.join(os.path.dirname(__file__), "locales", "zh_CN.json")
if os.path.exists(_default_file):
    try:
        with open(_default_file, "r", encoding="utf-8") as f:
            _translations = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("i18n.load.default_failed %s: %s", _default_file, e)


def set_locale(lang: str) -> None:
    """
    设置当前语言环境并加载对应的翻译文件
    """
    global _current_locale, _translations
    _current_locale = lang
    locale_file = os.path.join(os.path.dirname(__file__), "locales", f"{lang}.json")
    if os.path.exists(locale_file):
        try:
            with open(locale_file, "r", encoding="utf-8") as f:
                _translations = json.load(f)
            return
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(t("log.i18n.load.failed", path=locale_file, error=e))

    # 回退到默认中文
    default_file = os.path.join(os.path.dirname(__file__), "locales", "zh_CN.json")
    if os.path.exists(default_file):
        try:
            with open(default_file, "r", encoding="utf-8") as f:
                _translations = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(
                t("log.i18n.load.fallback_failed", path=default_file, error=e)
            )
            _translations = {}


def t(key: str, **kwargs) -> str:
    """
    获取翻译文本
    :param key: 翻译键名
    :param kwargs: 格式化参数
    :return: 翻译后的字符串
    """
    text = _translations.get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, ValueError):
            return text
    return text
