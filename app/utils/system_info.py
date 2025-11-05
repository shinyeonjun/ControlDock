"""
PC 시스템 정보 수집
"""
import platform
import socket
import psutil
from typing import Dict, Any

class SystemInfo:
    """시스템 정보 수집 클래스"""
    
    @staticmethod
    def get_hostname() -> str:
        """호스트명 가져오기"""
        return socket.gethostname()
    
    @staticmethod
    def get_os_info() -> str:
        """OS 정보 가져오기"""
        system = platform.system()
        release = platform.release()
        version = platform.version()
        
        if system == 'Windows':
            # Windows 버전 정보
            try:
                import winreg
                key = winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"
                )
                product_name = winreg.QueryValueEx(key, "ProductName")[0]
                winreg.CloseKey(key)
                return f"{product_name} {release}"
            except Exception:
                return f"Windows {release}"
        else:
            return f"{system} {release}"
    
    @staticmethod
    def get_system_info() -> Dict[str, Any]:
        """전체 시스템 정보 수집"""
        return {
            'hostname': SystemInfo.get_hostname(),
            'os': SystemInfo.get_os_info(),
            'platform': platform.platform(),
            'architecture': platform.machine(),
            'processor': platform.processor(),
            'cpu_count': psutil.cpu_count(),
            'memory_total': psutil.virtual_memory().total,
            'disk_total': sum(disk.total for disk in psutil.disk_partitions() if disk.fstype),
        }
    
    @staticmethod
    def get_basic_info() -> Dict[str, str]:
        """기본 정보만 (등록 요청용)"""
        return {
            'hostname': SystemInfo.get_hostname(),
            'os': SystemInfo.get_os_info(),
        }


