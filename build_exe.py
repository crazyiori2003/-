#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import shutil


def build_with_nuitka():
    """使用Nuitka构建"""

    print("使用Nuitka构建（更快更稳定）...")

    cmd = [
        sys.executable,  # 使用当前Python
        '-m', 'nuitka',
        '--standalone',  # 独立程序
        '--onefile',  # 单个文件
        '--windows-disable-console',  # 无控制台
        '--output-dir=build',  # 输出目录
        '--output-filename=音乐标签编辑器.exe',
        '--enable-plugin=pyqt5',  # PyQt5插件
        '--include-package=mutagen',
        '--include-package=beets',
        '--include-module=utils',
        '--include-module=tag_processor',
        '--remove-output',  # 清理输出
        '--assume-yes-for-downloads',  # 自动下载
        'main.py'
    ]

    print(f"执行命令: {' '.join(cmd[2:])}")

    try:
        print("构建中，请稍候（大约2-5分钟）...")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            print("✅ Nuitka构建成功！")

            # 检查输出文件
            exe_path = os.path.join('build', '音乐标签编辑器.exe')
            if os.path.exists(exe_path):
                # 创建完整发布目录
                if os.path.exists('dist'):
                    shutil.rmtree('dist')

                os.makedirs('dist', exist_ok=True)

                # 复制可执行文件
                shutil.copy2(exe_path, 'dist/音乐标签编辑器.exe')

                # 复制必要文件
                for file in ['utils.py', 'tag_processor.py']:
                    if os.path.exists(file):
                        shutil.copy2(file, 'dist/')

                # 创建说明文件
                with open('dist/说明.txt', 'w', encoding='utf-8') as f:
                    f.write('音乐标签编辑器\n直接运行 音乐标签编辑器.exe 即可\n')

                print(f"✅ 程序已生成: dist/音乐标签编辑器.exe")
                print(f"📦 文件大小: {os.path.getsize('dist/音乐标签编辑器.exe') / (1024 * 1024):.1f} MB")

                return True
            else:
                print("❌ 可执行文件未生成")
                return False
        else:
            print(f"❌ Nuitka构建失败")
            if result.stderr:
                print("错误信息:", result.stderr[:500])
            return False

    except Exception as e:
        print(f"❌ 构建异常: {e}")
        return False


def main():
    print("=" * 60)
    print("Nuitka快速打包工具")
    print("=" * 60)

    if build_with_nuitka():
        print("\n🎉 打包完成！")
        print("📁 程序位置: dist/")
        print("🚀 直接运行: 音乐标签编辑器.exe")
    else:
        print("\n❌ 打包失败")


if __name__ == "__main__":
    main()