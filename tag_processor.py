import os
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import mutagen
from mutagen.flac import FLAC
from mutagen.mp3 import MP3
from mutagen.id3 import ID3
from mutagen.wave import WAVE
import mutagen.id3 as id3


class OperationType(Enum):
    """操作类型枚举"""
    REPLACE = "替换"
    INSERT_TEXT_PREFIX = "插入文本前缀"
    INSERT_TEXT_SUFFIX = "插入文本后缀"
    INSERT_FIELD_PREFIX = "插入字段前缀"
    INSERT_FIELD_SUFFIX = "插入字段后缀"
    INSERT_FIELD_POSITION = "插入字段到位置"
    DELETE_RANGE = "删除范围"
    INSERT_POSITION = "插入到位置"
    REMOVE_BRACKETS = "清除括号"
    TRIM_SPACES = "修剪空格"
    CONVERT_PUNCTUATION = "转换标点"


@dataclass
class TagOperation:
    """标签操作类"""
    op_type: OperationType
    target_field: str
    source_field: str = ""
    text: str = ""  # 用于文本插入
    old_text: str = ""
    new_text: str = ""
    position: int = 0  # 0-based
    length: int = 0
    brackets: List[str] = field(default_factory=list)
    separator: str = ""  # 字段插入时的分隔符


class MusicTagProcessor:
    """音乐标签处理器"""

    def __init__(self):
        self.operations: List[TagOperation] = []

    def add_operation(self, operation: TagOperation):
        """添加操作"""
        self.operations.append(operation)

    def clear_operations(self):
        """清空所有操作"""
        self.operations.clear()

    def preview_changes(self, original_tags: Dict[str, str], selected_fields: List[str]) -> Dict[str, str]:
        """预览修改"""
        modified_tags = original_tags.copy()

        for operation in self.operations:
            if operation.target_field not in selected_fields:
                continue

            current_value = modified_tags.get(operation.target_field, "")

            # 根据操作类型处理
            if operation.op_type == OperationType.REPLACE:
                new_value = current_value.replace(operation.old_text, operation.new_text)

            elif operation.op_type == OperationType.INSERT_TEXT_PREFIX:
                new_value = operation.text + current_value

            elif operation.op_type == OperationType.INSERT_TEXT_SUFFIX:
                new_value = current_value + operation.text

            elif operation.op_type == OperationType.INSERT_FIELD_PREFIX:
                source_value = original_tags.get(operation.source_field, "")
                if source_value:
                    new_value = source_value + operation.separator + current_value
                else:
                    new_value = current_value

            elif operation.op_type == OperationType.INSERT_FIELD_SUFFIX:
                source_value = original_tags.get(operation.source_field, "")
                if source_value:
                    new_value = current_value + operation.separator + source_value
                else:
                    new_value = current_value

            elif operation.op_type == OperationType.INSERT_FIELD_POSITION:
                source_value = original_tags.get(operation.source_field, "")
                if source_value:
                    if operation.position <= len(current_value):
                        new_value = (current_value[:operation.position] +
                                     operation.separator + source_value +
                                     current_value[operation.position:])
                    else:
                        new_value = current_value + operation.separator + source_value
                else:
                    new_value = current_value

            elif operation.op_type == OperationType.DELETE_RANGE:
                if operation.position < len(current_value):
                    end_pos = min(operation.position + operation.length, len(current_value))
                    new_value = current_value[:operation.position] + current_value[end_pos:]
                else:
                    new_value = current_value

            elif operation.op_type == OperationType.INSERT_POSITION:
                if operation.position <= len(current_value):
                    new_value = (current_value[:operation.position] +
                                 operation.text +
                                 current_value[operation.position:])
                else:
                    new_value = current_value + operation.text

            elif operation.op_type == OperationType.REMOVE_BRACKETS:
                new_value = current_value
                for brackets in operation.brackets:
                    if len(brackets) == 2:
                        open_bracket, close_bracket = brackets[0], brackets[1]
                        # 使用正则表达式删除括号及内容
                        pattern = re.escape(open_bracket) + '.*?' + re.escape(close_bracket)
                        new_value = re.sub(pattern, '', new_value)

            elif operation.op_type == OperationType.TRIM_SPACES:
                new_value = current_value
                if operation.new_text in ["两端空格", "全部"]:
                    new_value = new_value.strip()
                if operation.new_text in ["重复空格", "全部"]:
                    new_value = re.sub(r'\s+', ' ', new_value)

            elif operation.op_type == OperationType.CONVERT_PUNCTUATION:
                new_value = current_value
                if operation.new_text == "中文转英文":
                    # 中文标点转英文标点
                    chinese_punctuation = '，。！？；："‘’""（）【】《》'
                    english_punctuation = ',.!?;:\'""""()[]<>'
                    trans_table = str.maketrans(chinese_punctuation, english_punctuation)
                    new_value = new_value.translate(trans_table)
                elif operation.new_text == "英文转中文":
                    # 英文标点转中文标点
                    english_punctuation = ',.!?;:\'""""()[]<>'
                    chinese_punctuation = '，。！？；："‘’""（）【】《》'
                    trans_table = str.maketrans(english_punctuation, chinese_punctuation)
                    new_value = new_value.translate(trans_table)

            else:
                new_value = current_value

            modified_tags[operation.target_field] = new_value

        return modified_tags

    def apply_to_file(self, file_path: str, selected_fields: List[str]):
        """应用到文件"""
        # 读取原始标签
        original_tags = self.read_file_tags(file_path)

        # 计算新标签
        new_tags = self.preview_changes(original_tags, selected_fields)

        # 写入文件
        self.write_file_tags(file_path, original_tags, new_tags)

    def read_file_tags(self, file_path: str) -> Dict[str, str]:
        """读取文件标签"""
        try:
            ext = os.path.splitext(file_path)[1].lower()

            if ext == '.flac':
                audio = FLAC(file_path)
                tags = {k.upper(): str(v[0]) if v else "" for k, v in audio.tags.items()}

            elif ext == '.mp3':
                audio = MP3(file_path, ID3=ID3)
                tags = {}
                if audio.tags:
                    for key in audio.tags.keys():
                        if key.startswith('T'):
                            tag_name = id3.ID3._get_frame_name(key)[0]
                            if tag_name:
                                text = str(audio.tags[key])
                                if text:
                                    tags[tag_name.upper()] = text

            elif ext == '.wav':
                audio = WAVE(file_path)
                if audio.tags:
                    tags = {k.upper(): str(v[0]) if v else "" for k, v in audio.tags.items()}
                else:
                    tags = {}

            elif ext == '.dsf':
                # DSF文件处理 - 尝试多种方法
                tags = {}

                # 方法1: 尝试使用beets读取标准字段
                try:
                    from beets.library import Library, Item
                    from beets import config
                    from beets.util import syspath

                    config.clear()
                    config.read(user=False)

                    lib = Library(':memory:')
                    item = Item.from_path(syspath(file_path))

                    field_mapping = {
                        'artist': 'ARTIST',
                        'title': 'TITLE',
                        'album': 'ALBUM',
                        'genre': 'GENRE',
                        'composer': 'COMPOSER',
                        'performer': 'PERFORMER',
                        'albumartist': 'ALBUMARTIST',
                        'year': 'DATE',
                        'track': 'TRACKNUMBER',
                        'tracktotal': 'TRACKTOTAL',
                        'disc': 'DISCNUMBER',
                        'disctotal': 'TOTALDISCS',
                        'comments': 'COMMENT'
                    }

                    for beets_field, our_field in field_mapping.items():
                        try:
                            value = getattr(item, beets_field)
                            if value is not None:
                                tags[our_field] = str(value)
                        except AttributeError:
                            pass

                except Exception as beets_error:
                    print(f"beets读取DSF失败 {file_path}: {beets_error}")
                    # 方法2: 回退到mutagen
                    try:
                        audio = mutagen.File(file_path, easy=True)
                        if audio:
                            tags = {k.upper(): str(v[0]) if v else "" for k, v in audio.items()}
                    except Exception as mutagen_error:
                        print(f"mutagen读取DSF失败 {file_path}: {mutagen_error}")
                        tags = {}

                # 方法3: 尝试读取自定义字段
                try:
                    custom_tags = self._read_dsf_custom_tags(file_path)
                    if custom_tags:
                        tags.update(custom_tags)
                except Exception as custom_error:
                    print(f"读取DSF自定义字段失败 {file_path}: {custom_error}")

            else:
                # 其他格式
                audio = mutagen.File(file_path, easy=True)
                if audio:
                    tags = {k.upper(): str(v[0]) if v else "" for k, v in audio.items()}
                else:
                    tags = {}

            # 标准字段列表
            standard_fields = [
                "ARTIST", "TITLE", "ALBUM", "GENRE", "COMPOSER",
                "PERFORMER", "ALBUMARTIST", "DATE", "TRACKNUMBER",
                "TRACKTOTAL", "DISCNUMBER", "TOTALDISCS", "COMMENT"
            ]

            # 确保所有标准字段都存在
            for field in standard_fields:
                if field not in tags:
                    tags[field] = ""

            return tags

        except Exception as e:
            print(f"读取标签失败 {file_path}: {e}")
            # 返回包含所有标准字段的空字典
            return {field: "" for field in [
                "ARTIST", "TITLE", "ALBUM", "GENRE", "COMPOSER",
                "PERFORMER", "ALBUMARTIST", "DATE", "TRACKNUMBER",
                "TRACKTOTAL", "DISCNUMBER", "TOTALDISCS", "COMMENT"
            ]}

    def _read_dsf_custom_tags(self, file_path: str) -> Dict[str, str]:
        """读取DSF自定义字段"""
        try:
            # 尝试使用mutagen的DSF模块
            try:
                from mutagen.dsf import DSF
                audio = DSF(file_path)
            except ImportError:
                return {}

            if not audio or not audio.tags:
                return {}

            tags = {}

            # 标准字段列表，用于过滤
            standard_fields = [
                "ARTIST", "TITLE", "ALBUM", "GENRE", "COMPOSER",
                "PERFORMER", "ALBUMARTIST", "DATE", "TRACKNUMBER",
                "TRACKTOTAL", "DISCNUMBER", "TOTALDISCS", "COMMENT",
                "TIT2", "TPE1", "TALB", "TCON", "TCOM", "TPE2",
                "TDRC", "TRCK", "TPOS", "COMM"
            ]

            try:
                # 处理TXXX帧（自定义字段）
                if 'TXXX' in audio.tags:
                    txxx_frames = audio.tags.getall('TXXX')
                    for frame in txxx_frames:
                        if hasattr(frame, 'desc') and hasattr(frame, 'text'):
                            field_name = frame.desc.upper()
                            if field_name and field_name not in standard_fields:
                                if hasattr(frame.text, '__len__') and len(frame.text) > 0:
                                    tags[field_name] = str(frame.text[0])
                                else:
                                    tags[field_name] = str(frame.text) if frame.text else ""

                # 遍历所有帧
                for frame_id in list(audio.tags.keys()):
                    try:
                        # 跳过已处理的和标准的TXXX
                        if frame_id == 'TXXX':
                            continue

                        # 跳过已知的标准字段ID
                        if frame_id in standard_fields:
                            continue

                        # 尝试获取帧
                        frame = audio.tags[frame_id]

                        # 尝试获取文本内容
                        if hasattr(frame, 'text'):
                            if hasattr(frame.text, '__len__') and len(frame.text) > 0:
                                text_value = str(frame.text[0])
                            else:
                                text_value = str(frame.text) if frame.text else ""

                            if text_value:
                                # 尝试获取人类可读的帧名
                                try:
                                    frame_name = id3.ID3._get_frame_name(frame_id)[0]
                                    if frame_name:
                                        tags[frame_name.upper()] = text_value
                                    else:
                                        tags[frame_id] = text_value
                                except:
                                    tags[frame_id] = text_value

                    except Exception as frame_error:
                        continue

            except Exception as e:
                print(f"处理DSF标签失败 {file_path}: {e}")

            return tags

        except Exception as e:
            print(f"读取DSF自定义字段失败 {file_path}: {e}")
            return {}

    def write_file_tags(self, file_path: str, original_tags: Dict[str, str], new_tags: Dict[str, str]):
        """写入文件标签"""
        try:
            ext = os.path.splitext(file_path)[1].lower()

            if ext == '.flac':
                audio = FLAC(file_path)

                for field, value in new_tags.items():
                    if value != original_tags.get(field, ""):
                        if value:  # 非空值
                            audio[field] = [value]
                        elif field in audio:  # 空值则删除
                            del audio[field]

                audio.save()

            elif ext == '.mp3':
                audio = MP3(file_path, ID3=ID3)

                # 确保有ID3标签
                if audio.tags is None:
                    audio.add_tags()

                # MP3字段映射
                mp3_field_map = {
                    'TITLE': 'TIT2',
                    'ARTIST': 'TPE1',
                    'ALBUM': 'TALB',
                    'DATE': 'TDRC',
                    'GENRE': 'TCON',
                    'TRACKNUMBER': 'TRCK',
                    'COMPOSER': 'TCOM',
                    'PERFORMER': 'TPE2',
                    'ALBUMARTIST': 'TPE2',
                    'COMMENT': 'COMM',
                    'DISCNUMBER': 'TPOS',
                }

                for field, value in new_tags.items():
                    if value != original_tags.get(field, ""):
                        mp3_field = mp3_field_map.get(field)
                        if mp3_field:
                            if value:
                                # 特殊处理TRACKNUMBER和TRACKTOTAL
                                if field == 'TRACKNUMBER':
                                    tracktotal = new_tags.get('TRACKTOTAL', '')
                                    if tracktotal:
                                        value = f"{value}/{tracktotal}"
                                elif field == 'TRACKTOTAL':
                                    # 跳过，因为已经在TRACKNUMBER中处理了
                                    continue

                                # 特殊处理DISCNUMBER
                                if field == 'DISCNUMBER':
                                    totaldiscs = new_tags.get('TOTALDISCS', '')
                                    if totaldiscs:
                                        value = f"{value}/{totaldiscs}"
                                elif field == 'TOTALDISCS':
                                    # 跳过，因为已经在DISCNUMBER中处理了
                                    continue

                                # 创建或更新帧
                                frame_class = getattr(id3, mp3_field, None)
                                if frame_class:
                                    audio.tags.add(frame_class(encoding=3, text=value))
                            elif mp3_field in audio.tags:
                                # 删除帧
                                del audio.tags[mp3_field]
                        else:
                            # 自定义字段
                            if value:
                                audio.tags.add(id3.TXXX(encoding=3, desc=field, text=value))
                            elif field in [frame.desc for frame in audio.tags.getall('TXXX')]:
                                # 删除自定义字段
                                for frame in audio.tags.getall('TXXX'):
                                    if frame.desc == field:
                                        audio.tags.remove(frame)

                audio.save()

            elif ext == '.wav':
                audio = WAVE(file_path)

                if audio.tags is None:
                    # 如果没有标签，尝试添加
                    pass
                else:
                    for field, value in new_tags.items():
                        if value != original_tags.get(field, ""):
                            if value:
                                audio[field] = [value]
                            elif field in audio:
                                del audio[field]

                audio.save()

            elif ext == '.dsf':
                # DSF文件写入
                self._write_dsf_tags(file_path, original_tags, new_tags)

            else:
                # 其他格式
                audio = mutagen.File(file_path, easy=True)
                if audio:
                    for field, value in new_tags.items():
                        if value != original_tags.get(field, ""):
                            if value:
                                audio[field.lower()] = value
                            elif field.lower() in audio:
                                del audio[field.lower()]

                    audio.save()

        except Exception as e:
            print(f"写入标签失败 {file_path}: {e}")
            # 不抛出异常，让程序继续
            pass

    def _write_dsf_tags(self, file_path: str, original_tags: Dict[str, str], new_tags: Dict[str, str]):
        """写入DSF文件标签"""
        try:
            # 首先尝试使用beets
            try:
                from beets.library import Library, Item
                from beets import config
                from beets.util import syspath

                config.clear()
                config.read(user=False)

                item = Item.from_path(syspath(file_path))

                field_mapping = {
                    'ARTIST': 'artist',
                    'TITLE': 'title',
                    'ALBUM': 'album',
                    'GENRE': 'genre',
                    'COMPOSER': 'composer',
                    'PERFORMER': 'performer',
                    'ALBUMARTIST': 'albumartist',
                    'DATE': 'year',
                    'TRACKNUMBER': 'track',
                    'TRACKTOTAL': 'tracktotal',
                    'DISCNUMBER': 'disc',
                    'TOTALDISCS': 'disctotal',
                    'COMMENT': 'comments'
                }

                for our_field, beets_field in field_mapping.items():
                    if our_field in new_tags and new_tags[our_field] != original_tags.get(our_field, ""):
                        value = new_tags[our_field]
                        if value:
                            setattr(item, beets_field, value)
                        else:
                            setattr(item, beets_field, None)

                # 写入自定义字段
                for field, value in new_tags.items():
                    if field not in field_mapping and value != original_tags.get(field, ""):
                        if value:
                            # 对于自定义字段，尝试使用TXXX
                            try:
                                item['_' + field.lower()] = value
                            except:
                                pass

                item.write()
                return

            except Exception as beets_error:
                print(f"beets写入DSF失败 {file_path}: {beets_error}")

            # 如果beets失败，尝试使用mutagen
            try:
                from mutagen.dsf import DSF
                audio = DSF(file_path)

                if audio.tags is None:
                    audio.add_tags()

                # DSF字段映射
                dsf_field_map = {
                    'ARTIST': 'TPE1',
                    'TITLE': 'TIT2',
                    'ALBUM': 'TALB',
                    'DATE': 'TDRC',
                    'GENRE': 'TCON',
                    'TRACKNUMBER': 'TRCK',
                    'COMPOSER': 'TCOM',
                    'PERFORMER': 'TPE2',
                    'ALBUMARTIST': 'TPE2',
                    'COMMENT': 'COMM',
                    'DISCNUMBER': 'TPOS',
                }

                for field, value in new_tags.items():
                    if value != original_tags.get(field, ""):
                        dsf_field = dsf_field_map.get(field)
                        if dsf_field:
                            if value:
                                # 特殊处理TRACKNUMBER和TRACKTOTAL
                                if field == 'TRACKNUMBER':
                                    tracktotal = new_tags.get('TRACKTOTAL', '')
                                    if tracktotal:
                                        value = f"{value}/{tracktotal}"
                                elif field == 'TRACKTOTAL':
                                    continue

                                # 创建或更新帧
                                frame_class = getattr(id3, dsf_field, None)
                                if frame_class:
                                    audio.tags.add(frame_class(encoding=3, text=value))
                        else:
                            # 自定义字段
                            if value:
                                audio.tags.add(id3.TXXX(encoding=3, desc=field, text=value))

                audio.save()

            except Exception as mutagen_error:
                print(f"mutagen写入DSF失败 {file_path}: {mutagen_error}")

        except Exception as e:
            print(f"所有DSF写入方法都失败 {file_path}: {e}")