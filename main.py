#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import traceback
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import time

# PyQt5导入 - 设置环境变量避免警告
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QListWidget, QListWidgetItem, QCheckBox,
                             QGroupBox, QTextEdit, QLineEdit, QSpinBox, QComboBox,
                             QDialog, QGridLayout, QScrollArea, QFrame, QMessageBox,
                             QFileDialog, QTabWidget, QSplitter, QToolButton, QMenu,
                             QAbstractItemView, QHeaderView, QTableWidget, QTableWidgetItem,
                             QRadioButton, QButtonGroup, QProgressBar)
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QEvent, QTimer, QThread
from PyQt5.QtGui import QFont, QIcon, QDragEnterEvent, QDropEvent
from PyQt5.QtCore import QMimeData, QUrl

# 导入音频处理库
try:
    import mutagen
    from mutagen.flac import FLAC
    from mutagen.mp3 import MP3
    from mutagen.id3 import ID3
    from mutagen.wave import WAVE
    import mutagen.id3 as id3

    HAS_MUTAGEN = True
except ImportError:
    HAS_MUTAGEN = False
    print("请先安装mutagen库: pip install mutagen")
    sys.exit(1)


# ============================================================================
# 启动画面
# ============================================================================
class SplashScreen(QWidget):
    """启动画面"""

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # 设置窗口大小
        self.setFixedSize(400, 200)

        # 居中显示
        screen_geometry = QApplication.primaryScreen().geometry()
        x = (screen_geometry.width() - self.width()) // 2
        y = (screen_geometry.height() - self.height()) // 2
        self.move(x, y)

        # 设置样式
        self.setStyleSheet("""
            QWidget {
                background-color: #1e4682;
                border-radius: 10px;
                border: 2px solid #2a5caa;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        # 标题
        title_label = QLabel("音乐标签批量编辑器")
        title_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 28px;
                font-weight: bold;
                font-family: 'Microsoft YaHei', 'Arial', sans-serif;
            }
        """)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        layout.addSpacing(20)

        # 版本信息
        version_label = QLabel("Version 1.0.0")
        version_label.setStyleSheet("""
            QLabel {
                color: #c8dcff;
                font-size: 14px;
                font-family: 'Microsoft YaHei', 'Arial', sans-serif;
            }
        """)
        version_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(version_label)

        layout.addSpacing(30)

        # 加载提示
        self.loading_label = QLabel("正在初始化...")
        self.loading_label.setStyleSheet("""
            QLabel {
                color: #b4c9ff;
                font-size: 12px;
                font-family: 'Microsoft YaHei', 'Arial', sans-serif;
            }
        """)
        self.loading_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.loading_label)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #2a5caa;
                border-radius: 5px;
                background-color: #0d2a5c;
                height: 10px;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4a9eff, stop:1 #2a5caa
                );
                border-radius: 5px;
            }
        """)
        layout.addWidget(self.progress_bar)

        # 定时器模拟进度
        self.progress_value = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_progress)
        self.timer.start(30)  # 30ms更新一次

    def update_progress(self):
        """更新进度"""
        self.progress_value += 1
        self.progress_bar.setValue(self.progress_value)

        # 根据进度更新文字
        if self.progress_value < 30:
            self.loading_label.setText("正在初始化...")
        elif self.progress_value < 60:
            self.loading_label.setText("加载模块...")
        elif self.progress_value < 90:
            self.loading_label.setText("准备界面...")
        else:
            self.loading_label.setText("启动完成...")

        if self.progress_value >= 100:
            self.timer.stop()
            self.close()

    def show_and_wait(self, duration=3000):
        """显示启动画面并等待"""
        self.show()
        QApplication.processEvents()
        time.sleep(duration / 1000)


# ============================================================================
# 操作类型枚举
# ============================================================================
class OperationType(Enum):
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
    apply_to_all: bool = False  # 是否应用于所有字段


# ============================================================================
# 多线程处理类
# ============================================================================
class BatchProcessor(QThread):
    """批量处理线程"""
    progress_updated = pyqtSignal(int, int, str)  # 当前进度，总数，当前文件名
    file_processed = pyqtSignal(str, bool, str)  # 文件路径，是否成功，错误信息
    batch_completed = pyqtSignal(int, int, list)  # 成功数，失败数，失败文件列表

    def __init__(self, processor, file_paths, selected_fields):
        super().__init__()
        self.processor = processor
        self.file_paths = file_paths
        self.selected_fields = selected_fields
        self.cancel_requested = False
        self.total_files = len(file_paths)

    def run(self):
        """线程运行函数"""
        success_count = 0
        error_count = 0
        error_files = []

        for i, file_path in enumerate(self.file_paths):
            if self.cancel_requested:
                break

            try:
                # 更新进度
                self.progress_updated.emit(i + 1, self.total_files, os.path.basename(file_path))

                # 处理文件
                self.processor.apply_to_file(file_path, self.selected_fields)
                success_count += 1
                self.file_processed.emit(file_path, True, "")

            except Exception as e:
                error_count += 1
                error_msg = str(e)
                error_files.append(f"{os.path.basename(file_path)}: {error_msg}")
                self.file_processed.emit(file_path, False, error_msg)

                # 记录详细错误但不中断处理
                print(f"处理文件失败 {file_path}: {error_msg}")

            # 小延迟，避免过快处理导致界面卡顿
            time.sleep(0.001)

        # 发送完成信号
        if not self.cancel_requested:
            self.batch_completed.emit(success_count, error_count, error_files)
        else:
            self.batch_completed.emit(success_count, error_count, ["操作被用户取消"])

    def cancel(self):
        """取消处理"""
        self.cancel_requested = True


class CustomFieldScanner(QThread):
    """自定义字段扫描线程"""
    progress_updated = pyqtSignal(int, int, str)  # 当前进度，总数，当前文件名
    scan_completed = pyqtSignal(dict)  # 字段统计字典

    def __init__(self, file_paths):
        super().__init__()
        self.file_paths = file_paths[:50]  # 只扫描前50个文件，避免过长时间
        self.cancel_requested = False
        self.total_files = len(self.file_paths)

    def run(self):
        """扫描自定义字段"""
        standard_fields = [
            "ARTIST", "TITLE", "ALBUM", "GENRE", "COMPOSER",
            "PERFORMER", "ALBUMARTIST", "DATE", "TRACKNUMBER",
            "TRACKTOTAL", "DISCNUMBER", "TOTALDISCS", "COMMENT"
        ]

        field_counts = {}

        for i, file_path in enumerate(self.file_paths):
            if self.cancel_requested:
                break

            try:
                # 更新进度
                self.progress_updated.emit(i + 1, self.total_files, os.path.basename(file_path))

                # 读取标签
                tags = self.read_tags(file_path)
                for field in tags.keys():
                    field_upper = field.upper()
                    is_standard = False
                    for std_field in standard_fields:
                        if field_upper.replace(" ", "") == std_field.replace(" ", ""):
                            is_standard = True
                            break

                    if not is_standard:
                        if field_upper not in field_counts:
                            field_counts[field_upper] = 0
                        field_counts[field_upper] += 1

            except Exception as e:
                print(f"扫描文件 {file_path} 失败: {e}")

            time.sleep(0.001)

        if not self.cancel_requested:
            self.scan_completed.emit(field_counts)

    def read_tags(self, file_path):
        """读取文件标签"""
        try:
            ext = os.path.splitext(file_path)[1].lower()

            if ext == '.flac':
                audio = FLAC(file_path)
                tags = {}
                if audio.tags:
                    for key, values in audio.tags.items():
                        key_upper = key.upper()
                        if values:
                            tags[key_upper] = str(values[0])

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

                    for frame in audio.tags.getall('TXXX'):
                        if hasattr(frame, 'desc') and hasattr(frame, 'text'):
                            field_name = frame.desc.upper()
                            tags[field_name] = str(frame.text[0]) if frame.text else ""

            elif ext == '.wav':
                audio = WAVE(file_path)
                tags = {}
                if audio.tags:
                    for key, values in audio.tags.items():
                        key_upper = key.upper()
                        if values:
                            tags[key_upper] = str(values[0])

            elif ext == '.dsf':
                tags = {}
                # 尝试多种方法读取DSF标签
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

                    # 尝试读取自定义字段
                    try:
                        from mutagen.dsf import DSF
                        audio = DSF(file_path)
                        if audio and audio.tags:
                            # 查找TXXX帧（自定义字段）
                            if 'TXXX' in audio.tags:
                                txxx_frames = audio.tags.getall('TXXX')
                                for frame in txxx_frames:
                                    if hasattr(frame, 'desc') and hasattr(frame, 'text'):
                                        field_name = frame.desc.upper()
                                        if field_name and field_name not in field_mapping.values():
                                            if hasattr(frame.text, '__len__') and len(frame.text) > 0:
                                                tags[field_name] = str(frame.text[0])
                    except:
                        pass

                except Exception:
                    try:
                        audio = mutagen.File(file_path, easy=True)
                        if audio:
                            for key, values in audio.items():
                                key_upper = key.upper()
                                if values:
                                    tags[key_upper] = str(values[0])
                    except Exception:
                        pass

            else:
                audio = mutagen.File(file_path, easy=True)
                tags = {}
                if audio:
                    for key, values in audio.items():
                        key_upper = key.upper()
                        if values:
                            tags[key_upper] = str(values[0])

            return tags

        except Exception as e:
            print(f"读取标签失败 {file_path}: {e}")
            return {}

    def cancel(self):
        """取消扫描"""
        self.cancel_requested = True


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
            # 确定要操作的字段
            if operation.apply_to_all:
                # 应用于所有选中的字段
                target_fields = selected_fields
            else:
                # 只应用于指定字段
                target_fields = [operation.target_field] if operation.target_field in selected_fields else []

            for target_field in target_fields:
                current_value = modified_tags.get(target_field, "")

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
                        if operation.separator:
                            new_value = source_value + operation.separator + current_value
                        else:
                            new_value = source_value + current_value
                    else:
                        new_value = current_value

                elif operation.op_type == OperationType.INSERT_FIELD_SUFFIX:
                    source_value = original_tags.get(operation.source_field, "")
                    if source_value:
                        if operation.separator:
                            new_value = current_value + operation.separator + source_value
                        else:
                            new_value = current_value + source_value
                    else:
                        new_value = current_value

                elif operation.op_type == OperationType.INSERT_FIELD_POSITION:
                    source_value = original_tags.get(operation.source_field, "")
                    if source_value:
                        if operation.position <= len(current_value):
                            if operation.separator:
                                new_value = (current_value[:operation.position] +
                                             operation.separator + source_value +
                                             current_value[operation.position:])
                            else:
                                new_value = (current_value[:operation.position] +
                                             source_value +
                                             current_value[operation.position:])
                        else:
                            if operation.separator:
                                new_value = current_value + operation.separator + source_value
                            else:
                                new_value = current_value + source_value
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

                modified_tags[target_field] = new_value

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
                tags = {}
                if audio.tags:
                    for key, values in audio.tags.items():
                        key_upper = key.upper()
                        if values:
                            tags[key_upper] = str(values[0])

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

                    # 处理自定义字段 (TXXX)
                    for frame in audio.tags.getall('TXXX'):
                        if hasattr(frame, 'desc') and hasattr(frame, 'text'):
                            field_name = frame.desc.upper()
                            tags[field_name] = str(frame.text[0]) if frame.text else ""

            elif ext == '.wav':
                audio = WAVE(file_path)
                tags = {}
                if audio.tags:
                    for key, values in audio.tags.items():
                        key_upper = key.upper()
                        if values:
                            tags[key_upper] = str(values[0])

            elif ext == '.dsf':
                # DSF文件处理 - 优先使用beets
                tags = self._read_dsf_tags_beets(file_path)
                if not tags:
                    # 回退到mutagen
                    tags = self._read_dsf_tags_mutagen(file_path)

                # 尝试读取自定义字段
                custom_tags = self._read_dsf_custom_tags(file_path)
                if custom_tags:
                    tags.update(custom_tags)

            else:
                # 其他格式
                audio = mutagen.File(file_path, easy=True)
                tags = {}
                if audio:
                    for key, values in audio.items():
                        key_upper = key.upper()
                        if values:
                            tags[key_upper] = str(values[0])

            return tags

        except Exception as e:
            print(f"读取标签失败 {file_path}: {e}")
            return {}

    def _read_dsf_tags_beets(self, file_path: str) -> Dict[str, str]:
        """使用beets库读取DSF标签"""
        try:
            from beets.library import Library, Item
            from beets import config
            from beets.util import syspath

            # 创建临时配置
            config.clear()
            config.read(user=False)

            # 创建内存中的库
            lib = Library(':memory:')

            # 使用beets的Item类读取文件
            item = Item.from_path(syspath(file_path))

            # 从item获取标签
            tags = {}

            # 字段映射
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

            return tags

        except Exception as e:
            print(f"beets读取DSF失败 {file_path}: {e}")
            return {}

    def _read_dsf_tags_mutagen(self, file_path: str) -> Dict[str, str]:
        """使用mutagen读取DSF标签"""
        try:
            audio = mutagen.File(file_path, easy=True)
            if audio:
                return {k.upper(): str(v[0]) if v else "" for k, v in audio.items()}
            return {}
        except Exception as e:
            print(f"mutagen读取DSF失败 {file_path}: {e}")
            return {}

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
                "TRACKTOTAL", "DISCNUMBER", "TOTALDISCS", "COMMENT"
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

                # 遍历所有帧，查找其他自定义字段
                for frame_id in list(audio.tags.keys()):
                    if frame_id == 'TXXX':
                        continue

                    # 跳过已知的标准帧
                    standard_frames = ['TIT2', 'TPE1', 'TALB', 'TCON', 'TCOM',
                                       'TPE2', 'TDRC', 'TRCK', 'TPOS', 'COMM']
                    if frame_id in standard_frames:
                        continue

                    # 尝试获取帧内容
                    try:
                        frame = audio.tags[frame_id]
                        if hasattr(frame, 'text'):
                            text_value = str(frame.text[0]) if hasattr(frame.text, '__len__') else str(frame.text)
                            if text_value:
                                # 尝试获取可读的帧名
                                try:
                                    frame_name = id3.ID3._get_frame_name(frame_id)[0]
                                    if frame_name:
                                        tags[frame_name.upper()] = text_value
                                    else:
                                        tags[frame_id] = text_value
                                except:
                                    tags[frame_id] = text_value
                    except:
                        pass

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
                        if value:
                            audio[field] = [value]
                        elif field in audio:
                            del audio[field]

                audio.save()

            elif ext == '.mp3':
                audio = MP3(file_path, ID3=ID3)

                # 确保有ID3标签
                if audio.tags is None:
                    audio.add_tags()

                # MP3字段映射
                mp3_field_map = {
                    'ARTIST': 'TPE1',
                    'TITLE': 'TIT2',
                    'ALBUM': 'TALB',
                    'GENRE': 'TCON',
                    'COMPOSER': 'TCOM',
                    'PERFORMER': 'TPE2',
                    'ALBUMARTIST': 'TPE2',
                    'DATE': 'TDRC',
                    'TRACKNUMBER': 'TRCK',
                    'TRACKTOTAL': 'TRCK',
                    'DISCNUMBER': 'TPOS',
                    'COMMENT': 'COMM',
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
                                    continue

                                # 特殊处理DISCNUMBER
                                if field == 'DISCNUMBER':
                                    totaldiscs = new_tags.get('TOTALDISCS', '')
                                    if totaldiscs:
                                        value = f"{value}/{totaldiscs}"
                                elif field == 'TOTALDISCS':
                                    continue

                                # 创建或更新帧
                                frame_class = getattr(id3, mp3_field, None)
                                if frame_class:
                                    # 删除现有的帧
                                    if mp3_field in audio.tags:
                                        del audio.tags[mp3_field]
                                    audio.tags.add(frame_class(encoding=3, text=value))
                            elif mp3_field in audio.tags:
                                del audio.tags[mp3_field]
                        else:
                            # 自定义字段 (TXXX)
                            if value:
                                # 删除现有的相同字段
                                frames_to_remove = []
                                for frame in audio.tags.getall('TXXX'):
                                    if hasattr(frame, 'desc') and frame.desc == field:
                                        frames_to_remove.append(frame)
                                for frame in frames_to_remove:
                                    audio.tags.remove(frame)

                                audio.tags.add(id3.TXXX(encoding=3, desc=field, text=value))
                            else:
                                # 删除字段
                                frames_to_remove = []
                                for frame in audio.tags.getall('TXXX'):
                                    if hasattr(frame, 'desc') and frame.desc == field:
                                        frames_to_remove.append(frame)
                                for frame in frames_to_remove:
                                    audio.tags.remove(frame)

                audio.save()

            elif ext == '.wav':
                audio = WAVE(file_path)

                if audio.tags is None:
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
            raise

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
                            try:
                                # 尝试存储自定义字段
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
                                    if dsf_field in audio.tags:
                                        del audio.tags[dsf_field]
                                    audio.tags.add(frame_class(encoding=3, text=value))
                            elif dsf_field in audio.tags:
                                del audio.tags[dsf_field]
                        else:
                            # 自定义字段
                            if value:
                                audio.tags.add(id3.TXXX(encoding=3, desc=field, text=value))

                audio.save()

            except Exception as mutagen_error:
                print(f"mutagen写入DSF失败 {file_path}: {mutagen_error}")

        except Exception as e:
            print(f"所有DSF写入方法都失败 {file_path}: {e}")


class DropFileWidget(QWidget):
    """支持拖放文件的Widget"""
    files_dropped = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

        layout = QVBoxLayout(self)
        self.label = QLabel("拖拽文件或文件夹到这里")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("""
            QLabel {
                border: 2px dashed #aaa;
                border-radius: 10px;
                padding: 30px;
                font-size: 14px;
                color: #666;
            }
            QLabel:hover {
                border-color: #0078d7;
                color: #0078d7;
            }
        """)
        layout.addWidget(self.label)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        file_paths = []
        for url in urls:
            file_path = url.toLocalFile()
            if file_path:
                file_paths.append(file_path)

        if file_paths:
            self.files_dropped.emit(file_paths)


class AddOperationDialog(QDialog):
    """添加操作对话框"""
    operation_added = pyqtSignal(object)

    def __init__(self, standard_fields, custom_fields, selected_fields, parent=None):
        super().__init__(parent)
        self.standard_fields = standard_fields
        self.custom_fields = custom_fields
        self.selected_fields = selected_fields

        self.setup_ui()
        self.op_type_combo.currentTextChanged.connect(self.on_op_type_changed)

    def setup_ui(self):
        self.setWindowTitle("添加操作")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        layout = QVBoxLayout(self)

        # 操作类型
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("操作类型:"))
        self.op_type_combo = QComboBox()
        self.op_type_combo.addItem("===== 文本操作 =====")
        self.op_type_combo.addItem("替换文本")
        self.op_type_combo.addItem("插入文本前缀")
        self.op_type_combo.addItem("插入文本后缀")
        self.op_type_combo.addItem("删除范围")
        self.op_type_combo.addItem("插入到位置")
        self.op_type_combo.addItem("===== 字段操作 =====")
        self.op_type_combo.addItem("插入字段前缀")
        self.op_type_combo.addItem("插入字段后缀")
        self.op_type_combo.addItem("插入字段到位置")
        self.op_type_combo.addItem("===== 其他操作 =====")
        self.op_type_combo.addItem("清除括号内容")
        self.op_type_combo.addItem("修剪空格")
        self.op_type_combo.addItem("转换标点符号")
        type_layout.addWidget(self.op_type_combo)
        layout.addLayout(type_layout)

        # 目标字段选择
        self.target_group = QGroupBox("目标字段")
        target_layout = QVBoxLayout(self.target_group)
        self.target_radio_group = QButtonGroup(self)
        self.single_field_radio = QRadioButton("单个字段:")
        self.all_fields_radio = QRadioButton("所有选中的字段")
        self.single_field_radio.setChecked(True)
        self.target_radio_group.addButton(self.single_field_radio)
        self.target_radio_group.addButton(self.all_fields_radio)
        target_layout.addWidget(self.single_field_radio)

        field_layout = QHBoxLayout()
        field_layout.addSpacing(20)
        field_layout.addWidget(QLabel("选择字段:"))
        self.target_combo = QComboBox()
        for field in self.selected_fields:
            self.target_combo.addItem(field)
        field_layout.addWidget(self.target_combo)
        target_layout.addLayout(field_layout)
        target_layout.addWidget(self.all_fields_radio)
        layout.addWidget(self.target_group)

        # 源字段设置
        self.source_group = QGroupBox("源字段设置")
        source_layout = QGridLayout(self.source_group)
        source_layout.addWidget(QLabel("源字段:"), 0, 0)
        self.source_combo = QComboBox()
        all_fields = self.standard_fields + self.custom_fields
        for field in all_fields:
            self.source_combo.addItem(field)
        source_layout.addWidget(self.source_combo, 0, 1)
        source_layout.addWidget(QLabel("分隔符:"), 1, 0)
        self.separator_edit = QLineEdit(" - ")
        source_layout.addWidget(self.separator_edit, 1, 1)
        layout.addWidget(self.source_group)
        self.source_group.hide()

        # 参数设置
        self.params_group = QGroupBox("参数设置")
        self.params_layout = QGridLayout(self.params_group)
        layout.addWidget(self.params_group)

        # 按钮
        button_layout = QHBoxLayout()
        self.ok_btn = QPushButton("确定")
        self.cancel_btn = QPushButton("取消")
        self.ok_btn.clicked.connect(self.on_ok)
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(self.ok_btn)
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)

        self.on_op_type_changed(self.op_type_combo.currentText())

    def on_op_type_changed(self, op_type):
        """操作类型变化"""
        if op_type in ["插入字段前缀", "插入字段后缀", "插入字段到位置"]:
            self.source_group.show()
        else:
            self.source_group.hide()

        self.clear_params()

        if op_type == "替换文本":
            self.params_layout.addWidget(QLabel("查找文本:"), 0, 0)
            self.old_text_edit = QLineEdit()
            self.params_layout.addWidget(self.old_text_edit, 0, 1)
            self.params_layout.addWidget(QLabel("替换为:"), 1, 0)
            self.new_text_edit = QLineEdit()
            self.params_layout.addWidget(self.new_text_edit, 1, 1)

        elif op_type in ["插入文本前缀", "插入文本后缀"]:
            self.params_layout.addWidget(QLabel("插入文本:"), 0, 0)
            self.text_edit = QLineEdit()
            self.params_layout.addWidget(self.text_edit, 0, 1)

        elif op_type == "删除范围":
            self.params_layout.addWidget(QLabel("起始位置:"), 0, 0)
            self.start_spin = QSpinBox()
            self.start_spin.setMinimum(1)
            self.start_spin.setMaximum(1000)
            self.start_spin.setValue(1)
            self.params_layout.addWidget(self.start_spin, 0, 1)
            self.params_layout.addWidget(QLabel("删除长度:"), 1, 0)
            self.length_spin = QSpinBox()
            self.length_spin.setMinimum(1)
            self.length_spin.setMaximum(1000)
            self.length_spin.setValue(1)
            self.params_layout.addWidget(self.length_spin, 1, 1)

        elif op_type == "插入到位置":
            self.params_layout.addWidget(QLabel("插入位置:"), 0, 0)
            self.pos_spin = QSpinBox()
            self.pos_spin.setMinimum(1)
            self.pos_spin.setMaximum(1000)
            self.pos_spin.setValue(1)
            self.params_layout.addWidget(self.pos_spin, 0, 1)
            self.params_layout.addWidget(QLabel("插入文本:"), 1, 0)
            self.text_edit = QLineEdit()
            self.params_layout.addWidget(self.text_edit, 1, 1)

        elif op_type == "清除括号内容":
            bracket_layout = QHBoxLayout()
            self.bracket_vars = {}
            label = QLabel("选择括号类型:")
            bracket_layout.addWidget(label)
            for bracket in ["()", "[]", "{}"]:
                cb = QCheckBox(bracket)
                if bracket == "()":
                    cb.setChecked(True)
                self.bracket_vars[bracket] = cb
                bracket_layout.addWidget(cb)
            bracket_layout.addStretch()
            bracket_widget = QWidget()
            bracket_widget.setLayout(bracket_layout)
            self.params_layout.addWidget(bracket_widget, 0, 0, 1, 2)

        elif op_type == "转换标点符号":
            self.params_layout.addWidget(QLabel("转换方向:"), 0, 0)
            self.direction_combo = QComboBox()
            self.direction_combo.addItems(["中文转英文", "英文转中文"])
            self.params_layout.addWidget(self.direction_combo, 0, 1)

        elif op_type == "修剪空格":
            self.params_layout.addWidget(QLabel("操作:"), 0, 0)
            self.trim_combo = QComboBox()
            self.trim_combo.addItems(["两端空格", "重复空格", "全部"])
            self.params_layout.addWidget(self.trim_combo, 0, 1)

        self.params_layout.setColumnStretch(1, 1)

    def clear_params(self):
        """清除参数区域"""
        for i in reversed(range(self.params_layout.count())):
            widget = self.params_layout.itemAt(i).widget()
            if widget:
                widget.hide()

        while self.params_layout.count():
            item = self.params_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def on_ok(self):
        """确定按钮"""
        op_type_str = self.op_type_combo.currentText()

        if "=====" in op_type_str:
            QMessageBox.warning(self, "警告", "请选择一个具体的操作类型")
            return

        op_type_map = {
            "替换文本": OperationType.REPLACE,
            "插入文本前缀": OperationType.INSERT_TEXT_PREFIX,
            "插入文本后缀": OperationType.INSERT_TEXT_SUFFIX,
            "插入字段前缀": OperationType.INSERT_FIELD_PREFIX,
            "插入字段后缀": OperationType.INSERT_FIELD_SUFFIX,
            "插入字段到位置": OperationType.INSERT_FIELD_POSITION,
            "删除范围": OperationType.DELETE_RANGE,
            "插入到位置": OperationType.INSERT_POSITION,
            "清除括号内容": OperationType.REMOVE_BRACKETS,
            "修剪空格": OperationType.TRIM_SPACES,
            "转换标点符号": OperationType.CONVERT_PUNCTUATION
        }

        op_type = op_type_map.get(op_type_str)
        if not op_type:
            QMessageBox.critical(self, "错误", f"未知的操作类型: {op_type_str}")
            return

        apply_to_all = self.all_fields_radio.isChecked()

        operation = TagOperation(
            op_type=op_type,
            target_field=self.target_combo.currentText(),
            source_field=self.source_combo.currentText() if self.source_group.isVisible() else "",
            separator=self.separator_edit.text() if self.source_group.isVisible() else "",
            apply_to_all=apply_to_all
        )

        try:
            if op_type == OperationType.REPLACE:
                operation.old_text = self.old_text_edit.text()
                operation.new_text = self.new_text_edit.text()

            elif op_type in [OperationType.INSERT_TEXT_PREFIX, OperationType.INSERT_TEXT_SUFFIX]:
                operation.text = self.text_edit.text()

            elif op_type == OperationType.DELETE_RANGE:
                operation.position = self.start_spin.value() - 1
                operation.length = self.length_spin.value()

            elif op_type == OperationType.INSERT_POSITION:
                operation.position = self.pos_spin.value() - 1
                operation.text = self.text_edit.text()

            elif op_type == OperationType.REMOVE_BRACKETS:
                operation.brackets = []
                for bracket, cb in self.bracket_vars.items():
                    if cb.isChecked():
                        operation.brackets.append(bracket)

            elif op_type == OperationType.CONVERT_PUNCTUATION:
                operation.new_text = self.direction_combo.currentText()

            elif op_type == OperationType.TRIM_SPACES:
                operation.new_text = self.trim_combo.currentText()

            self.operation_added.emit(operation)
            self.accept()

        except Exception as e:
            QMessageBox.critical(self, "错误", f"创建操作失败: {str(e)}")


class ProcessingDialog(QDialog):
    """处理进度对话框"""

    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setFixedSize(400, 150)

        layout = QVBoxLayout(self)

        self.label = QLabel("正在处理...")
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)

        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.on_cancel)
        layout.addWidget(self.cancel_btn)

        self.cancel_requested = False

    def on_cancel(self):
        """取消处理"""
        self.cancel_requested = True
        self.label.setText("正在取消...")
        self.cancel_btn.setEnabled(False)

    def update_progress(self, current, total, filename):
        """更新进度"""
        percent = int((current / total) * 100) if total > 0 else 0
        self.progress_bar.setValue(percent)
        self.label.setText(f"正在处理: {filename}\n({current}/{total})")


class CustomFieldDialog(QDialog):
    """自定义字段扫描对话框"""

    def __init__(self, file_paths, parent=None):
        super().__init__(parent)
        self.file_paths = file_paths
        self.custom_fields = []
        self.setup_ui()

        # 使用线程扫描
        self.scanner = CustomFieldScanner(file_paths)
        self.scanner.progress_updated.connect(self.on_scan_progress)
        self.scanner.scan_completed.connect(self.on_scan_completed)
        self.scanner.start()

    def setup_ui(self):
        self.setWindowTitle("扫描自定义字段")
        self.setGeometry(300, 300, 600, 400)
        layout = QVBoxLayout(self)

        self.progress_label = QLabel("正在扫描文件，请稍候...")
        layout.addWidget(self.progress_label)

        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

        self.field_table = QTableWidget()
        self.field_table.setColumnCount(2)
        self.field_table.setHorizontalHeaderLabels(["字段名", "包含的文件数"])
        self.field_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.field_table)

        button_layout = QHBoxLayout()
        self.select_all_btn = QPushButton("全选")
        self.select_none_btn = QPushButton("全不选")
        self.ok_btn = QPushButton("确定")
        self.cancel_btn = QPushButton("取消")

        self.select_all_btn.clicked.connect(self.select_all)
        self.select_none_btn.clicked.connect(self.select_none)
        self.ok_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)

        # 初始禁用按钮
        self.select_all_btn.setEnabled(False)
        self.select_none_btn.setEnabled(False)
        self.ok_btn.setEnabled(False)

        button_layout.addWidget(self.select_all_btn)
        button_layout.addWidget(self.select_none_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.ok_btn)
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)

    def on_scan_progress(self, current, total, filename):
        """扫描进度更新"""
        percent = int((current / total) * 100) if total > 0 else 0
        self.progress_bar.setValue(percent)
        self.progress_label.setText(f"正在扫描: {filename}\n({current}/{total})")

    def on_scan_completed(self, field_counts):
        """扫描完成"""
        sorted_fields = sorted(field_counts.items(), key=lambda x: x[1], reverse=True)
        self.field_table.setRowCount(len(sorted_fields))
        self.custom_fields = []

        for i, (field, count) in enumerate(sorted_fields):
            checkbox = QCheckBox(field)
            checkbox.setChecked(True)
            self.custom_fields.append(field)
            self.field_table.setCellWidget(i, 0, checkbox)
            self.field_table.setItem(i, 1, QTableWidgetItem(str(count)))

        # 隐藏进度条，显示表格
        self.progress_label.hide()
        self.progress_bar.hide()

        # 启用按钮
        self.select_all_btn.setEnabled(True)
        self.select_none_btn.setEnabled(True)
        self.ok_btn.setEnabled(True)

    def select_all(self):
        """全选"""
        for i in range(self.field_table.rowCount()):
            checkbox = self.field_table.cellWidget(i, 0)
            if checkbox:
                checkbox.setChecked(True)

    def select_none(self):
        """全不选"""
        for i in range(self.field_table.rowCount()):
            checkbox = self.field_table.cellWidget(i, 0)
            if checkbox:
                checkbox.setChecked(False)

    def get_selected_fields(self):
        """获取选中的字段"""
        selected = []
        for i in range(self.field_table.rowCount()):
            checkbox = self.field_table.cellWidget(i, 0)
            if checkbox and checkbox.isChecked():
                selected.append(checkbox.text())
        return selected

    def reject(self):
        """取消扫描"""
        self.scanner.cancel()
        super().reject()


class MusicTagEditor(QMainWindow):
    """音乐标签编辑器主窗口"""

    def __init__(self):
        super().__init__()

        # 初始化变量
        self.file_list = []
        self.selected_files = []
        self.custom_fields = []
        self.tag_processor = MusicTagProcessor()
        self.current_preview = {}

        # 批量处理相关
        self.batch_processor = None
        self.processing_dialog = None

        # 标准字段列表 (使用foobar内部字段名)
        self.standard_fields = [
            "ARTIST", "TITLE", "ALBUM", "GENRE", "COMPOSER",
            "PERFORMER", "ALBUMARTIST", "DATE", "TRACKNUMBER",
            "TRACKTOTAL", "DISCNUMBER", "TOTALDISCS", "COMMENT"
        ]

        # 字段显示名称映射 (改为中文显示)
        self.field_display_names = {
            "ARTIST": "艺术家",
            "TITLE": "标题",
            "ALBUM": "专辑",
            "GENRE": "流派",
            "COMPOSER": "作曲家",
            "PERFORMER": "指挥",
            "ALBUMARTIST": "专辑艺术家",
            "DATE": "日期",
            "TRACKNUMBER": "音轨号",
            "TRACKTOTAL": "总音轨数",
            "DISCNUMBER": "碟号",
            "TOTALDISCS": "总碟数",
            "COMMENT": "注释"
        }

        # 支持的音频格式 (添加dsf)
        self.supported_formats = {'.flac', '.mp3', '.wav', '.m4a', '.aac', '.ogg', '.dsf'}

        # 设置窗口
        self.setWindowTitle("音乐标签批量编辑器")
        self.setGeometry(100, 100, 1200, 800)

        # 设置窗口图标（如果存在）
        if os.path.exists("icon.ico"):
            self.setWindowIcon(QIcon("icon.ico"))

        # 创建界面
        self.setup_ui()

        # 设置状态栏
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("就绪")

    def setup_ui(self):
        """设置用户界面"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        self.setup_main_tab()
        self.setup_bottom_buttons(main_layout)

    def setup_main_tab(self):
        """设置主选项卡"""
        main_tab = QWidget()
        main_layout = QVBoxLayout(main_tab)
        splitter = QSplitter(Qt.Vertical)

        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)
        left_widget = self.create_file_selection_widget()
        top_layout.addWidget(left_widget, 2)
        right_widget = self.create_field_selection_widget()
        top_layout.addWidget(right_widget, 1)
        splitter.addWidget(top_widget)

        middle_widget = self.create_operations_widget()
        splitter.addWidget(middle_widget)

        bottom_widget = self.create_preview_widget()
        splitter.addWidget(bottom_widget)

        splitter.setSizes([200, 200, 200])
        main_layout.addWidget(splitter)
        self.tab_widget.addTab(main_tab, "编辑")

    def create_file_selection_widget(self):
        """创建文件选择部件"""
        widget = QGroupBox("文件选择")
        layout = QVBoxLayout(widget)
        self.drop_widget = DropFileWidget()
        self.drop_widget.files_dropped.connect(self.on_files_dropped)
        layout.addWidget(self.drop_widget)

        btn_layout = QHBoxLayout()
        self.select_files_btn = QPushButton("选择文件")
        self.select_folder_btn = QPushButton("选择文件夹")
        self.clear_files_btn = QPushButton("清空列表")
        self.select_all_btn = QPushButton("全选")
        self.invert_select_btn = QPushButton("反选")
        self.scan_custom_btn = QPushButton("扫描自定义字段")

        self.select_files_btn.clicked.connect(self.select_files)
        self.select_folder_btn.clicked.connect(self.select_folder)
        self.clear_files_btn.clicked.connect(self.clear_file_list)
        self.select_all_btn.clicked.connect(self.select_all_files)
        self.invert_select_btn.clicked.connect(self.invert_selection)
        self.scan_custom_btn.clicked.connect(self.scan_custom_fields_dialog)

        btn_layout.addWidget(self.select_files_btn)
        btn_layout.addWidget(self.select_folder_btn)
        btn_layout.addWidget(self.clear_files_btn)
        btn_layout.addWidget(self.select_all_btn)
        btn_layout.addWidget(self.invert_select_btn)
        btn_layout.addWidget(self.scan_custom_btn)

        layout.addLayout(btn_layout)

        self.file_list_widget = QListWidget()
        self.file_list_widget.setSelectionMode(QListWidget.MultiSelection)
        self.file_list_widget.itemSelectionChanged.connect(self.on_file_selection_changed)
        layout.addWidget(self.file_list_widget)

        return widget

    def create_field_selection_widget(self):
        """创建字段选择部件"""
        widget = QGroupBox("选择要修改的字段")
        layout = QVBoxLayout(widget)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.field_layout = QVBoxLayout(self.scroll_content)

        self.field_checkboxes = {}
        std_label = QLabel("标准字段:")
        std_label.setFont(QFont("Arial", 10, QFont.Bold))
        self.field_layout.addWidget(std_label)

        grid_layout = QGridLayout()
        row, col = 0, 0

        for field in self.standard_fields:
            display_name = self.field_display_names.get(field, field)
            cb = QCheckBox(display_name)
            cb.setChecked(True)
            cb.setProperty("field_name", field)
            self.field_checkboxes[field] = cb

            grid_layout.addWidget(cb, row, col)
            col += 1
            if col >= 2:
                col = 0
                row += 1

        self.field_layout.addLayout(grid_layout)

        self.custom_fields_label = QLabel("自定义字段:")
        self.custom_fields_label.setFont(QFont("Arial", 10, QFont.Bold))
        self.field_layout.addWidget(self.custom_fields_label)

        self.custom_fields_container = QWidget()
        self.custom_fields_layout = QVBoxLayout(self.custom_fields_container)
        self.field_layout.addWidget(self.custom_fields_container)
        self.field_layout.addStretch()

        scroll.setWidget(self.scroll_content)
        layout.addWidget(scroll)

        return widget

    def create_operations_widget(self):
        """创建操作序列部件"""
        widget = QGroupBox("操作序列")
        layout = QVBoxLayout(widget)
        self.operations_list = QListWidget()
        self.operations_list.itemSelectionChanged.connect(self.on_operation_selection_changed)
        layout.addWidget(self.operations_list)

        btn_layout = QHBoxLayout()
        self.add_op_btn = QPushButton("添加操作")
        self.remove_op_btn = QPushButton("删除操作")
        self.clear_ops_btn = QPushButton("清空操作")
        self.move_up_btn = QPushButton("上移")
        self.move_down_btn = QPushButton("下移")

        self.add_op_btn.clicked.connect(self.add_operation)
        self.remove_op_btn.clicked.connect(self.remove_operation)
        self.clear_ops_btn.clicked.connect(self.clear_operations)
        self.move_up_btn.clicked.connect(self.move_operation_up)
        self.move_down_btn.clicked.connect(self.move_operation_down)

        btn_layout.addWidget(self.add_op_btn)
        btn_layout.addWidget(self.remove_op_btn)
        btn_layout.addWidget(self.clear_ops_btn)
        btn_layout.addWidget(self.move_up_btn)
        btn_layout.addWidget(self.move_down_btn)
        btn_layout.addStretch()

        layout.addLayout(btn_layout)

        self.op_details_text = QTextEdit()
        self.op_details_text.setReadOnly(True)
        self.op_details_text.setMaximumHeight(100)
        layout.addWidget(self.op_details_text)

        return widget

    def create_preview_widget(self):
        """创建预览部件"""
        widget = QGroupBox("预览")
        layout = QVBoxLayout(widget)
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        layout.addWidget(self.preview_text)
        return widget

    def setup_bottom_buttons(self, main_layout):
        """设置底部按钮"""
        btn_layout = QHBoxLayout()
        self.preview_btn = QPushButton("预览修改")
        self.apply_btn = QPushButton("执行修改")
        self.undo_btn = QPushButton("撤销上次")
        self.save_config_btn = QPushButton("保存配置")
        self.load_config_btn = QPushButton("加载配置")

        self.preview_btn.clicked.connect(self.preview_changes)
        self.apply_btn.clicked.connect(self.apply_changes)
        self.undo_btn.clicked.connect(self.undo_changes)
        self.save_config_btn.clicked.connect(self.save_config)
        self.load_config_btn.clicked.connect(self.load_config)

        btn_layout.addWidget(self.preview_btn)
        btn_layout.addWidget(self.apply_btn)
        btn_layout.addWidget(self.undo_btn)
        btn_layout.addWidget(self.save_config_btn)
        btn_layout.addWidget(self.load_config_btn)

        main_layout.addLayout(btn_layout)

    def on_files_dropped(self, file_paths):
        """处理拖放的文件"""
        all_files = []
        for file_path in file_paths:
            if os.path.isdir(file_path):
                all_files.extend(self.scan_directory(file_path))
            elif os.path.isfile(file_path) and self.is_supported_format(file_path):
                all_files.append(file_path)

        self.add_files(all_files)

    def scan_directory(self, directory):
        """递归扫描目录中的音频文件"""
        audio_files = []
        for root, dirs, files in os.walk(directory):
            for file in files:
                if self.is_supported_format(file):
                    file_path = os.path.join(root, file)
                    audio_files.append(file_path)
        return audio_files

    def is_supported_format(self, filename):
        """检查文件格式是否支持"""
        ext = os.path.splitext(filename)[1].lower()
        return ext in self.supported_formats

    def add_files(self, files):
        """添加文件到列表"""
        new_files = []
        for file_path in files:
            if file_path not in self.file_list:
                self.file_list.append(file_path)
                new_files.append(file_path)

        if new_files:
            self.update_file_list()
            self.status_bar.showMessage(f"已添加 {len(new_files)} 个文件")

            # 如果文件数量很大，优化显示
            if len(self.file_list) > 1000:
                self.status_bar.showMessage(f"已添加 {len(new_files)} 个文件，当前总计 {len(self.file_list)} 个文件")
                # 禁用列表更新以提高性能
                self.file_list_widget.setUpdatesEnabled(False)

    def update_file_list(self):
        """更新文件列表显示"""
        self.file_list_widget.clear()

        # 对于大量文件，只显示文件名以提高性能
        for file_path in self.file_list:
            filename = os.path.basename(file_path)
            item = QListWidgetItem(filename)
            item.setToolTip(file_path)  # 显示完整路径
            self.file_list_widget.addItem(item)

        # 重新启用更新
        self.file_list_widget.setUpdatesEnabled(True)
        self.file_list_widget.update()

    def select_files(self):
        """选择文件"""
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择音频文件", "",
            "音频文件 (*.flac *.mp3 *.wav *.m4a *.aac *.ogg *.dsf);;所有文件 (*.*)"
        )

        if files:
            self.add_files(files)

    def select_folder(self):
        """选择文件夹"""
        folder = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if folder:
            # 显示进度对话框
            dialog = ProcessingDialog("扫描文件夹")
            dialog.show()

            # 在小延迟后开始扫描，避免界面卡顿
            QTimer.singleShot(100, lambda: self.scan_folder_with_progress(folder, dialog))

    def scan_folder_with_progress(self, folder, dialog):
        """带进度显示的文件夹扫描"""
        try:
            audio_files = []
            total_files = 0
            scanned_files = 0

            # 先统计文件总数
            for root, dirs, files in os.walk(folder):
                total_files += len(files)

            # 显示进度
            dialog.label.setText(f"正在扫描文件夹...\n找到 {total_files} 个文件")

            # 扫描文件
            for root, dirs, files in os.walk(folder):
                for file in files:
                    if self.is_supported_format(file):
                        file_path = os.path.join(root, file)
                        audio_files.append(file_path)

                    scanned_files += 1
                    if scanned_files % 100 == 0:  # 每100个文件更新一次
                        percent = int((scanned_files / total_files) * 100) if total_files > 0 else 0
                        dialog.progress_bar.setValue(percent)
                        QApplication.processEvents()  # 处理UI事件

            dialog.close()

            if audio_files:
                self.add_files(audio_files)
            else:
                QMessageBox.warning(self, "警告", "该文件夹中没有找到支持的音频文件")

        except Exception as e:
            dialog.close()
            QMessageBox.critical(self, "错误", f"扫描文件夹失败: {str(e)}")

    def clear_file_list(self):
        """清空文件列表"""
        self.file_list.clear()
        self.selected_files.clear()
        self.file_list_widget.clear()
        self.status_bar.showMessage("文件列表已清空")

    def select_all_files(self):
        """选择所有文件"""
        self.file_list_widget.selectAll()
        self.on_file_selection_changed()

    def invert_selection(self):
        """反选文件"""
        for i in range(self.file_list_widget.count()):
            item = self.file_list_widget.item(i)
            item.setSelected(not item.isSelected())
        self.on_file_selection_changed()

    def on_file_selection_changed(self):
        """文件选择变化事件"""
        selected_items = self.file_list_widget.selectedItems()
        self.selected_files = [self.file_list[i] for i in range(self.file_list_widget.count())
                               if self.file_list_widget.item(i) in selected_items]

        # 更新状态栏
        if self.selected_files:
            self.status_bar.showMessage(f"已选择 {len(self.selected_files)} 个文件")

    def scan_custom_fields_dialog(self):
        """扫描自定义字段对话框"""
        if not self.selected_files:
            QMessageBox.warning(self, "警告", "请先选择文件")
            return

        dialog = CustomFieldDialog(self.selected_files, self)
        if dialog.exec_() == QDialog.Accepted:
            selected_fields = dialog.get_selected_fields()
            self.update_custom_fields_display(selected_fields)

    def update_custom_fields_display(self, custom_fields):
        """更新自定义字段显示"""
        while self.custom_fields_layout.count():
            item = self.custom_fields_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.custom_fields = custom_fields

        if custom_fields:
            grid_layout = QGridLayout()
            row, col = 0, 0

            for i, field in enumerate(custom_fields):
                cb = QCheckBox(field)
                cb.setChecked(True)
                cb.setProperty("field_name", field)
                self.field_checkboxes[field] = cb

                grid_layout.addWidget(cb, row, col)
                col += 1
                if col >= 2:
                    col = 0
                    row += 1

            self.custom_fields_layout.addLayout(grid_layout)
            self.custom_fields_label.show()
        else:
            self.custom_fields_label.hide()

    def get_selected_fields(self):
        """获取选中的字段"""
        selected_fields = []
        for field, cb in self.field_checkboxes.items():
            if cb.isChecked():
                selected_fields.append(field)
        return selected_fields

    def add_operation(self):
        """添加操作"""
        selected_fields = self.get_selected_fields()
        if not selected_fields:
            QMessageBox.warning(self, "警告", "请先选择要修改的字段")
            return

        dialog = AddOperationDialog(
            self.standard_fields,
            self.custom_fields,
            selected_fields,
            self
        )

        dialog.operation_added.connect(self.on_operation_added)

        if dialog.exec_() == QDialog.Accepted:
            pass

    def on_operation_added(self, operation):
        """处理添加的操作"""
        self.tag_processor.add_operation(operation)
        self.update_operations_list()
        if operation.apply_to_all:
            self.status_bar.showMessage(f"已添加操作: {operation.op_type.value} (应用于所有字段)")
        else:
            self.status_bar.showMessage(f"已添加操作: {operation.op_type.value} -> {operation.target_field}")

    def update_operations_list(self):
        """更新操作列表"""
        self.operations_list.clear()

        for i, op in enumerate(self.tag_processor.operations):
            if op.apply_to_all:
                display_text = f"{i + 1}. {op.op_type.value} -> [所有字段]"
            else:
                display_text = f"{i + 1}. {op.op_type.value} -> {op.target_field}"

            if op.source_field:
                display_text += f" [从 {op.source_field}]"
                if op.separator:
                    display_text += f" 分隔符:'{op.separator}'"

            if op.text:
                display_text += f" 文本:'{op.text[:20]}...'" if len(op.text) > 20 else f" 文本:'{op.text}'"

            self.operations_list.addItem(display_text)

    def on_operation_selection_changed(self):
        """操作选择变化事件"""
        current_row = self.operations_list.currentRow()
        if current_row >= 0 and current_row < len(self.tag_processor.operations):
            self.show_operation_details(current_row)

    def show_operation_details(self, index):
        """显示操作详情"""
        if 0 <= index < len(self.tag_processor.operations):
            op = self.tag_processor.operations[index]

            info_text = f"操作详情:\n"
            info_text += f"{'=' * 40}\n"
            info_text += f"操作类型: {op.op_type.value}\n"

            if op.apply_to_all:
                info_text += f"目标字段: 所有选中的字段\n"
            else:
                info_text += f"目标字段: {op.target_field}\n"

            if op.source_field:
                info_text += f"源字段: {op.source_field}\n"
                if op.separator:
                    info_text += f"分隔符: '{op.separator}'\n"

            if op.text:
                info_text += f"插入文本: {op.text}\n"

            if op.old_text:
                info_text += f"查找文本: {op.old_text}\n"

            if op.new_text and op.op_type == OperationType.REPLACE:
                info_text += f"替换为: {op.new_text}\n"

            if op.position > 0:
                info_text += f"位置: {op.position + 1}\n"

            if op.length > 0:
                info_text += f"删除长度: {op.length}\n"

            if op.brackets:
                info_text += f"清除括号: {', '.join(op.brackets)}\n"

            if op.new_text and op.op_type in [OperationType.CONVERT_PUNCTUATION, OperationType.TRIM_SPACES]:
                info_text += f"操作参数: {op.new_text}\n"

            info_text += f"{'=' * 40}"

            self.op_details_text.setPlainText(info_text)
        else:
            self.op_details_text.clear()

    def remove_operation(self):
        """删除操作"""
        current_row = self.operations_list.currentRow()
        if current_row >= 0 and current_row < len(self.tag_processor.operations):
            self.tag_processor.operations.pop(current_row)
            self.update_operations_list()
            self.op_details_text.clear()
            self.status_bar.showMessage("操作已删除")

    def clear_operations(self):
        """清空所有操作"""
        self.tag_processor.clear_operations()
        self.update_operations_list()
        self.op_details_text.clear()
        self.status_bar.showMessage("所有操作已清空")

    def move_operation_up(self):
        """上移操作"""
        current_row = self.operations_list.currentRow()
        if current_row > 0:
            ops = self.tag_processor.operations
            ops[current_row], ops[current_row - 1] = ops[current_row - 1], ops[current_row]
            self.update_operations_list()
            self.operations_list.setCurrentRow(current_row - 1)

    def move_operation_down(self):
        """下移操作"""
        current_row = self.operations_list.currentRow()
        if current_row >= 0 and current_row < len(self.tag_processor.operations) - 1:
            ops = self.tag_processor.operations
            ops[current_row], ops[current_row + 1] = ops[current_row + 1], ops[current_row]
            self.update_operations_list()
            self.operations_list.setCurrentRow(current_row + 1)

    def preview_changes(self):
        """预览修改"""
        if not self.selected_files:
            QMessageBox.warning(self, "警告", "请先选择文件")
            return

        if not self.tag_processor.operations:
            QMessageBox.warning(self, "警告", "请先添加操作")
            return

        selected_fields = self.get_selected_fields()
        if not selected_fields:
            QMessageBox.warning(self, "警告", "请先选择要修改的字段")
            return

        try:
            self.current_preview = {}
            preview_text = "预览修改结果:\n" + "=" * 50 + "\n\n"

            # 限制预览文件数量，避免内存溢出
            preview_files = self.selected_files[:10]  # 增加到10个文件预览
            total_files = len(self.selected_files)

            for i, file_path in enumerate(preview_files):
                preview_text += f"文件 {i + 1}/{len(preview_files)}: {os.path.basename(file_path)}\n"
                original_tags = self.tag_processor.read_file_tags(file_path)
                modified_tags = self.tag_processor.preview_changes(original_tags, selected_fields)

                for field in selected_fields:
                    original = original_tags.get(field, "")
                    modified = modified_tags.get(field, "")

                    if original != modified:
                        preview_text += f"  {field}:\n"
                        preview_text += f"    原: {original}\n"
                        preview_text += f"    新: {modified}\n"

                preview_text += "-" * 30 + "\n"
                self.current_preview[file_path] = {
                    'original': original_tags,
                    'modified': modified_tags
                }

                # 处理UI事件，避免界面卡顿
                if i % 5 == 0:
                    QApplication.processEvents()

            if total_files > 10:
                preview_text += f"\n... 还有 {total_files - 10} 个文件未显示预览\n"

            self.preview_text.setPlainText(preview_text)
            self.status_bar.showMessage(f"预览已生成 (显示前{len(preview_files)}个文件)")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"预览失败: {str(e)}")
            traceback.print_exc()

    def apply_changes(self):
        """应用修改"""
        if not self.selected_files:
            QMessageBox.warning(self, "警告", "请先选择文件")
            return

        if not self.tag_processor.operations:
            QMessageBox.warning(self, "警告", "请先添加操作")
            return

        selected_fields = self.get_selected_fields()
        if not selected_fields:
            QMessageBox.warning(self, "警告", "请先选择要修改的字段")
            return

        reply = QMessageBox.question(
            self, "确认",
            f"确定要修改 {len(self.selected_files)} 个文件的标签吗？",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # 创建进度对话框
        self.processing_dialog = ProcessingDialog("批量修改文件")
        self.processing_dialog.cancel_btn.clicked.connect(self.cancel_processing)

        # 创建并启动处理线程
        self.batch_processor = BatchProcessor(
            self.tag_processor,
            self.selected_files,
            selected_fields
        )

        # 连接信号
        self.batch_processor.progress_updated.connect(self.on_processing_progress)
        self.batch_processor.batch_completed.connect(self.on_processing_completed)

        # 显示对话框并启动线程
        self.processing_dialog.show()
        self.batch_processor.start()

    def on_processing_progress(self, current, total, filename):
        """处理进度更新"""
        if self.processing_dialog:
            self.processing_dialog.update_progress(current, total, filename)

            # 更新状态栏
            self.status_bar.showMessage(f"正在处理: {filename} ({current}/{total})")

    def on_processing_completed(self, success_count, error_count, error_files):
        """处理完成"""
        if self.processing_dialog:
            self.processing_dialog.close()
            self.processing_dialog = None

        result_message = f"修改完成！\n成功: {success_count} 个文件\n失败: {error_count} 个文件"

        if error_files:
            result_message += "\n\n失败的文件:\n" + "\n".join(error_files[:10])
            if len(error_files) > 10:
                result_message += f"\n... 还有 {len(error_files) - 10} 个"

        QMessageBox.information(self, "结果", result_message)
        self.status_bar.showMessage(f"修改完成 - 成功: {success_count}, 失败: {error_count}")

        self.current_preview.clear()
        self.preview_text.clear()

        # 清空处理器
        self.batch_processor = None

    def cancel_processing(self):
        """取消处理"""
        if self.batch_processor:
            self.batch_processor.cancel()
            self.status_bar.showMessage("正在取消操作...")

    def undo_changes(self):
        """撤销修改"""
        QMessageBox.information(self, "提示", "撤销功能需要保存历史记录，当前版本尚未实现")

    def save_config(self):
        """保存配置"""
        config = {
            'operations': [],
            'selected_fields': self.get_selected_fields(),
            'custom_fields': self.custom_fields
        }

        for op in self.tag_processor.operations:
            op_dict = {
                'op_type': op.op_type.value,
                'target_field': op.target_field,
                'source_field': op.source_field,
                'text': op.text,
                'old_text': op.old_text,
                'new_text': op.new_text,
                'position': op.position,
                'length': op.length,
                'brackets': op.brackets,
                'separator': op.separator,
                'apply_to_all': op.apply_to_all
            }
            config['operations'].append(op_dict)

        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存配置", "", "JSON文件 (*.json);;所有文件 (*.*)"
        )

        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, ensure_ascii=False, indent=2)
                self.status_bar.showMessage("配置已保存")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存配置失败: {str(e)}")

    def load_config(self):
        """加载配置"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "加载配置", "", "JSON文件 (*.json);;所有文件 (*.*)"
        )

        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)

                self.tag_processor.clear_operations()

                for op_dict in config.get('operations', []):
                    op_type = OperationType(op_dict['op_type'])
                    operation = TagOperation(
                        op_type=op_type,
                        target_field=op_dict['target_field'],
                        source_field=op_dict.get('source_field', ''),
                        text=op_dict.get('text', ''),
                        old_text=op_dict.get('old_text', ''),
                        new_text=op_dict.get('new_text', ''),
                        position=op_dict.get('position', 0),
                        length=op_dict.get('length', 0),
                        brackets=op_dict.get('brackets', []),
                        separator=op_dict.get('separator', ''),
                        apply_to_all=op_dict.get('apply_to_all', False)
                    )
                    self.tag_processor.add_operation(operation)

                selected_fields = config.get('selected_fields', [])
                for field, cb in self.field_checkboxes.items():
                    cb.setChecked(field in selected_fields)

                custom_fields = config.get('custom_fields', [])
                self.update_custom_fields_display(custom_fields)
                self.update_operations_list()
                self.status_bar.showMessage("配置已加载")

            except Exception as e:
                QMessageBox.critical(self, "错误", f"加载配置失败: {str(e)}")
                traceback.print_exc()


def main():
    """主函数"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    # 显示启动画面
    splash = SplashScreen()
    splash.show()

    # 模拟加载过程
    QTimer.singleShot(2000, splash.close)

    # 创建主窗口
    window = MusicTagEditor()

    # 在启动画面关闭后显示主窗口
    QTimer.singleShot(2200, window.show)

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()