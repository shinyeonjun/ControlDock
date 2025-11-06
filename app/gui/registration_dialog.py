"""
등록 승인 확인 다이얼로그 (PyQt6) - 시작 프로그램 등록 옵션 포함
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QApplication, QCheckBox
)
from PyQt6.QtCore import Qt
from typing import Optional, Callable, Tuple
import sys

def show_registration_dialog(
    on_approve: Callable[[], None], 
    on_cancel: Optional[Callable[[], None]] = None
) -> Tuple[bool, bool]:
    """
    등록 승인 확인 다이얼로그 표시 (시작 프로그램 등록 옵션 포함)
    
    Args:
        on_approve: 승인 시 호출할 함수
        on_cancel: 취소 시 호출할 함수 (선택)
    
    Returns:
        (approved: bool, register_startup: bool): 승인 여부, 시작 프로그램 등록 여부
    """
    # QApplication이 없으면 생성
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
        print("QApplication 생성 완료")
    
    print("등록 승인 다이얼로그 표시 중...")
    
    # 간단한 커스텀 다이얼로그 생성
    dialog = QDialog()
    dialog.setWindowTitle("OpsHub PC 등록")
    dialog.setFixedSize(400, 180)
    dialog.setModal(True)
    dialog.setWindowFlags(
        Qt.WindowType.Dialog | 
        Qt.WindowType.WindowCloseButtonHint |
        Qt.WindowType.WindowStaysOnTopHint
    )
    
    # 레이아웃
    layout = QVBoxLayout()
    layout.setSpacing(15)
    layout.setContentsMargins(20, 20, 20, 20)
    
    # 메시지
    message_label = QLabel("이 PC를 OpsHub에 등록하시겠습니까?")
    message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(message_label)
    
    # 설명
    desc_label = QLabel("등록하면 원격 관리 기능을 사용할 수 있습니다.")
    desc_label.setStyleSheet("color: gray;")
    desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(desc_label)
    
    # 시작 프로그램 등록 체크박스
    startup_checkbox = QCheckBox("재부팅 후 자동으로 실행되도록 시작 프로그램에 등록")
    startup_checkbox.setChecked(True)  # 기본적으로 체크
    layout.addWidget(startup_checkbox)
    
    # 버튼 레이아웃
    button_layout = QHBoxLayout()
    button_layout.setSpacing(10)
    
    # 예 버튼
    yes_button = QPushButton("예")
    yes_button.setMinimumSize(100, 35)
    yes_button.clicked.connect(dialog.accept)
    button_layout.addWidget(yes_button)
    
    # 아니오 버튼
    no_button = QPushButton("아니오")
    no_button.setMinimumSize(100, 35)
    no_button.clicked.connect(dialog.reject)
    button_layout.addWidget(no_button)
    
    layout.addLayout(button_layout)
    dialog.setLayout(layout)
    
    # 창 중앙 배치
    screen = QApplication.primaryScreen().geometry()
    dialog.move(
        (screen.width() - dialog.width()) // 2,
        (screen.height() - dialog.height()) // 2
    )
    
    # 다이얼로그 표시
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
    app.processEvents()
    
    print("다이얼로그 표시 완료, 사용자 입력 대기 중...")
    
    # 체크박스 상태를 미리 저장할 변수
    register_startup_result = False
    
    # 예 버튼 클릭 시 체크박스 상태 저장
    def on_yes_clicked():
        nonlocal register_startup_result
        register_startup_result = startup_checkbox.isChecked()
        dialog.accept()
    
    # 예 버튼에 직접 연결
    yes_button.clicked.disconnect()
    yes_button.clicked.connect(on_yes_clicked)
    
    # 모달 다이얼로그 실행
    result = dialog.exec()
    
    print(f"다이얼로그 결과: {result}")
    
    if result == QDialog.DialogCode.Accepted:
        print("사용자가 '예'를 선택했습니다.")
        # 예 버튼 클릭 시 저장한 값을 사용
        register_startup = register_startup_result
        print(f"시작 프로그램 등록: {register_startup}")
        
        if on_approve:
            on_approve()
        return True, register_startup
    else:
        print("사용자가 '아니오'를 선택했습니다.")
        if on_cancel:
            on_cancel()
        return False, False
