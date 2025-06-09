# tests/test_transcription.py

import requests
import os
from app.logging_config import logger

HTTP_API_ENDPOINT = "http://localhost:7000/transcribe"

def test_transcribe():
    audio_file_path = "../media/recordings/14-10-53.wav"
    text_file_path = "../media/transcriptions/14-10-53.wav.txt"
    # audio_file_path = "../media/temp/ch3.wav"
    # text_file_path = "../media/transcriptions/ch3.wav.txt"


    # 确保测试音频文件存在
    if not os.path.exists(audio_file_path):
        logger.error(f"测试音频文件不存在: {audio_file_path}")
        return

    try:
        logger.info(f"发送音频文件到 HTTP API: {audio_file_path}")
        with open(audio_file_path, 'rb') as audio_file:
            files = {'file': (os.path.basename(audio_file_path), audio_file, 'audio/wav')}
            response = requests.post(HTTP_API_ENDPOINT, files=files)

        logger.debug(f"HTTP 响应状态码: {response.status_code}")
        logger.debug(f"HTTP 响应内容: {response.text}")

        if response.status_code == 200:
            result = response.json()
            if result.get('code') == 0:
                transcription = result.get('data', '')

                print("data:" + response.text)
                if isinstance(transcription, str):
                    with open(text_file_path, 'w', encoding='utf-8') as f:
                        f.write(transcription)
                    logger.info(f"转录结果已保存到: {text_file_path}")
                    print("转录成功:")
                    print(transcription)
                else:
                    logger.error(f"API 返回的数据格式不正确: {transcription}")
            else:
                logger.error(f"HTTP API 错误: {result.get('msg')}")
        else:
            logger.error(f"HTTP API 返回状态码 {response.status_code}: {response.text}")
    except Exception as e:
        logger.error(f"与 HTTP API 通信出错: {e}", exc_info=True)

if __name__ == "__main__":
    test_transcribe()
