#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
打包脚本 - 将音乐标签编辑器打包为 Windows 可执行文件
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path


def clean_build_dirs():
    """清理构建目录"""
    dirs_to_clean = ['build', 'dist', '__pycache__']
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            print(f"清理目录: {dir_name}")
            shutil.rmtree(dir_name)

    # 清理 .spec 文件
    spec_files = [f for f in os.listdir('.') if f.endswith('.spec')]
    for spec_file in spec_files:
        print(f"删除文件: {spec_file}")
        os.remove(spec_file)


def check_dependencies():
    """检查依赖包"""
    required_packages = ['PyQt5', 'mutagen', 'beets', 'Pillow']
    missing_packages = []

    for package in required_packages:
        try:
            __import__(package)
            print(f"✓ {package} 已安装")
        except ImportError:
            missing_packages.append(package)
            print(f"✗ {package} 未安装")

    if missing_packages:
        print("\n缺少以下依赖包，正在安装...")
        for package in missing_packages:
            try:
                subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])
                print(f"✓ {package} 安装成功")
            except Exception as e:
                print(f"✗ {package} 安装失败: {e}")

    # 安装 PyInstaller（如果未安装）
    try:
        import PyInstaller
        print("✓ PyInstaller 已安装")
    except ImportError:
        print("安装 PyInstaller...")
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pyinstaller'])
            print("✓ PyInstaller 安装成功")
        except Exception as e:
            print(f"✗ PyInstaller 安装失败: {e}")
            return False

    return True


def create_icon():
    """创建程序图标"""
    print("\n创建程序图标...")

    icon_script = '''
from PIL import Image, ImageDraw, ImageFont
import os

def create_icon():
    # 创建多个尺寸的图标
    sizes = [16, 32, 48, 64, 128, 256]
    images = []

    for size in sizes:
        # 创建新图像 - 蓝色渐变背景
        img = Image.new('RGBA', (size, size), (30, 100, 200, 255))

        # 创建绘图对象
        draw = ImageDraw.Draw(img)

        # 计算字体大小
        font_size = int(size * 0.6)

        try:
            # 尝试加载系统字体
            font_paths = [
                "C:/Windows/Fonts/arial.ttf",
                "C:/Windows/Fonts/arialbd.ttf",
                "C:/Windows/Fonts/seguiemj.ttf",
                "C:/Windows/Fonts/msyh.ttc",
            ]

            font = None
            for font_path in font_paths:
                if os.path.exists(font_path):
                    try:
                        font = ImageFont.truetype(font_path, font_size)
                        break
                    except:
                        continue

            if font is None:
                font = ImageFont.load_default()

        except:
            font = ImageFont.load_default()

        # 绘制M字母
        text = "M"

        # 计算文本位置（居中）
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
        except:
            text_width = font_size
            text_height = font_size

        x = (size - text_width) // 2
        y = (size - text_height) // 2

        # 绘制白色M字母，带阴影效果
        draw.text((x+1, y+1), text, fill=(100, 150, 220, 255), font=font)  # 阴影
        draw.text((x, y), text, fill=(255, 255, 255, 255), font=font)  # 主文字

        # 添加边框
        if size >= 32:
            border_width = max(2, size // 32)
            draw.rectangle([border_width, border_width, size-border_width-1, size-border_width-1], 
                          outline=(255, 255, 255, 200), width=border_width)

        images.append(img)

    # 保存为ICO文件
    images[0].save(
        'icon.ico',
        format='ICO',
        append_images=images[1:],
        sizes=[(img.width, img.height) for img in images],
        quality=100
    )

    return True

if __name__ == "__main__":
    create_icon()
'''

    with open('create_icon_temp.py', 'w', encoding='utf-8') as f:
        f.write(icon_script)

    try:
        subprocess.run([sys.executable, 'create_icon_temp.py'], check=True)

        if os.path.exists('icon.ico'):
            print("✓ 图标已创建: icon.ico")

            # 创建预览
            try:
                from PIL import Image
                img = Image.open('icon.ico')
                img.save('icon_preview.png', 'PNG')
                print("✓ 图标预览已保存: icon_preview.png")
            except:
                pass
        else:
            print("✗ 图标创建失败")
            return False

    except Exception as e:
        print(f"✗ 图标创建失败: {e}")
        return False
    finally:
        if os.path.exists('create_icon_temp.py'):
            os.remove('create_icon_temp.py')

    return True


def create_spec_file():
    """创建 PyInstaller 配置文件"""
    print("\n创建打包配置文件...")

    spec_content = '''# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('utils.py', '.'),
        ('tag_processor.py', '.'),
        ('requirements.txt', '.'),
        ('icon.ico', '.'),
    ],
    hiddenimports=[
        'mutagen',
        'mutagen.id3',
        'mutagen.flac',
        'mutagen.mp3',
        'mutagen.wave',
        'mutagen.dsf',
        'mutagen._util',
        'mutagen._tags',
        'mutagen._file',
        'beets',
        'beets.library',
        'beets.util',
        'beets.config',
        'beets.plugins',
        'beets.dbcore',
        'beets.mediafile',
        'PyQt5',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'PyQt5.QtNetwork',
        'PyQt5.QtPrintSupport',
        'PyQt5.QtSvg',
        'PyQt5.sip',
        'dataclasses',
        'enum',
        'typing',
        'json',
        're',
        'os',
        'sys',
        'time',
        'traceback',
        'pathlib',
        'warnings',
        'collections.abc',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=1,
)

# 排除不必要的模块以减小体积
excludes = [
    'tkinter',
    'matplotlib',
    'numpy',
    'pandas',
    'scipy',
    'sqlite3',
    'test',
    'unittest',
]

for exclude in excludes:
    if exclude in a.pure:
        a.pure.remove(exclude)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='音乐标签批量编辑器',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    runtime_tmpdir=None,
    console=False,
    icon='icon.ico',
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name='音乐标签批量编辑器',
)
'''

    with open('music_tag_editor.spec', 'w', encoding='utf-8') as f:
        f.write(spec_content)

    print("✓ 已创建 .spec 配置文件")
    return True


def build_exe():
    """构建可执行文件"""
    print("\n" + "=" * 50)
    print("开始构建可执行文件...")
    print("=" * 50)

    # 使用 PyInstaller 构建
    cmd = [
        'pyinstaller',
        '--clean',
        '--noconfirm',
        '--noconsole',  # 不显示控制台窗口
        '--icon=icon.ico',
        '--name=音乐标签批量编辑器',
        '--add-data=utils.py;.',
        '--add-data=tag_processor.py;.',
        '--add-data=requirements.txt;.',
        '--add-data=icon.ico;.',
        '--hidden-import=mutagen',
        '--hidden-import=mutagen.id3',
        '--hidden-import=mutagen.flac',
        '--hidden-import=mutagen.mp3',
        '--hidden-import=mutagen.wave',
        '--hidden-import=mutagen.dsf',
        '--hidden-import=beets',
        '--hidden-import=beets.library',
        '--hidden-import=beets.util',
        '--hidden-import=PyQt5',
        '--hidden-import=PyQt5.QtCore',
        '--hidden-import=PyQt5.QtGui',
        '--hidden-import=PyQt5.QtWidgets',
        '--exclude-module=tkinter',
        '--exclude-module=matplotlib',
        '--exclude-module=numpy',
        '--upx-dir=C:\\upx' if os.path.exists('C:\\upx') else '',
        'main.py'
    ]

    # 移除空参数
    cmd = [arg for arg in cmd if arg]

    print(f"执行命令: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            print("\n✓ 构建成功！")
            print(f"输出目录: dist/音乐标签批量编辑器/")

            # 显示构建信息
            if result.stdout:
                print("\n构建输出:")
                print(result.stdout[:500] + "..." if len(result.stdout) > 500 else result.stdout)
        else:
            print("\n✗ 构建失败！")
            print(f"错误代码: {result.returncode}")
            print(f"错误信息: {result.stderr}")
            return False

    except Exception as e:
        print(f"\n✗ 构建过程异常: {e}")
        return False

    return True


def create_readme():
    """创建说明文件"""
    print("\n创建说明文件...")

    readme_content = '''音乐标签批量编辑器 - 使用说明
====================================

📋 程序简介
------------------------------------
本程序是一个专业的音乐标签批量编辑工具，支持多种音频格式，
可以快速批量修改音乐文件的元数据标签。

✨ 主要功能
------------------------------------
1. 支持格式：FLAC、MP3、WAV、DSF、M4A、AAC、OGG 等
2. 批量操作：一次性处理数千个文件
3. 拖拽支持：可直接拖拽文件或文件夹
4. 多种操作：替换、插入、删除、清除括号、转换标点等
5. 字段管理：标准字段 + 自定义字段
6. 操作序列：可保存和加载操作配置
7. 预览功能：修改前预览效果

🖥️ 系统要求
------------------------------------
- Windows 7/8/10/11 (64位推荐)
- 需要安装 Microsoft Visual C++ Redistributable
- 建议内存：4GB 或更高

🚀 使用方法
------------------------------------
1. 运行 "音乐标签批量编辑器.exe"
2. 通过拖拽或按钮添加音频文件/文件夹
3. 选择要修改的字段（标准字段或自定义字段）
4. 添加需要的操作（替换、插入等）
5. 点击"预览修改"查看效果
6. 确认无误后点击"执行修改"

⚡ 性能提示
------------------------------------
- 处理大量文件（2000+）时，程序会自动优化内存使用
- 可随时取消长时间的操作
- 建议先预览再批量修改

❓ 常见问题
------------------------------------
Q: 程序无法启动，提示缺少 DLL
A: 请安装 Microsoft Visual C++ Redistributable 最新版

Q: DSF 文件标签读取不正常
A: 确保文件格式正确，程序使用混合技术读取DSF标签

Q: 界面显示异常或字体不对
A: 尝试调整系统显示缩放设置

📁 文件结构
------------------------------------
音乐标签批量编辑器/
├── 音乐标签批量编辑器.exe    # 主程序
├── utils.py                 # 工具模块
├── tag_processor.py         # 标签处理模块
├── requirements.txt         # 依赖列表
└── icon.ico                # 程序图标

🔄 更新与支持
------------------------------------
本程序为开源项目，如有问题或建议，请联系开发者。

⚠️ 注意事项
------------------------------------
1. 修改前建议备份重要文件
2. 批量操作请先预览确认
3. 程序会在原始文件上直接修改

------------------------------------
版本: 1.0.0
更新日期: 2024年
------------------------------------
'''

    dist_dir = os.path.join('dist', '音乐标签批量编辑器')
    os.makedirs(dist_dir, exist_ok=True)

    readme_path = os.path.join(dist_dir, '使用说明.txt')
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)

    print("✓ 已创建使用说明文件")


def create_launcher_bat():
    """创建启动批处理文件"""
    print("\n创建启动脚本...")

    bat_content = '''@echo off
chcp 65001 > nul
title 音乐标签批量编辑器 - 启动器
color 0A

echo ========================================
echo   音乐标签批量编辑器 启动器
echo ========================================
echo.
echo 正在启动程序...

REM 检查程序是否存在
if not exist "音乐标签批量编辑器.exe" (
    echo 错误：找不到主程序文件！
    echo 请确保 "音乐标签批量编辑器.exe" 存在于当前目录。
    echo.
    pause
    exit /b 1
)

echo 启动主程序...
echo.

start "" "音乐标签批量编辑器.exe"

echo 程序已启动！
echo 请查看使用说明.txt了解详细使用方法。
echo.
timeout /t 3 /nobreak > nul

exit
'''

    dist_dir = os.path.join('dist', '音乐标签批量编辑器')
    bat_path = os.path.join(dist_dir, '启动程序.bat')

    with open(bat_path, 'w', encoding='utf-8') as f:
        f.write(bat_content)

    print("✓ 已创建启动脚本")


def copy_additional_files():
    """复制额外的文件到 dist 目录"""
    print("\n复制必要文件...")

    dist_dir = os.path.join('dist', '音乐标签批量编辑器')

    files_to_copy = ['utils.py', 'tag_processor.py', 'requirements.txt', 'icon.ico']

    for file_name in files_to_copy:
        if os.path.exists(file_name):
            try:
                shutil.copy2(file_name, os.path.join(dist_dir, file_name))
                print(f"✓ 已复制: {file_name}")
            except Exception as e:
                print(f"✗ 复制失败 {file_name}: {e}")


def compress_output():
    """压缩输出文件"""
    import zipfile

    dist_dir = 'dist'
    output_zip = '音乐标签批量编辑器_Windows版.zip'

    if os.path.exists(dist_dir):
        print(f"\n正在压缩到 {output_zip}...")

        try:
            with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(dist_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, dist_dir)
                        zipf.write(file_path, arcname)
                        print(f"  - 添加: {arcname}")

            # 计算压缩包大小
            size_mb = os.path.getsize(output_zip) / (1024 * 1024)
            print(f"\n✓ 已创建压缩包: {output_zip}")
            print(f"  压缩包大小: {size_mb:.2f} MB")

            # 显示压缩包内容
            print("\n压缩包内容:")
            with zipfile.ZipFile(output_zip, 'r') as zipf:
                for name in zipf.namelist():
                    print(f"  - {name}")

        except Exception as e:
            print(f"✗ 压缩失败: {e}")
    else:
        print("✗ 输出目录不存在")


def main():
    """主函数"""
    print("🎵 音乐标签批量编辑器 - 打包工具 🎵")
    print("=" * 60)

    # 检查工作目录
    current_dir = os.getcwd()
    print(f"工作目录: {current_dir}")

    # 检查必要文件是否存在
    required_files = ['main.py', 'utils.py', 'tag_processor.py']
    missing_files = []

    for file_name in required_files:
        if not os.path.exists(file_name):
            missing_files.append(file_name)

    if missing_files:
        print(f"\n✗ 缺少必要文件: {missing_files}")
        print("请确保以下文件存在于当前目录:")
        for file_name in required_files:
            print(f"  - {file_name}")
        return

    print("\n✓ 所有必要文件都存在")

    # 清理旧文件
    print("\n清理旧构建文件...")
    clean_build_dirs()

    # 检查依赖
    print("\n检查依赖包...")
    if not check_dependencies():
        print("\n✗ 依赖检查失败，请手动安装所需包")
        return

    # 创建图标
    if not create_icon():
        print("\n⚠️ 图标创建失败，使用默认图标")
        # 继续打包，PyInstaller 会使用默认图标

    # 构建可执行文件
    if not build_exe():
        print("\n✗ 构建失败")
        return

    # 创建说明文件
    create_readme()

    # 创建启动脚本
    create_launcher_bat()

    # 复制额外文件
    copy_additional_files()

    # 压缩输出
    compress_output()

    print("\n" + "=" * 60)
    print("🎉 打包完成！")
    print("=" * 60)
    print("\n输出文件:")
    print(f"  1. 可执行程序: dist/音乐标签批量编辑器/")
    print(f"  2. 压缩包: 音乐标签批量编辑器_Windows版.zip")
    print(f"\n使用说明:")
    print(f"  1. 解压压缩包到任意目录")
    print(f"  2. 运行 '启动程序.bat' 或直接运行 '音乐标签批量编辑器.exe'")
    print(f"  3. 详细说明请查看 '使用说明.txt'")
    print("\n✨ 程序打包成功，可以分享使用了！")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ 用户中断操作")
    except Exception as e:
        print(f"\n❌ 打包过程中出现错误: {e}")
        import traceback

        traceback.print_exc()