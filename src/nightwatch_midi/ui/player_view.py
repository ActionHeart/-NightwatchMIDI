"""Player presentation. All playback decisions remain in the existing controller."""
from PySide6.QtCore import QEvent, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout, QGroupBox, QLabel,
    QPushButton, QComboBox, QCheckBox, QSpinBox, QDoubleSpinBox, QLineEdit,
    QPlainTextEdit, QListWidget, QSlider, QStackedWidget, QStyle,
    QStyledItemDelegate, QTabWidget, QScrollArea,
    QSizePolicy, QGraphicsDropShadowEffect,
)


STYLE = """
QWidget { color: #253347; font-size: 12px; }
QWidget#mainWindow { background: #f5f7fa; }
QTabWidget::pane { border: none; background: #f5f7fa; top: -1px; }
QTabBar::tab { background: transparent; padding: 7px 18px; margin-right: 4px;
               border-radius: 8px; color: #637186; }
QTabBar::tab:selected { background: #ffffff; color: #2463ce; font-weight: 600; }
QTabBar::tab:hover { background: #e9eef6; }
QLabel#title { font-size: 23px; font-weight: 700; color: #17283e; }
QLabel#muted { color: #637186; }
QLabel#hint { color: #7a889c; font-size: 11px; }
QLabel#fileName { font-size: 14px; font-weight: 600; color: #253347; }
QLabel#fileName[empty="true"] { font-size: 12px; font-weight: 400; color: #8792a2; }
QLabel#badge { background: #e8eef8; color: #2463ce; border-radius: 9px; font-weight: 700; }
QLabel#infoPanel { background: #f8fafc; border: 1px solid #e6ebf2; border-radius: 8px;
                   padding: 8px 12px; }
QLabel#status { background: #eaf1fb; border: 1px solid #d8e5f8; border-radius: 8px;
                padding: 6px 10px; color: #3b5c8a; }
QLabel#countdown { font-size: 26px; font-weight: 800; color: #2463ce; }
QPushButton#disclaimer { background: #c0392b; color: #ffffff; border: none; border-radius: 6px;
                         padding: 3px 12px; text-align: left; font-size: 11px; font-weight: 600; }
QPushButton#disclaimer:hover { background: #a93226; }
QPushButton#disclaimer:pressed { background: #922b21; }
QGroupBox { background: white; border: none; border-radius: 8px;
            margin-top: 0; padding: 20px 12px 4px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: padding; subcontrol-position: top left;
                   left: 12px; top: 3px; padding: 0; color: #2463ce;
                   background: transparent; }
QPushButton, QToolButton { background: #ffffff; border: 1px solid #cbd5e1;
                           border-radius: 8px; padding: 6px 12px; }
QPushButton:hover, QToolButton:hover { background: #eef3fb; }
QPushButton:pressed, QToolButton:pressed { background: #dbe7fa; }
QPushButton:disabled { color: #8792a2; background: #eef0f4; border-color: #dfe4ec; }
QPushButton:checked { background: #2463ce; color: white; border-color: #2463ce; }
QPushButton#primary { background: #2463ce; color: white; border: none;
                      font-size: 15px; font-weight: 700; padding: 11px 22px; }
QPushButton#primary:hover { background: #1d55b4; }
QPushButton#primary:pressed { background: #17499c; }
QPushButton#primary:disabled { background: #c4d2e7; color: #637186; }
QPushButton#filePick { background: #f2f7ff; border: 1px solid #a7c6f0; color: #2463ce;
                       font-weight: 600; padding: 9px 14px; }
QPushButton#filePick:hover { background: #e3eefc; }
QPushButton#accent { border: 1px solid #2463ce; color: #2463ce; font-weight: 600; }
QPushButton#accent:hover { background: #eef4ff; }
QPushButton#accent:disabled { border-color: #dfe4ec; color: #9aa6b6; background: #f2f4f7; }
QPushButton#danger { border: 1px solid #d9534f; color: #c0392b; font-weight: 600; }
QPushButton#danger:hover { background: #fdecec; }
QPushButton#danger:pressed { background: #f8d7d7; }
QPushButton#gear { border: none; background: transparent; font-size: 16px; padding: 4px; }
QPushButton#gear:hover { background: #e9eef6; border-radius: 8px; }
QToolButton#instrument { border: none; background: transparent; font-size: 13px;
                         color: #253347; padding: 5px 10px; }
QToolButton#instrument:hover { background: #e9eef6; border-radius: 8px; }
QToolButton#instrument::menu-indicator { image: none; subcontrol-position: right center;
                                         subcontrol-origin: padding; left: -6px; }
QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit { background: white; border: 1px solid #cbd5e1;
                                   border-radius: 8px; padding: 5px 6px; min-height: 20px; }
QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover, QLineEdit:hover { border-color: #9db6d8; }
QComboBox::drop-down { border: none; background: transparent; width: 26px; }
QComboBox::down-arrow { image: url(:/qt-project.org/styles/commonstyle/images/arrow-down-16.png);
                        width: 12px; height: 12px; }
QComboBox QAbstractItemView { background: white; border: 1px solid #dce3ec; border-radius: 8px;
                              padding: 4px; outline: none;
                              selection-background-color: #2463ce; selection-color: white; }
QSpinBox::up-button, QDoubleSpinBox::up-button { subcontrol-origin: border;
                        subcontrol-position: top right; width: 18px; border: none; background: transparent; }
QSpinBox::down-button, QDoubleSpinBox::down-button { subcontrol-origin: border;
                        subcontrol-position: bottom right; width: 18px; border: none; background: transparent; }
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow { image: url(:/qt-project.org/styles/commonstyle/images/arrow-up-16.png);
                                               width: 10px; height: 10px; }
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow { image: url(:/qt-project.org/styles/commonstyle/images/arrow-down-16.png);
                                                   width: 10px; height: 10px; }
QLabel#empty { color: #8792a2; background: #fbfcfe; border: 1px dashed #cbd5e1;
               border-radius: 8px; padding: 18px; }
QPushButton#ghost { border: none; background: transparent; color: #4a5a70; }
QPushButton#ghost:hover { background: #e9eef6; }
QListWidget { background: white; border: 1px solid #e6ebf2; border-radius: 8px;
              padding: 6px; outline: none; }
QListWidget::item { padding: 0; border: none; }
QListWidget::item:selected { background: transparent; }
QSlider::groove:horizontal { height: 10px; background: #e4eaf2; border-radius: 5px; }
QSlider::sub-page:horizontal { background: #2463ce; border-radius: 5px; }
QSlider::handle:horizontal { width: 18px; margin: -5px 0; border-radius: 9px; background: #2463ce; }
QSlider::handle:horizontal:hover { background: #1d55b4; }
QSlider::handle:horizontal:disabled { background: #b9c6d8; }
QSlider::sub-page:horizontal:disabled { background: #c4d2e7; }
"""


def button(text, callback):
    result = QPushButton(text)
    result.clicked.connect(callback)
    return result


def spin(low, high, value, suffix=""):
    result = QSpinBox()
    result.setRange(low, high)
    result.setValue(value)
    result.setSuffix(suffix)
    return result


def combo(items):
    result = QComboBox()
    result.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    result.setMinimumContentsLength(8)
    for text, data in items:
        result.addItem(text, data)
    return result


def card(widget):
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(18)
    effect.setOffset(0, 2)
    effect.setColor(QColor(31, 45, 61, 28))
    widget.setGraphicsEffect(effect)
    return widget


class LibraryItemDelegate(QStyledItemDelegate):
    """Song row: favorite star, title, meta line and optimization badge."""

    favorite_toggled = Signal(str)
    DATA_ROLE = Qt.ItemDataRole.UserRole + 1

    def sizeHint(self, option, index):
        return QSize(0, 64)

    @staticmethod
    def star_rect(rect):
        return QRect(rect.left() + 10, rect.top() + 18, 28, 28)

    def paint(self, painter, option, index):
        painter.save()
        data = index.data(self.DATA_ROLE) or {}
        rect = option.rect.adjusted(4, 3, -4, -3)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        painter.setPen(Qt.PenStyle.NoPen)
        if selected:
            painter.setBrush(QColor("#2463ce"))
            painter.drawRoundedRect(rect, 8, 8)
        elif option.state & QStyle.StateFlag.State_MouseOver:
            painter.setBrush(QColor("#f0f5fc"))
            painter.drawRoundedRect(rect, 8, 8)

        star_font = painter.font()
        star_font.setPointSize(14)
        painter.setFont(star_font)
        if selected:
            painter.setPen(QColor("#ffffff"))
        else:
            painter.setPen(QColor("#f0b429") if data.get("favorite") else QColor("#b6c2d4"))
        painter.drawText(self.star_rect(option.rect), Qt.AlignmentFlag.AlignCenter,
                         "★" if data.get("favorite") else "☆")

        text_left = self.star_rect(option.rect).right() + 10
        title_rect = QRect(text_left, rect.top() + 8, rect.right() - text_left - 8, 22)
        title_font = painter.font()
        title_font.setPointSize(10)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.setPen(QColor("#ffffff") if selected else QColor("#253347"))
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         painter.fontMetrics().elidedText(data.get("title", ""),
                                                          Qt.TextElideMode.ElideRight, title_rect.width()))

        badge = data.get("badge", "")
        if badge:
            badge_font = painter.font()
            badge_font.setPointSize(8)
            badge_font.setBold(False)
            painter.setFont(badge_font)
            width = painter.fontMetrics().horizontalAdvance(badge) + 18
            badge_rect = QRect(rect.right() - width - 10, rect.top() + 9, width, 20)
            if not selected:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor("#e8f1ff"))
                painter.drawRoundedRect(badge_rect, 10, 10)
            painter.setPen(QColor("#ffffff") if selected else QColor("#2463ce"))
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, badge)

        meta_font = painter.font()
        meta_font.setPointSize(8)
        meta_font.setBold(False)
        painter.setFont(meta_font)
        painter.setPen(QColor("#dbe7fa") if selected else QColor("#7a889c"))
        meta_rect = QRect(text_left, rect.top() + 32, rect.right() - text_left - 8, 20)
        painter.drawText(meta_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         painter.fontMetrics().elidedText(data.get("meta", ""),
                                                          Qt.TextElideMode.ElideRight, meta_rect.width()))
        painter.restore()

    def editorEvent(self, event, model, option, index):
        if (event.type() == QEvent.Type.MouseButtonRelease
                and event.button() == Qt.MouseButton.LeftButton
                and self.star_rect(option.rect).contains(event.position().toPoint())):
            self.favorite_toggled.emit(index.data(Qt.ItemDataRole.UserRole))
            return True
        return super().editorEvent(event, model, option, index)


def info_html(duration="--", bpm="--", notes="--"):
    cells = "".join(
        f"<td style='color:#8792a2; padding:0 6px 0 0'>{key}</td>"
        f"<td style='color:#253347; font-weight:600; padding:0 22px 0 0'>{value}</td>"
        for key, value in (("时长", duration), ("原谱 BPM", bpm), ("音符", notes)))
    return f"<table cellspacing='0'><tr>{cells}</tr></table>"


def help_row(widget, text):
    row = QWidget()
    row_layout = QVBoxLayout(row)
    row_layout.setContentsMargins(0, 0, 0, 0)
    row_layout.setSpacing(2)
    row_layout.addWidget(widget)
    hint = QLabel(text)
    hint.setWordWrap(True)
    hint.setObjectName("hint")
    row_layout.addWidget(hint)
    return row


def build_view(p):
    layout = QVBoxLayout(p)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)

    p.tabs = QTabWidget()

    # ---------- 演奏页：乐谱 → 参数 → 播放器 ----------
    p.play_page = QWidget()
    play_layout = QVBoxLayout(p.play_page)
    play_layout.setContentsMargins(14, 4, 14, 4)
    play_layout.setSpacing(6)

    score = card(QGroupBox("乐谱"))
    score_layout = QVBoxLayout(score)
    score_layout.setSpacing(8)
    score_top = QHBoxLayout()
    score_top.setSpacing(18)
    picker = QVBoxLayout()
    picker.setSpacing(6)
    p.file_label = QLabel("尚未选择乐谱")
    p.file_label.setObjectName("fileName")
    p.file_label.setProperty("empty", "true")
    p.file_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
    p.file_label.setToolTip("尚未选择文件")
    p.open_button = button("♪  选择 MIDI 文件", p.choose_file)
    p.open_button.setObjectName("filePick")
    p.open_button.setToolTip("打开文件对话框；仅支持 .mid / .midi")
    picker.addWidget(p.file_label)
    picker.addWidget(p.open_button)
    p.file_info = QLabel(info_html())
    p.file_info.setTextFormat(Qt.TextFormat.RichText)
    p.file_info.setObjectName("infoPanel")
    p.file_info.setToolTip("时长、原谱 BPM 与音符数")
    optimize_col = QVBoxLayout()
    p.optimize_button = button("一键优化", p.optimize)
    p.optimize_button.setObjectName("accent")
    p.optimize_button.setEnabled(False)
    p.optimize_button.setToolTip("保持当前速度，推荐旋律与音域，并尝试短时间和弦归组减少冲突。会取舍复音，不保证无损还原；不会启用游戏输入。")
    optimize_col.addWidget(p.optimize_button)
    optimize_col.addStretch(1)
    score_top.addLayout(picker, 3)
    score_top.addWidget(p.file_info, 3)
    score_top.addLayout(optimize_col, 2)
    score_layout.addLayout(score_top)
    p.library_prompt = QWidget()
    prompt_layout = QHBoxLayout(p.library_prompt)
    prompt_layout.setContentsMargins(0, 0, 0, 0)
    p.library_prompt_label = QLabel("加入曲库？")
    p.library_add_button = button("加入曲库", p.add_to_library)
    p.library_skip_button = button("不用了", p.dismiss_library_prompt)
    prompt_layout.addWidget(p.library_prompt_label)
    prompt_layout.addWidget(p.library_add_button)
    prompt_layout.addWidget(p.library_skip_button)
    prompt_layout.addStretch(1)
    p.library_prompt.hide()
    score_layout.addWidget(p.library_prompt)
    p.analysis_label = QLabel("选择乐谱后，这里会显示推荐旋律、音域适配与优化建议。")
    p.analysis_label.setWordWrap(True)
    p.analysis_label.setObjectName("muted")
    score_layout.addStretch(1)
    score_layout.addWidget(p.analysis_label)
    play_layout.addWidget(score, 1)

    params = card(QGroupBox("参数"))
    params_layout = QVBoxLayout(params)
    params_layout.setSpacing(8)
    preset_row = QHBoxLayout()
    preset_row.setSpacing(8)
    preset_row.addWidget(QLabel("预设"))
    badge = QLabel("?")
    badge.setObjectName("badge")
    badge.setFixedSize(18, 18)
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    badge.setToolTip("预设会自动写入下方与高级设置中的参数（时序、归组、音域、速度），仍可手动微调；改动后预设自动取消。")
    preset_row.addWidget(badge)
    p.preset_buttons = {}
    presets = [
        ("balance", "平衡", "推荐默认：稳健时序 + 自动适配音域，速度保持当前值。"),
        ("stable", "稳定", "优先少漏音：稳健时序 + 20 ms 近似音归组。"),
        ("fidelity", "高还原", "最少改编：原始音高、原速、不合并、保留开头。"),
        ("fast", "高速", "紧凑时序 + 1.5x 速度，适合熟练后提速。"),
    ]
    for key, text, tip in presets:
        preset = QPushButton(text)
        preset.setCheckable(True)
        preset.setToolTip(tip)
        preset.clicked.connect(lambda _=False, k=key: p.apply_preset(k))
        p.preset_buttons[key] = preset
        preset_row.addWidget(preset)
    preset_row.addStretch(1)
    params_layout.addLayout(preset_row)
    params_layout.addStretch(1)
    grid = QGridLayout()
    grid.setHorizontalSpacing(14)
    p.range_mode = combo([("自动适配", "auto"), ("原始", "original"), ("自定义", "custom")])
    p.basic_speed = combo([(f"{n:g}x", n) for n in (.5, .75, 1, 1.25, 1.5, 1.75, 2)])
    p.basic_speed.setCurrentIndex(2)
    p.basic_delay = combo([("关闭", 0), ("3 秒", 3), ("5 秒", 5), ("10 秒", 10)])
    p.basic_delay.setCurrentIndex(2)
    for column, (title, widget) in enumerate(
            (("音域", p.range_mode), ("速度", p.basic_speed), ("倒计时", p.basic_delay))):
        key_label = QLabel(title)
        key_label.setObjectName("muted")
        grid.addWidget(key_label, 0, column * 2)
        grid.addWidget(widget, 0, column * 2 + 1)
        grid.setColumnStretch(column * 2 + 1, 1)
    params_layout.addLayout(grid)
    play_layout.addWidget(params, 1)

    control = card(QGroupBox("播放器"))
    control_layout = QVBoxLayout(control)
    control_layout.setSpacing(8)
    p.input_mode = combo([("预览模式", False), ("游戏演奏模式", True)])
    p.enable = QCheckBox(p)  # Kept as the existing controller's arming state.
    p.enable.hide()
    p.enable.toggled.connect(p.set_real_input)
    p.mode = QLabel("预览只检查演奏进度，不发声，也不控制游戏。")
    p.mode.setObjectName("muted")
    p.mode.setWordWrap(True)
    mode_row = QHBoxLayout()
    mode_row.addWidget(QLabel("演奏方式"))
    mode_row.addWidget(p.input_mode)
    mode_row.addWidget(p.mode, 1)
    control_layout.addLayout(mode_row)
    control_layout.addStretch(1)

    p.progress_header = QStackedWidget()
    p.progress_header.setFixedHeight(32)
    progress_row_widget = QWidget()
    progress_row = QHBoxLayout(progress_row_widget)
    progress_row.setContentsMargins(0, 0, 0, 0)
    p.now_playing = QLabel("准备演奏")
    p.time_label = QLabel("00:00 / 00:00")
    p.now_playing.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
    progress_row.addWidget(p.now_playing, 1)
    progress_row.addWidget(p.time_label)
    p.countdown_label = QLabel("")
    p.countdown_label.setObjectName("countdown")
    p.countdown_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    p.progress_header.addWidget(progress_row_widget)
    p.progress_header.addWidget(p.countdown_label)
    control_layout.addWidget(p.progress_header)

    p.seek_back_button = button("<<", p.seek_backward)
    p.seek_forward_button = button(">>", p.seek_forward)
    for seek_button, tip in ((p.seek_back_button, "F9：后退 10 秒并从该处继续"),
                             (p.seek_forward_button, "F10：前进 10 秒并从该处继续")):
        seek_button.setFixedWidth(44)
        seek_button.setToolTip(tip)
    seek_row = QHBoxLayout()
    seek_row.setSpacing(8)
    seek_row.addWidget(p.seek_back_button)
    p.progress = QSlider(Qt.Orientation.Horizontal)
    p.progress.setRange(0, 1000)
    p.progress.setToolTip("拖动或点击设定播放起点；播放中显示实时进度")
    seek_row.addWidget(p.progress, 1)
    seek_row.addWidget(p.seek_forward_button)
    control_layout.addLayout(seek_row)

    p.play_button = button("开始演奏", p.play)
    p.play_button.setObjectName("primary")
    p.play_button.setEnabled(False)
    p.pause_button = QPushButton("暂停（暂不可用）")
    p.pause_button.setEnabled(False)
    p.pause_button.setToolTip("当前播放核心尚未提供暂停/继续；本次界面更新不新增播放能力。")
    p.pause_button.hide()
    p.stop_button = button("紧急停止 · F12", p.emergency_stop)
    p.stop_button.setObjectName("danger")
    p.stop_button.setMinimumWidth(150)
    controls = QHBoxLayout()
    controls.setSpacing(10)
    controls.addWidget(p.play_button, 1)
    controls.addWidget(p.pause_button)
    controls.addWidget(p.stop_button)
    control_layout.addLayout(controls)
    play_layout.addWidget(control, 1)
    p.tabs.addTab(p.play_page, "演奏")

    # ---------- 曲库页 ----------
    p.library_page = QWidget()
    library_layout = QVBoxLayout(p.library_page)
    library_layout.setContentsMargins(18, 12, 18, 12)
    library_layout.setSpacing(10)
    library_top = QHBoxLayout()
    library_top.setSpacing(10)
    p.library_search = QLineEdit()
    p.library_search.setPlaceholderText("搜索曲名…")
    p.library_search.setClearButtonEnabled(True)
    p.library_favorites_only = QCheckBox("只看收藏")
    p.library_sort = combo([("按名称", "name"), ("最近播放", "recent"), ("加入时间", "added")])
    p.library_sort.setToolTip("排序方式；「最近播放」把最近演奏的曲目排在前面")
    p.library_folder_button = button("打开文件夹", p.open_library_folder)
    p.library_folder_button.setObjectName("ghost")
    p.library_folder_button.setToolTip("在资源管理器中打开曲库目录")
    p.library_import_button = button("＋ 从文件导入", p.import_to_library)
    p.library_import_button.setObjectName("accent")
    library_top.addWidget(p.library_search, 1)
    library_top.addWidget(p.library_favorites_only)
    library_top.addWidget(p.library_sort)
    library_top.addWidget(p.library_folder_button)
    library_top.addWidget(p.library_import_button)
    library_layout.addLayout(library_top)
    p.library_empty = QLabel("")
    p.library_empty.setObjectName("empty")
    p.library_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
    p.library_empty.setWordWrap(True)
    p.library_empty.hide()
    library_layout.addWidget(p.library_empty)
    p.library_list = QListWidget()
    p.library_list.setUniformItemSizes(True)
    p.library_list.setMouseTracking(True)
    p.library_list.setItemDelegate(LibraryItemDelegate(p.library_list))
    p.library_list.setToolTip("单击选中；双击直接载入演奏；点左侧星标收藏")
    library_layout.addWidget(p.library_list, 1)
    p.library_info = QLabel("选中一首曲子可查看时长、播放次数与优化状态。")
    p.library_info.setObjectName("muted")
    p.library_info.setWordWrap(True)
    library_layout.addWidget(p.library_info)
    library_actions = QHBoxLayout()
    library_actions.setSpacing(10)
    p.library_load_button = button("载入所选曲目", p.load_from_library)
    p.library_load_button.setObjectName("accent")
    p.library_favorite_button = button("☆ 收藏", p.toggle_favorite)
    p.library_remove_button = button("移出曲库", p.remove_from_library)
    p.library_remove_button.setObjectName("danger")
    library_actions.addWidget(p.library_load_button)
    library_actions.addWidget(p.library_favorite_button)
    library_actions.addWidget(p.library_remove_button)
    library_actions.addStretch(1)
    library_layout.addLayout(library_actions)
    p.tabs.addTab(p.library_page, "曲库")

    # ---------- 谱曲页 ----------
    p.score_page = QWidget()
    score_layout = QVBoxLayout(p.score_page)
    score_layout.setContentsMargins(18, 12, 18, 12)
    score_layout.setSpacing(10)
    compose = card(QGroupBox("谱曲"))
    compose_layout = QVBoxLayout(compose)
    compose_layout.setSpacing(8)
    score_toolbar = QHBoxLayout()
    score_toolbar.setSpacing(10)
    p.score_format = combo([("按键谱", "keys"), ("简谱", "numbered")])
    p.score_format.setToolTip("格式：按键谱按当前乐器配置的键位解析；简谱按 1-7 音级解析")
    p.score_bpm = spin(40, 240, 120, " BPM")
    p.score_bpm.setToolTip("生成 MIDI 的速度；谱面里的 BPM 指令会覆盖它")
    p.score_key = combo([(f"1={name}", name) for name in
                         ("C", "D", "E", "F", "G", "A", "B", "F#", "Bb", "Eb", "Ab")])
    p.score_key.setEnabled(False)
    p.score_key.setToolTip("简谱中 1 对应的调；按键谱由乐器配置决定音高")
    p.score_meter = combo([("4/4", (4, 4)), ("3/4", (3, 4)), ("2/4", (2, 4)), ("6/8", (6, 8))])
    p.score_meter.setToolTip("写入 MIDI 的拍号；谱面里的拍号指令会覆盖它")
    for widget in (p.score_format, p.score_key, p.score_meter):
        widget.setMinimumContentsLength(0)
        widget.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
    p.score_title = QLineEdit()
    p.score_title.setPlaceholderText("曲名（可选）")
    p.score_title.setMaximumWidth(180)
    p.score_title.setToolTip("生成与保存到曲库时使用的曲名")
    p.score_example_button = button("载入示例", p.load_score_example)
    p.score_preview_button = button("解析预览", p.preview_score)
    p.score_play_button = button("生成并演奏", p.play_score)
    p.score_play_button.setObjectName("accent")
    p.score_save_button = button("保存到曲库", p.save_score_to_library)
    for widget in (p.score_format, p.score_bpm, p.score_key, p.score_meter, p.score_title):
        score_toolbar.addWidget(widget)
    score_toolbar.addStretch(1)
    compose_layout.addLayout(score_toolbar)
    score_actions = QHBoxLayout()
    score_actions.setSpacing(10)
    score_actions.addWidget(p.score_example_button)
    score_actions.addWidget(p.score_preview_button)
    score_actions.addStretch(1)
    score_actions.addWidget(p.score_play_button)
    score_actions.addWidget(p.score_save_button)
    compose_layout.addLayout(score_actions)
    p.score_editor = QPlainTextEdit()
    p.score_editor.setPlaceholderText(
        "粘贴谱面文本…\n"
        "简谱：1=C 4/4 / BPM 120 / | 1 1 5 5 | 6 6 5- |\n"
        "按键谱：Z X C V B N M / [60] 指定音高 / Z+X 同时按键")
    p.score_editor.setMinimumHeight(170)
    compose_layout.addWidget(p.score_editor, 1)
    p.score_result = QLabel(
        "谱面支持：简谱 1-7 / 0 休止 / #b 变音 / ' , 八度 / - . / 时值 / [1 3 5] 和弦；"
        "按键谱 Z X C… / [60] 指定音高 / Z+X 同时按键。生成后可演奏或保存到曲库。")
    p.score_result.setObjectName("muted")
    p.score_result.setWordWrap(True)
    compose_layout.addWidget(p.score_result)
    score_layout.addWidget(compose, 1)
    p.tabs.addTab(p.score_page, "谱曲")

    # ---------- 高级设置页 ----------
    p.advanced_page = QWidget()
    advanced_layout = QVBoxLayout(p.advanced_page)
    advanced_layout.setContentsMargins(18, 12, 18, 12)
    advanced_layout.setSpacing(8)
    advanced_hint = QLabel("高级设置会立即重新编排当前乐谱；每个选项下方有说明，不确定时用「参数」里的预设即可。")
    advanced_hint.setObjectName("muted")
    advanced_hint.setWordWrap(True)
    advanced_layout.addWidget(advanced_hint)
    p.advanced = QTabWidget()
    p.hotkeys_enable = QCheckBox("启用全局播放快捷键（F8 重播 / F9 后退 / F10 前进）")
    p.hotkeys_enable.setChecked(True)
    p.hotkeys_enable.setToolTip("在游戏前台时也能触发。按键仍会传给游戏，请确认该键位不会与游戏功能冲突。")
    p.track = combo([("全部声部", None)])
    p.channel = combo([("全部乐器通道", None)] + [(f"乐器通道 {i + 1}", i) for i in range(16)])
    p.voicing = combo([("旋律单音", False), ("兼容和弦（实验）", True)])
    p.transpose = spin(-48, 48, 0, " 半音")
    p.fold = QCheckBox("超出音域时移动八度")
    p.fold.setChecked(True)
    p.drums = QCheckBox("忽略鼓点（第 10 通道）")
    p.drums.setChecked(True)
    p.trim = QCheckBox("跳过开头空白")
    p.trim.setChecked(True)
    p.note_gap = spin(0, 100, 40, " ms")
    p.onset_window = spin(0, 100, 0, " ms")
    p.timing_preset = combo([("稳健 · 提前 40 / 按住 50 ms", "stable"),
                             ("标准 · 提前 25 / 按住 35 ms", "standard"),
                             ("快速 · 提前 15 / 按住 25 ms", "fast")])
    p.density = combo([("保持原谱节奏，跳过来不及的音", "score"),
                       ("节奏优先，允许轻微延后", "rhythm"),
                       ("音符优先，可能越弹越慢", "complete")])
    p.speed = QDoubleSpinBox()
    p.speed.setRange(0.25, 2)
    p.speed.setSingleStep(0.05)
    p.speed.setValue(1)
    p.speed.setSuffix(" x")
    p.delay = spin(0, 30, 5, " 秒")
    p.suggest_button = button("重新推荐旋律", p.suggest_melody)
    p.octave_button = button("推荐移调", p.suggest_octave)
    p.slower_button = button("自动降速，减少漏音", p.suggest_speed)
    p.original_button = button("恢复原谱节奏", p.restore_original)
    p.summary = QLabel("选择乐谱后显示详细编排结果。")
    p.summary.setWordWrap(True)
    p.rhythm_info = QLabel("原谱速度与拍号")
    p.rhythm_info.setWordWrap(True)
    p.beat_label = QLabel("播放时显示小节与拍位")
    p.beat_label.setWordWrap(True)
    groups = [
        ("乐谱处理", "选择演奏哪个声部以及音高如何适配；默认值由「一键优化」推荐，通常无需改动。",
         [("旋律声部", p.track, "多轨文件里要演奏的声部；不确定就用推荐的。"),
          ("乐器通道", p.channel, "该声部所在的 MIDI 通道；默认「全部乐器通道」即可。"),
          ("", p.suggest_button, "按口琴音域重新挑选最合适的声部。"),
          ("移调", p.transpose, "整体升降音高，单位是半音；±12 等于一个八度。"),
          ("", p.fold, "口琴没有的音，自动移到最近的可用八度。"),
          ("", p.drums, "第 10 通道通常是鼓，口琴弹不了，默认忽略。"),
          ("", p.trim, "自动裁掉乐曲开头的静音，不用干等。"),
          ("", p.octave_button, "自动挑一个让最多音符落在音域内的移调。")]),
        ("演奏方式", "控制同时发声的音、起音对齐与速度；改动会立即重新编排。",
         [("和弦处理", p.voicing, "单音最稳；兼容和弦会同时按多个音，实验性功能。"),
          ("相近音合并", p.onset_window, "把几乎同时响起的音合并成一个；0 只合并完全同时的音。"),
          ("密集音符", p.density, "太快来不及弹时，优先保住节奏还是保住音符。"),
          ("精细速度", p.speed, "0.25–2 倍的精确速度；常用档位在主界面直接可选。"),
          ("", p.slower_button, "自动尝试较慢速度，尽量减少漏音。"),
          ("", p.original_button, "回到原速、不合并、不顺延，按原谱起音对齐。"),
          ("", p.rhythm_info, ""),
          ("", p.beat_label, ""),
          ("", p.summary, "")]),
        ("游戏兼容性", "调节按键与鼠标切换的时间余量，适配不同电脑的流畅度。",
         [("提前量 / 最短按键时间", p.timing_preset, "给游戏留反应时间：越稳健，按键越早、按得越久。"),
          ("最小音间隔", p.note_gap, "相邻两个音的最小间隔；游戏卡顿时可以调大。")]),
        ("输入与安全", "倒计时与安全行为；输入测试和诊断位于右上角「设置」。",
         [("自定义倒计时", p.delay, "点开始后留给你切回游戏的时间；0 表示立即开始。"),
          ("", p.hotkeys_enable, "关闭后 F8/F9/F10 不再控制播放，F12 停止始终可用。按键仍会传给游戏，请先确认没有键位冲突。")]),
    ]
    for title, description, fields in groups:
        content = QWidget()
        content_layout = QVBoxLayout(content)
        hint = QLabel(description)
        hint.setWordWrap(True)
        hint.setObjectName("muted")
        content_layout.addWidget(hint)
        form = QFormLayout()
        for name, widget, help_text in fields:
            field = help_row(widget, help_text) if help_text else widget
            form.addRow(name, field) if name else form.addRow(field)
        content_layout.addLayout(form)
        content_layout.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        p.advanced.addTab(scroll, title)
    advanced_layout.addWidget(p.advanced, 1)
    p.tabs.addTab(p.advanced_page, "高级设置")

    layout.addWidget(p.tabs, 1)

    p.status = QLabel("1. 点击选择乐谱  →  2. 选择预设与演奏方式  →  3. 点击「开始演奏」")
    p.status.setObjectName("status")
    p.status.setWordWrap(True)
    p.status.setMinimumHeight(26)
    layout.addWidget(p.status)

    # These are hosted exclusively in SettingsDialog, never in the main view.
    p.profile_label = QLabel("乐器：守夜人口琴", p)
    p.profile_button = button("导入乐器配置（JSON）", p.choose_profile)
    p.profile_button.setParent(p)
    p.diagnostics = QPlainTextEdit(p)
    p.diagnostics.setReadOnly(True)
    for widget in (p.profile_label, p.profile_button, p.diagnostics):
        widget.hide()
    p.settings = (p.open_button, p.profile_button, p.track, p.channel, p.voicing, p.transpose,
                  p.fold, p.drums, p.note_gap, p.speed, p.delay, p.timing_preset, p.density,
                  p.trim, p.suggest_button, p.octave_button, p.slower_button, p.onset_window,
                  p.original_button, p.range_mode, p.basic_speed, p.basic_delay, p.optimize_button,
                  p.library_add_button, p.library_skip_button, *p.preset_buttons.values())
