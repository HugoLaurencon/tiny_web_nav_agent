"""
python -m unittest tiny_web_nav_agent.tests.test_agent
"""

import unittest
from unittest.mock import MagicMock

from ..agent import (
    Action,
    ActionParseError,
    build_message,
    execute_action,
    parse_action,
    trim_images,
)
from ..browser import BrowserState


class ParseActionTest(unittest.TestCase):
    def test_click_valid(self):
        result = parse_action("Action: Click(500, 300)")
        self.assertEqual(result.name, "Click")
        self.assertEqual(result.args, {"x": 500, "y": 300})

    def test_click_with_reasoning(self):
        response = """<reasoning>
I need to click the button.
</reasoning>
Action: Click(100, 200)"""
        result = parse_action(response)
        self.assertEqual(result.name, "Click")
        self.assertEqual(result.args, {"x": 100, "y": 200})

    def test_click_boundary_values(self):
        result = parse_action("Action: Click(0, 0)")
        self.assertEqual(result.args, {"x": 0, "y": 0})

        result = parse_action("Action: Click(1000, 1000)")
        self.assertEqual(result.args, {"x": 1000, "y": 1000})

    def test_click_out_of_bounds(self):
        with self.assertRaises(ActionParseError) as ctx:
            parse_action("Action: Click(1001, 500)")
        self.assertIn("0-1000", str(ctx.exception))

    def test_click_negative_coordinates(self):
        with self.assertRaises(ActionParseError):
            parse_action("Action: Click(-1, 500)")

    def test_click_wrong_arg_count(self):
        with self.assertRaises(ActionParseError) as ctx:
            parse_action("Action: Click(500)")
        self.assertIn("exactly 2 arguments", str(ctx.exception))

    def test_click_non_integer(self):
        with self.assertRaises(ActionParseError) as ctx:
            parse_action("Action: Click(abc, 300)")
        self.assertIn("Invalid argument format", str(ctx.exception))

    def test_type_valid(self):
        result = parse_action("Action: Type(hello world)")
        self.assertEqual(result.name, "Type")
        self.assertEqual(result.args, {"content": "hello world"})

    def test_type_with_special_chars(self):
        result = parse_action("Action: Type(test@email.com)")
        self.assertEqual(result.args, {"content": "test@email.com"})

    def test_type_empty(self):
        with self.assertRaises(ActionParseError):
            parse_action("Action: Type()")

    def test_scroll_valid(self):
        result = parse_action("Action: Scroll(500, 500, down)")
        self.assertEqual(result.name, "Scroll")
        self.assertEqual(result.args, {"x": 500, "y": 500, "direction": "down"})

    def test_scroll_up(self):
        result = parse_action("Action: Scroll(500, 500, up)")
        self.assertEqual(result.args["direction"], "up")

    def test_scroll_invalid_direction(self):
        with self.assertRaises(ActionParseError) as ctx:
            parse_action("Action: Scroll(500, 500, left)")
        self.assertIn("up", str(ctx.exception))
        self.assertIn("down", str(ctx.exception))

    def test_press_valid(self):
        result = parse_action("Action: Press(Enter)")
        self.assertEqual(result.name, "Press")
        self.assertEqual(result.args, {"key": "Enter"})

    def test_press_tab(self):
        result = parse_action("Action: Press(Tab)")
        self.assertEqual(result.args, {"key": "Tab"})

    def test_press_empty(self):
        with self.assertRaises(ActionParseError):
            parse_action("Action: Press()")

    def test_wait_valid(self):
        result = parse_action("Action: Wait()")
        self.assertEqual(result.name, "Wait")
        self.assertEqual(result.args, {})

    def test_wait_no_parens(self):
        result = parse_action("Action: Wait")
        self.assertEqual(result.name, "Wait")

    def test_finished_valid(self):
        result = parse_action("Action: Finished()")
        self.assertEqual(result.name, "Finished")

    def test_finished_no_parens(self):
        result = parse_action("Action: Finished")
        self.assertEqual(result.name, "Finished")

    def test_calluser_valid(self):
        result = parse_action("Action: CallUser(What is your password?)")
        self.assertEqual(result.name, "CallUser")
        self.assertEqual(result.args, {"question": "What is your password?"})

    def test_calluser_empty(self):
        with self.assertRaises(ActionParseError):
            parse_action("Action: CallUser()")

    def test_unknown_action(self):
        with self.assertRaises(ActionParseError) as ctx:
            parse_action("Action: UnknownAction(123)")
        self.assertIn("Unknown action", str(ctx.exception))

    def test_no_action_found(self):
        with self.assertRaises(ActionParseError) as ctx:
            parse_action("I will click on the button")
        self.assertIn("No valid action found", str(ctx.exception))

    def test_action_without_args_when_required(self):
        with self.assertRaises(ActionParseError) as ctx:
            parse_action("Action: Click")
        self.assertIn("requires arguments", str(ctx.exception))


class BuildMessageTest(unittest.TestCase):
    def test_with_task(self):
        state = BrowserState(
            screenshot_b64="test_screenshot_1", url="https://example.com"
        )
        result = build_message(state, task="Book a flight")

        self.assertEqual(result["role"], "user")
        self.assertIsInstance(result["content"], list)
        self.assertEqual(len(result["content"]), 3)

        self.assertEqual(result["content"][0]["type"], "text")
        self.assertIn("Book a flight", result["content"][0]["text"])

        self.assertEqual(result["content"][1]["type"], "text")
        self.assertIn("https://example.com", result["content"][1]["text"])

        self.assertEqual(result["content"][2]["type"], "image_url")
        self.assertIn("test_screenshot_1", result["content"][2]["image_url"]["url"])

    def test_without_task(self):
        state = BrowserState(
            screenshot_b64="test_screenshot_2", url="https://google.com"
        )
        result = build_message(state)

        self.assertEqual(result["role"], "user")
        self.assertEqual(len(result["content"]), 2)

        self.assertEqual(result["content"][0]["type"], "text")
        self.assertIn("https://google.com", result["content"][0]["text"])

        self.assertEqual(result["content"][1]["type"], "image_url")


class TrimImagesTest(unittest.TestCase):
    def _make_image_message(self, text: str = "URL: test") -> dict:
        return {
            "role": "user",
            "content": [
                {"type": "text", "text": text},
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/png;base64,xxx"},
                },
            ],
        }

    def _make_text_message(self, role: str, text: str) -> dict:
        return {"role": role, "content": text}

    def test_no_trimming_needed(self):
        conversation = [
            self._make_text_message("system", "System prompt"),
            self._make_image_message("URL: page1"),
        ]
        result = trim_images(conversation, max_images=1)
        self.assertEqual(len(result), 2)

    def test_trim_to_one_image(self):
        conversation = [
            self._make_text_message("system", "System prompt"),
            self._make_image_message("URL: page1"),
            self._make_text_message("assistant", "Click"),
            self._make_image_message("URL: page2"),
            self._make_text_message("assistant", "Type"),
            self._make_image_message("URL: page3"),
        ]
        result = trim_images(conversation, max_images=1)

        image_count = 0
        for msg in result:
            if msg["role"] == "user" and isinstance(msg.get("content"), list):
                for item in msg["content"]:
                    if item.get("type") == "image_url":
                        image_count += 1
        self.assertEqual(image_count, 1)

    def test_trim_to_two_images(self):
        conversation = [
            self._make_text_message("system", "System prompt"),
            self._make_image_message("URL: page1"),
            self._make_image_message("URL: page2"),
            self._make_image_message("URL: page3"),
        ]
        result = trim_images(conversation, max_images=2)

        image_count = 0
        for msg in result:
            if msg["role"] == "user" and isinstance(msg.get("content"), list):
                for item in msg["content"]:
                    if item.get("type") == "image_url":
                        image_count += 1
        self.assertEqual(image_count, 2)

    def test_keeps_text_content(self):
        conversation = [
            self._make_text_message("system", "System prompt"),
            self._make_image_message("URL: page1"),
            self._make_image_message("URL: page2"),
        ]
        result = trim_images(conversation, max_images=1)

        has_page1_text = False
        for msg in result:
            if msg["role"] == "user" and isinstance(msg.get("content"), list):
                for item in msg["content"]:
                    if item.get("type") == "text" and "page1" in item.get("text", ""):
                        has_page1_text = True
        self.assertTrue(has_page1_text)

    def test_empty_conversation(self):
        result = trim_images([], max_images=1)
        self.assertEqual(result, [])

    def test_no_images(self):
        conversation = [
            self._make_text_message("system", "System prompt"),
            self._make_text_message("assistant", "Response"),
        ]
        result = trim_images(conversation, max_images=1)
        self.assertEqual(len(result), 2)


class ExecuteActionTest(unittest.TestCase):
    def test_click(self):
        mock_browser = MagicMock()
        action = Action(name="Click", args={"x": 500, "y": 300})

        result = execute_action(action, mock_browser)

        self.assertIsNone(result)
        mock_browser.click.assert_called_once_with(500, 300)

    def test_type(self):
        mock_browser = MagicMock()
        action = Action(name="Type", args={"content": "hello"})

        result = execute_action(action, mock_browser)

        self.assertIsNone(result)
        mock_browser.type_text.assert_called_once_with("hello")

    def test_scroll(self):
        mock_browser = MagicMock()
        action = Action(name="Scroll", args={"x": 500, "y": 500, "direction": "down"})

        result = execute_action(action, mock_browser)

        self.assertIsNone(result)
        mock_browser.scroll.assert_called_once_with(500, 500, "down")

    def test_press(self):
        mock_browser = MagicMock()
        action = Action(name="Press", args={"key": "Enter"})

        result = execute_action(action, mock_browser)

        self.assertIsNone(result)
        mock_browser.press_key.assert_called_once_with("Enter")

    def test_wait(self):
        mock_browser = MagicMock()
        action = Action(name="Wait", args={})

        result = execute_action(action, mock_browser)

        self.assertIsNone(result)
        mock_browser.wait.assert_called_once()

    def test_browser_exception(self):
        mock_browser = MagicMock()
        mock_browser.click.side_effect = Exception("Browser error")
        action = Action(name="Click", args={"x": 500, "y": 300})

        result = execute_action(action, mock_browser)

        self.assertIsNotNone(result)
        self.assertIn("Action execution failed", result)
        self.assertIn("Browser error", result)


if __name__ == "__main__":
    unittest.main()
