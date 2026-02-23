"""
Manual testing script where you act as the LLM and provide the next action.
It shows screenshots of the websites, with the coordinates on hover.
python -m tiny_web_nav_agent.interactive
"""

import base64
import io

import matplotlib.pyplot as plt
from matplotlib.backend_bases import MouseEvent
from PIL import Image

from .agent import WebNavAgent


def show_screenshot(b64_image: str) -> None:
    img_bytes = base64.b64decode(b64_image)
    img = Image.open(io.BytesIO(img_bytes))
    w, h = img.size

    fig, ax = plt.subplots()
    ax.imshow(img)
    ax.set_title("Hover to see coordinates. Close window to continue.")

    def on_move(event: MouseEvent) -> None:
        if event.inaxes:
            x_1000 = int(event.xdata * 1000 / w)
            y_1000 = int(event.ydata * 1000 / h)
            ax.set_xlabel(f"Coordinates: ({x_1000}, {y_1000})")
            fig.canvas.draw_idle()

    fig.canvas.mpl_connect("motion_notify_event", on_move)
    plt.show()


def mock_llm(conversation: list[dict]) -> str:
    for msg in reversed(conversation):
        if msg["role"] == "user" and isinstance(msg.get("content"), list):
            for item in msg["content"]:
                if item.get("type") == "image_url":
                    b64 = item["image_url"]["url"].split(",", 1)[1]
                    show_screenshot(b64)
                    break
            break

    print("\n" + "=" * 60)
    for msg in conversation:
        role = msg["role"]
        if role == "system":
            print(f"[SYSTEM] {msg['content'][:100]}...")
        elif role == "assistant":
            print(f"[ASSISTANT] {msg['content']}")
        elif role == "user":
            content = msg["content"]
            if isinstance(content, list):
                for item in content:
                    if item["type"] == "text":
                        print(f"[USER] {item['text']}")
                    elif item["type"] == "image_url":
                        print("[USER] [IMAGE]")
            else:
                print(f"[USER] {content}")
    print("=" * 60)
    print("\nActions:")
    print("  Click(x, y)              - Click at coordinates")
    print("  Type(text)               - Type text")
    print("  Scroll(x, y, up/down)    - Scroll at position")
    print("  Press(Enter/Tab/...)     - Press key")
    print("  Wait()                   - Wait for page load")
    print("  Finished()               - Task complete")
    print("  CallUser(question)       - Ask user for help")
    print("\nEnter action:")
    line = input()
    return f"Action: {line}" if not line.startswith("Action:") else line


if __name__ == "__main__":
    # task = input("Task: ").strip()
    task = "Add to cart the book 'The Thinking Machine' by Ian Anderson on Amazon."
    agent = WebNavAgent(llm_fn=mock_llm, headless=False)
    agent.run(task)
