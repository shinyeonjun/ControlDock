"""
OpsHub Agent 메인 엔트리포인트
"""
import sys
import os

# 현재 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.config import Config
from core.agent import Agent
import platform

def run_as_service():
    """서비스로 실행 (Windows 전용)"""
    if platform.system() != 'Windows':
        print("서비스 모드는 Windows에서만 지원됩니다.")
        print("Mac/Linux에서는 LaunchAgent/LaunchDaemon을 사용하세요.")
        sys.exit(1)
    
    try:
        from service.windows_service import OpsHubAgentService
        import win32serviceutil
        
        if len(sys.argv) == 1:
            import servicemanager
            servicemanager.Initialize()
            servicemanager.PrepareToHostSingle(OpsHubAgentService)
            servicemanager.StartServiceCtrlDispatcher()
        else:
            win32serviceutil.HandleCommandLine(OpsHubAgentService)
    except ImportError:
        print("Windows 서비스 모듈을 사용할 수 없습니다.")
        print("pywin32 패키지가 설치되어 있는지 확인하세요.")
        sys.exit(1)

def run_as_console():
    """콘솔 모드로 실행 (디버깅용)"""
    print("OpsHub Agent 시작 (콘솔 모드)")
    print("=" * 50)
    
    try:
        from gui.tray_icon import TrayIcon
        from client.tcp_client import TCPClient
        from utils.system_info import SystemInfo
        
        config = Config()
        
        # 등록 여부 확인
        if not config.agent_id or not config.get_agent_token():
            # 등록되지 않은 경우 등록 승인 확인
            print("등록되지 않은 PC입니다. 등록 승인 창을 표시합니다...")
            
            system_info = SystemInfo.get_basic_info()
            
            def on_approve():
                """등록 승인 처리 - 등록 요청 전송"""
                print("등록 요청 전송 중...")
                print(f"[DEBUG] 서버 설정 확인:")
                print(f"  - server_host: {config.server_host}")
                print(f"  - server_tcp_port: {config.server_tcp_port}")
                print(f"  - server_url: {config.server_url}")
                
                # TCP 클라이언트로 등록 요청 전송
                try:
                    tcp_client = TCPClient(host=config.server_host, port=config.server_tcp_port)
                    print(f"[DEBUG] TCP 클라이언트 생성 완료: {tcp_client.host}:{tcp_client.port}")
                    
                    response = tcp_client.send_registration_request(
                        system_info['hostname'],
                        system_info['os'],
                        config.get('version', '1.0.0')
                    )
                    
                    if response and response.get('success'):
                        request_id = response.get('request_id')
                        print(f"등록 요청 전송 완료: request_id={request_id}")
                        print("대시보드에서 승인을 기다려주세요.")
                        
                        # request_id를 config에 저장 (Agent가 상태 확인할 때 사용)
                        config.set('registration_request_id', request_id)
                        
                        # 등록 요청 완료 알림 다이얼로그 표시
                        from PyQt6.QtWidgets import QApplication, QMessageBox
                        msg = QMessageBox()
                        msg.setWindowTitle('등록 요청 전송 완료')
                        msg.setText(f'등록 요청이 전송되었습니다.\n\n요청 ID: {request_id}\n호스트명: {system_info["hostname"]}')
                        msg.setInformativeText('대시보드에서 관리자가 승인하면 등록이 완료됩니다.')
                        msg.setIcon(QMessageBox.Icon.Information)
                        msg.exec()
                    else:
                        error = response.get('error', '알 수 없는 오류') if response else '서버 연결 실패'
                        print(f"등록 요청 실패: {error}")
                        print(f"[DEBUG] 응답 내용: {response}")
                        
                        # 오류 메시지 표시
                        from PyQt6.QtWidgets import QApplication, QMessageBox
                        msg = QMessageBox()
                        msg.setWindowTitle('등록 요청 실패')
                        msg.setText(f'등록 요청 전송에 실패했습니다.\n\n오류: {error}\n\n서버: {config.server_host}:{config.server_tcp_port}')
                        msg.setInformativeText('서버가 실행 중인지 확인하고, 방화벽 설정을 확인해주세요.')
                        msg.setIcon(QMessageBox.Icon.Warning)
                        msg.exec()
                except Exception as e:
                    error_msg = f"TCP 클라이언트 생성 오류: {e}"
                    print(f"[ERROR] {error_msg}")
                    import traceback
                    traceback.print_exc()
                    
                    # 오류 메시지 표시
                    from PyQt6.QtWidgets import QApplication, QMessageBox
                    msg = QMessageBox()
                    msg.setWindowTitle('등록 요청 실패')
                    msg.setText(f'등록 요청 전송에 실패했습니다.\n\n오류: {error_msg}')
                    msg.setInformativeText(f'서버 설정을 확인해주세요.\n서버: {config.server_host}:{config.server_tcp_port}')
                    msg.setIcon(QMessageBox.Icon.Critical)
                    msg.exec()
            
            def on_cancel():
                """등록 취소"""
                print("등록이 취소되었습니다.")
            
            # 등록 승인 다이얼로그 표시 (시작 프로그램 등록 옵션 포함)
            from gui.registration_dialog import show_registration_dialog
            
            print("등록 승인 다이얼로그 표시 중...")
            approved, register_startup = show_registration_dialog(on_approve, on_cancel)
            
            if not approved:
                print("등록이 취소되었습니다. 프로그램을 종료합니다.")
                sys.exit(0)
            
            # 시작 프로그램 등록 여부를 config에 저장
            if register_startup:
                print("사용자가 시작 프로그램 등록을 선택했습니다.")
                config.set('should_register_startup', True)
            else:
                print("사용자가 시작 프로그램 등록을 선택하지 않았습니다.")
                config.set('should_register_startup', False)
        
        # 트레이 아이콘 시작
        tray_icon = TrayIcon()
        
        # 시작 프로그램 등록 콜백 (메인 스레드에서 실행)
        import threading
        from PyQt6.QtCore import QTimer, QObject, pyqtSignal
        from PyQt6.QtWidgets import QApplication
        
        # sys는 이미 파일 상단에서 import되어 있음
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # 시작 프로그램 등록을 위한 QObject (시그널/슬롯 사용)
        class StartupDialogTrigger(QObject):
            show_dialog_signal = pyqtSignal()  # PyQt6에서는 pyqtSignal 사용
            
            def __init__(self):
                super().__init__()
                self.show_dialog_signal.connect(self._show_dialog)
            
            def _show_dialog(self):
                """메인 스레드에서 실행되는 다이얼로그 표시"""
                show_startup_registration_dialog()
        
        startup_trigger = StartupDialogTrigger()
        
        # 시작 프로그램 등록 다이얼로그를 표시하는 함수
        def show_startup_registration_dialog():
            """시작 프로그램 등록 다이얼로그 표시 (메인 스레드에서 실행)"""
            try:
                print("시작 프로그램 등록 다이얼로그 표시 시작")
                from PyQt6.QtWidgets import QMessageBox
                import os
                from pathlib import Path
                # sys는 이미 파일 상단에서 import되어 있음
                
                app = QApplication.instance()
                if app is None:
                    print("QApplication이 없어서 생성합니다...")
                    app = QApplication(sys.argv)
                
                print("QMessageBox 생성 중...")
                msg = QMessageBox()
                msg.setWindowTitle('자동 실행 설정')
                msg.setText('등록이 완료되었습니다.')
                msg.setInformativeText('컴퓨터를 재시작해도 자동으로 실행되도록 시작 프로그램에 추가하시겠습니까?')
                msg.setIcon(QMessageBox.Icon.Question)
                msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                msg.setDefaultButton(QMessageBox.StandardButton.Yes)
                
                # 다이얼로그를 강제로 최상위로 표시
                msg.setWindowFlags(msg.windowFlags() | 0x00000008)  # WindowStaysOnTopHint
                msg.activateWindow()
                msg.raise_()
                
                print("다이얼로그 표시 중...")
                result = msg.exec()
                print(f"다이얼로그 결과: {result}")
                
                if result == QMessageBox.StandardButton.Yes.value:
                    print("사용자가 시작 프로그램 등록을 승인했습니다.")
                    # 시작 프로그램 등록 실행
                    try:
                        startup_folder = os.path.join(
                            os.environ.get('APPDATA', ''),
                            r'Microsoft\Windows\Start Menu\Programs\Startup'
                        )
                        shortcut_name = "OpsHubAgent.lnk"
                        shortcut_path = os.path.join(startup_folder, shortcut_name)
                        
                        if os.path.exists(shortcut_path):
                            print(f"이미 시작 프로그램에 등록되어 있습니다: {shortcut_path}")
                            success = True
                        else:
                            import win32com.client
                            shell = win32com.client.Dispatch("WScript.Shell")
                            shortcut = shell.CreateShortCut(shortcut_path)
                            
                            if getattr(sys, 'frozen', False):
                                shortcut.Targetpath = sys.executable
                                shortcut.WorkingDirectory = os.path.dirname(sys.executable)
                            else:
                                script_path = Path(__file__).resolve()
                                main_path = script_path
                                python_exe = sys.executable
                                bat_path = os.path.join(startup_folder, "OpsHubAgent.bat")
                                with open(bat_path, 'w', encoding='utf-8') as f:
                                    f.write(f'@echo off\n')
                                    f.write(f'cd /d "{os.path.dirname(main_path)}"\n')
                                    f.write(f'"{python_exe}" "{main_path}"\n')
                                shortcut.Targetpath = bat_path
                                shortcut.WorkingDirectory = os.path.dirname(main_path)
                            
                            shortcut.save()
                            print(f"시작 프로그램에 등록되었습니다: {shortcut_path}")
                            success = True
                    except Exception as e:
                        print(f"시작 프로그램 등록 실패: {e}")
                        import traceback
                        traceback.print_exc()
                        success = False
                    
                    if success:
                        msg2 = QMessageBox()
                        msg2.setWindowTitle('등록 완료')
                        msg2.setText('시작 프로그램에 등록되었습니다.')
                        msg2.setInformativeText('재부팅 후 자동으로 실행됩니다.')
                        msg2.setIcon(QMessageBox.Icon.Information)
                        msg2.exec()
                    else:
                        msg2 = QMessageBox()
                        msg2.setWindowTitle('등록 실패')
                        msg2.setText('시작 프로그램 등록에 실패했습니다.')
                        msg2.setInformativeText('수동으로 등록해주세요.')
                        msg2.setIcon(QMessageBox.Icon.Warning)
                        msg2.exec()
                else:
                    print("사용자가 시작 프로그램 등록을 취소했습니다.")
                    msg2 = QMessageBox()
                    msg2.setWindowTitle('알림')
                    msg2.setText('시작 프로그램 등록을 건너뜁니다.')
                    msg2.setInformativeText('나중에 수동으로 등록할 수 있습니다.')
                    msg2.setIcon(QMessageBox.Icon.Information)
                    msg2.exec()
                    
            except Exception as e:
                print(f"시작 프로그램 등록 다이얼로그 표시 오류: {e}")
                import traceback
                traceback.print_exc()
        
        # 콜백 함수: 시그널을 사용하여 메인 스레드에서 다이얼로그 표시
        def trigger_startup_check():
            """시작 프로그램 등록 확인 트리거"""
            print("=" * 50)
            print("시작 프로그램 등록 확인 트리거 호출됨")
            print(f"현재 스레드: {threading.current_thread().name}")
            print("=" * 50)
            try:
                app = QApplication.instance()
                if app:
                    print("QApplication 인스턴스 발견, 시그널로 메인 스레드에 전달 중...")
                    # 시그널을 emit하여 메인 스레드에서 다이얼로그 표시
                    startup_trigger.show_dialog_signal.emit()
                    print("시그널 emit 완료 (메인 스레드에서 다이얼로그 표시 예정)")
                else:
                    print("QApplication이 없어서 직접 실행 시도")
                    show_startup_registration_dialog()
            except Exception as e:
                print(f"시작 프로그램 등록 트리거 오류: {e}")
                import traceback
                traceback.print_exc()
        
        agent = Agent(config, tray_icon=tray_icon, startup_callback=trigger_startup_check)
        
        # 트레이 아이콘 시작
        tray_icon.start('unknown')
        
        # 에이전트 시작
        agent.start()
        
        print("에이전트가 실행 중입니다. 종료하려면 Ctrl+C를 누르세요.")
        print("트레이 아이콘을 우클릭하여 설정을 변경할 수 있습니다.")
        
        # PyQt 이벤트 루프 실행 (메인 스레드에서 GUI 이벤트 처리)
        # app은 이미 위에서 생성되었음
        import time
        while True:
            if app:
                app.processEvents()  # GUI 이벤트 처리 (다이얼로그 표시 가능)
            time.sleep(0.1)  # 짧은 간격으로 대기
            
    except KeyboardInterrupt:
        print("\n에이전트 종료 중...")
        agent.stop()
        if tray_icon:
            tray_icon.stop()
        print("에이전트가 종료되었습니다.")
    except Exception as e:
        print(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    # 서비스 모드인지 확인
    if '--service' in sys.argv or '--install' in sys.argv or '--remove' in sys.argv:
        run_as_service()
    else:
        # 콘솔 모드
        run_as_console()

