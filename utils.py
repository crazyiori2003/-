import os
import re
from typing import List, Set


def get_audio_files_from_directory(directory: str, supported_formats: Set[str]) -> List[str]:
    """从目录获取所有音频文件"""
    audio_files = []

    for root, dirs, files in os.walk(directory):
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in supported_formats:
                file_path = os.path.join(root, file)
                audio_files.append(file_path)

    return audio_files


def is_audio_file(filename: str, supported_formats: Set[str]) -> bool:
    """检查是否为支持的音频文件"""
    ext = os.path.splitext(filename)[1].lower()
    return ext in supported_formats


def normalize_field_name(field_name: str) -> str:
    """规范化字段名"""
    # 去除空格，转为大写
    return field_name.strip().upper()


def parse_range(range_str: str) -> tuple:
    """解析范围字符串，如 '1-4'"""
    try:
        if '-' in range_str:
            start, end = range_str.split('-')
            return int(start.strip()), int(end.strip())
        else:
            pos = int(range_str.strip())
            return pos, pos
    except:
        return 1, 1


def remove_brackets_content(text: str, brackets: List[str]) -> str:
    """移除括号及内容"""
    result = text
    for bracket_pair in brackets:
        if len(bracket_pair) == 2:
            open_bracket, close_bracket = bracket_pair[0], bracket_pair[1]
            # 使用正则表达式删除括号及内容
            pattern = re.escape(open_bracket) + '.*?' + re.escape(close_bracket)
            result = re.sub(pattern, '', result)
    return result


def convert_punctuation(text: str, to_english: bool = True) -> str:
    """转换标点符号"""
    if to_english:
        # 中文标点转英文标点
        chinese_punctuation = '，。！？；："‘’""（）【】《》'
        english_punctuation = ',.!?;:\'""""()[]<>'
        trans_table = str.maketrans(chinese_punctuation, english_punctuation)
        return text.translate(trans_table)
    else:
        # 英文标点转中文标点
        english_punctuation = ',.!?;:\'""""()[]<>'
        chinese_punctuation = '，。！？；："‘’""（）【】《》'
        trans_table = str.maketrans(english_punctuation, chinese_punctuation)
        return text.translate(trans_table)


def trim_spaces(text: str, trim_type: str = "all") -> str:
    """修剪空格"""
    result = text

    if trim_type in ["both", "all"]:
        result = result.strip()

    if trim_type in ["duplicate", "all"]:
        result = re.sub(r'\s+', ' ', result)

    return result