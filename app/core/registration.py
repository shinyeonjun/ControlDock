"""
PC 등록 관리
"""
import time
from typing import Optional, Dict, Any
from config.config import Config
from client.api_client import APIClient
from utils.system_info import SystemInfo

class RegistrationManager:
    """등록 관리 클래스"""
    
    def __init__(self, config: Config, client: APIClient):
        self.config = config
        self.client = client
        # 저장된 request_id가 있으면 사용 (TCP로 이미 등록 요청을 보낸 경우)
        self.request_id: Optional[str] = config.get('registration_request_id')
        self.startup_callback = None  # 시작 프로그램 등록 콜백 (메인 스레드에서 실행)
    
    def set_startup_callback(self, callback):
        """시작 프로그램 등록 콜백 설정"""
        self.startup_callback = callback
    
    def request_registration(self) -> Optional[str]:
        """등록 승인 요청"""
        # 이미 request_id가 있으면 다시 요청하지 않음
        if self.request_id:
            print(f"이미 등록 요청이 있습니다. Request ID: {self.request_id}")
            return self.request_id
        
        # HTTP API로 등록 요청 (TCP를 사용하지 않는 경우)
        system_info = SystemInfo.get_basic_info()
        
        response = self.client.register_request(system_info)
        if response and response.get('success'):
            self.request_id = response.get('request_id')
            # config에 저장
            self.config.set('registration_request_id', self.request_id)
            print(f"등록 요청 성공: {self.request_id}")
            return self.request_id
        else:
            print(f"등록 요청 실패: {response}")
            return None
    
    def check_status(self) -> Optional[str]:
        """등록 상태 확인
        
        Returns:
            'pending': 대기 중
            'approved': 승인됨
            'rejected': 거부됨
            'completed': 등록 완료
            None: 오류
        """
        if not self.request_id:
            return None
        
        response = self.client.check_registration_status(self.request_id)
        if response and response.get('success'):
            return response.get('status')  # 'pending', 'approved', 'rejected', 'completed'
        return None
    
    def complete_registration(self) -> Optional[Dict[str, Any]]:
        """등록 완료 (상세 정보 전송)"""
        if not self.request_id:
            return None
        
        system_info = SystemInfo.get_system_info()
        response = self.client.complete_registration(self.request_id, system_info)
        
        if response and response.get('success'):
            # agent_id와 agent_token 저장
            agent_id = response.get('agent_id')
            agent_token = response.get('agent_token')
            
            if agent_id:
                self.config.agent_id = agent_id
            if agent_token:
                # 토큰은 메모리에만 캐싱 (로컬 파일 저장 안 함)
                self.config.set_agent_token(agent_token)
            
            print(f"등록 완료: agent_id={agent_id}")
            
            # 재부팅 후 자동 실행을 위한 시작 프로그램 등록
            # 사용자가 등록 요청 시 선택한 경우 자동으로 등록
            should_register = self.config.get('should_register_startup', False)
            
            if should_register:
                print("사용자가 등록 요청 시 시작 프로그램 등록을 선택했습니다. 등록을 진행합니다...")
                # 시작 프로그램 등록 실행
                if self._register_startup():
                    print("시작 프로그램 등록 완료. 재부팅 후 자동으로 실행됩니다.")
                else:
                    print("시작 프로그램 등록 실패.")
                # 설정에서 제거 (한 번만 등록)
                self.config.set('should_register_startup', False)
            else:
                print("시작 프로그램 등록을 선택하지 않았으므로 등록하지 않습니다.")
            
            return response
        
        return None
    
    def _ask_and_register_startup(self):
        """사용자에게 시작 프로그램 등록 여부를 물어보고 등록"""
        try:
            from PyQt6.QtWidgets import QApplication, QMessageBox
            from PyQt6.QtCore import QTimer, QThread
            import sys
            import threading
            
            # 현재 스레드가 메인 스레드인지 확인
            is_main_thread = threading.current_thread() is threading.main_thread()
            
            def show_startup_dialog():
                """시작 프로그램 등록 다이얼로그 표시"""
                try:
                    print("show_startup_dialog 함수 호출됨")
                    app = QApplication.instance()
                    if app is None:
                        print("QApplication이 없어서 생성합니다...")
                        app = QApplication(sys.argv)
                    else:
                        print(f"QApplication 인스턴스 발견: {app}")
                    
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
                    msg.activateWindow()  # 창 활성화
                    msg.raise_()  # 창을 맨 앞으로
                    
                    print("다이얼로그 표시 중...")
                    result = msg.exec()
                    print(f"다이얼로그 결과: {result}")
                    
                    if result == QMessageBox.StandardButton.Yes.value:
                        print("사용자가 시작 프로그램 등록을 승인했습니다.")
                        if self._register_startup():
                            print("시작 프로그램 등록 완료. 재부팅 후 자동으로 실행됩니다.")
                            
                            # 성공 메시지 표시
                            msg2 = QMessageBox()
                            msg2.setWindowTitle('등록 완료')
                            msg2.setText('시작 프로그램에 등록되었습니다.')
                            msg2.setInformativeText('재부팅 후 자동으로 실행됩니다.')
                            msg2.setIcon(QMessageBox.Icon.Information)
                            msg2.exec()
                        else:
                            print("시작 프로그램 등록 실패.")
                            
                            # 실패 메시지 표시
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
            
            app = QApplication.instance()
            if app is None:
                print("QApplication이 없어서 생성합니다...")
                app = QApplication(sys.argv)
            else:
                print(f"QApplication 인스턴스 발견: {app}")
            
            print(f"현재 스레드가 메인 스레드인가? {is_main_thread}")
            if is_main_thread:
                # 메인 스레드에서 직접 실행
                print("메인 스레드에서 직접 실행")
                show_startup_dialog()
            else:
                # 백그라운드 스레드에서 실행 중이면 QTimer로 메인 스레드로 전달
                print("백그라운드 스레드에서 실행 중. QTimer로 메인 스레드로 전달")
                # QApplication의 메인 스레드로 전달
                if app:
                    # QTimer를 사용하여 메인 이벤트 루프에서 실행
                    timer = QTimer()
                    timer.setSingleShot(True)
                    timer.timeout.connect(show_startup_dialog)
                    timer.start(100)
                    print("QTimer 설정 완료 (100ms 후 실행)")
                else:
                    print("QApplication이 없어서 직접 실행 시도")
                    show_startup_dialog()
                
        except Exception as e:
            print(f"시작 프로그램 등록 확인 중 오류: {e}")
            import traceback
            traceback.print_exc()
    
    def _register_startup(self):
        """시작 프로그램에 등록 (재부팅 후 자동 실행) - 플랫폼별 처리"""
        import platform
        
        if platform.system() == 'Windows':
            return self._register_startup_windows()
        elif platform.system() == 'Darwin':  # macOS
            return self._register_startup_mac()
        else:
            print(f"{platform.system()} 플랫폼은 아직 지원하지 않습니다.")
            return False
    
    def _register_startup_windows(self):
        """Windows 시작 프로그램에 등록 (재부팅 후 자동 실행)"""
        try:
            import os
            import sys
            from pathlib import Path
            
            # 현재 실행 파일 경로 찾기
            exe_path = None
            python_exe = None
            main_path = None
            
            if getattr(sys, 'frozen', False):
                # PyInstaller로 빌드된 경우
                exe_path = sys.executable
            else:
                # 개발 모드인 경우
                python_exe = sys.executable
                script_path = Path(__file__).resolve()
                main_path = script_path.parent.parent / 'main.py'
                if not main_path.exists():
                    print(f"main.py를 찾을 수 없습니다: {main_path}")
                    return False
            
            # 시작 프로그램 폴더 경로
            startup_folder = os.path.join(
                os.environ.get('APPDATA', ''),
                r'Microsoft\Windows\Start Menu\Programs\Startup'
            )
            
            # 바로가기 파일 이름
            shortcut_name = "OpsHubAgent.lnk"
            shortcut_path = os.path.join(startup_folder, shortcut_name)
            
            # 이미 등록되어 있는지 확인
            if os.path.exists(shortcut_path):
                print(f"이미 시작 프로그램에 등록되어 있습니다: {shortcut_path}")
                return True
            
            # 바로가기 생성
            try:
                import win32com.client
                shell = win32com.client.Dispatch("WScript.Shell")
                shortcut = shell.CreateShortCut(shortcut_path)
                
                if getattr(sys, 'frozen', False):
                    # EXE 파일인 경우
                    shortcut.Targetpath = exe_path
                    shortcut.WorkingDirectory = os.path.dirname(exe_path)
                else:
                    # Python 스크립트인 경우
                    # 배치 파일을 생성하여 실행
                    bat_path = os.path.join(startup_folder, "OpsHubAgent.bat")
                    
                    # 가상 환경 확인 (venv가 있는 경우)
                    venv_python = None
                    script_dir = os.path.dirname(main_path)
                    # app 폴더의 상위 폴더에 venv가 있을 수 있음
                    parent_dir = os.path.dirname(script_dir)
                    venv_python_exe = os.path.join(parent_dir, 'venv', 'Scripts', 'python.exe')
                    if os.path.exists(venv_python_exe):
                        venv_python = venv_python_exe
                        print(f"가상 환경 Python 발견: {venv_python}")
                    
                    with open(bat_path, 'w', encoding='utf-8') as f:
                        f.write('@echo off\n')
                        f.write(f'cd /d "{script_dir}"\n')
                        # 가상 환경이 있으면 사용, 없으면 시스템 Python 사용
                        if venv_python:
                            f.write(f'"{venv_python}" "{main_path}"\n')
                        else:
                            f.write(f'"{python_exe}" "{main_path}"\n')
                    
                    shortcut.Targetpath = bat_path
                    shortcut.WorkingDirectory = script_dir
                
                shortcut.save()
                print(f"시작 프로그램에 등록되었습니다: {shortcut_path}")
                print("재부팅 후 자동으로 실행됩니다.")
                return True
            except ImportError:
                print("win32com 모듈을 사용할 수 없습니다.")
                print("pywin32 패키지를 설치하세요: pip install pywin32")
                return False
            except Exception as e:
                print(f"시작 프로그램 등록 실패: {e}")
                import traceback
                traceback.print_exc()
                return False
                
        except Exception as e:
            print(f"시작 프로그램 등록 중 오류: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _register_startup_mac(self):
        """Mac 시작 프로그램에 등록 (재부팅 후 자동 실행) - LaunchAgent 사용"""
        try:
            import os
            import sys
            import json
            from pathlib import Path
            
            # LaunchAgent plist 파일 경로
            home = os.path.expanduser("~")
            launch_agents_dir = os.path.join(home, "Library", "LaunchAgents")
            plist_name = "com.opshub.agent.plist"
            plist_path = os.path.join(launch_agents_dir, plist_name)
            
            # 이미 등록되어 있는지 확인
            if os.path.exists(plist_path):
                print(f"이미 시작 프로그램에 등록되어 있습니다: {plist_path}")
                return True
            
            # 실행 파일 경로 찾기
            program_arguments = []
            
            if getattr(sys, 'frozen', False):
                # .app 번들인 경우
                # PyInstaller로 빌드된 경우 sys.executable이 .app/Contents/MacOS/OpsHubAgent 경로
                executable_path = sys.executable
                program_arguments = [executable_path]
            else:
                # 개발 모드인 경우
                python_exe = sys.executable
                script_path = Path(__file__).resolve()
                main_path = script_path.parent.parent / 'main.py'
                if not main_path.exists():
                    print(f"main.py를 찾을 수 없습니다: {main_path}")
                    return False
                
                # 가상 환경 확인
                venv_python = None
                script_dir = os.path.dirname(main_path)
                parent_dir = os.path.dirname(script_dir)
                venv_python_exe = os.path.join(parent_dir, 'venv', 'bin', 'python3')
                if os.path.exists(venv_python_exe):
                    venv_python = venv_python_exe
                    print(f"가상 환경 Python 발견: {venv_python}")
                
                python_path = venv_python if venv_python else python_exe
                program_arguments = [python_path, str(main_path)]
            
            # LaunchAgent 디렉토리 생성
            os.makedirs(launch_agents_dir, exist_ok=True)
            
            # 로그 디렉토리 생성
            log_dir = os.path.join(home, 'Library', 'Logs', 'OpsHubAgent')
            os.makedirs(log_dir, exist_ok=True)
            
            # plist 파일 생성
            plist_content = {
                'Label': 'com.opshub.agent',
                'ProgramArguments': program_arguments,
                'RunAtLoad': True,
                'KeepAlive': False,
                'StandardOutPath': os.path.join(log_dir, 'stdout.log'),
                'StandardErrorPath': os.path.join(log_dir, 'stderr.log'),
            }
            
            # plist 파일을 XML 형식으로 작성
            import plistlib
            with open(plist_path, 'wb') as f:
                plistlib.dump(plist_content, f)
            
            print(f"LaunchAgent plist 파일 생성: {plist_path}")
            
            # LaunchAgent 로드
            try:
                import subprocess
                result = subprocess.run(
                    ['launchctl', 'load', plist_path],
                    capture_output=True,
                    text=True,
                    check=False
                )
                
                if result.returncode == 0:
                    print("LaunchAgent가 성공적으로 로드되었습니다.")
                    print("재부팅 후 자동으로 실행됩니다.")
                    return True
                else:
                    print(f"LaunchAgent 로드 실패: {result.stderr}")
                    print("수동으로 로드하려면:")
                    print(f"  launchctl load {plist_path}")
                    return False
            except Exception as e:
                print(f"LaunchAgent 로드 중 오류: {e}")
                print("수동으로 로드하려면:")
                print(f"  launchctl load {plist_path}")
                return False
                
        except Exception as e:
            print(f"Mac 시작 프로그램 등록 중 오류: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _check_and_install_service(self):
        """Windows 서비스 설치 확인 및 설치"""
        try:
            import win32serviceutil
            import win32service
            
            service_name = "OpsHubAgent"
            
            # 서비스 설치 여부 확인
            try:
                win32serviceutil.QueryServiceStatus(service_name)
                print("Windows 서비스가 이미 설치되어 있습니다.")
                return
            except win32service.error as e:
                # 서비스가 없으면 설치 진행
                if e.winerror == 1060:  # ERROR_SERVICE_DOES_NOT_EXIST
                    print("Windows 서비스가 설치되지 않았습니다. 서비스 설치를 시도합니다...")
                    
                    # 사용자에게 서비스 설치 여부 물어보기
                    try:
                        from PyQt6.QtWidgets import QApplication, QMessageBox
                        from PyQt6.QtCore import QTimer
                        import sys
                        import threading
                        
                        print("서비스 설치 다이얼로그를 표시합니다...")
                        
                        def show_service_dialog():
                            """서비스 설치 다이얼로그 표시"""
                            try:
                                print("다이얼로그 표시 시작...")
                                app = QApplication.instance()
                                if app is None:
                                    print("QApplication 생성 중...")
                                    app = QApplication(sys.argv)
                                
                                print("QMessageBox 생성 중...")
                                msg = QMessageBox()
                                msg.setWindowTitle('Windows 서비스 설치')
                                msg.setText('등록이 완료되었습니다.')
                                msg.setInformativeText('컴퓨터를 재시작해도 자동으로 실행되도록 Windows 서비스를 설치하시겠습니까?\n\n(관리자 권한이 필요합니다)')
                                msg.setIcon(QMessageBox.Icon.Question)
                                msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                                msg.setDefaultButton(QMessageBox.StandardButton.Yes)
                                
                                # 다이얼로그를 강제로 최상위로 표시
                                msg.setWindowFlags(msg.windowFlags() | msg.windowFlags().WindowStaysOnTopHint)
                                msg.activateWindow()  # 창 활성화
                                msg.raise_()  # 창을 맨 앞으로
                                
                                print("다이얼로그 표시 중...")
                                result = msg.exec()
                                print(f"다이얼로그 결과: {result}")
                                
                                if result == QMessageBox.StandardButton.Yes:
                                    print("사용자가 서비스 설치를 승인했습니다.")
                                    # 서비스 설치 시도
                                    self._install_service()
                                else:
                                    print("사용자가 서비스 설치를 취소했습니다.")
                                    msg2 = QMessageBox()
                                    msg2.setWindowTitle('알림')
                                    msg2.setText('서비스 설치를 건너뜁니다.')
                                    msg2.setInformativeText('나중에 수동으로 설치하려면:\nOpsHubAgent.exe --install\n\n을 관리자 권한으로 실행하세요.')
                                    msg2.setIcon(QMessageBox.Icon.Information)
                                    msg2.exec()
                            except Exception as e:
                                print(f"서비스 설치 다이얼로그 표시 오류: {e}")
                                import traceback
                                traceback.print_exc()
                        
                        app = QApplication.instance()
                        if app is None:
                            print("QApplication이 없습니다. 생성합니다...")
                            app = QApplication(sys.argv)
                        
                        # 현재 스레드가 메인 스레드인지 확인
                        is_main_thread = threading.current_thread() is threading.main_thread()
                        print(f"현재 스레드가 메인 스레드인가? {is_main_thread}")
                        
                        if is_main_thread:
                            # 메인 스레드에서 직접 실행
                            print("메인 스레드에서 다이얼로그 표시")
                            show_service_dialog()
                        else:
                            # 백그라운드 스레드에서 실행 중이면 QTimer로 메인 스레드로 전달
                            print("백그라운드 스레드에서 실행 중. QTimer로 메인 스레드로 전달")
                            # QTimer를 사용하여 메인 스레드에서 실행
                            # QApplication이 실행 중이어야 함
                            if app:
                                QTimer.singleShot(100, show_service_dialog)  # 100ms 후 실행
                                print("QTimer 설정 완료. 이벤트 루프가 실행 중이면 다이얼로그가 표시됩니다.")
                                # QTimer가 실행되도록 이벤트 루프에 알림
                                # 하지만 백그라운드 스레드에서는 app.processEvents()를 호출할 수 없음
                                # 따라서 메인 스레드에서 processEvents()가 호출되어야 함
                            else:
                                # QApplication이 없으면 직접 실행 시도
                                print("QApplication이 없어서 직접 실행 시도")
                                show_service_dialog()
                        
                    except Exception as e:
                        print(f"서비스 설치 확인 중 오류: {e}")
                        import traceback
                        traceback.print_exc()
                        print("나중에 수동으로 서비스를 설치하려면:")
                        print("OpsHubAgent.exe --install")
                        print("을 관리자 권한으로 실행하세요.")
                else:
                    print(f"서비스 확인 중 오류: {e}")
        except ImportError:
            print("win32service 모듈을 사용할 수 없습니다.")
        except Exception as e:
            print(f"서비스 설치 확인 중 오류: {e}")
            import traceback
            traceback.print_exc()
    
    def _install_service(self):
        """Windows 서비스 설치"""
        try:
            import subprocess
            import sys
            import os
            
            # EXE 파일 경로 찾기
            if getattr(sys, 'frozen', False):
                # PyInstaller로 빌드된 경우
                exe_path = sys.executable
            else:
                # 개발 모드
                exe_path = os.path.abspath(sys.executable)
                # main.py 실행 경로로 변경
                main_dir = os.path.dirname(os.path.abspath(__file__))
                main_dir = os.path.dirname(main_dir)  # core -> app
                exe_path = os.path.join(main_dir, 'main.py')
            
            # 서비스 설치 명령 실행
            # 서비스 설치에는 관리자 권한이 필요하므로 subprocess로 실행
            print(f"서비스 설치 중: {exe_path}")
            
            # 서비스 설치를 위해 별도 프로세스로 실행
            # 하지만 관리자 권한이 필요하므로 안내만 제공
            print("\n" + "="*50)
            print("서비스 설치를 위해 관리자 권한이 필요합니다.")
            print("다음 단계를 따라주세요:")
            print("1. EXE 파일을 우클릭하여 '관리자 권한으로 실행' 선택")
            print("2. 또는 명령 프롬프트를 관리자 권한으로 열고:")
            print(f"   {exe_path} --install")
            print("3. 서비스 시작:")
            print(f"   {exe_path} --start")
            print("="*50)
            
            # 자동 설치 시도 (관리자 권한이 있는 경우)
            try:
                result = subprocess.run(
                    [exe_path, '--install'],
                    check=False,
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    print("서비스가 성공적으로 설치되었습니다.")
                    
                    # 서비스 시작 시도
                    try:
                        subprocess.run(
                            [exe_path, '--start'],
                            check=False,
                            capture_output=True,
                            text=True
                        )
                        print("서비스가 시작되었습니다.")
                    except Exception as e:
                        print(f"서비스 시작 실패: {e}")
                        print("수동으로 시작하려면:")
                        print(f"  {exe_path} --start")
                else:
                    print("서비스 설치 실패 (관리자 권한이 필요할 수 있습니다)")
                    print("위의 안내를 따라 수동으로 설치해주세요.")
            except Exception as e:
                print(f"서비스 설치 시도 중 오류: {e}")
                print("위의 안내를 따라 수동으로 설치해주세요.")
                
        except Exception as e:
            print(f"서비스 설치 중 오류: {e}")
    
    def wait_for_approval(self, check_interval: int = 30, timeout: int = 3600) -> bool:
        """승인 대기 (폴링)
        
        Args:
            check_interval: 확인 주기 (초)
            timeout: 타임아웃 (초)
        
        Returns:
            True: 승인 완료, False: 타임아웃 또는 거부
        """
        start_time = time.time()
        
        while True:
            status = self.check_status()
            
            if status == 'approved':
                # 승인됨 -> 등록 완료
                result = self.complete_registration()
                return result is not None
            
            elif status == 'rejected':
                print("등록 요청이 거부되었습니다.")
                return False
            
            elif status == 'completed':
                print("이미 등록이 완료되었습니다.")
                return True
            
            # 타임아웃 확인
            if time.time() - start_time > timeout:
                print(f"승인 대기 타임아웃 ({timeout}초)")
                return False
            
            # 대기 중
            time.sleep(check_interval)
    
    def is_registered(self) -> bool:
        """등록 여부 확인 (agent_id만 체크, 토큰은 서버에서 가져옴)"""
        # agent_id만 있으면 등록된 것으로 간주 (토큰은 서버에서 가져올 수 있음)
        return self.config.agent_id is not None

