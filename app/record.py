
import subprocess
import time
import os
import requests
import signal
import platform
import threading
from datetime import datetime, timedelta
import shutil
from app.logging_config import get_logger


class RadioRecorder:
    def __init__(self):
        # 初始化配置
        self.FLOWGRAPH_SCRIPT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../gunradio/sdr.py"))
        self.RECORD_DURATION = 360  # 恢复6分钟录制
        self.API_ENDPOINT = "http://localhost:7000/transcribe"
        self.BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        self.running = False
        self.process = None

        # 关键路径配置
        self.TEMP_DIR = os.path.join(self.BASE_DIR, "../media", "temp")
        self.RECORDINGS_DIR = os.path.join(self.BASE_DIR, "../media", "recordings")
        self.TRANSCRIPTIONS_DIR = os.path.join(self.BASE_DIR, "../media", "transcriptions")

        # 确保目录存在
        os.makedirs(self.TEMP_DIR, exist_ok=True)
        os.makedirs(self.RECORDINGS_DIR, exist_ok=True)
        os.makedirs(self.TRANSCRIPTIONS_DIR, exist_ok=True)

        self.debug_countdown = True  # 设为False可关闭详细倒计时

        # self.setup_logging()
        self.logger = get_logger(__name__)


    def start(self):
        """启动主程序"""
        if self.running:
            self.logger.warning("主程序已在运行中")
            return False

        self.running = True
        self.recording_thread = threading.Thread(target=self._run, daemon=True)
        self.recording_thread.start()
        self.logger.info("主程序启动成功，将等待整点/半点自动录制")
        return True

    def stop(self):
        """停止主程序"""
        if not self.running:
            self.logger.warning("主程序未运行")
            return False

        self.running = False
        if self.process:
            self.stop_flowgraph(self.process)
        self.logger.info("主程序已停止")
        return True

    def _run(self):
        """主运行循环"""
        try:
            while self.running:
                # 等待下一个整点或半点
                self.wait_until_trigger_time()

                if not self.running:
                    break

                # 执行录制流程
                self.execute_recording_cycle()

        except Exception as e:
            self.logger.error(f"主循环出错: {e}", exc_info=True)
        finally:
            self.running = False


    def wait_until_trigger_time(self):
        """等待直到整点或半点（修复时间计算错误版）"""
        while self.running:
            now = datetime.now()
            current_minute = now.minute

            # 判断是否到达触发时间（00或30分钟）
            if current_minute % 30 == 0:
                self.logger.info(f"到达触发时间: {now.strftime('%H:%M:%S')}")
                return

            try:
                # 计算下一个触发时间
                if current_minute < 30:
                    next_trigger_time = now.replace(minute=30, second=0, microsecond=0)
                else:
                    # 处理跨小时情况
                    next_trigger_time = (now.replace(minute=0, second=0, microsecond=0)
                                         + timedelta(hours=1))

                # 初始提示
                remaining = (next_trigger_time - now).total_seconds()
                self.logger.info(
                    f"下次录制时间: {next_trigger_time.strftime('%H:%M:%S')} | "
                    f"剩余等待: {int(remaining // 60)}分{int(remaining % 60)}秒"
                )

                # 等待循环（优化日志频率）
                last_log_minute = None
                while self.running:
                    now = datetime.now()
                    if now >= next_trigger_time:
                        break

                    remaining = (next_trigger_time - now).total_seconds()
                    current_minute = now.minute

                    # 智能日志输出
                    if remaining > 300 and current_minute % 5 == 0 and current_minute != last_log_minute:
                        self.logger.info(f"剩余等待: {int(remaining // 60)}分{int(remaining % 60)}秒")
                        last_log_minute = current_minute
                    elif remaining <= 5:
                        self.logger.debug(f"触发倒计时: {int(remaining)}秒")

                    time.sleep(1)

            except Exception as e:
                self.logger.error(f"时间计算错误: {e}", exc_info=True)
                time.sleep(10)  # 防止错误循环

    def execute_recording_cycle(self):
        """执行完整的录制周期"""
        try:
            self.logger.info("=== 开始新的录制周期 ===")

            # 1. 启动录制
            self.process = self.run_flowgraph()
            start_time = time.time()

            # 2. 等待录制完成
            while time.time() - start_time < self.RECORD_DURATION and self.running:
                time.sleep(1)

            # 3. 停止录制
            if self.process:
                self.stop_flowgraph(self.process)
                time.sleep(2)  # 确保文件完全写入

            # 4. 处理录制的文件
            if self.running:
                self.process_recorded_files()

            self.logger.info("=== 录制周期完成 ===")

        except Exception as e:
            self.logger.error(f"录制周期出错: {e}", exc_info=True)

    def process_recorded_files(self):
        """处理录制的音频文件"""
        # 定义预期的文件路径
        file_paths = [
            os.path.join(self.TEMP_DIR, "ch1.wav"),
            os.path.join(self.TEMP_DIR, "ch2.wav"),
            os.path.join(self.TEMP_DIR, "ch3.wav")
        ]

        for file_path in file_paths:
            if not self.running:
                break

            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                if file_size > 1024:  # 文件大小至少1KB
                    try:
                        # 1. 归档录音文件
                        archived_path = self.archive_recording(file_path)

                        # 2. 发送转录
                        if archived_path:
                            self.send_for_transcription(archived_path)
                    except Exception as e:
                        self.logger.error(f"处理文件 {file_path} 出错: {e}")
                else:
                    self.logger.warning(f"文件过小可能无效: {file_path} ({file_size}字节)")
            else:
                self.logger.warning(f"文件不存在: {file_path}")

    def archive_recording(self, src_path):
        """归档录音文件到日期目录"""
        try:
            # 创建日期分类目录
            dated_dir = self.get_dated_subfolder(self.RECORDINGS_DIR)

            # 生成带时间戳的文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{timestamp}_{os.path.basename(src_path)}"
            dest_path = os.path.join(dated_dir, filename)

            # 复制文件
            shutil.copy(src_path, dest_path)
            self.logger.info(f"录音文件已归档: {dest_path}")
            return dest_path
        except Exception as e:
            self.logger.error(f"归档失败: {e}")
            return None

    def send_for_transcription(self, audio_path):
        """发送音频到转录API"""
        try:
            # 准备转录结果路径
            dated_dir = self.get_dated_subfolder(self.TRANSCRIPTIONS_DIR)
            base_name = os.path.splitext(os.path.basename(audio_path))[0]
            text_path = os.path.join(dated_dir, f"{base_name}.txt")

            # 发送API请求
            with open(audio_path, 'rb') as audio_file:
                response = requests.post(
                    self.API_ENDPOINT,
                    files={'file': (os.path.basename(audio_path), audio_file, 'audio/wav')},
                    timeout=60
                )

            # 处理响应
            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 0:
                    with open(text_path, 'w', encoding='utf-8') as f:
                        f.write(result.get('data', ''))
                    self.logger.info(f"转录结果已保存: {text_path}")
                else:
                    self.logger.error(f"API业务错误: {result.get('msg')}")
            else:
                self.logger.error(f"API请求失败: {response.status_code}")

        except Exception as e:
            self.logger.error(f"转录失败: {e}")

    # 保留之前定义的辅助方法：
    # get_dated_subfolder(), run_flowgraph(),
    # stop_flowgraph(), _redirect_output() 等
    def run_flowgraph(self):
        """启动GNU Radio进程（不修改sdr.py的版本）"""
        # 在脚本所在目录运行
        working_dir = os.path.dirname(self.FLOWGRAPH_SCRIPT)

        self.logger.info(f"启动GNU Radio (工作目录: {working_dir})")

        if platform.system() == "Windows":
            process = subprocess.Popen(
                ["python", os.path.basename(self.FLOWGRAPH_SCRIPT)],
                cwd=working_dir,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                encoding='utf-8'
            )
        else:
            process = subprocess.Popen(
                ["python", os.path.basename(self.FLOWGRAPH_SCRIPT)],
                cwd=working_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                encoding='utf-8'
            )

        # 启动输出重定向
        threading.Thread(
            target=self._redirect_output,
            args=(process,),
            daemon=True
        ).start()

        return process

    def _redirect_output(self, process):
        """捕获子进程输出"""
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                self.logger.debug(f"[GNU Radio] {output.strip()}")

        while True:
            err = process.stderr.readline()
            if err == '' and process.poll() is not None:
                break
            if err:
                self.logger.error(f"[GNU Radio ERR] {err.strip()}")

    def stop_flowgraph(self, process):
        """停止GNU Radio进程"""
        try:
            if platform.system() == "Windows":
                process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                process.send_signal(signal.SIGINT)

            process.wait(timeout=10)
        except Exception as e:
            self.logger.error(f"停止Flowgraph出错: {e}")
            process.kill()

    def get_dated_subfolder(self, base_dir):
        """获取按日期分类的子目录"""
        date_str = datetime.now().strftime('%Y-%m-%d')
        dated_dir = os.path.join(base_dir, date_str)
        os.makedirs(dated_dir, exist_ok=True)
        return dated_dir


def main():
    recorder = RadioRecorder()
    try:
        recorder.start()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        recorder.stop()


if __name__ == "__main__":
    main()
