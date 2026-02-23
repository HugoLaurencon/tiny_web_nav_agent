import re
from dataclasses import dataclass, field
from typing import Any, Callable

from .browser import Browser, BrowserState
from .llm import call_llm


SYSTEM_PROMPT = """You are a web navigation agent. You control a browser to accomplish user tasks.

## Input
Each turn you receive:
- A screenshot of the current webpage
- The current URL

## Output Format
Think step by step, then output your action:

<reasoning>
[Your thinking about what to do next]
</reasoning>
Action: ActionName(arguments)

## Available Actions
- Click(x, y) - Click at coordinates
- Scroll(x, y, direction) - Scroll at position, direction is "up" or "down"
- Type(text) - Type text (click input field first)
- Press(key) - Press key: Enter, Tab, Escape, Backspace, etc.
- Wait() - Wait for page to load
- Finished() - Task complete
- CallUser(question) - Ask user for help

## Coordinate System
Coordinates are 0-1000 for both x and y:
- (0, 0) = top-left
- (1000, 1000) = bottom-right
- (500, 500) = center

## Examples
<reasoning>
I see Google's homepage. I need to click the search box to type my query.
</reasoning>
Action: Click(500, 400)

<reasoning>
The search box is focused. I'll type my search query.
</reasoning>
Action: Type(flights to Paris)

<reasoning>
Query typed. I'll press Enter to search.
</reasoning>
Action: Press(Enter)

<reasoning>
I need login credentials. I'll ask the user.
</reasoning>
Action: CallUser(What are the login credentials?)"""


@dataclass
class Action:
    name: str
    args: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass
class Step:
    state: BrowserState
    response: str
    action: Action


class ActionParseError(Exception):
    pass


def build_message(state: BrowserState, task: str | None = None) -> dict:
    content = []
    if task:
        content.append({"type": "text", "text": f"Task: {task}"})
    content.append({"type": "text", "text": f"Current URL: {state.url}"})
    content.append(
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{state.screenshot_b64}"},
        }
    )
    return {"role": "user", "content": content}


def trim_images(conversation: list[dict], max_images: int) -> list[dict]:
    """Keep only the last N images in conversation."""
    image_indices = []
    for i, msg in enumerate(conversation):
        if msg["role"] == "user" and isinstance(msg.get("content"), list):
            for item in msg["content"]:
                if item.get("type") == "image_url":
                    image_indices.append(i)
                    break

    if len(image_indices) <= max_images:
        return conversation

    indices_to_remove = set(image_indices[:-max_images])
    result = []
    for i, msg in enumerate(conversation):
        if i in indices_to_remove:
            if msg["role"] == "user" and isinstance(msg.get("content"), list):
                new_content = [
                    item for item in msg["content"] if item.get("type") != "image_url"
                ]
                if new_content:
                    result.append({"role": "user", "content": new_content})
        else:
            result.append(msg)
    return result


def parse_action(response: str) -> Action:
    """Parse action from the LLM response."""
    action_match = re.search(r"Action:\s*(\w+)\(([^)]*)\)", response)
    if not action_match:
        action_line = re.search(r"Action:\s*(\w+)", response)
        if action_line:
            name = action_line.group(1)
            if name in ("Wait", "Finished"):
                return Action(name=name)
            raise ActionParseError(
                f"Action '{name}' requires arguments but none provided"
            )
        raise ActionParseError(
            "No valid action found in response. Expected format: Action: Name(args)"
        )

    name = action_match.group(1)
    args_str = action_match.group(2).strip()

    try:
        if name == "Click":
            if not args_str:
                raise ActionParseError("Click requires coordinates: Click(x, y)")
            parts = [p.strip() for p in args_str.split(",")]
            if len(parts) != 2:
                raise ActionParseError(
                    f"Click requires exactly 2 arguments (x, y), got {len(parts)}"
                )
            x, y = int(parts[0]), int(parts[1])
            if not (0 <= x <= 1000 and 0 <= y <= 1000):
                raise ActionParseError(f"Coordinates must be 0-1000, got ({x}, {y})")
            return Action(name="Click", args={"x": x, "y": y})

        elif name == "Scroll":
            if not args_str:
                raise ActionParseError(
                    "Scroll requires arguments: Scroll(x, y, direction)"
                )
            parts = [p.strip() for p in args_str.split(",")]
            if len(parts) != 3:
                raise ActionParseError(
                    f"Scroll requires 3 arguments (x, y, direction), got {len(parts)}"
                )
            x, y = int(parts[0]), int(parts[1])
            direction = parts[2].strip("'\"").lower()
            if direction not in ("up", "down"):
                raise ActionParseError(
                    f"Scroll direction must be 'up' or 'down', got '{direction}'"
                )
            return Action(name="Scroll", args={"x": x, "y": y, "direction": direction})

        elif name == "Type":
            if not args_str:
                raise ActionParseError("Type requires content: Type(text to type)")
            return Action(name="Type", args={"content": args_str})

        elif name == "Press":
            if not args_str:
                raise ActionParseError("Press requires a key: Press(Enter)")
            return Action(name="Press", args={"key": args_str})

        elif name == "CallUser":
            if not args_str:
                raise ActionParseError(
                    "CallUser requires a question: CallUser(your question here)"
                )
            return Action(name="CallUser", args={"question": args_str})

        elif name in ("Wait", "Finished"):
            return Action(name=name)

        else:
            raise ActionParseError(f"Unknown action: {name}")

    except ValueError as e:
        raise ActionParseError(f"Invalid argument format: {e}")


def execute_action(action: Action, browser: Browser) -> str | None:
    try:
        if action.name == "Click":
            browser.click(action.args["x"], action.args["y"])
        elif action.name == "Scroll":
            browser.scroll(action.args["x"], action.args["y"], action.args["direction"])
        elif action.name == "Type":
            browser.type_text(action.args["content"])
        elif action.name == "Press":
            browser.press_key(action.args["key"])
        elif action.name == "Wait":
            browser.wait()
        return None
    except Exception as e:
        return f"Action execution failed: {e}"


class WebNavAgent:
    def __init__(
        self,
        llm_fn: Callable[[list[dict]], str] = call_llm,
        max_images: int = 1,
        max_steps: int = 10,
        headless: bool = True,
        start_url: str = "https://www.amazon.com/",
        user_input_fn: Callable[[str], str] = input,
    ):
        self.llm_fn = llm_fn
        self.max_images = max_images
        self.max_steps = max_steps
        self.headless = headless
        self.start_url = start_url
        self.user_input_fn = user_input_fn

    def run(self, task: str) -> list[Step]:
        steps: list[Step] = []
        conversation = [{"role": "system", "content": SYSTEM_PROMPT}]

        with Browser(headless=self.headless) as browser:
            state = browser.start(self.start_url)
            conversation.append(build_message(state, task))

            for _ in range(self.max_steps):
                trimmed_conv = trim_images(conversation, self.max_images)
                response = self.llm_fn(trimmed_conv)
                conversation.append({"role": "assistant", "content": response})

                try:
                    action = parse_action(response)
                except ActionParseError as e:
                    action = Action(name="Error", error=str(e))

                steps.append(Step(state=state, response=response, action=action))

                if action.error:
                    conversation.append(
                        {
                            "role": "user",
                            "content": f"Error: {action.error}\nPlease try again with a valid action.",
                        }
                    )
                    continue

                if action.name == "Finished":
                    break

                if action.name == "CallUser":
                    question = action.args.get("question", "Agent needs assistance")
                    user_response = self.user_input_fn(
                        f"Agent asks: {question}\nYour response: "
                    )
                    conversation.append(
                        {"role": "user", "content": f"User response: {user_response}"}
                    )
                    continue

                error = execute_action(action, browser)
                if error:
                    action.error = error
                    conversation.append(
                        {
                            "role": "user",
                            "content": f"Error: {error}\nPlease try a different action.",
                        }
                    )
                    continue

                browser.wait(3000)  # Waits 3 seconds
                state = browser.get_state()
                conversation.append(build_message(state))

        return steps
