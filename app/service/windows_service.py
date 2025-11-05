"""
Windows 서비스 래퍼
"""
import sys
import win32serviceutil
import win32service
import servicemanager
from core.agent import Agent
from config.config import Config

class OpsHubAgentService(win32serviceutil.ServiceFramework):
    """OpsHub 에이전트 Windows 서비스"""
    
    _svc_name_ = "OpsHubAgent"
    _svc_display_name_ = "OpsHub Agent Service"
    _svc_description_ = "OpsHub PC 원격 관리 에이전트 서비스"
    
    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.agent = None
        self.config = None
    
    def SvcStop(self):
        """서비스 중지"""
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        if self.agent:
            self.agent.stop()
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STOPPED,
            (self._svc_name_, '')
        )
    
    def SvcDoRun(self):
        """서비스 실행"""
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, '')
        )
        
        try:
            self.config = Config()
            # 서비스 모드에서는 트레이 아이콘 없음
            self.agent = Agent(self.config, tray_icon=None)
            self.agent.start()
            
            # 서비스 실행 유지
            while True:
                import time
                time.sleep(1)
                
        except Exception as e:
            servicemanager.LogErrorMsg(f"서비스 실행 오류: {e}")

def main():
    """서비스 진입점"""
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(OpsHubAgentService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(OpsHubAgentService)

if __name__ == '__main__':
    main()

