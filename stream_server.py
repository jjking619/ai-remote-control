import cv2
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
import os

class StreamHandler(BaseHTTPRequestHandler):
    latest_frame = None
    frame_lock = threading.Lock()
    video_frames = []  # 存储测试视频帧
    video_frame_index = 0
    show_video_preview = False  # 是否显示视频预览
    show_video_playback = False  # 是否显示视频播放内容
    current_mode = "video"  # 当前模式: "video" 或 "document"
    pending_video_command = None  # 待处理的视频命令
    pending_document_command = None  # 待处理的文档命令
    pending_mode_switch = None  # 待处理的模式切换
    pending_open_pdf = None  # 待处理的打开PDF命令
    
    def log_message(self, format, *args):
        """覆盖默认的日志消息方法，禁止打印HTTP请求日志"""
        pass
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            
            html_content = '''<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <title>AI Eye Remote Control</title>
    <style>
        body { 
            margin: 0; 
            padding: 20px; 
            background: #000; 
            color: #0f0; 
            font-family: monospace;
        }
        .container { 
            max-width: 1200px; 
            margin: 0 auto; 
            text-align: center;
        }
        h1 { margin-bottom: 20px; }
        img { 
            max-width: 100%; 
            border: 2px solid #0f0;
        }
        .info { 
            margin-top: 20px; 
            padding: 10px; 
            background: #222;
        }
        .tabs {
            margin: 20px 0;
        }
        .tab-button {
            background: #333;
            color: #0f0;
            border: 2px solid #0f0;
            padding: 10px 20px;
            margin: 0 5px;
            cursor: pointer;
            font-family: monospace;
            font-size: 16px;
        }
        .tab-button.active {
            background: #0f0;
            color: #000;
        }
        .tab-button:hover:not(.active) {
            background: #444;
        }
        .tab-content {
            display: none;
            padding: 20px;
        }
        .tab-content.active {
            display: block;
        }
        .control-button {
            background: #0f0;
            color: #000;
            border: none;
            padding: 10px 20px;
            margin: 5px;
            cursor: pointer;
            font-family: monospace;
            font-size: 16px;
        }
        .control-button:hover {
            background: #0a0;
        }
        .pdf-input {
            padding: 5px;
            margin: 5px;
            font-family: monospace;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>AI Eye Remote Control</h1>
        
        <!-- 选项卡 -->
        <div class="tabs">
            <button class="tab-button active" onclick="switchTab('video')">视频控制</button>
            <button class="tab-button" onclick="switchTab('document')">文档控制</button>
        </div>
        
        <!-- 视频控制面板 -->
        <div id="video" class="tab-content active">
            <h2>视频控制</h2>
            <div>
                <button class="control-button" onclick="sendVideoCommand('play')">播放视频</button>
                <button class="control-button" onclick="sendVideoCommand('pause')">暂停视频</button>
                <button class="control-button" onclick="sendVideoCommand('stop')">停止视频</button>
            </div>
        </div>
        
        <!-- 文档控制面板 -->
        <div id="document" class="tab-content">
            <h2>文档控制</h2>
            <div>
                <input type="text" id="pdfPath" class="pdf-input" placeholder="输入PDF文件路径" value="test.pdf">
                <button class="control-button" onclick="openPDF()">打开PDF</button>
                <br><br>
                <button class="control-button" onclick="sendDocumentCommand('page_up')">上一页</button>
                <button class="control-button" onclick="sendDocumentCommand('page_down')">下一页</button>
            </div>
        </div>
        
        <img id="stream" src="/video_feed" />
        <div class="info">
            <p>实时监控中... 按 Ctrl+C 停止程序</p>
            <p>在其他设备上访问: http://YOUR_IP:8080</p>
        </div>
    </div>
    <script>
        // 自动刷新图像
        const img = document.getElementById('stream');
        setInterval(() => {
            img.src = '/video_feed?t=' + new Date().getTime();
        }, 50);
        
        // 切换选项卡
        function switchTab(tabName) {
            // 更新选项卡按钮状态
            document.querySelectorAll('.tab-button').forEach(button => {
                button.classList.remove('active');
            });
            event.target.classList.add('active');
            
            // 显示对应的内容面板
            document.querySelectorAll('.tab-content').forEach(content => {
                content.classList.remove('active');
            });
            document.getElementById(tabName).classList.add('active');
            
            // 发送模式切换命令
            fetch('/switch_mode?mode=' + tabName)
                .then(response => response.text())
                .then(data => console.log(data))
                .catch(error => console.error('Error:', error));
        }
        
        // 发送视频控制命令
        function sendVideoCommand(command) {
            fetch('/video_control?command=' + command)
                .then(response => response.text())
                .then(data => console.log(data))
                .catch(error => console.error('Error:', error));
        }
        
        // 发送文档控制命令
        function sendDocumentCommand(command) {
            fetch('/document_control?command=' + command)
                .then(response => response.text())
                .then(data => console.log(data))
                .catch(error => console.error('Error:', error));
        }
        
        // 打开PDF文档
        function openPDF() {
            const pdfPath = document.getElementById('pdfPath').value;
            fetch('/open_pdf?path=' + encodeURIComponent(pdfPath))
                .then(response => response.text())
                .then(data => console.log(data))
                .catch(error => console.error('Error:', error));
        }
    </script>
</body>
</html>'''
            self.wfile.write(html_content.encode('utf-8'))
        elif self.path.startswith('/video_feed'):
            self.send_response(200)
            self.send_header('Content-Type', 'image/jpeg')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            
            # 获取最新帧
            with StreamHandler.frame_lock:
                frame_to_send = None
                
                # 优先级: 视频播放 > 视频预览 > 摄像头实时画面
                if StreamHandler.show_video_playback and len(StreamHandler.video_frames) > 0:
                    # 显示视频播放内容
                    frame_to_send = StreamHandler.video_frames[StreamHandler.video_frame_index]
                    StreamHandler.video_frame_index = (StreamHandler.video_frame_index + 1) % len(StreamHandler.video_frames)
                elif StreamHandler.show_video_preview and len(StreamHandler.video_frames) > 0:
                    # 显示视频预览
                    frame_to_send = StreamHandler.video_frames[StreamHandler.video_frame_index]
                    StreamHandler.video_frame_index = (StreamHandler.video_frame_index + 1) % len(StreamHandler.video_frames)
                elif StreamHandler.latest_frame is not None:
                    # 显示摄像头实时画面
                    frame_to_send = StreamHandler.latest_frame
                
                if frame_to_send is not None:
                    try:
                        # 编码JPEG图像
                        ret, buffer = cv2.imencode('.jpg', frame_to_send, 
                                                  [cv2.IMWRITE_JPEG_QUALITY, 70])
                        if ret:
                            self.wfile.write(buffer.tobytes())
                    except Exception as e:
                        print(f"Error encoding image: {e}")
        elif self.path.startswith('/switch_mode'):
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            
            # 处理模式切换
            if 'mode=video' in self.path:
                with StreamHandler.frame_lock:
                    StreamHandler.pending_mode_switch = "video"
                self.wfile.write(b"Switched to video mode")
            elif 'mode=document' in self.path:
                with StreamHandler.frame_lock:
                    StreamHandler.pending_mode_switch = "document"
                self.wfile.write(b"Switched to document mode")
        elif self.path.startswith('/video_control'):
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            
            # 处理视频控制命令
            command = None
            if 'command=play' in self.path:
                command = "play"
            elif 'command=pause' in self.path:
                command = "pause"
            elif 'command=stop' in self.path:
                command = "stop"
                
            if command:
                with StreamHandler.frame_lock:
                    StreamHandler.pending_video_command = command
                self.wfile.write(f"Video command {command} sent".encode('utf-8'))
            else:
                self.wfile.write(b"Invalid video command")
        elif self.path.startswith('/document_control'):
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            
            # 处理文档控制命令
            command = None
            if 'command=page_up' in self.path:
                command = "page_up"
            elif 'command=page_down' in self.path:
                command = "page_down"
                
            if command:
                with StreamHandler.frame_lock:
                    StreamHandler.pending_document_command = command
                self.wfile.write(f"Document command {command} sent".encode('utf-8'))
            else:
                self.wfile.write(b"Invalid document command")
        elif self.path.startswith('/open_pdf'):
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            
            # 处理打开PDF命令
            if 'path=' in self.path:
                with StreamHandler.frame_lock:
                    StreamHandler.pending_open_pdf = self.path.split('path=')[1]
                self.wfile.write(b"Open PDF command sent")
            else:
                self.wfile.write(b"Invalid PDF path")
        else:
            self.send_error(404)
        
class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

class StreamServer:
    def __init__(self, port=8080):
        self.port = port
        self.server = None
        self.thread = None
        self.video_loaded = False
        
    def start(self):
        StreamHandler.latest_frame = None
        StreamHandler.video_frames = []
        StreamHandler.video_frame_index = 0
        StreamHandler.show_video_preview = False
        StreamHandler.show_video_playback = False
        StreamHandler.current_mode = "video"
        StreamHandler.pending_video_command = None
        StreamHandler.pending_document_command = None
        StreamHandler.pending_mode_switch = None
        StreamHandler.pending_open_pdf = None
        
        # 尝试绑定端口，如果失败则尝试其他端口
        ports_to_try = [self.port, 8081, 8082, 9000]
        for port in ports_to_try:
            try:
                self.server = ThreadedHTTPServer(('', port), StreamHandler)
                self.port = port  # 更新实际使用的端口
                break
            except OSError as e:
                if e.errno == 98:  # Address already in use
                    print(f"Port {port} is already in use, trying another port...")
                    continue
                else:
                    raise e
        else:
            raise Exception("Unable to find an available port")
            
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.daemon = True
        self.thread.start()
        print(f"Stream server started on port {self.port}")
        print(f"Please open http://<device_ip>:{self.port} in browser to view real-time video")
        
    def update_frame(self, frame):
        with StreamHandler.frame_lock:
            StreamHandler.latest_frame = frame
        
    def load_video_preview(self, video_path, max_frames=50):
        """加载视频预览帧"""
        if not os.path.exists(video_path):
            print(f"Video file not found: {video_path}")
            return False
            
        try:
            cap = cv2.VideoCapture(video_path)
            frames = []
            
            frame_count = 0
            while True:
                ret, frame = cap.read()
                if not ret or frame_count >= max_frames:
                    break
                    
                # 调整帧大小以适应显示
                frame = cv2.resize(frame, (640, 480))
                frames.append(frame)
                frame_count += 1
                
            cap.release()
            
            with StreamHandler.frame_lock:
                StreamHandler.video_frames = frames
                StreamHandler.video_frame_index = 0
                
            print(f"Loaded {len(frames)} frames for video preview")
            self.video_loaded = True
            return True
            
        except Exception as e:
            print(f"Error loading video preview: {e}")
            return False
    
    def set_video_playback_mode(self, enabled):
        """设置视频播放模式"""
        with StreamHandler.frame_lock:
            StreamHandler.show_video_playback = enabled
            if enabled:
                StreamHandler.show_video_preview = False
    
    def is_video_loaded(self):
        """检查是否已加载视频"""
        return self.video_loaded
        
    def stop(self):
        if self.server:
            self.server.shutdown()