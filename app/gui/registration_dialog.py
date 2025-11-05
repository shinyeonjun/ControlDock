"""
등록 승인 확인 다이얼로그 (PyQt6)
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QApplication
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont
from typing import Optional, Callable

class RegistrationDialog(QDialog):
    """등록 승인 확인 다이얼로그"""
    
    def __init__(self, on_approve: Callable[[], None], on_cancel: Optional[Callable[[], None]] = None):
        super().__init__()
        self.on_approve = on_approve
        self.on_cancel = on_cancel
        self.result = None
        self.init_ui()
    
    def init_ui(self):
        """UI 초기화"""
        self.setWindowTitle("OpsHub PC 등록")
        self.setFixedSize(400, 200)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)
        
        # 레이아웃
        main_layout = QVBoxLayout()
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(30, 30, 30, 30)
        
        # 메시지
        message_label = QLabel("이 PC를 OpsHub에 등록하시겠습니까?")
        message_font = QFont("맑은 고딕", 12)
        message_font.setBold(True)
        message_label.setFont(message_font)
        message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(message_label)
        
        # 설명
        desc_label = QLabel("등록하면 원격 관리 기능을 사용할 수 있습니다.")
        desc_font = QFont("맑은 고딕", 9)
        desc_label.setFont(desc_font)
        desc_label.setStyleSheet("color: gray;")
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(desc_label)
        
        # 버튼 레이아웃
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        # 예 버튼
        yes_button = QPushButton("예")
        yes_button.setMinimumSize(QSize(100, 35))
        yes_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 5px;
                font-size: 10pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        yes_button.clicked.connect(self._on_yes)
        button_layout.addWidget(yes_button)
        
        # 아니오 버튼
        no_button = QPushButton("아니오")
        no_button.setMinimumSize(QSize(100, 35))
        no_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                border-radius: 5px;
                font-size: 10pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:pressed {
                background-color: #c62828;
            }
        """)
        no_button.clicked.connect(self._on_no)
        button_layout.addWidget(no_button)
        
        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)
        
        # 중앙 정렬
        self._center_window()
    
    def _center_window(self):
        """창을 화면 중앙에 배치"""
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().geometry()
        size = self.geometry()
        x = (screen.width() - size.width()) // 2
        y = (screen.height() - size.height()) // 2
        self.move(x, y)
    
    def _on_yes(self):
        """예 버튼 클릭"""
        self.result = True
        self.accept()
        if self.on_approve:
            self.on_approve()
    
    def _on_no(self):
        """아니오 버튼 클릭"""
        self.result = False
        self.reject()
        if self.on_cancel:
            self.on_cancel()
    
    def exec(self) -> bool:
        """다이얼로그 실행 (True: 승인, False: 취소)"""
        result = super().exec()
        return result == QDialog.DialogCode.Accepted

