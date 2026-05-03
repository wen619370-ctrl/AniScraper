# 临时测试脚本: test_workers.py
import sys
from PySide6.QtCore import QCoreApplication
from workers.scrape_worker import ScrapeWorker

def run_test():
    # 必须创建 Qt 核心应用以提供事件循环
    app = QCoreApplication(sys.argv)

    print("=== 测试 ScrapeWorker (网络请求子线程) ===")
    worker = ScrapeWorker(keyword="孤独摇滚")

    # 绑定信号与槽函数 (这里用简单的 lambda 函数模拟 UI 更新)
    worker.progress_signal.connect(lambda msg: print(f"[UI 进度更新]: {msg}"))
    worker.error_signal.connect(lambda err: print(f"[UI 报错弹窗]: {err}"))
    
    def on_result(data):
        print(f"[UI 接收数据]: 成功获取了 {len(data)} 条搜索结果！")
        print(f"第一条结果: {data[0].get('name_cn') or data[0].get('name')}")
        app.quit() # 测试成功，退出事件循环

    worker.result_signal.connect(on_result)

    # 启动子线程！
    worker.start()

    # 启动 Qt 事件循环，阻塞主线程，直到 app.quit() 被调用
    sys.exit(app.exec())

if __name__ == "__main__":
    run_test()