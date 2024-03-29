import time

from src.modules import ModuleWrapper, skills

PRIORITY = 3  # because hanoi


def is_valid(text: str) -> bool:
    text = text.lower()
    if (
            "buchstabier" in text
            or "diktier" in text
            or ("wie" in text and ("geschrieben" in text or "schreibt" in text))
    ):
        return True
    return False


def handle(text: str, wrapper: ModuleWrapper) -> None:
    if "buchstabier" in text:
        word = skills.get_text_between("buchstabier", text)[0]
    elif "diktier" in text:
        word = skills.get_text_between("diktier", text)[0]
    elif "wie" in text and "geschrieben" in text:
        word = skills.get_text_between("wird", text)[0]
    elif "wie" in text and "schreibt" in text:
        word = skills.get_text_between("man", text)[0]
    else:
        wrapper.say("Leider habe ich nicht verstanden, was ich buchstabieren soll.")
        return

    for letter in word:
        wrapper.say(letter)
        time.sleep(0.5)
