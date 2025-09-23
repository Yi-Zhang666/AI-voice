import os
from dotenv import load_dotenv  # 新增

load_dotenv()  # 新增：会自动读取同目录或根目录下的 .env 文件

from openai import OpenAI

client = OpenAI(
    api_key=os.environ["OPENAI_API_KEY"],
    base_url=os.environ.get("OPENAI_BASE_URL")
)

models = client.models.list()
print("可用模型：")
for m in models.data:
    print("-", m.id)
