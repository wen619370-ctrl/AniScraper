import PyInstaller.__main__
import os
import sys
import argparse
from typing import List, Optional


class BuildConfig:
    """打包配置类，集中管理所有打包选项"""
    
    # 默认配置
    APP_NAME = "AniScraper"
    APP_VERSION = "1.0"
    MAIN_SCRIPT = "main.py"
    ICON_PATH = "resources/icons/app.ico"
    CONFIG_PATH = "config.json"
    RESOURCES_DIR = "resources"
    OUTPUT_DIR = "dist"
    
    # 可选配置
    USE_UPX = True
    SHOW_CONSOLE = False
    CLEAN_BUILD = True
    ONE_FILE_MODE = False  # 默认使用目录模式，方便调试


def add_data_file(src: str, dest: str) -> str:
    """添加数据文件的辅助函数，自动处理路径分隔符"""
    separator = ";" if os.name == "nt" else ":"
    return f"--add-data={src}{separator}{dest}"


def build(config: Optional[BuildConfig] = None) -> None:
    """
    执行 PyInstaller 打包
    
    Args:
        config: 打包配置对象，如果为 None 则使用默认配置
    """
    if config is None:
        config = BuildConfig()
    
    print("🚀 开始初始化打包环境...")
    
    # 设置工作目录为脚本所在目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(current_dir)
    print(f"📍 当前工作目录: {current_dir}")
    
    # 构建基本参数
    params = [
        config.MAIN_SCRIPT,
        f"--name={config.APP_NAME}",
    ]
    
    # 添加模式参数
    if config.ONE_FILE_MODE:
        params.append("--onefile")
        print("📦 使用单文件模式")
    else:
        params.append("--onedir")
        print("📂 使用目录模式")
    
    # 添加控制台选项
    if not config.SHOW_CONSOLE:
        params.append("--noconsole")
    
    # 添加清理选项
    if config.CLEAN_BUILD:
        params.append("--clean")
        print("🧹 启用清理构建")
    
    # 添加 UPX 压缩选项
    if config.USE_UPX:
        params.append("--upx")
        print("📦 启用 UPX 压缩")
    
    # 添加图标
    icon_path = os.path.join(current_dir, config.ICON_PATH)
    if os.path.exists(icon_path):
        params.append(f"--icon={icon_path}")
        print(f"🎨 使用图标: {config.ICON_PATH}")
    else:
        print(f"⚠️  图标文件不存在: {icon_path}")
    
    # 添加数据文件
    separator = ";" if os.name == "nt" else ":"
    
    # 配置文件
    config_path = os.path.join(current_dir, config.CONFIG_PATH)
    if os.path.exists(config_path):
        params.append(add_data_file(config_path, "."))
        print(f"📄 添加配置文件: {config.CONFIG_PATH}")
    
    # 资源文件夹
    resources_path = os.path.join(current_dir, config.RESOURCES_DIR)
    if os.path.exists(resources_path):
        params.append(add_data_file(resources_path, config.RESOURCES_DIR))
        print(f"📁 添加资源目录: {config.RESOURCES_DIR}")
    
    # 添加版本信息（Windows）
    if os.name == "nt":
        params.extend([
            f"--version-file={create_version_file(config)}"
        ])
    
    # 显示最终参数
    print(f"\n📋 打包参数: {' '.join(params)}")
    print(f"\n🔨 开始执行打包...")
    
    try:
        PyInstaller.__main__.run(params)
        
        print(f"\n✅ 打包任务圆满完成！")
        output_path = os.path.join(current_dir, config.OUTPUT_DIR, config.APP_NAME)
        print(f"📂 请在 '{output_path}' 文件夹中寻找可执行程序。")
        
    except Exception as e:
        print(f"\n❌ 打包失败: {e}")
        sys.exit(1)


def create_version_file(config: BuildConfig) -> str:
    """
    创建 Windows 版本信息文件
    
    Args:
        config: 打包配置
        
    Returns:
        版本信息文件路径
    """
    version_file_content = f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({config.APP_VERSION.replace('.', ',')}, 0),
    prodvers=({config.APP_VERSION.replace('.', ',')}, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'AniScraper'),
        StringStruct(u'FileDescription', u'AniScraper - Anime Metadata Scraper'),
        StringStruct(u'FileVersion', u'{config.APP_VERSION}'),
        StringStruct(u'InternalName', u'{config.APP_NAME}'),
        StringStruct(u'LegalCopyright', u'MIT License'),
        StringStruct(u'OriginalFilename', u'{config.APP_NAME}.exe'),
        StringStruct(u'ProductName', u'{config.APP_NAME}'),
        StringStruct(u'ProductVersion', u'{config.APP_VERSION}')])
      ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)"""
    
    version_file = "version_info.txt"
    with open(version_file, "w", encoding="utf-8") as f:
        f.write(version_file_content)
    
    return version_file


def parse_arguments() -> BuildConfig:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description=f"打包 {BuildConfig.APP_NAME} 应用程序")
    
    parser.add_argument("--name", default=BuildConfig.APP_NAME, help="应用程序名称")
    parser.add_argument("--version", default=BuildConfig.APP_VERSION, help="应用程序版本")
    parser.add_argument("--console", action="store_true", help="显示控制台窗口")
    parser.add_argument("--onefile", action="store_true", help="使用单文件模式")
    parser.add_argument("--no-upx", action="store_true", help="禁用 UPX 压缩")
    parser.add_argument("--no-clean", action="store_true", help="跳过清理旧构建")
    
    args = parser.parse_args()
    
    # 创建配置对象
    config = BuildConfig()
    config.APP_NAME = args.name
    config.APP_VERSION = args.version
    config.SHOW_CONSOLE = args.console
    config.ONE_FILE_MODE = args.onefile
    config.USE_UPX = not args.no_upx
    config.CLEAN_BUILD = not args.no_clean
    
    return config


def main():
    """主函数"""
    print("=" * 60)
    print(f"  {BuildConfig.APP_NAME} 打包工具 v{BuildConfig.APP_VERSION}")
    print("=" * 60)
    
    # 解析命令行参数
    config = parse_arguments()
    
    # 执行打包
    build(config)


if __name__ == '__main__':
    main()