import json
import os

_current_locale = "zh_CN"
_translations = {}

# 初始化默认语言包
_default_file = os.path.join(os.path.dirname(__file__), "locales", "zh_CN.json")
if os.path.exists(_default_file):
    with open(_default_file, "r", encoding="utf-8") as f:
        _translations = json.load(f)

def set_locale(lang: str) -> None:
    """
    设置当前语言环境并加载对应的翻译文件
    """
    global _current_locale, _translations
    _current_locale = lang
    locale_file = os.path.join(os.path.dirname(__file__), "locales", f"{lang}.json")
    if os.path.exists(locale_file):
        with open(locale_file, "r", encoding="utf-8") as f:
            _translations = json.load(f)
    else:
        # 如果找不到语言包，回退到默认中文
        default_file = os.path.join(os.path.dirname(__file__), "locales", "zh_CN.json")
        with open(default_file, "r", encoding="utf-8") as f:
            _translations = json.load(f)

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