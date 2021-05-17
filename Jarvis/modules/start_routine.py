import logging


def isValid(text):
    return False


def handle(text, core, skills):
    actions = text["actions"]

    try:
        for action in actions:
            if action["module_name"] == "":
                core.start_module(text=action["text"], user=core.user)
            else:
                core.start_module(name=action["module_name"], text=action["text"], user=core.user)
    except:
        core.local_storage["routines"].remove(text)
        logging.warning(f'Routine with action {text["description"]} doesnt works. It is removed from the List!')
