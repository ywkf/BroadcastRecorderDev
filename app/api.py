
import os
import sys
import time
import traceback

from PyQt5.QtCore import QObject, pyqtSignal, QProcess, QProcessEnvironment
from PyQt5.QtGui import QTextCursor


class RadioRecorderAPI:
    def __init__(self):
        self.recording_process = None
        self.transcription_process = None
        self.is_recording = False
        self.is_transcribing = False
        self.process = None
        self.is_running = False
        self.output_emitter = Emitter()  # 用于输出信号
        self.config = {
            "recordings_dir": "./media/recordings",
            "transcriptions_dir": "./media/transcriptions",
            "duration": 360,
            "transcription_port": 7000  # 转录服务端口
        }
        self.process = QProcess()
        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.readyReadStandardError.connect(self.handle_stderr)
        # 获取主程序路径
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.main_program_path = os.path.join(script_dir, "record.py")

    def start_transcription_service(self):
        """启动转录服务（改进版）"""
        if self.is_transcribing:
            return False

        try:
            # 确保之前的进程已清理
            if self.transcription_process:
                self.transcription_process.kill()
                self.transcription_process = None

            self.transcription_process = QProcess()
            self.transcription_process.readyReadStandardOutput.connect(
                lambda: self._handle_process_output(self.transcription_process, "stdout")
            )
            self.transcription_process.readyReadStandardError.connect(
                lambda: self._handle_process_output(self.transcription_process, "stderr")
            )

            # 设置环境变量（如有需要）
            env = QProcessEnvironment.systemEnvironment()
            self.transcription_process.setProcessEnvironment(env)

            # 启动命令
            working_dir = os.path.dirname(os.path.abspath(__file__))
            self.transcription_process.setWorkingDirectory(working_dir)

            self.transcription_process.start(
                sys.executable,
                ["../api4sensevoice/server01.py", "--port", str(self.config["transcription_port"])]
            )

            if not self.transcription_process.waitForStarted(5000):
                raise Exception("转录服务启动超时")

            self.is_transcribing = True
            self.output_emitter.text_written.emit("转录服务启动成功")
            return True

        except Exception as e:
            error_msg = f"启动转录服务失败: {str(e)}"
            self.output_emitter.text_written.emit(error_msg)
            if self.transcription_process:
                self.transcription_process.kill()
                self.transcription_process = None
            return False


        except Exception as e:
            print(f"!! 启动失败: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    def _handle_process_output(self, process, stream_type):
        """处理进程输出（线程安全）"""
        try:
            if stream_type == "stdout":
                data = bytes(process.readAllStandardOutput()).decode('utf-8', errors='replace').strip()
            else:
                data = bytes(process.readAllStandardError()).decode('utf-8', errors='replace').strip()

            if data:
                # 分割多行日志
                for line in data.splitlines():
                    self.output_emitter.text_written.emit(f"[转录服务] {line}")
        except Exception as e:
            self.output_emitter.text_written.emit(f"处理输出错误: {str(e)}")

    def stop_transcription_service(self):
        """停止转录服务"""
        if not self.is_transcribing or not self.transcription_process:
            return False

        try:
            # 先尝试正常终止
            self.transcription_process.terminate()

            # 使用waitForFinished代替wait
            if not self.transcription_process.waitForFinished(5000):  # 等待5秒
                # 如果正常终止失败，强制杀死进程
                self.transcription_process.kill()
                self.transcription_process.waitForFinished(1000)

            self.is_transcribing = False
            return True
        except Exception as e:
            self.output_emitter.text_written.emit(f"停止转录服务失败: {str(e)}")
            try:
                self.transcription_process.kill()
            except:
                pass
            return False
        finally:
            self.transcription_process = None

    def _redirect_output(self, process):
        """重定向子进程输出"""
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                self.output_emitter.text_written.emit(output.strip())

        while True:
            err = process.stderr.readline()
            if err == '' and process.poll() is not None:
                break
            if err:
                self.output_emitter.text_written.emit(f"[ERROR] {err.strip()}")

    def get_service_status(self):
        """获取服务状态"""
        return {
            "recording": "running" if self.is_running else "stopped",
            "transcription": "running" if self.is_transcribing else "stopped"
        }


    def handle_stdout(self):
        data = self.process.readAllStandardOutput()
        self.output_emitter.text_written.emit(str(data, 'utf-8').strip())

    def handle_stderr(self):
        data = self.process.readAllStandardError()
        self.output_emitter.text_written.emit(str(data, 'utf-8').strip())

    def start_main_program(self):
        if self.is_running:
            return False

        try:
            # if self.process.state() == QProcess.Running:
            #     return False

            self.process.start(sys.executable, [self.main_program_path])
            self.is_running = True
            return True
        except Exception as e:
            print(f"启动主程序失败: {str(e)}")
            return False

    def stop_main_program(self):
        if not self.is_running:
            return False

        try:
            # if self.process.state() == QProcess.Running:
            #     self.process.terminate()
            #     if not self.process.waitForFinished(10000):  # 10秒超时
            #         self.process.kill()
            self.process.kill()
            self.is_running = False
            return True
        except Exception as e:
            print(f"停止主程序失败: {str(e)}")
            return False

    def read_output(self):
        """读取程序输出"""
        import pyqtgraph as pg  # 确保在子线程外导入

        while self.is_running and self.process:
            try:
                # 使用QProcess代替subprocess可能更好
                output = self.process.stdout.readline()
                if output:
                    # 使用信号发射而不是直接操作UI
                    self.output_emitter.text_written.emit(output.strip())

                error = self.process.stderr.readline()
                if error:
                    self.output_emitter.text_written.emit(error.strip())

                time.sleep(0.01)  # 添加小延迟
            except Exception as e:
                print(f"读取输出错误: {str(e)}")
                break


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