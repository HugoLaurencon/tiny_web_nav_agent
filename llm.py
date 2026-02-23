import os

from openai import OpenAI

client = OpenAI(
    api_key=os.environ.get("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
)


def call_llm(conversation: list[dict]) -> str:
    response = client.chat.completions.create(
        model="qwen/qwen3-vl-235b-a22b-instruct",
        messages=conversation,
    )
    return response.choices[0].message.content
