import time
from threading import Thread
from selenium import webdriver
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.keys import Keys
from pyvirtualdisplay import Display


class Text_to_Speech:

    def __init__(self, ):
        self.driver = None
        self.text_area = None
        self.play_button = None
        self.to_say = []
        self.stopped = False
        self.is_reading = False

    def start(self, gender):
        print("\n\n")
        tts_thread = Thread(target=self.run(gender))
        tts_thread.daemon = True
        tts_thread.start()

    def run(self, gender):
        print("[LOADING] Speechmodule")
        self.display = Display(visible=False, size=(800, 600))
        self.display.start()
        # start browser
        URL = "https://ttsmp3.com/text-to-speech/German/"
        opt = webdriver.ChromeOptions()
        chrome_prefs = {"profile.managed_default_content_settings.images": 2}
        opt.add_argument("--no-sandbox")
        opt.add_argument("--disable-setuid-sandbox")
        opt.add_argument("--disable-webgl")
        opt.add_argument("no-default-browser-check")
        opt.add_argument("no-first-run")
        opt.add_experimental_option("prefs", chrome_prefs)
        self.driver = webdriver.Chrome('/usr/lib/chromium-browser/chromedriver', chrome_options=opt)
        self.driver.get(URL)
        self.text_area = self.driver.find_element_by_id('voicetext')
        self.play_button = self.driver.find_element_by_id('vorlesenbutton')
        self.select_voice(gender)

    def say(self, text):
        # output the entered text as audio
        self.is_reading = True
        self.push_text(text)
        # wait until the text has been changed
        while self.text_area.get_attribute('value') != text:
            time.sleep(0.1)
        self.play_audio()
        # wait until the text was said
        while not self.play_button.get_attribute('value') == "Read":
            time.sleep(0.1)
        self.is_reading = False

    def push_text(self, text):
        script = "var element = arguments[0], txt = arguments[1]; element.value = txt; element.dispatchEvent(new Event('change'));"
        self.driver.execute_script(script, self.text_area, text)

    def select_voice(self, gender):
        voice = ''
        if gender == "male":
            voice = 'Hans'
        elif gender == "female":
            voice = 'Vicki'
        Select(self.driver.find_element_by_id('sprachwahl')).select_by_value(voice)

    def play_audio(self):
        self.play_button.click()

    def stop(self):
        self.stopped = True
        self.driver.quit()
        self.display.stop()