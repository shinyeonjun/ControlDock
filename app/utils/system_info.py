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
                
                # 빌드 번호 확인 (Windows 11 감지용)
                try:
                    build_number = int(winreg.QueryValueEx(key, "CurrentBuildNumber")[0])
                except (ValueError, FileNotFoundError):
                    build_number = 0
                
                # Windows 11 감지 (빌드 22000 이상)
                if build_number >= 22000:
                    # 에디션 정보 확인
                    try:
                        edition_id = winreg.QueryValueEx(key, "EditionID")[0]
                    except (FileNotFoundError, OSError):
                        edition_id = "Pro"
                    
                    # 에디션 매핑
                    edition_map = {
                        "Professional": "Pro",
                        "ProfessionalWorkstation": "Pro",
                        "Enterprise": "Enterprise",
                        "Education": "Education",
                        "Home": "Home",
                        "Core": "Home",
                        "CoreSingleLanguage": "Home",
                    }
                    
                    # 기본값은 "Pro"
                    edition = edition_map.get(edition_id, edition_id if edition_id else "Pro")
                    
                    # DisplayVersion 확인 (22H2, 23H2 등)
                    try:
                        display_version = winreg.QueryValueEx(key, "DisplayVersion")[0]
                        if display_version:
                            return f"Windows 11 {edition} {display_version}"
                    except (FileNotFoundError, OSError):
                        pass
                    
                    return f"Windows 11 {edition}"
                
                # Windows 10 이하
                try:
                    product_name = winreg.QueryValueEx(key, "ProductName")[0]
                    # ProductName에서 "Windows 10" 제거하고 에디션만 사용
                    if "Windows 10" in product_name:
                        edition = product_name.replace("Windows 10 ", "").strip()
                        return f"Windows 10 {edition}"
                    else:
                        return f"{product_name}"
                except (FileNotFoundError, OSError):
                    return f"Windows {release}"
                finally:
                    winreg.CloseKey(key)
            except Exception as e:
                print(f"OS 정보 수집 오류: {e}")
                return f"Windows {release}"
        else:
            return f"{system} {release}"
    
    @staticmethod
    def get_system_info() -> Dict[str, Any]:
        """전체 시스템 정보 수집"""
        # 디스크 총 용량 계산 (마운트된 파티션의 용량 합계)
        disk_total = 0
        try:
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    disk_total += usage.total
                except (PermissionError, OSError):
                    # 접근 권한이 없는 파티션은 건너뛰기
                    continue
        except Exception as e:
            print(f"디스크 정보 수집 오류: {e}")
        
        return {
            'hostname': SystemInfo.get_hostname(),
            'os': SystemInfo.get_os_info(),
            'platform': platform.platform(),
            'architecture': platform.machine(),
            'processor': platform.processor(),
            'cpu_count': psutil.cpu_count(),
            'memory_total': psutil.virtual_memory().total,
            'disk_total': disk_total,
        }
    
    @staticmethod
    def get_basic_info() -> Dict[str, str]:
        """기본 정보만 (등록 요청용)"""
        return {
            'hostname': SystemInfo.get_hostname(),
            'os': SystemInfo.get_os_info(),
        }


