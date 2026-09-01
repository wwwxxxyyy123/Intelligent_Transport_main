import os
from openai import OpenAI
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()

# 从环境变量读取敏感信息
API_KEY = os.getenv("AGNES_API_KEY")
BASE_URL = os.getenv("AGNES_BASE_URL")

# 初始化客户端
client = OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL,
)


def test_chat():
    """测试文本对话：发送 '你好'"""
    try:
        response = client.chat.completions.create(
            model="agnes-2.0-flash",  # 文本模型[reference:6]
            messages=[
                {"role": "user", "content": "你好"}
            ],
            max_tokens=500,
            temperature=0.7,
        )

        print("=" * 50)
        print("【Agnes AI 回复】")
        print(response.choices[0].message.content)
        print("=" * 50)
        print(f"消耗 Token: {response.usage.total_tokens}")

    except Exception as e:
        print(f"调用失败: {e}")


def test_stream_chat():
    """测试流式对话（逐字输出）"""
    try:
        stream = client.chat.completions.create(
            model="agnes-2.0-flash",
            messages=[
                {"role": "user", "content": "你好，请做一个简单的自我介绍"}
            ],
            stream=True,  # 开启流式输出
        )

        print("=" * 50)
        print("【Agnes AI 流式回复】")
        for chunk in stream:
            if chunk.choices[0].delta.content:
                print(chunk.choices[0].delta.content, end="", flush=True)
        print("\n" + "=" * 50)

    except Exception as e:
        print(f"调用失败: {e}")


if __name__ == "__main__":
    print("--- 测试1: 普通对话 ---")
    test_chat()

    print("\n--- 测试2: 流式对话 ---")
    test_stream_chat()