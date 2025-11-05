"""
OpsHub Agent 메인 엔트리포인트
"""
import sys
import os

# 현재 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.config import Config
from core.agent import Agent
from service.windows_service import OpsHubAgentService
import win32serviceutil

def run_as_service():
    """서비스로 실행"""
    if len(sys.argv) == 1:
        import servicemanager
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(OpsHubAgentService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(OpsHubAgentService)

def run_as_console():
    """콘솔 모드로 실행 (디버깅용)"""
    print("OpsHub Agent 시작 (콘솔 모드)")
    print("=" * 50)
    
    try:
        from gui.tray_icon import TrayIcon
        from gui.registration_dialog import RegistrationDialog
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
                
                # TCP 클라이언트로 등록 요청 전송
                tcp_client = TCPClient(host=config.server_host, port=config.server_tcp_port)
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
                    
                    # 오류 메시지 표시
                    from PyQt6.QtWidgets import QApplication, QMessageBox
                    msg = QMessageBox()
                    msg.setWindowTitle('등록 요청 실패')
                    msg.setText(f'등록 요청 전송에 실패했습니다.\n\n오류: {error}')
                    msg.setIcon(QMessageBox.Icon.Warning)
                    msg.exec()
            
            def on_cancel():
                """등록 취소"""
                print("등록이 취소되었습니다.")
            
            # 등록 승인 다이얼로그 표시 (PyQt)
            from PyQt6.QtWidgets import QApplication
            import sys
            
            # QApplication이 없으면 생성
            app = QApplication.instance()
            if app is None:
                app = QApplication(sys.argv)
            
            dialog = RegistrationDialog(on_approve, on_cancel)
            approved = dialog.exec()
            
            if not approved:
                print("등록이 취소되었습니다. 프로그램을 종료합니다.")
                sys.exit(0)
        
        # 트레이 아이콘 시작
        tray_icon = TrayIcon()
        
        # 시작 프로그램 등록 콜백 (메인 스레드에서 실행)
        from PyQt6.QtCore import QObject, pyqtSignal
        from PyQt6.QtWidgets import QApplication
        
        # 시작 프로그램 등록을 위한 시그널 클래스
        class StartupSignal(QObject):
            show_dialog = pyqtSignal()
        
        startup_signal = StartupSignal()
        
        # 시작 프로그램 등록 콜백 (메인 스레드에서 실행)
        def check_startup_register():
            """시작 프로그램 등록 확인 (메인 스레드에서 실행)"""
            try:
                print("시작 프로그램 등록 확인 시작 (메인 스레드)")
                from core.registration import RegistrationManager
                from client.api_client import APIClient
                
                # RegistrationManager 인스턴스를 생성하여 시작 프로그램 등록 확인
                api_client = APIClient(config)
                registration = RegistrationManager(config, api_client)
                print("RegistrationManager 인스턴스 생성 완료")
                registration._ask_and_register_startup()
                print("_ask_and_register_startup 호출 완료")
            except Exception as e:
                print(f"시작 프로그램 등록 확인 중 오류: {e}")
                import traceback
                traceback.print_exc()
        
        # 시그널 연결
        print("시그널 연결 중...")
        startup_signal.show_dialog.connect(check_startup_register)
        print("시그널 연결 완료")
        
        # 간단한 콜백 함수 (시그널 발생)
        def trigger_startup_check():
            """시작 프로그램 등록 확인 트리거"""
            print("시작 프로그램 등록 확인 트리거 호출됨")
            try:
                startup_signal.show_dialog.emit()
                print("시그널 emit 완료")
            except Exception as e:
                print(f"시그널 emit 실패: {e}")
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
        app = QApplication.instance()
        if app:
            # QApplication 이벤트 루프 실행
            import time
            while True:
                app.processEvents()  # GUI 이벤트 처리 (다이얼로그 표시 가능)
                time.sleep(0.1)  # 짧은 간격으로 대기
        else:
            # QApplication이 없으면 일반 대기
            import time
            while True:
                time.sleep(1)
            
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

