from src.modules import ModuleWrapper


def is_valid(text: str) -> bool:
    if "wie" in text and "ist" in text and "wetter" in text and not "wird" in text:
        return True
    return False


def handle(text: str, core: ModuleWrapper) -> None:
    city: str = core.analysis.get("town")
    if city is None:
        city = core.local_storage.get("city")

    response: str = core.services.weather.get_current_weather_string(city)
    core.say(response)
