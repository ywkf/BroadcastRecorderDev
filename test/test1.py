# test_websocket_client.py

import asyncio
import websockets


async def send_test_audio():
    uri = "ws://localhost:27000/ws/transcribe"
    async with websockets.connect(uri) as websocket:
        with open("../media/recordings/2024-12-11_21-34-15_2.wav", "rb") as f:
            data = f.read()
            await websocket.send(data)
            print(f"发送了 {len(data)} bytes 音频数据")

        response = await websocket.recv()
        print(f"收到响应: {response}")


if __name__ == "__main__":
    asyncio.run(send_test_audio())
