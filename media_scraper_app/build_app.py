import PyInstaller.__main__
import os

def build():
    print("🚀 开始初始化打包环境...")
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(current_dir)
    print(f"📍 当前工作目录已锁定至: {current_dir}")
    
    icon_absolute_path = os.path.join(current_dir, "resources", "icons", "app.ico")
    config_absolute_path = os.path.join(current_dir, "config.json")
    
    # ✅ 核心修复：拿到 resources 文件夹的绝对路径
    resources_absolute_path = os.path.join(current_dir, "resources")
    
    separator = os.pathsep

    params = [
        'main.py',                     
        '--name=AniScraper',           
        '--onedir',                    
        '--noconsole',                 
        '--clean',                     
        f'--icon={icon_absolute_path}',  
    ]

    # 添加 config.json
    if os.path.exists(config_absolute_path):
        params.append(f'--add-data={config_absolute_path}{separator}.')
        
    # ✅ 核心修复：把整个 resources 文件夹连同里面的图片，原封不动地打包进 dist！
    if os.path.exists(resources_absolute_path):
        params.append(f'--add-data={resources_absolute_path}{separator}resources')

    print(f"📦 正在执行打包...")
    PyInstaller.__main__.run(params)
    
    print("\n✅ 打包任务圆满完成！")
    print(f"📂 请在 '{os.path.join(current_dir, 'dist', 'AniScraper')}' 文件夹中寻找可执行程序。")

if __name__ == '__main__':
    build()