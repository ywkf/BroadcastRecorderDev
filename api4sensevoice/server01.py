
from fastapi import FastAPI, File, UploadFile, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY
from pydantic import BaseModel
from funasr import AutoModel
from pydub import AudioSegment
import asyncio
import numpy as np
import torch
import torchaudio
import io
import soundfile as sf
import argparse
import uvicorn
import time
# import logging
from app.logging_config import get_logger

# Set up logging
# logging.basicConfig(level=logging.ERROR)
# logger = logging.getLogger(__name__)

logger = get_logger(__name__)


emo_dict = {
    "<|HAPPY|>": "😊",
    "<|SAD|>": "😔",
    "<|ANGRY|>": "😡",
    "<|NEUTRAL|>": "",
    "<|FEARFUL|>": "😰",
    "<|DISGUSTED|>": "🤢",
    "<|SURPRISED|>": "😮",
}

event_dict = {
    "<|BGM|>": "🎼",
    "<|Speech|>": "",
    "<|Applause|>": "👏",
    "<|Laughter|>": "😀",
    "<|Cry|>": "😭",
    "<|Sneeze|>": "🤧",
    "<|Breath|>": "",
    "<|Cough|>": "🤧",
}

emoji_dict = {
    "<|nospeech|><|Event_UNK|>": "❓",
    "<|zh|>": "",
    "<|en|>": "",
    "<|yue|>": "",
    "<|ja|>": "",
    "<|ko|>": "",
    "<|nospeech|>": "",
    "<|HAPPY|>": "😊",
    "<|SAD|>": "😔",
    "<|ANGRY|>": "😡",
    "<|NEUTRAL|>": "",
    "<|BGM|>": "🎼",
    "<|Speech|>": "",
    "<|Applause|>": "👏",
    "<|Laughter|>": "😀",
    "<|FEARFUL|>": "😰",
    "<|DISGUSTED|>": "🤢",
    "<|SURPRISED|>": "😮",
    "<|Cry|>": "😭",
    "<|EMO_UNKNOWN|>": "",
    "<|Sneeze|>": "🤧",
    "<|Breath|>": "",
    "<|Cough|>": "😷",
    "<|Sing|>": "",
    "<|Speech_Noise|>": "",
    "<|withitn|>": "",
    "<|woitn|>": "",
    "<|GBG|>": "",
    "<|Event_UNK|>": "",
}

lang_dict = {
    "<|zh|>": "<|lang|>",
    "<|en|>": "<|lang|>",
    "<|yue|>": "<|lang|>",
    "<|ja|>": "<|lang|>",
    "<|ko|>": "<|lang|>",
    "<|nospeech|>": "<|lang|>",
}

emo_set = {"😊", "😔", "😡", "😰", "🤢", "😮"}
event_set = {"🎼", "👏", "😀", "😭", "🤧", "😷", }


def format_str(s):
    for sptk in emoji_dict:
        s = s.replace(sptk, emoji_dict[sptk])
    return s


def format_str_v2(s):
    sptk_dict = {}

    for sptk in emoji_dict:
        sptk_dict[sptk] = s.count(sptk)
        s = s.replace(sptk, "")
        emo = "<|NEUTRAL|>"
    for e in emo_dict:
        if sptk_dict[e] > sptk_dict[emo]:
            emo = e
    for e in event_dict:
        if sptk_dict[e] > 0:
            s = event_dict[e] + s
            s = s + emo_dict[emo]

    for emoji in emo_set.union(event_set):
        s = s.replace(" " + emoji, emoji)
        s = s.replace(emoji + " ", emoji)

    return s.strip()


def format_str_v3(s):

    def get_emo(s):
        return s[-1] if s[-1] in emo_set else None

    def get_event(s):
        return s[0] if s[0] in event_set else None

    s = s.replace("<|nospeech|><|Event_UNK|>", "❓")

    for lang in lang_dict:
        s = s.replace(lang, "<|lang|>")

    s_list = [format_str_v2(s_i).strip(" ") for s_i in s.split("<|lang|>")]
    new_s = " " + s_list[0]
    cur_ent_event = get_event(new_s)

    for i in range(1, len(s_list)):

        if len(s_list[i]) == 0:
            continue
        if get_event(s_list[i]) == cur_ent_event and get_event(s_list[i]) != None:
            s_list[i] = s_list[i][1:]
        # else:
        cur_ent_event = get_event(s_list[i])
        if get_emo(s_list[i]) != None and get_emo(s_list[i]) == get_emo(new_s):
            new_s = new_s[:-1]
        new_s += s_list[i].strip().lstrip()
    new_s = new_s.replace("The.", " ")
    return new_s.strip()


app = FastAPI()

# 设置跨域中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=[""],  # 允许所有来源，可以根据需要指定特定的域名
    allow_credentials=True,
    allow_methods=[""],  # 允许所有方法
    allow_headers=["*"],  # 允许所有请求头
)

# Initialize the model outside the endpoint to avoid reloading it for each request
model = AutoModel(model="iic/SenseVoiceSmall",
                      vad_model="fsmn-vad",
                      vad_kwargs={"max_single_segment_time": 300000},
                      trust_remote_code=True,
                      device="cuda:0",
                      )


def transcribe_with_timing(*args, **kwargs):
    start_time = time.time()
    result = model.generate(*args, **kwargs)
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"转录耗时: {elapsed_time:.2f} 秒")
    return result, elapsed_time


@app.exception_handler(Exception)
async def custom_exception_handler(request: Request, exc: Exception):
    logger.error("Exception occurred", exc_info=True)
    if isinstance(exc, HTTPException):
        status_code = exc.status_code
        message = exc.detail
        data = ""
    elif isinstance(exc, RequestValidationError):
        status_code = HTTP_422_UNPROCESSABLE_ENTITY
        message = "Validation error: " + str(exc.errors())
        data = ""
    else:
        status_code = 500
        message = "Internal server error: " + str(exc)
        data = ""

    return JSONResponse(
        status_code=status_code,
        content=TranscriptionResponse(
            code=status_code,
            msg=message,
            data=data
        ).model_dump()
    )


# Define the response model
class TranscriptionResponse(BaseModel):
    code: int
    msg: str
    data: str


@app.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(file: UploadFile = File(...)):
    try:
        file.file.seek(0)
        file_content = await file.read()  # 异步读取文件内容
        print(f"[DEBUG] UploadFile Object is {file}")

        if file_content.startswith(b'RIFF'):  # 如果文件以RIFF开头，说明是WAV格式
            input_wav, sr = sf.read(io.BytesIO(file_content), dtype=np.int16)
            bit_depth = sf.info(io.BytesIO(file_content)).subtype
            is16 = True if bit_depth == 'PCM_16' else False
            print(f"[DEBUG] 音频格式为wav")

        elif file_content.startswith(b'\x89\x50\x4E\x47\x0D\x0A\x1A\x0A'):  # 如果文件以89 50 4E 47 0D 0A 1A 0A开头，说明是WebM格式
            input_wav, sr = torchaudio.load(io.BytesIO(file_content))  # 使用torchaudio库读取WebM文件内容和采样率
            dtype = input_wav.dtype  # 获取音频数据类型
            is16 = True if dtype == np.int16 else False  # 判断是否为16位音频
            print(f"[DEBUG] 音频格式为webm")
        elif file_content.startswith(b'\xFF\xF1') or file_content.startswith(b'\xFF\xF9') or file_content.startswith(
                b'\xFF\xFA') or file_content.startswith(b'\xFFxFB'):  # 如果文件以FF F1开头，说明是AAC格式
            audio_segment = AudioSegment.from_file(io.BytesIO(file_content), format="aac")  # 使用pydub库读取AAC文件内容
            input_wav = np.array(audio_segment.get_array_of_samples()).astype(np.int16)  # 将音频数据转换为numpy数组并设置为16位格式
            sr = audio_segment.frame_rate  # 获取音频的采样率
            is16 = True  # 设置为16位音频
            print(f"[DEBUG] 音频格式为aac")
        elif file_content.startswith(b'ID3'):  # 如果文件以FF E2开头，说明是MP3格式
            audio_segment = AudioSegment.from_file(io.BytesIO(file_content), format="mp3")  # 使用pydub库读取MP3文件内容
            input_wav = np.array(audio_segment.get_array_of_samples()).astype(np.int16)  # 将音频数据转换为numpy数组并设置为16位格式
            sr = audio_segment.frame_rate  # 获取音频的采样率
            is16 = True  # 设置为16位音频
            print(f"[DEBUG] 音频格式为mp3")
        else:
            raise HTTPException(status_code=400, detail="Unsupported audio format")

        # filename = (file.filename if file.filename else "test") + "." + suffix
        # with open(filename, "wb") as f:
            # f.write(file_content)


        if len(input_wav.shape) > 1:  # 如果音频是立体声，将其转换为单声道
            input_wav = input_wav.mean(-1)

        if is16:  # 如果音频数据不是浮点数类型，将其转换为浮点数类型并归一化到[-1, 1]范围
            input_wav = input_wav.astype(np.float32) / np.iinfo(np.int16).max

        if sr != 16000:  # 如果音频的采样率不是16000，将其重采样为16000
            print(f"[DEBUG] 音频采样率是 {sr}  进行重采样")
            start_time = time.time()
            resampler = torchaudio.transforms.Resample(sr, 16000)  # 创建一个重采样器，将采样率从sr重采样为16000
            input_wav_t = torch.from_numpy(input_wav).to(torch.float32)  # 将音频数据转换为PyTorch张量并设置为浮点数类型
            input_wav = resampler(input_wav_t[None, :])[0, :].numpy()  # 使用重采样器进行重采样，并将结果转换回NumPy数组
            end_time = time.time()
            elapsed_time = end_time - start_time
            print(f"重采样耗时: {elapsed_time:.2f} 秒")


        async def generate_text():
            return await asyncio.to_thread(transcribe_with_timing,
                                           input=input_wav,
                                           cache={},
                                           language="auto",
                                           use_itn=True,
                                           batch_size=64)

        # Run the asynchronous function
        resp, elapsed_time = await generate_text()
        print(f"[DEBUG] 转录的原始结果是 {resp}")
        text = format_str_v3(resp[0]["text"])
        print(f'[DEBUG] 格式化后的结果 res:{resp} text:{text}')

        # Create the response
        response = TranscriptionResponse(
            code=0,
            msg=f"success, 转录的时间为: {elapsed_time:.2f} 秒",
            data=text
        )
    except Exception as e:
        logger.error("Exception occurred", exc_info=True)
        response = TranscriptionResponse(
            code=1,
            msg=str(e),
            data=" "
        )
    return JSONResponse(content=response.model_dump())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the FastAPI app with a specified port.")
    parser.add_argument('--port', type=int, default=7000, help='Port number to run the FastAPI app on.')
    # parser.add_argument('--certfile', type=str, default='path_to_your_certfile', help='SSL certificate file')
    # parser.add_argument('--keyfile', type=str, default='path_to_your_keyfile', help='SSL key file')
    args = parser.parse_args()

    uvicorn.run(app, host="0.0.0.0", port=args.port)
