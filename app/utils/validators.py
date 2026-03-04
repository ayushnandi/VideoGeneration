from config.settings import Config


def validate_dialogue(data):
    """Validate uploaded dialogue JSON. Returns (lines, error_message)."""
    if not isinstance(data, list):
        return None, "JSON must be an array of dialogue objects."

    if len(data) == 0:
        return None, "Dialogue array is empty."

    if len(data) > Config.MAX_DIALOGUE_LINES:
        return None, f"Too many lines (max {Config.MAX_DIALOGUE_LINES})."

    for i, item in enumerate(data):
        if not isinstance(item, dict):
            return None, f"Line {i + 1}: must be an object."
        if "speaker" not in item or "text" not in item:
            return None, f'Line {i + 1}: must have "speaker" and "text" fields.'
        if not isinstance(item["speaker"], str) or not item["speaker"].strip():
            return None, f"Line {i + 1}: speaker must be a non-empty string."
        if not isinstance(item["text"], str) or not item["text"].strip():
            return None, f"Line {i + 1}: text must be a non-empty string."
        if len(item["text"]) > Config.MAX_TEXT_LENGTH:
            return None, f"Line {i + 1}: text exceeds {Config.MAX_TEXT_LENGTH} chars."

    return data, None
