"""
시스템 트레이 아이콘
"""
import threading
import pystray
from PIL import Image, ImageDraw
from typing import Optional, Callable

class TrayIcon:
    """시스템 트레이 아이콘 클래스"""
    
    def __init__(self, agent_status_callback: Optional[Callable] = None):
        self.icon: Optional[pystray.Icon] = None
        self.agent_status_callback = agent_status_callback
        self.thread: Optional[threading.Thread] = None
    
    def _create_image(self, status: str = 'unknown'):
        """트레이 아이콘 이미지 생성"""
        # 아이콘 색상 (상태에 따라)
        colors = {
            'online': (0, 150, 105),      # 녹색
            'offline': (156, 163, 175),    # 회색
            'pending': (217, 119, 6),      # 주황색
            'unknown': (107, 114, 128)     # 회색
        }
        color = colors.get(status, colors['unknown'])
        
        # 16x16 아이콘 생성
        image = Image.new('RGB', (16, 16), color)
        draw = ImageDraw.Draw(image)
        
        # 간단한 원형 아이콘
        draw.ellipse([2, 2, 14, 14], fill=color, outline=(255, 255, 255))
        
        return image
    
    def _create_menu(self):
        """트레이 메뉴 생성"""
        status = 'unknown'
        if self.agent_status_callback:
            try:
                status = self.agent_status_callback()
            except:
                pass
        
        status_text = {
            'online': '온라인',
            'offline': '오프라인',
            'pending': '등록 대기 중',
            'unknown': '알 수 없음'
        }.get(status, '알 수 없음')
        
        menu = pystray.Menu(
            pystray.MenuItem(f'상태: {status_text}', None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('설정 열기', self._open_settings),
            pystray.MenuItem('로그 보기', self._open_logs),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('종료', self._quit)
        )
        return menu
    
    def _open_settings(self, icon, item):
        """설정 열기"""
        import os
        import subprocess
        config_path = os.path.join(os.getenv('APPDATA', ''), 'OpsHub', 'config.json')
        if os.path.exists(config_path):
            subprocess.Popen(['notepad.exe', config_path])
    
    def _open_logs(self, icon, item):
        """로그 보기"""
        import os
        import subprocess
        log_path = os.path.join(os.getenv('APPDATA', ''), 'OpsHub', 'agent.log')
        if os.path.exists(log_path):
            subprocess.Popen(['notepad.exe', log_path])
        else:
            # 로그 파일이 없으면 메시지 표시
            try:
                from PyQt6.QtWidgets import QMessageBox
                msg = QMessageBox()
                msg.setWindowTitle('로그')
                msg.setText('로그 파일이 없습니다.')
                msg.setIcon(QMessageBox.Icon.Information)
                msg.exec()
            except:
                # PyQt를 사용할 수 없으면 pass
                pass
    
    def _quit(self, icon, item):
        """종료"""
        self.stop()
    
    def start(self, status: str = 'unknown'):
        """트레이 아이콘 시작"""
        if self.icon is not None:
            return
        
        image = self._create_image(status)
        menu = self._create_menu()
        
        self.icon = pystray.Icon(
            "OpsHub Agent",
            image,
            "OpsHub Agent",
            menu
        )
        
        # 별도 스레드에서 실행
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
    
    def _run(self):
        """트레이 아이콘 실행"""
        if self.icon:
            self.icon.run()
    
    def update_status(self, status: str = 'unknown'):
        """상태 업데이트"""
        if self.icon:
            image = self._create_image(status)
            menu = self._create_menu()
            self.icon.icon = image
            self.icon.menu = menu
    
    def stop(self):
        """트레이 아이콘 중지"""
        if self.icon:
            self.icon.stop()
            self.icon = None

