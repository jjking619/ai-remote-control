import cv2
import time
import sys
import os
import threading
# 眼睛检测器导入（MediaPipe 版本）
from eye_detector_mediapipe import MediaPipeEyeDetector
# 动作控制器导入
from action_controller_simple import SimpleActionController, ControlMode
# 媒体控制器导入（处理VLC依赖问题）
from media_controller_simple_fallback import SimpleMediaController
# 流媒体服务器
from stream_server import StreamServer
from stream_server import StreamHandler

class SimpleEyeRemote:
    def __init__(self):
        # 初始化各模块
        self.eye_detector = MediaPipeEyeDetector()
        self.action_controller = SimpleActionController()
        self.media_controller = SimpleMediaController()
        
        # 流媒体服务器
        self.stream_server = StreamServer()
        
        # 摄像头对象
        self.cap = None
        
        # 运行状态
        self.running = False
        self.show_debug = True
        self.show_landmarks = True  # 是否显示关键点
        
        # 性能统计
        self.frame_count = 0
        self.start_time = time.time()
        
        # 多线程相关
        self.recognition_thread = None
        self.video_thread = None
        self.document_thread = None
        
        # 视频播放状态跟踪
        self.last_video_status = False
        self.pending_video_command = None  # 待执行的视频命令
        self.pending_document_command = None  # 待执行的文档命令
        self.pending_mode_switch = None  # 待执行的模式切换
        
        # 文档相关
        self.test_pdf = "test.pdf"  # 测试PDF文件名
        
        # 自动加载测试视频
        self.auto_load_test_video()
        
    def auto_load_test_video(self):
        """自动加载测试视频"""
        test_videos = ["test.mp4", "test.MP4", "video.mp4", "video.MP4"]
        for video_file in test_videos:
            if os.path.exists(video_file):
                if self.media_controller.load_video(video_file):
                    print(f"自动加载测试视频: {video_file}")
                    # 同时加载视频预览到流媒体服务器
                    if self.stream_server.load_video_preview(video_file):
                        print("视频预览已加载到流媒体服务器")
                    break
        else:
            print("未找到测试视频文件 (test.mp4)")
    
    # 在main_simple.py中修改摄像头初始化
    def initialize_camera(self):
        """初始化摄像头"""
        try:
            self.cap = cv2.VideoCapture(2)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.cap.set(cv2.CAP_PROP_FPS, 30)
            
            if self.cap.isOpened():
                print("Camera initialized successfully")
                return True
            else:
                print("Failed to open camera")
                return False
                
        except Exception as e:
            print(f"Camera initialization error: {e}")
            return False
    
    def process_control_loop(self):
        """主控制循环"""
        if not self.initialize_camera():
            return
        
        # 启动流媒体服务器
        self.stream_server.start()
        
        self.running = True
        print("AI Eye Remote Control started successfully!")
        print("Please open http://<device_ip>:8080 in browser to view real-time video")
        print("Control instructions:")
        print("  Ctrl+C - Exit program")
        
        # 创建并启动各个线程
        self.recognition_thread = threading.Thread(target=self._recognition_loop, daemon=True)
        self.video_thread = threading.Thread(target=self._video_processing_loop, daemon=True)
        self.document_thread = threading.Thread(target=self._document_processing_loop, daemon=True)
        
        self.recognition_thread.start()
        self.video_thread.start()
        self.document_thread.start()
        
        try:
            while self.running:
                # 主循环可以做其他事情，比如监控状态
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            print("Program interrupted by user")
        finally:
            self.cleanup()

    def _recognition_loop(self):
        """实时识别线程"""
        print("Starting recognition thread...")
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                print("Failed to read camera frame")
                time.sleep(1)
                continue
            
            # 检测眼睛状态
            detection_result = self.eye_detector.detect_eyes_state(frame)
            
            # 处理动作
            command = self.action_controller.process_detection(detection_result)
            
            # 执行命令
            if command:
                self.execute_command(command)
            
            # 添加调试信息到帧
            visualized_frame = frame.copy()
            if self.show_landmarks:
                self.eye_detector.draw_landmarks(visualized_frame, detection_result)
            visualized_frame = self.draw_debug_info(visualized_frame, detection_result, command)
            
            # 发送到流媒体服务器（始终显示摄像头画面）
            self.stream_server.update_frame(visualized_frame)
            
            # 显示调试信息到终端
            if self.show_debug and self.frame_count % 30 == 0:  # 每30帧打印一次
                self.print_debug_info(detection_result, command)
            
            # 性能统计
            self.frame_count += 1
            
            # 控制处理速度
            time.sleep(0.03)  # 约30fps
    
    def _video_processing_loop(self):
        """视频处理线程"""
        print("Starting video processing thread...")
        while self.running:
            # 检查视频播放状态变化
            current_video_status = self.media_controller.get_video_status()
            
            # 如果视频状态发生变化
            if current_video_status != self.last_video_status:
                if current_video_status:
                    print("视频开始播放")
                else:
                    print("视频停止/暂停")
                
                self.last_video_status = current_video_status
            
            # 检查来自Web界面的命令
            with StreamHandler.frame_lock:
                if StreamHandler.pending_video_command:
                    self.pending_video_command = StreamHandler.pending_video_command
                    StreamHandler.pending_video_command = None
                if StreamHandler.pending_document_command:
                    self.pending_document_command = StreamHandler.pending_document_command
                    StreamHandler.pending_document_command = None
                if StreamHandler.pending_mode_switch:
                    self.pending_mode_switch = StreamHandler.pending_mode_switch
                    StreamHandler.pending_mode_switch = None
            
            # 处理待执行的视频命令
            if self.pending_video_command:
                print(f"执行视频命令: {self.pending_video_command}")
                if self.pending_video_command == "play":
                    self.media_controller.play_video()
                elif self.pending_video_command == "pause":
                    self.media_controller.pause_video()
                elif self.pending_video_command == "stop":
                    self.media_controller.stop_video()
                    
                self.pending_video_command = None
            
            # 处理模式切换
            if self.pending_mode_switch:
                if self.pending_mode_switch == "video":
                    self.action_controller.switch_mode(ControlMode.VIDEO)
                    print("切换到视频模式")
                elif self.pending_mode_switch == "document":
                    self.action_controller.switch_mode(ControlMode.DOCUMENT)
                    # 切换到文档模式时自动打开PDF文档
                    self.auto_open_test_pdf()
                    print("切换到文档模式")
                self.pending_mode_switch = None
            
            time.sleep(0.1)
    
    def _document_processing_loop(self):
        """文档处理线程"""
        print("Starting document processing thread...")
        while self.running:
            # 检查来自Web界面的文档命令
            with StreamHandler.frame_lock:
                if StreamHandler.pending_document_command:
                    self.pending_document_command = StreamHandler.pending_document_command
                    StreamHandler.pending_document_command = None
                if StreamHandler.pending_open_pdf:
                    # 处理打开PDF命令
                    pdf_path = StreamHandler.pending_open_pdf
                    StreamHandler.pending_open_pdf = None
                    if pdf_path:
                        print(f"打开PDF文档: {pdf_path}")
                        self.media_controller.open_pdf(pdf_path)
            
            # 处理待执行的文档命令
            if self.pending_document_command:
                print(f"执行文档命令: {self.pending_document_command}")
                self.media_controller.control_document(self.pending_document_command)
                self.pending_document_command = None
            
            time.sleep(0.1)
    
    def auto_open_test_pdf(self):
        """自动打开测试PDF文档"""
        test_pdfs = [self.test_pdf, "document.pdf", "test.pdf"]
        for pdf_file in test_pdfs:
            if os.path.exists(pdf_file):
                print(f"自动打开测试PDF文档: {pdf_file}")
                self.media_controller.open_pdf(pdf_file)
                return
        else:
            print(f"未找到测试PDF文档 ({self.test_pdf})")
    
    def print_debug_info(self, detection_result, last_command):
        """打印调试信息到终端"""
        print(f"\n=== Frame {self.frame_count} ===")
        print(f"Mode: {self.action_controller.mode.value}")
        print(f"Face: {'Yes' if detection_result['face_detected'] else 'No'}")
        print(f"Eyes: {'Closed' if detection_result['eyes_closed'] else 'Open'}")
        print(f"Gazing: {'Yes' if detection_result['is_gazing'] else 'No'}")
        if detection_result['vertical_movement']:
            print(f"Vertical Movement: {detection_result['vertical_movement']}")
        elif detection_result['face_detected']:
            print("Vertical Movement: None (未检测到足够移动)")
        if detection_result['eye_center']:
            print(f"Eye Center: ({detection_result['eye_center'][0]:.1f}, {detection_result['eye_center'][1]:.1f})")
        if detection_result['left_ear'] > 0 and detection_result['right_ear'] > 0:
            print(f"Left EAR: {detection_result['left_ear']:.2f}, Right EAR: {detection_result['right_ear']:.2f}")
        print(f"Last Command: {last_command if last_command else 'None'}")
        print(f"Video Status: {'Playing' if self.media_controller.get_video_status() else 'Paused/Stopped'}")
        print(f"Video Preview: {'Loaded' if self.stream_server.is_video_loaded() else 'Not loaded'}")
        print(f"FPS: {self.calculate_fps():.1f}")
        
    def execute_command(self, command):
        """执行控制命令"""
        if self.action_controller.mode == ControlMode.VIDEO:
            if command == "play":
                # 直接执行播放命令
                self.media_controller.play_video()
                print("视频开始播放")
            elif command == "pause":
                # 直接执行暂停命令
                self.media_controller.pause_video()
                print("视频暂停播放")
        elif self.action_controller.mode == ControlMode.DOCUMENT:
            self.media_controller.control_document(command)
    
    def draw_debug_info(self, frame, detection_result, last_command):
        """在画面上绘制调试信息"""
        h, w = frame.shape[:2]
        
        # 绘制状态信息
        status_lines = [
            f"Mode: {self.action_controller.mode.value}",
            f"Face: {'Yes' if detection_result['face_detected'] else 'No'}",
            f"Eyes: {'Closed' if detection_result['eyes_closed'] else 'Open'}",
            f"Gazing: {'Yes' if detection_result['is_gazing'] else 'No'}",
            f"Video: {'Playing' if self.media_controller.get_video_status() else 'Paused'}",
            f"Frame: {self.frame_count} FPS: {self.calculate_fps():.1f}"
        ]
        
        for i, line in enumerate(status_lines):
            y_pos = 30 + i * 25
            cv2.putText(frame, line, (10, y_pos), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        return frame
    
    def calculate_fps(self):
        """计算实时FPS"""
        elapsed = time.time() - self.start_time
        return self.frame_count / elapsed if elapsed > 0 else 0
    
    def cleanup(self):
        """清理资源"""
        # 停止所有线程
        self.running = False
        
        if self.cap:
            self.cap.release()
        # 停止视频播放
        if self.media_controller:
            self.media_controller.stop_video()
        # 停止流媒体服务器
        if self.stream_server:
            self.stream_server.stop()
        print("Program exited")

if __name__ == "__main__":
    controller = SimpleEyeRemote()
    controller.process_control_loop()