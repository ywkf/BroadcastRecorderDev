
import os

import queue
import sys
import json
from datetime import datetime

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QTextEdit,
                             QTabWidget, QStatusBar, QMessageBox,
                             QFileDialog, QSlider, QTreeWidget,
                             QTreeWidgetItem, QSplitter, QStyle, QDateEdit, QDialog, QFormLayout,
                             QSpinBox, QLineEdit, QDialogButtonBox)
from PyQt5.QtCore import QTimer, Qt, QUrl, QDate, pyqtSignal, QObject
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtGui import QIcon, QTextCursor
from app.api import RadioRecorderAPI

import os
import sys
from pathlib import Path


def verify_environment():
    """严格验证运行环境"""
    # 硬编码预期路径
    EXPECTED_PYTHON = r"D:\Anaconda3\envs\gr_py310\python.exe"
    EXPECTED_PREFIX = r"D:\Anaconda3\envs\gr_py310"

    # 验证Python解释器
    if Path(sys.executable) != Path(EXPECTED_PYTHON):
        raise RuntimeError(f"Python路径不符，预期: {EXPECTED_PYTHON}，实际: {sys.executable}")

    # 验证CONDA_PREFIX
    if 'CONDA_PREFIX' not in os.environ:
        os.environ['CONDA_PREFIX'] = EXPECTED_PREFIX  # 手动注入
    elif Path(os.environ['CONDA_PREFIX']) != Path(EXPECTED_PREFIX):
        raise RuntimeError(f"Conda环境不符，预期: {EXPECTED_PREFIX}，实际: {os.environ['CONDA_PREFIX']}")

    # 验证项目路径
    project_path = r"D:\PythonPro\BroadcastRecorder_dev"
    if project_path not in sys.path:
        sys.path.insert(0, project_path)

    print("✓ 环境验证通过")
    print(f"Python: {sys.executable}")
    print(f"Conda: {os.environ['CONDA_PREFIX']}")
    print(f"WorkDir: {os.getcwd()}")


class Emitter(QObject):
    """用于线程安全地发送信号到GUI"""
    text_written = pyqtSignal(str)


class TextStream:
    """重定向标准输出到QTextEdit的类"""

    def __init__(self, text_edit):
        self.text_edit = text_edit
        self.emitter = Emitter()
        self.emitter.text_written.connect(self._append_text)

    def write(self, text):
        self.emitter.text_written.emit(text)

    def _append_text(self, text):
        cursor = self.text_edit.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(text)
        self.text_edit.setTextCursor(cursor)
        self.text_edit.ensureCursorVisible()

    def flush(self):
        pass


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.api = RadioRecorderAPI()
        self.media_player = QMediaPlayer()
        self.user_interacting = False
        self.current_search_date = None
        self.init_ui()
        self.init_media_player()
        self.refresh_data()
        # 添加日志队列处理
        self.log_queue = queue.Queue()
        self.log_timer = QTimer()
        self.log_timer.timeout.connect(self.process_log_queue)
        self.log_timer.start(100)  # 每100ms处理一次日志


        # 设置输出重定向
        sys.stdout = TextStream(self.log_display)
        sys.stderr = TextStream(self.log_display)

        # 连接子进程输出信号
        self.api.output_emitter.text_written.connect(self.append_log)


    def toggle_main_program(self):
        """切换主程序状态"""
        if self.api.is_running:  # 根据API的实际状态判断
            # 停止主程序
            if self.api.stop_main_program():
                self.main_program_btn.setText("启动主程序")
                self.update_status()
                self.append_log("主程序已停止")
            else:
                self.main_program_btn.setChecked(True)
                QMessageBox.warning(self, "错误", "主程序停止失败")
        else:
            # 启动主程序
            if self.api.start_main_program():
                self.main_program_btn.setText("停止主程序")
                self.update_status()
                self.append_log("主程序已启动")
            else:
                self.main_program_btn.setChecked(False)
                QMessageBox.warning(self, "错误", "主程序启动失败")

    def process_log_queue(self):
        """从队列中处理日志（防止GUI卡住）"""
        while not self.log_queue.empty():
            try:
                msg = self.log_queue.get_nowait()
                self.append_log(msg)
            except queue.Empty:
                break

    def append_log(self, text):
        """线程安全的日志追加（改进版）"""
        cursor = self.log_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(text + "\n")
        self.log_display.setTextCursor(cursor)
        self.log_display.ensureCursorVisible()

        # 自动滚动到底部
        scrollbar = self.log_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

        # 处理事件队列防止卡顿
        QApplication.processEvents()


    def init_ui(self):
        """初始化主界面"""
        self.setWindowTitle("广播录制转录系统")
        self.setGeometry(100, 100, 1000, 700)

        # 创建菜单栏
        self.init_menu()

        # 主窗口布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # 标签页
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # 首页
        self.home_tab = self.create_home_tab()
        self.tabs.addTab(self.home_tab, "首页")

        # 音频页
        self.audio_tab = self.create_content_tab("音频管理", ".wav", ["名称", "大小", "日期"])
        self.tabs.addTab(self.audio_tab, "音频管理")

        # 文本页
        self.text_tab = self.create_content_tab("文本管理", ".txt", ["名称", "字数", "日期"], with_editor=True)
        self.tabs.addTab(self.text_tab, "文本管理")

        # 底部播放器
        self.player_widget = self.create_player_widget()
        main_layout.addWidget(self.player_widget)

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.update_status()

        # 定时刷新数据（但不刷新日志）
        self.timer = QTimer()
        self.timer.timeout.connect(self.safe_refresh_status)  # 改为只刷新状态
        self.timer.start(5000)

        # 应用样式
        self.apply_styles()

    def safe_refresh_status(self):
        """只刷新状态，不刷新日志和内容列表"""
        if not self.user_interacting:
            self.update_status()

    def safe_refresh_data(self):
        """手动刷新数据时使用"""
        if not self.user_interacting:
            self.update_status()
            self.refresh_content_list(".wav")
            self.refresh_content_list(".txt")
            # 注意：这里移除了update_log_display()调用

    def create_content_tab(self, title, file_extension, headers, with_editor=False):
        """创建统一的内容管理标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 搜索栏
        search_layout = QHBoxLayout()
        date_edit = QDateEdit()
        date_edit.setDisplayFormat("yyyy-MM-dd")
        date_edit.setCalendarPopup(True)
        date_edit.setDate(QDate.currentDate())

        search_btn = QPushButton("搜索")
        search_btn.clicked.connect(lambda: self.search_by_date(file_extension, date_edit.date()))

        clear_btn = QPushButton("清除")
        clear_btn.clicked.connect(lambda: self.clear_search(file_extension))

        search_layout.addWidget(QLabel("日期筛选:"))
        search_layout.addWidget(date_edit)
        search_layout.addWidget(search_btn)
        search_layout.addWidget(clear_btn)
        search_layout.addStretch()

        # 工具栏
        toolbar = QHBoxLayout()
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(lambda: self.refresh_content_list(file_extension))
        delete_btn = QPushButton("删除选中")
        delete_btn.clicked.connect(lambda: self.delete_selected_item(file_extension))

        toolbar.addWidget(refresh_btn)
        toolbar.addWidget(delete_btn)

        if with_editor:
            edit_btn = QPushButton("编辑选中")
            edit_btn.clicked.connect(self.edit_selected_text)
            toolbar.addWidget(edit_btn)

        toolbar.addStretch()

        # 树形控件
        tree = QTreeWidget()
        tree.setHeaderLabels(headers)
        tree.setSortingEnabled(True)
        tree.header().setSectionsClickable(True)
        tree.header().sectionClicked.connect(self.on_header_clicked)

        # 根据类型设置属性和事件
        if file_extension == ".wav":
            self.audio_tree = tree
            tree.itemDoubleClicked.connect(self.on_audio_item_double_clicked)
            setattr(self, "audio_date_edit", date_edit)
        else:
            self.text_tree = tree
            tree.itemClicked.connect(self.on_text_item_clicked)
            setattr(self, "text_date_edit", date_edit)
            self.text_edit = QTextEdit()
            self.text_edit.setReadOnly(True)

        # 布局
        layout.addLayout(search_layout)
        layout.addLayout(toolbar)

        if with_editor:
            splitter = QSplitter(Qt.Horizontal)
            splitter.addWidget(tree)
            splitter.addWidget(self.text_edit)
            splitter.setStretchFactor(0, 1)
            splitter.setStretchFactor(1, 2)
            layout.addWidget(splitter)
        else:
            layout.addWidget(tree)

        return tab

    def apply_styles(self):
        """应用统一的样式"""
        tree_style = """
            QTreeWidget {
                font-size: 18px;
                show-decoration-selected: 1;
            }
            QTreeWidget::item {
                padding: 5px;
                height: 22px;
            }
            QTreeWidget::item:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #e7effd, stop:1 #cbdaf1);
            }
            QTreeWidget::item:selected {
                border: 1px solid #567dbc;
                color: black;
            }
        """
        self.audio_tree.setStyleSheet(tree_style)
        self.text_tree.setStyleSheet(tree_style)

        header_style = """
            QHeaderView::section {
                padding: 5px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #f6f7fa, stop:1 #dadbde);
                border: 1px solid #ccc;
                font-size: 18px;  /* 增大表头字体 */
            }
        """
        self.audio_tree.header().setStyleSheet(header_style)
        self.text_tree.header().setStyleSheet(header_style)

        date_edit_style = """
            QDateEdit {
                padding: 3px;
                min-width: 120px;
            }
            QCalendarWidget QAbstractItemView {
                selection-background-color: #3daee9;
            }
        """
        self.audio_date_edit.setStyleSheet(date_edit_style)
        self.text_date_edit.setStyleSheet(date_edit_style)

    def init_menu(self):
        """初始化菜单栏"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件")
        file_menu.addAction("退出", self.close)

        # 设置菜单
        settings_menu = menubar.addMenu("设置")
        settings_menu.addAction("参数设置", self.show_settings)
        settings_menu.addAction("关于", self.show_about)

    def create_home_tab(self):
        """创建首页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 服务控制
        control_layout = QHBoxLayout()

        # 转录服务按钮
        self.transcription_btn = QPushButton("启动转录服务")
        self.transcription_btn.setCheckable(True)
        self.transcription_btn.clicked.connect(self.toggle_transcription_service)

        # 主程序服务按钮（切换按钮）
        self.main_program_btn = QPushButton("启动主程序")
        self.main_program_btn.setCheckable(True)  # 设置为可切换状态
        self.main_program_btn.clicked.connect(self.toggle_main_program)

        self.status_label = QLabel("服务状态: 转录服务停止 | 主程序停止")


        # 修改按钮添加顺序
        control_layout.addWidget(self.transcription_btn)
        control_layout.addWidget(self.main_program_btn)
        control_layout.addWidget(self.status_label)
        control_layout.addStretch()

        # 日志显示
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)

        layout.addLayout(control_layout)
        layout.addWidget(QLabel("实时日志:"))
        layout.addWidget(self.log_display)

        return tab

    def toggle_transcription_service(self):
        """切换转录服务状态"""
        if self.api.is_transcribing:
            if self.api.stop_transcription_service():
                self.transcription_btn.setText("启动转录服务")
                self.update_status()
                self.append_log("转录服务已停止")
            else:
                self.transcription_btn.setChecked(True)
                QMessageBox.warning(self, "错误", "停止转录服务失败")
        else:
            if self.api.start_transcription_service():
                self.transcription_btn.setText("停止转录服务")
                self.update_status()
                self.append_log("转录服务已启动")
            else:
                self.transcription_btn.setChecked(False)
                QMessageBox.warning(self, "错误", "启动转录服务失败")

    def update_status(self):
        """更新状态显示"""
        status = self.api.get_service_status()
        recording_status = "运行中" if status["recording"] == "running" else "停止"
        transcribing_status = "运行中" if status["transcription"] == "running" else "停止"

        self.status_label.setText(
            f"服务状态: 转录服务{transcribing_status} | 主程序{recording_status}"
        )

        # 更新按钮状态
        self.main_program_btn.setChecked(status["recording"] == "running")
        self.main_program_btn.setText(
            "停止主程序" if status["recording"] == "running" else "启动主程序"
        )

        self.transcription_btn.setChecked(status["transcription"] == "running")
        self.transcription_btn.setText(
            "停止转录服务" if status["transcription"] == "running" else "启动转录服务"
        )

    def create_player_widget(self):
        """创建底部播放器"""
        widget = QWidget()
        layout = QHBoxLayout(widget)

        # 播放/暂停按钮
        self.play_btn = QPushButton("播放")
        self.play_btn.setIcon(self.style().standardIcon(getattr(QStyle, 'SP_MediaPlay')))
        self.play_btn.clicked.connect(self.toggle_play)

        # 停止按钮
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setIcon(self.style().standardIcon(getattr(QStyle, 'SP_MediaStop')))
        self.stop_btn.clicked.connect(self.stop_play)
        self.stop_btn.setEnabled(False)

        # 进度条
        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.setRange(0, 0)
        self.position_slider.sliderMoved.connect(self.set_position)

        # 时间显示
        self.time_label = QLabel("00:00 / 00:00")

        # 音量控制
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(50)
        self.volume_slider.valueChanged.connect(self.set_volume)

        # 添加到布局
        layout.addWidget(self.play_btn)
        layout.addWidget(self.stop_btn)
        layout.addWidget(self.position_slider, 3)
        layout.addWidget(self.time_label)
        layout.addWidget(QLabel("音量:"))
        layout.addWidget(self.volume_slider, 1)

        return widget

    def init_media_player(self):
        """初始化媒体播放器"""
        self.media_player = QMediaPlayer()
        self.media_player.setVolume(50)

        # 连接信号槽
        self.media_player.stateChanged.connect(self.update_play_button_state)
        self.media_player.error.connect(self.handle_media_error)
        self.media_player.positionChanged.connect(self.update_position)
        self.media_player.durationChanged.connect(self.update_duration)

    def refresh_data(self):
        """刷新所有数据（检查用户交互状态）"""
        if self.user_interacting:
            return

        self.update_status()
        self.refresh_content_list(".wav")
        self.refresh_content_list(".txt")
        self.update_log_display()

    def refresh_content_list(self, file_extension):
        """统一刷新内容列表"""
        try:
            tree = self.audio_tree if file_extension == ".wav" else self.text_tree
            dir_path = self.api.config["recordings_dir"] if file_extension == ".wav" else self.api.config[
                "transcriptions_dir"]

            # 保存当前展开状态和选中项
            expanded_items = []
            selected_path = None
            current_item = tree.currentItem()
            if current_item:
                selected_path = current_item.data(0, Qt.UserRole)

            root = tree.invisibleRootItem()
            for i in range(root.childCount()):
                item = root.child(i)
                if item.isExpanded():
                    expanded_items.append(item.text(0))

            tree.clear()
            tree.setSortingEnabled(False)

            if not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)

            # 构建目录结构
            for entry in os.scandir(dir_path):
                if entry.is_dir():
                    self._add_directory_to_tree(tree, entry, file_extension)

            # 恢复展开状态和选中项
            root = tree.invisibleRootItem()
            for i in range(root.childCount()):
                item = root.child(i)
                if item.text(0) in expanded_items:
                    item.setExpanded(True)
                if selected_path and self._select_item_by_path(tree, selected_path):
                    break

            tree.setSortingEnabled(True)

            # 如果有搜索条件，重新应用
            if self.current_search_date and file_extension == self.current_search_date[0]:
                self.search_by_date(file_extension, self.current_search_date[1])

        except Exception as e:
            print(f"刷新{file_extension}列表错误: {str(e)}")
            QMessageBox.warning(self, "错误", f"加载列表失败:\n{str(e)}")

    def search_by_date(self, file_extension, date):
        """统一按日期搜索文件"""
        try:
            self.user_interacting = True
            self.current_search_date = (file_extension, date)

            search_date = date.toString("yyyy-MM-dd")
            tree = self.audio_tree if file_extension == ".wav" else self.text_tree
            root = tree.invisibleRootItem()
            has_results = False

            for i in range(root.childCount()):
                dir_item = root.child(i)
                dir_has_match = False

                for j in range(dir_item.childCount()):
                    file_item = dir_item.child(j)
                    if file_item.data(2, Qt.UserRole):
                        file_date = file_item.data(2, Qt.UserRole).strftime("%Y-%m-%d")
                        if file_date == search_date:
                            file_item.setHidden(False)
                            dir_has_match = True
                            has_results = True
                        else:
                            file_item.setHidden(True)
                    else:
                        file_item.setHidden(True)

                dir_item.setHidden(not dir_has_match)

            if not has_results:
                QMessageBox.information(self, "提示", f"未找到{search_date}的文件")

        except Exception as e:
            print(f"搜索{file_extension}时出错: {str(e)}")
            QMessageBox.critical(self, "错误", f"搜索失败: {str(e)}")
        finally:
            QTimer.singleShot(5000, lambda: setattr(self, 'user_interacting', False))

    def clear_search(self, file_extension):
        """统一清除搜索条件"""
        self.user_interacting = True
        self.current_search_date = None

        tree = self.audio_tree if file_extension == ".wav" else self.text_tree
        root = tree.invisibleRootItem()
        for i in range(root.childCount()):
            dir_item = root.child(i)
            dir_item.setHidden(False)
            for j in range(dir_item.childCount()):
                dir_item.child(j).setHidden(False)

        QTimer.singleShot(5000, lambda: setattr(self, 'user_interacting', False))

    def _add_directory_to_tree(self, tree, dir_entry, extension):
        """添加目录到树形结构"""
        dir_item = QTreeWidgetItem(tree, [dir_entry.name])
        dir_item.setData(0, Qt.UserRole, dir_entry.path)
        dir_item.setIcon(0, QIcon.fromTheme("folder"))

        # 添加文件
        try:
            for entry in os.scandir(dir_entry.path):
                if entry.is_file() and entry.name.endswith(extension):
                    self._add_file_to_item(dir_item, entry, extension)
        except PermissionError:
            pass

        # 递归添加子目录
        try:
            for entry in os.scandir(dir_entry.path):
                if entry.is_dir():
                    self._add_directory_to_tree(dir_item, entry, extension)
        except PermissionError:
            pass

    def _add_file_to_item(self, parent_item, file_entry, extension):
        """添加文件到树形项"""
        try:
            file_size = file_entry.stat().st_size
            create_time = datetime.fromtimestamp(file_entry.stat().st_ctime)

            if extension == ".wav":
                columns = [
                    os.path.splitext(file_entry.name)[0],
                    f"{file_size / 1024:.1f} KB",
                    create_time.strftime('%Y-%m-%d %H:%M:%S')
                ]
                icon = QIcon.fromTheme("audio-x-generic")
            else:
                with open(file_entry.path, 'r', encoding='utf-8') as f:
                    word_count = len(f.read())
                columns = [
                    os.path.splitext(file_entry.name)[0],
                    f"{word_count} 字",
                    create_time.strftime('%Y-%m-%d %H:%M:%S')
                ]
                icon = QIcon.fromTheme("text-x-generic")

            file_item = QTreeWidgetItem(parent_item, columns)
            file_item.setData(0, Qt.UserRole, file_entry.path)
            file_item.setIcon(0, icon)
            file_item.setData(2, Qt.UserRole, create_time)  # 存储日期对象用于排序
        except Exception as e:
            print(f"添加文件到树错误: {str(e)}")

    def _select_item_by_path(self, tree, path):
        """根据路径选中树中的项目"""
        root = tree.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            if self._find_and_select_item(item, path):
                return True
        return False

    def _find_and_select_item(self, item, path):
        """递归查找并选中项目"""
        if item.data(0, Qt.UserRole) == path:
            self.text_tree.setCurrentItem(item)
            return True

        for i in range(item.childCount()):
            if self._find_and_select_item(item.child(i), path):
                return True
        return False

    def on_header_clicked(self, logical_index):
        """处理表头点击事件（排序）"""
        if logical_index == 2:  # 日期列特殊处理
            self._sort_by_date(logical_index)
        else:
            self.audio_tree.sortByColumn(logical_index,
                                         Qt.AscendingOrder if not self.audio_tree.isSortOrderAscending()
                                         else Qt.DescendingOrder)

    def _sort_by_date(self, column):
        """按日期排序（特殊处理）"""
        root = self.audio_tree.invisibleRootItem()
        for i in range(root.childCount()):
            dir_item = root.child(i)
            dir_item.sortChildren(column, dir_item.sortOrder(column))

        self.audio_tree.header().setSortIndicator(
            column,
            Qt.AscendingOrder if not self.audio_tree.isSortOrderAscending()
            else Qt.DescendingOrder
        )

    def on_audio_item_double_clicked(self, item, column):
        """处理音频项双击事件"""
        self.user_interacting = True
        try:
            if not item or item.childCount() > 0:  # 忽略文件夹点击
                return

            file_path = item.data(0, Qt.UserRole)
            if not file_path or not os.path.isfile(file_path):
                return

            self.play_selected_audio(item)
        finally:
            QTimer.singleShot(5000, lambda: setattr(self, 'user_interacting', False))

    def on_text_item_clicked(self, item, column):
        """处理文本项单击事件"""
        self.user_interacting = True
        try:
            if not item or item.childCount() > 0:  # 忽略文件夹点击
                return

            file_path = item.data(0, Qt.UserRole)
            if not file_path or not os.path.isfile(file_path):
                return

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    self.text_edit.setPlainText(content)
            except Exception as e:
                QMessageBox.critical(self, "错误", f"无法加载文本:\n{str(e)}")
        finally:
            QTimer.singleShot(5000, lambda: setattr(self, 'user_interacting', False))


    def play_selected_audio(self, item):
        """播放选中的音频"""
        file_path = item.data(0, Qt.UserRole)
        if not file_path:
            return

        # 转换为绝对路径
        abs_path = os.path.abspath(file_path)
        print(f"尝试播放文件: {abs_path}")

        # 检查文件有效性
        if not os.path.exists(abs_path):
            QMessageBox.warning(self, "错误", "音频文件不存在")
            return

        if os.path.getsize(abs_path) == 0:
            QMessageBox.warning(self, "错误", "音频文件为空")
            return

        # 创建媒体内容
        media_url = QUrl.fromLocalFile(abs_path)
        content = QMediaContent(media_url)

        # 设置并播放
        self.media_player.setMedia(content)
        self.media_player.play()

    def toggle_play(self):
        """切换播放/暂停状态"""
        if self.media_player.state() == QMediaPlayer.PlayingState:
            self.media_player.pause()
        else:
            if self.media_player.media().isNull():
                # 如果没有媒体内容，尝试播放当前选中项
                selected = self.audio_tree.currentItem()
                if selected:
                    self.play_selected_audio(selected)
            else:
                self.media_player.play()

    def stop_play(self):
        """停止播放"""
        self.media_player.stop()

    def update_play_button_state(self, state):
        """更新播放按钮状态"""
        if state == QMediaPlayer.PlayingState:
            self.play_btn.setText("暂停")
            self.play_btn.setIcon(self.style().standardIcon(getattr(QStyle, 'SP_MediaPause')))
        else:
            self.play_btn.setText("播放")
            self.play_btn.setIcon(self.style().standardIcon(getattr(QStyle, 'SP_MediaPlay')))

        # 停止按钮状态
        self.stop_btn.setEnabled(state != QMediaPlayer.StoppedState)

    def handle_media_error(self, error):
        """处理媒体错误"""
        error_mapping = {
            QMediaPlayer.NoError: "无错误",
            QMediaPlayer.ResourceError: "资源错误",
            QMediaPlayer.FormatError: "格式不支持",
            QMediaPlayer.NetworkError: "网络错误",
            QMediaPlayer.AccessDeniedError: "访问被拒绝"
        }
        error_msg = error_mapping.get(error, f"未知错误({error})")
        print(f"媒体错误: {error_msg} - {self.media_player.errorString()}")
        QMessageBox.critical(self, "播放错误", f"无法播放音频:\n{error_msg}\n{self.media_player.errorString()}")

    def set_position(self, position):
        """设置播放位置"""
        self.media_player.setPosition(position)

    def set_volume(self, volume):
        """设置音量"""
        self.media_player.setVolume(volume)

    def update_position(self, position):
        """更新播放位置显示"""
        self.position_slider.setValue(position)
        m, s = divmod(position // 1000, 60)
        duration = self.media_player.duration() // 1000
        md, sd = divmod(duration, 60) if duration > 0 else (0, 0)
        self.time_label.setText(f"{m:02d}:{s:02d} / {md:02d}:{sd:02d}")

    def update_duration(self, duration):
        """更新总时长显示"""
        self.position_slider.setRange(0, duration)

    def delete_selected_item(self, file_extension):
        """删除选中项"""
        tree = self.audio_tree if file_extension == ".wav" else self.text_tree
        selected = tree.currentItem()
        if not selected or selected.childCount() > 0:  # 不能删除目录
            return

        file_path = selected.data(0, Qt.UserRole)
        if not file_path:
            return

        if QMessageBox.question(self, "确认", f"确定要删除 {os.path.basename(file_path)} 吗？") == QMessageBox.Yes:
            if self.api.delete_file(file_path):
                self.refresh_content_list(file_extension)

    def edit_selected_text(self):
        """编辑选中文本"""
        self.user_interacting = True
        try:
            selected = self.text_tree.currentItem()
            if not selected or selected.childCount() > 0:
                return

            path = selected.data(0, Qt.UserRole)
            if not path:
                return

            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()

                self.text_edit.setReadOnly(False)
                self.text_edit.setPlainText(content)

                # 添加保存按钮
                if hasattr(self, "save_btn"):
                    self.save_btn.deleteLater()

                self.save_btn = QPushButton("保存")
                self.save_btn.clicked.connect(lambda: self.save_text_edit(path))
                self.text_tab.layout().insertWidget(2, self.save_btn)

            except Exception as e:
                QMessageBox.critical(self, "错误", f"无法加载文本:\n{str(e)}")
        finally:
            QTimer.singleShot(5000, lambda: setattr(self, 'user_interacting', False))

    def save_text_edit(self, path):
        """保存文本编辑"""
        self.user_interacting = True
        try:
            new_content = self.text_edit.toPlainText()
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(new_content)

                QMessageBox.information(self, "成功", "修改已保存")
                self.text_edit.setReadOnly(True)
                if hasattr(self, "save_btn"):
                    self.save_btn.deleteLater()
                self.refresh_content_list(".txt")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存失败:\n{str(e)}")
        finally:
            QTimer.singleShot(5000, lambda: setattr(self, 'user_interacting', False))

    def update_log_display(self):
        """更新日志显示"""
        try:
            with open("radio_recorder.log", "r") as f:
                self.log_display.setPlainText(f.read())
                # 修复：使用QTextCursor移动到最后
                cursor = self.log_display.textCursor()
                cursor.movePosition(QTextCursor.End)
                self.log_display.setTextCursor(cursor)
        except Exception as e:
            print(f"更新日志显示错误: {str(e)}")



    def start_service(self):
        """启动服务"""
        if self.api.start_service():
            QMessageBox.information(self, "成功", "服务已启动")
            self.update_status()
        else:
            QMessageBox.warning(self, "错误", "服务启动失败")

    def stop_service(self):
        """停止服务"""
        if self.api.stop_service():
            QMessageBox.information(self, "成功", "服务已停止")
            self.update_status()
        else:
            QMessageBox.warning(self, "错误", "服务停止失败")

    def show_settings(self):
        """显示设置对话框"""
        dialog = QDialog(self)
        dialog.setWindowTitle("系统设置")
        dialog.setMinimumWidth(400)
        layout = QFormLayout(dialog)

        duration_spin = QSpinBox()
        duration_spin.setRange(60, 1800)
        duration_spin.setValue(self.api.config.get("duration", 360))
        layout.addRow("录制时长(秒):", duration_spin)

        recordings_edit = QLineEdit(self.api.config["recordings_dir"])
        recordings_btn = QPushButton("浏览...")
        recordings_btn.clicked.connect(lambda: self.choose_directory(recordings_edit))

        recordings_layout = QHBoxLayout()
        recordings_layout.addWidget(recordings_edit)
        recordings_layout.addWidget(recordings_btn)
        layout.addRow("录音存储目录:", recordings_layout)

        transcriptions_edit = QLineEdit(self.api.config["transcriptions_dir"])
        transcriptions_btn = QPushButton("浏览...")
        transcriptions_btn.clicked.connect(lambda: self.choose_directory(transcriptions_edit))

        transcriptions_layout = QHBoxLayout()
        transcriptions_layout.addWidget(transcriptions_edit)
        transcriptions_layout.addWidget(transcriptions_btn)
        layout.addRow("文本存储目录:", transcriptions_layout)

        # 按钮框
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addRow(button_box)

        if dialog.exec_() == QDialog.Accepted:
            # 保存设置
            new_config = {
                "recordings_dir": recordings_edit.text(),
                "transcriptions_dir": transcriptions_edit.text(),
                "duration": duration_spin.value()
            }
            try:
                with open("config.json", "w") as f:
                    json.dump(new_config, f)
                QMessageBox.information(self, "成功", "设置已保存，重启后生效")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"保存设置失败: {str(e)}")

    def choose_directory(self, line_edit):
        """选择目录"""
        dir_path = QFileDialog.getExistingDirectory(self, "选择目录")
        if dir_path:
            line_edit.setText(dir_path)

    def show_about(self):
        """显示关于对话框"""
        QMessageBox.about(self, "关于",
                          "广播录制转录系统\n\n"
                          "版本: 1.0\n"
                          "使用技术:\n"
                          "- Python 3\n"
                          "- PyQt5\n"
                          "- GNU Radio\n"
                          "- SDR (RSP1)\n"
                          "- SenseVoice 语音识别")

    def closeEvent(self, event):
        """关闭窗口事件"""
        if self.api.get_service_status() == "running":
            reply = QMessageBox.question(
                self, "确认退出",
                "服务正在运行，退出将停止服务。确定要退出吗？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                event.ignore()
                return

        self.media_player.stop()
        self.timer.stop()
        event.accept()


if __name__ == "__main__":
    try:
        verify_environment()
        from app.api import RadioRecorderAPI  # 测试关键导入
    except Exception as e:
        print("!! 环境验证失败 !!")
        print(str(e))
        input("按Enter退出...")
        sys.exit(1)

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())