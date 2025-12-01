"""
공지 처리 모듈
"""
import json
import threading
from typing import Dict, Any, Optional
from client.tcp_client import TCPClient
from config.config import Config

class AnnouncementHandler:
    """공지 처리 핸들러"""
    
    def __init__(self, config: Config, tcp_client: TCPClient):
        """
        공지 핸들러 초기화
        
        Args:
            config: 설정 객체
            tcp_client: TCP 클라이언트 (ACK 전송용)
        """
        self.config = config
        self.tcp_client = tcp_client
        self.received_announcements = set()  # 수신한 공지 ID 저장 (중복 방지)
    
    def handle_notification(self, notification: Dict[str, Any]):
        """공지 수신 처리"""
        try:
            announcement_id = notification.get('announcement_id')
            title = notification.get('title', '')
            content = notification.get('content', '')
            priority = notification.get('priority', 'normal')
            
            if not announcement_id:
                print("[공지] 공지 ID가 없습니다")
                return
            
            # 중복 수신 방지
            if announcement_id in self.received_announcements:
                print(f"[공지] 이미 수신한 공지입니다: {announcement_id}")
                return
            
            self.received_announcements.add(announcement_id)
            
            # 공지 표시 (GUI)
            self._show_announcement(title, content, priority, announcement_id)
            
            # ACK 전송 (TCP)
            self._send_ack(announcement_id)
            
        except Exception as e:
            print(f"[공지] 공지 처리 오류: {e}")
    
    def _show_announcement(self, title: str, content: str, priority: str, announcement_id: str):
        """공지 표시 (GUI) - 화면 오른쪽 위에 토스트 알림"""
        # 우선순위에 따른 표시 방식 결정
        priority_map = {
            'low': '정보',
            'normal': '공지',
            'high': '중요',
            'urgent': '긴급'
        }
        
        priority_label = priority_map.get(priority, '공지')
        
        print(f"\n{'='*50}")
        print(f"[{priority_label}] {title}")
        print(f"{'='*50}")
        print(content)
        print(f"{'='*50}\n")
        
        # Windows Toast Notification 사용 (QApplication 없이도 작동)
        try:
            self._show_windows_toast(title, content, priority_label, priority)
        except Exception as e:
            print(f"[공지] Windows Toast 실패, PyQt6 토스트 시도: {e}")
            # 폴백: PyQt6 토스트 시도
            try:
                self._show_pyqt6_toast(title, content, priority_label, priority)
            except Exception as e2:
                print(f"[공지] ❌ 모든 토스트 알림 표시 실패: {e2}")
                import traceback
                traceback.print_exc()
    
    def _show_windows_toast(self, title: str, content: str, priority_label: str, priority: str):
        """Windows Toast Notification 표시 (QApplication 불필요)"""
        try:
            import platform
            if platform.system() != 'Windows':
                print(f"[공지] Windows가 아니어서 Toast Notification을 사용할 수 없습니다")
                return
            
            # 방법 1: win10toast 시도 (threaded=False로 변경하여 더 안정적으로)
            try:
                from win10toast import ToastNotifier
                toaster = ToastNotifier()
                
                duration = 10 if priority == 'urgent' else 5
                full_message = f"[{priority_label}] {title}\n{content[:200]}"
                
                # threaded=False로 변경 (exe에서 더 안정적)
                # 별도 스레드에서 실행하여 블로킹 방지
                def show_toast():
                    try:
                        toaster.show_toast(
                            title=f"OpsHub 공지",
                            msg=full_message,
                            duration=duration,
                            threaded=False,  # False로 변경
                            icon_path=None
                        )
                        print(f"[공지] ✅ Windows Toast Notification 표시 완료 (win10toast): {title}")
                    except Exception as e:
                        print(f"[공지] win10toast 실행 오류: {e}")
                        import traceback
                        traceback.print_exc()
                        # 실패 시 MessageBox로 폴백
                        self._show_windows_toast_api(title, content, priority_label, priority)
                
                # 별도 스레드에서 실행 (UI 블로킹 방지)
                threading.Thread(target=show_toast, daemon=True).start()
                return
            except ImportError:
                print(f"[공지] win10toast가 없어 다른 방법 시도...")
            except Exception as e:
                print(f"[공지] win10toast 초기화 오류: {e}, 다른 방법 시도...")
                import traceback
                traceback.print_exc()
            
            # 방법 2: MessageBox 폴백 (항상 작동)
            self._show_windows_toast_api(title, content, priority_label, priority)
        except Exception as e:
            print(f"[공지] Windows Toast Notification 오류: {e}")
            raise
    
    def _show_windows_toast_api(self, title: str, content: str, priority_label: str, priority: str):
        """Windows Toast Notification API 직접 사용"""
        try:
            from win32api import MessageBox
            from win32con import MB_OK, MB_ICONINFORMATION, MB_ICONWARNING, MB_ICONERROR
            
            # 우선순위에 따른 아이콘 선택
            icon_map = {
                'low': MB_ICONINFORMATION,
                'normal': MB_ICONINFORMATION,
                'high': MB_ICONWARNING,
                'urgent': MB_ICONERROR
            }
            icon = icon_map.get(priority, MB_ICONINFORMATION)
            
            message = f"[{priority_label}] {title}\n\n{content}"
            MessageBox(None, message, "OpsHub 공지", MB_OK | icon)
            print(f"[공지] ✅ Windows MessageBox 표시 완료: {title}")
        except Exception as e:
            print(f"[공지] Windows MessageBox 오류: {e}")
            raise
    
    def _show_pyqt6_toast(self, title: str, content: str, priority_label: str, priority: str):
        """PyQt6 토스트 알림 표시 (폴백) - exe에서도 작동하도록 개선"""
        # 별도 스레드에서 QApplication 생성 및 실행
        thread = threading.Thread(
            target=self._show_pyqt6_toast_thread,
            args=(title, content, priority_label, priority),
            daemon=True
        )
        thread.start()
    
    def _show_pyqt6_toast_thread(self, title: str, content: str, priority_label: str, priority: str):
        """PyQt6 토스트 알림 표시 (별도 스레드) - exe 호환"""
        try:
            from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QPushButton
            from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QThread
            from PyQt6.QtGui import QFont
            import sys
            import time
            
            # 별도 스레드에서 QApplication 생성 (exe에서도 작동)
            app = QApplication.instance()
            if app is None:
                # exe에서는 sys.argv가 없을 수 있으므로 빈 리스트 사용
                try:
                    app = QApplication(sys.argv if hasattr(sys, 'argv') else [])
                except:
                    app = QApplication([])
            
            # 토스트 창 생성 및 표시
            toast = self._create_toast_widget(title, content, priority_label, priority, app)
            if toast:
                toast.show()
                toast.raise_()
                toast.activateWindow()
                
                # 자동 닫기 타이머
                auto_close_time = 10000 if priority == 'urgent' else 5000
                QTimer.singleShot(auto_close_time, toast.close)
                
                # 이벤트 루프 실행 (토스트가 표시되는 동안)
                import time
                end_time = time.time() + (auto_close_time / 1000) + 1  # 여유 시간 추가
                while time.time() < end_time:
                    app.processEvents()
                    time.sleep(0.05)  # 50ms 간격으로 이벤트 처리
                    
        except Exception as e:
            print(f"[공지] PyQt6 토스트 스레드 오류: {e}")
            import traceback
            traceback.print_exc()
    
    def _create_toast_widget(self, title: str, content: str, priority_label: str, priority: str, app):
        """토스트 위젯 생성"""
        try:
            from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
            from PyQt6.QtCore import Qt
            from PyQt6.QtGui import QFont
            
            # 우선순위에 따른 색상
            priority_colors = {
                'low': '#2196F3',
                'normal': '#4CAF50',
                'high': '#FF9800',
                'urgent': '#F44336'
            }
            color = priority_colors.get(priority, '#4CAF50')
            
            # 토스트 창 생성
            toast = QWidget()
            toast.setWindowFlags(
                Qt.WindowType.FramelessWindowHint |
                Qt.WindowType.WindowStaysOnTopHint |
                Qt.WindowType.Tool |
                Qt.WindowType.X11BypassWindowManagerHint
            )
            toast.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            toast.setFixedSize(400, 150)
            
            # 레이아웃
            layout = QVBoxLayout()
            layout.setContentsMargins(15, 15, 15, 15)
            layout.setSpacing(8)
            
            # 헤더 레이아웃
            header_layout = QHBoxLayout()
            header_layout.setContentsMargins(0, 0, 0, 0)
            
            # 제목 레이블
            title_label = QLabel(f"[{priority_label}] {title}")
            title_font = QFont()
            title_font.setBold(True)
            title_font.setPointSize(11)
            title_label.setFont(title_font)
            title_label.setStyleSheet(f"color: {color};")
            title_label.setWordWrap(True)
            header_layout.addWidget(title_label)
            
            # 닫기 버튼
            close_btn = QPushButton('×')
            close_btn.setFixedSize(25, 25)
            close_btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(0, 0, 0, 0.1);
                    border: none;
                    border-radius: 12px;
                    font-size: 16px;
                    font-weight: bold;
                    color: #666;
                }
                QPushButton:hover {
                    background-color: rgba(0, 0, 0, 0.2);
                }
            """)
            close_btn.clicked.connect(toast.close)
            header_layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
            
            layout.addLayout(header_layout)
            
            # 내용 레이블
            content_label = QLabel(content[:200] + ('...' if len(content) > 200 else ''))
            content_label.setWordWrap(True)
            content_label.setStyleSheet("color: #333; font-size: 10pt;")
            layout.addWidget(content_label)
            
            toast.setLayout(layout)
            
            # 스타일 설정
            toast.setStyleSheet(f"""
                QWidget {{
                    background-color: rgba(255, 255, 255, 0.95);
                    border-radius: 10px;
                    border: 2px solid {color};
                }}
            """)
            
            # 화면 오른쪽 위에 배치
            screen = app.primaryScreen().geometry()
            x = screen.width() - toast.width() - 20
            y = 20
            toast.move(x, y)
            
            return toast
            
        except Exception as e:
            print(f"[공지] 토스트 위젯 생성 오류: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _show_toast_notification(self, title: str, content: str, priority_label: str, priority: str):
        """토스트 알림 표시 (화면 오른쪽 위) - 메인 스레드에서 실행되어야 함"""
        try:
            from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QPushButton
            from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint
            from PyQt6.QtGui import QFont
            import sys
            
            # QApplication 인스턴스 가져오기
            app = QApplication.instance()
            if app is None:
                print(f"[공지] ⚠️ QApplication이 없어 토스트 알림을 표시할 수 없습니다")
                return
            
            print(f"[공지] QApplication 확인 완료, 토스트 창 생성 시작...")
            
            # 토스트 창 생성
            toast = QWidget()
            toast.setWindowFlags(
                Qt.WindowType.FramelessWindowHint |
                Qt.WindowType.WindowStaysOnTopHint |
                Qt.WindowType.Tool |
                Qt.WindowType.X11BypassWindowManagerHint
            )
            toast.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            toast.setFixedSize(400, 150)
            
            # 레이아웃
            layout = QVBoxLayout()
            layout.setContentsMargins(15, 15, 15, 15)
            layout.setSpacing(8)
            
            # 우선순위에 따른 색상
            priority_colors = {
                'low': '#2196F3',      # 파란색
                'normal': '#4CAF50',   # 초록색
                'high': '#FF9800',     # 주황색
                'urgent': '#F44336'    # 빨간색
            }
            color = priority_colors.get(priority, '#4CAF50')
            
            # 헤더 레이아웃 (제목 + 닫기 버튼)
            from PyQt6.QtWidgets import QHBoxLayout
            header_layout = QHBoxLayout()
            header_layout.setContentsMargins(0, 0, 0, 0)
            
            # 제목 레이블
            title_label = QLabel(f"[{priority_label}] {title}")
            title_font = QFont()
            title_font.setBold(True)
            title_font.setPointSize(11)
            title_label.setFont(title_font)
            title_label.setStyleSheet(f"color: {color};")
            title_label.setWordWrap(True)
            header_layout.addWidget(title_label)
            
            # 닫기 버튼
            close_btn = QPushButton('×')
            close_btn.setFixedSize(25, 25)
            close_btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(0, 0, 0, 0.1);
                    border: none;
                    border-radius: 12px;
                    font-size: 16px;
                    font-weight: bold;
                    color: #666;
                }
                QPushButton:hover {
                    background-color: rgba(0, 0, 0, 0.2);
                }
            """)
            close_btn.clicked.connect(toast.close)
            header_layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
            
            layout.addLayout(header_layout)
            
            # 내용 레이블
            content_label = QLabel(content)
            content_label.setWordWrap(True)
            content_label.setStyleSheet("color: #333; font-size: 10pt;")
            # 내용이 길면 최대 3줄만 표시
            if len(content) > 100:
                content_label.setText(content[:100] + '...')
            layout.addWidget(content_label)
            
            toast.setLayout(layout)
            
            # 스타일 설정 (반투명 배경, 그림자 효과)
            toast.setStyleSheet(f"""
                QWidget {{
                    background-color: rgba(255, 255, 255, 0.95);
                    border-radius: 10px;
                    border: 2px solid {color};
                }}
            """)
            
            # 화면 오른쪽 위에 배치
            screen = app.primaryScreen().geometry()
            x = screen.width() - toast.width() - 20
            y = 20
            toast.move(x, y)
            
            # 페이드인 애니메이션
            fade_in = QPropertyAnimation(toast, b"windowOpacity")
            fade_in.setDuration(300)
            fade_in.setStartValue(0.0)
            fade_in.setEndValue(1.0)
            fade_in.setEasingCurve(QEasingCurve.Type.InOutQuad)
            fade_in.start()
            
            toast.show()
            toast.raise_()
            toast.activateWindow()
            
            # 5초 후 자동 닫기 (긴급은 10초)
            auto_close_time = 10000 if priority == 'urgent' else 5000
            timer = QTimer()
            timer.timeout.connect(lambda: self._fade_out_and_close(toast))
            timer.setSingleShot(True)
            timer.start(auto_close_time)
            
            # 이벤트 루프 실행 (GUI 업데이트)
            app.processEvents()
            
        except Exception as e:
            print(f"[공지] 토스트 알림 표시 오류: {e}")
            import traceback
            traceback.print_exc()
    
    def _fade_out_and_close(self, widget):
        """페이드아웃 후 창 닫기"""
        try:
            from PyQt6.QtCore import QPropertyAnimation, QEasingCurve
            
            fade_out = QPropertyAnimation(widget, b"windowOpacity")
            fade_out.setDuration(300)
            fade_out.setStartValue(1.0)
            fade_out.setEndValue(0.0)
            fade_out.setEasingCurve(QEasingCurve.Type.InOutQuad)
            fade_out.finished.connect(widget.close)
            fade_out.start()
        except:
            widget.close()
    
    def _send_ack(self, announcement_id: str):
        """공지 수신 ACK 전송 (TCP)"""
        try:
            agent_id = self.config.agent_id
            if not agent_id:
                print("[공지] agent_id가 없어 ACK를 전송할 수 없습니다")
                return
            
            # TCP 클라이언트를 통해 ACK 전송
            response = self.tcp_client.send_notification_ack(agent_id, announcement_id)
            
            if response and response.get('success'):
                print(f"[공지] ACK 전송 완료: announcement_id={announcement_id}")
            else:
                print(f"[공지] ACK 전송 실패: announcement_id={announcement_id}")
            
        except Exception as e:
            print(f"[공지] ACK 전송 오류: {e}")

