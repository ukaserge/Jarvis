import json
import math
from datetime import datetime
import requests

INTERVALL = 2

numb_to_day = {
        "1": "monday",
        "2": "tuesday",
        "3": "wednesday",
        "4": "thursday",
        "5": "friday",
        "6": "saturday",
        "7": "sunday"}


def run(core, skills):
    now = datetime.now()

    for routine in core.local_storage["routines"]:
        if is_day_correct(now, routine) and is_time_correct(now, routine, core):
            core.start_module(name="start_routine", text=routine, user=core.user)


def is_day_correct(now, inf):
    is_correct = False
    day_name = numb_to_day.get(str(now.isoweekday()))
    day_inf = inf.get("retakes").get("days")
    if day_inf["daily"] or day_inf[day_name]:
        is_correct = True
    for day in day_inf["date_of_day"]:
        if day == numb_to_day.get(now.day):
            is_correct = True
    return is_correct


def is_time_correct(now, inf, core):
    # after_alarm is ignored, since this is only called by the alarm itself
    is_correct = False
    time_inf = inf["retakes"]["time"]
    if time_inf["clock_time"] is not [""]:
        for time in time_inf["clock_time"]:
            hour = int(time.split(":")[0])
            minute = int(time.split(":")[1])
            if now.hour >= hour and now.minute >= minute:
                is_correct = True
    if inf["retakes"]["after_sunrise"]:
        if is_sunrise(core.local_storage, now):
            is_correct = True
    if inf["retakes"]["after_sunset"]:
        if is_sunset(core.local_storage, now):
            is_correct = True
    return is_correct


def is_sunrise(local_storage, now):
    location = local_storage["home_location"]
    sunrise, sunset = get_sunrise_sunset_inf(location)
    if (sunrise // 60) >= now.hour and (sunrise % 60) >= now.minute:
        return True


def is_sunset(local_storage, now):
    location = local_storage["home_location"]
    sunrise, sunset = get_sunrise_sunset_inf(location)
    if (sunset // 60) >= now.hour and (sunset % 60) >= now.minute:
        return True


def get_sunrise_sunset_inf(location):
    place = location.replace(" ", "+")
    r = requests.get("https://nominatim.openstreetmap.org/search?q={0}&format=json".format(place))
    try:
        response = json.loads(r.text)
        placeData = response[0]
        lat = float(placeData["lat"])
        lon = float(placeData["lon"])
        datetimeTemp = datetime.now()

        day_of_year = int(datetimeTemp.strftime("%j"))
        if 88 < day_of_year < 298:
            timezone = 2
        else:
            timezone = 1
        sT = sunsetTimes(lat, lon, day_of_year, timezone)
        sunrise, sunset = sT.converted
        return sunrise, sunset
    except:
        print("[WARINING] Something went wrong with the Sunrise and Sunset module!")


class sunsetTimes(object):
    def __init__(self, lat_d, lon_d, day_of_year, time_zone=0):
        """
        lat_d: float
        Latitude in degrees
        lon_d: float
        Longitude in degrees
        date: int
        Day of the year
        time_zone: int
        Offset to the UTC-Timezone
        """
        lat = math.radians(lat_d)
        lon = math.radians(lon_d)
        frac_year = ((math.pi * 2) / (365)) * (day_of_year - 1)  # radians
        eq_time = 229.18 * (0.000075 + (0.001868 * math.cos(frac_year)) - (0.032077 * math.sin(frac_year)) - (0.014615 * math.cos(2 * frac_year)) - (0.040849 * math.sin(2 * frac_year)))  # minutes
        decl = 0.006918 - (0.399912 * math.cos(frac_year)) + (0.070257 * math.sin(frac_year)) \
               - (0.006758 * math.cos(2 * frac_year)) + (0.000907 * math.sin(2 * frac_year)) \
               - (0.002697 * math.cos(3 * frac_year)) + (0.00148 * math.sin(3 * frac_year))  # radians
        hour_angle = math.degrees(math.acos(
            math.cos(math.radians(90.833)) / (math.cos(lat) * math.cos(decl))
            - (math.tan(lat) * math.tan(decl))))  # degrees

        times = self.utc_times(lon_d, hour_angle, eq_time)
        self.converted = ((times[0] + time_zone * 60), (times[1] + time_zone * 60))

    @staticmethod
    def utc_times(lon, hour_angle, eq_time):
        """returns utc sunrise and sunset times based on parameters"""
        sunrise = 720 - 4 * (lon + hour_angle) - eq_time
        sunset = 720 - 4 * (lon - hour_angle) - eq_time
        return (sunrise, sunset)

    @staticmethod
    def is_leap(year):
        """checks if the date occurs in a leap year"""
        year = int(year)
        if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0):
            return True
        else:
            return False