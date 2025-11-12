#!/usr/bin/env python3
"""
简单的HTTP服务器，用于提供SynHome演示界面
"""

import http.server
import socketserver
import os
import webbrowser
from urllib.parse import urlparse

class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=os.path.dirname(os.path.abspath(__file__)), **kwargs)

    def end_headers(self):
        # 添加CORS头，允许跨域请求
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

def main():
    PORT = 3000
    Handler = CustomHTTPRequestHandler

    print("🚀 启动SynHome演示界面服务器...")
    print(f"📱 本地访问地址: http://localhost:{PORT}/demo.html")
    print(f"🌐 外部访问地址: http://0.0.0.0:{PORT}/demo.html")
    print("🔌 确保设备模拟服务器在 http://localhost:8000 运行")
    print("⏹️  按 Ctrl+C 停止服务器")

    try:
        with socketserver.TCPServer(("", PORT), Handler) as httpd:
            # 自动打开浏览器
            webbrowser.open(f'http://localhost:{PORT}/demo.html')
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 服务器已停止")
    except OSError as e:
        if e.errno == 48:  # Address already in use
            print(f"❌ 端口 {PORT} 已被占用，请选择其他端口或关闭占用该端口的程序")
        else:
            print(f"❌ 服务器启动失败: {e}")

if __name__ == "__main__":
    main()