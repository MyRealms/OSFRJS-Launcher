def build_app_stylesheet() -> str:
    return """
QMainWindow, QDialog, QProgressDialog {
    background-color: rgba(10, 16, 24, 245);
    color: #F4EFE4;
}
QGroupBox {
    border: 1px solid rgba(244, 199, 104, 0.35);
    border-radius: 16px;
    margin-top: 14px;
    padding: 14px 14px 10px 14px;
    font-weight: 600;
    color: #F2D08A;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}
QTabWidget::pane {
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 16px;
    background: rgba(17, 25, 35, 0.88);
    top: -1px;
}
QTabBar::tab {
    background: rgba(255, 255, 255, 0.05);
    color: #D7E0EA;
    border-top-left-radius: 12px;
    border-top-right-radius: 12px;
    padding: 9px 16px;
    margin-right: 6px;
}
QTabBar::tab:selected {
    background: rgba(241, 199, 122, 0.22);
    color: #FFF7E7;
}
QLineEdit, QSpinBox {
    background: rgba(7, 11, 17, 0.88);
    color: #F7F4ED;
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 12px;
    padding: 8px 10px;
    selection-background-color: #8FB7FF;
}
QLineEdit:focus, QSpinBox:focus {
    border: 1px solid rgba(241, 199, 122, 0.75);
}
QPushButton, QDialogButtonBox QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(74, 172, 108, 0.95),
        stop:1 rgba(34, 105, 66, 0.95));
    color: #F8FBF6;
    border: 1px solid rgba(230, 255, 238, 0.28);
    border-radius: 14px;
    padding: 9px 18px;
    font-weight: 700;
}
QPushButton:hover, QDialogButtonBox QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(92, 196, 126, 0.98),
        stop:1 rgba(41, 122, 74, 0.98));
}
QPushButton:pressed, QDialogButtonBox QPushButton:pressed {
    padding-top: 10px;
}
QCheckBox {
    spacing: 8px;
    color: #E8E0D0;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 5px;
    border: 1px solid rgba(255, 255, 255, 0.26);
    background: rgba(7, 11, 17, 0.88);
}
QCheckBox::indicator:checked {
    background: rgba(241, 199, 122, 0.95);
    border: 1px solid rgba(255, 249, 235, 0.42);
}
QLabel {
    color: #EBE4D7;
}
"""
