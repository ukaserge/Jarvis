import io
import json
import logging
import os
import pkgutil
import random
import time
import traceback
import urllib
from threading import Thread
from urllib.request import Request, urlopen

import requests

import wb_server as ws
from Audio import AudioOutput, AudioInput
from resources.analyze import Sentence_Analyzer
from resources.module_skills import Skills
from resources.intent.Wrapper import IntentWrapper as AIWrapper
from services import *


class Modules:
    def __init__(self, core, local_storage):
        logging.getLogger().setLevel(logging.INFO)
        self.core = core
        self.local_storage = local_storage
        self.modules = []
        self.continuous_modules = []

        self.module_wrapper = Modulewrapper
        self.module_wrapper_continuous = Modulewrapper_continuous

        self.continuous_stopped = False
        self.continuous_threads_running = 0

        self.load_modules()

    def load_modules(self):
        self.local_storage["modules"] = {}
        time.sleep(1)
        print('---------- MODULES...  ----------')
        self.modules = self.get_modules('modules')
        if self.modules is []:
            print('[INFO] -- (None present)')
        print('\n----- Continuous MODULES... -----')
        self.continuous_modules = self.get_modules('modules/continuous', continuous=True)
        if self.continuous_modules is []:
            print('[INFO] -- (None present)')

    def get_modules(self, directory, continuous=False):
        dirname = os.path.dirname(os.path.abspath(__file__))
        locations = [os.path.join(dirname, directory)]
        modules = []
        if "modules" not in self.local_storage:
            self.local_storage["modules"] = {}
        for finder, name, ispkg in pkgutil.walk_packages(locations):
            try:
                loader = finder.find_module(name)
                mod = loader.load_module(name)
                self.local_storage["modules"][name] = {"name": name, "status": "loaded"}
            except:
                traceback.print_exc()
                self.local_storage["modules"][name] = {"name": name, "status": "error"}
                print('[WARNING] Modul {} is incorrect and was skipped!'.format(name))
                continue
            else:
                if continuous:
                    print('[INFO] Continuous module {} loaded'.format(name))
                    modules.append(mod)
                else:
                    print('[INFO] Modul {} loaded'.format(name))
                    modules.append(mod)
        modules.sort(key=lambda mod: mod.PRIORITY if hasattr(mod, 'PRIORITY') else 0, reverse=True)
        return modules

    def query_threaded(self, name, text, user, messenger=False):
        mod_skill = self.core.skills
        if text is None:
            # generate a random text
            text = random.randint(0, 1000000000)
            analysis = {}
        else:
            # else there is a valid text -> analyze
            try:
                analysis = self.core.analyzer.analyze(str(text))
            except:
                traceback.print_exc()
                print('[ERROR] Sentence analysis failed!')
                analysis = {}
        if name is not None:
            # Module was called via start_module
            for module in self.modules:
                if module.__name__ == name:
                    self.core.active_modules[str(text)] = self.module_wrapper(self.core, text, analysis, messenger,
                                                                              user)
                    mt = Thread(target=self.run_threaded_module, args=(text, module, mod_skill))
                    mt.daemon = True
                    mt.start()
                    return True
            print('[ERROR] Modul {} could not be found!'.format(name))
        elif text is not None:
            # Search the modules normally
            for module in self.modules:
                try:
                    if module.isValid(str(text).lower()):
                        self.core.active_modules[str(text)] = self.module_wrapper(self.core, text, analysis, messenger,
                                                                                  user)
                        mt = Thread(target=self.run_threaded_module, args=(text, module, mod_skill))
                        mt.daemon = True
                        mt.start()
                        return True
                except:
                    traceback.print_exc()
                    print('[ERROR] Modul {} could not be queried!'.format(module.__name__))
        return False

    def start_continuous(self):
        self.continuous_threads_running = 0
        if not self.continuous_modules == []:
            cct = Thread(target=self.run_continuous)
            cct.daemon = True
            cct.start()
            self.continuous_threads_running += 1
        else:
            print('[INFO] -- (None present)')
        return

    def start_module(self, user=None, text=None, name=None, messenger=False):
        # self.query_threaded(name, text, direct, messenger=messenger)
        mod_skill = self.core.skills
        analysis = {}
        if text is None:
            text = str(random.randint(0, 1000000000))
        else:
            try:
                analysis = self.core.analyzer.analyze(str(text))
                # logging.info('Analysis: ' + str(analysis))
            except:
                traceback.print_exc()
                logging.warning('[WARNING] Sentence analysis failed!')

        if name is not None:
            for module in self.modules:
                if module.__name__ == name:
                    logging.info('[ACTION] --Modul {} was called directly (Parameter: {})--'.format(name, text))
                    self.core.active_modules[str(text)] = self.module_wrapper(self.core, text, analysis, messenger,
                                                                              user)
                    mt = Thread(target=self.run_threaded_module, args=(text, module, mod_skill))
                    mt.daemon = True
                    mt.start()
                    break
        else:
            try:
                analysis = self.core.analyzer.analyze(str(text))
            except:
                traceback.print_exc()
                print('[ERROR] Sentence analysis failed!')
                analysis = {}
            for module in self.modules:
                try:
                    if module.isValid(text.lower()):
                        self.core.active_modules[str(text)] = self.module_wrapper(self.core, text, analysis, messenger,
                                                                                  user)
                        mt = Thread(target=self.run_threaded_module, args=(text, module, mod_skill))
                        mt.daemon = True
                        mt.start()
                        mt.join()  # wait until Module is done...
                        self.start_module(user=user, name='wartende_benachrichtigung')
                        break
                except:
                    traceback.print_exc()
                    print('[ERROR] Modul {} could not be queried!'.format(module.__name__))
        return False

    def run_threaded_module(self, text, module, mod_skill):
        try:
            module.handle(text, self.core.active_modules[str(text)], mod_skill)
        except:
            traceback.print_exc()
            print('[ERROR] Runtime error in module {}. The module was terminated.\n'.format(module.__name__))
            self.core.active_modules[str(text)].say(
                'Entschuldige, es gab ein Problem mit dem Modul {}.'.format(module.__name__))
        finally:
            try:
                del self.core.active_modules[str(text)]

            except:
                pass
            return

    def run_module(self, text, module_wrapper, mod_skill):
        for module in self.modules:
            if module.isValid(text):
                module.handle(text, module_wrapper, mod_skill)

    def run_continuous(self):
        # Runs the continuous_modules. Continuous_modules always run in the background,
        # to wait for events other than voice commands (e.g. sensor values, data etc.).
        self.core.continuous_modules = {}
        for module in self.continuous_modules:
            intervall_time = module.INTERVALL if hasattr(module, 'INTERVALL') else 0
            if __name__ == '__main__':
                self.core.continuous_modules[module.__name__] = self.module_wrapper_continuous(self.core,
                                                                                               intervall_time,
                                                                                               self)
            try:
                module.start(self.core.continuous_modules[module.__name__], self.core.local_storage)
                logging.info('[ACTION] Modul {} started'.format(module.__name__))
            except:
                # traceback.print_exc()
                continue
        self.local_storage['module_counter'] = 0
        while not self.continuous_stopped:
            for module in self.continuous_modules:
                if time.time() - self.core.continuous_modules[module.__name__].last_call >= \
                        self.core.continuous_modules[module.__name__].intervall_time:
                    self.core.continuous_modules[module.__name__].last_call = time.time()
                    try:
                        module.run(self.core.continuous_modules[module.__name__], self.core.skills)
                    except:
                        traceback.print_exc()
                        print(
                            '[ERROR] Runtime-Error in Continuous-Module {}. The module is no longer executed.\n'.format(
                                module.__name__))
                        del self.core.continuous_modules[module.__name__]
                        self.continuous_modules.remove(module)
            self.local_storage['module_counter'] += 1
            time.sleep(0.01)
        self.continuous_threads_running -= 1

    def stop_continuous(self):
        # Stops the thread in which the continuous_modules are executed at the end of the run.
        # But gives the modules another opportunity to clean up afterwards...
        if self.continuous_threads_running > 0:
            logging.info('------ Modules are terminated...')
            self.continuous_stopped = True
            # Wait until all threads have returned
            while self.continuous_threads_running > 0:
                print('waiting...', end='\r')
                time.sleep(0.01)
            self.continuous_stopped = False
            # Call the stop() function of each module, if present
            no_stopped_modules = True
            for module in self.continuous_modules:
                try:
                    module.stop(self.core.continuous_modules[module.__name__], self.core.local_storage)
                    logging.info('[ACTION] Modul {} terminated'.format(module.__name__))
                    no_stopped_modules = False
                except:
                    continue
            # clean up
            self.core.continuous_modules = {}
            if no_stopped_modules:
                logging.info('-- (None to finish)')
        return


class Modulewrapper:
    def __init__(self, core, text, analysis, messenger, user):
        self.text = text
        self.analysis = analysis
        # toDo: down below
        # self.analysis['town'] = core.local_storage['home_location'] if self.analysis['town'] is None else None

        self.Audio_Output = core.Audio_Output
        self.Audio_Input = core.Audio_Input

        self.messenger_call = messenger

        self.room = "messenger" if messenger else "raum"
        self.messenger = core.messenger

        self.core = core
        self.skills = core.skills
        self.services = core.services
        self.Analyzer = core.analyzer
        self.local_storage = core.local_storage
        self.system_name = core.system_name
        self.path = core.path
        self.user = user

    def say(self, text, output='auto'):
        text = self.speechVariation(text)
        if output == 'auto':
            if self.messenger_call:
                output = 'messenger'
        if 'messenger' in output.lower() or self.messenger_call:
            self.messenger_say(text)
        else:
            text = self.correct_output_automate(text)
            self.Audio_Output.say(text)

    def messenger_say(self, text):
        try:
            self.messenger.say(text, self.user['telegram_id'])
        except KeyError:
            logging.warning(
                '[WARNING] Sending message "{}" to messenger failed, because there is no Telegram-ID for this user '
                '({}) '.format(text, self.user["name"]))
        except AttributeError:
            logging.info('[WARNING] Sending message to messenger failed,  because there is no key for it!')
        return

    def play(self, path=None, audiofile=None, next=False, notification=False):
        if path is not None:
            with open(path, "rb") as wav_file:
                input_wav = wav_file.read()
        if audiofile is not None:
            with open(audiofile, "rb"):
                input_wav = wav_file.read()
        data = io.BytesIO(input_wav)
        if notification:
            self.Audio_Output.play_notification(data, next)
        else:
            self.Audio_Output.play_playback(data, next)

    def play_music(self, by_name=None, url=None, path=None, next=None, now=None, playlist=None, announce=None):
        if by_name is not None:
            by_name = "'" + by_name + "'"
        # simply forward information
        self.Audio_Output.music_player.play(by_name=by_name, url=url, path=path, next=next, now=now, playlist=playlist,
                                            announce=announce)

    def listen(self, text=None, messenger=None):
        if messenger is None:
            messenger = self.messenger_call
        if text is not None:
            self.say(text)
        if messenger:
            return self.core.messenger_listen(self.user["first_name"].lower())
        else:
            return self.Audio_Input.recognize_input(listen=True)

    def recognize(self, audio_file):
        return self.Audio_Input.recognize_file(audio_file)

    @staticmethod
    def words_in_text(words, text):
        for word in words:
            if word not in text:
                return False
        return True

    def start_module(self, name=None, text=None, user=None):
        self.core.start_module(text, name, user, messenger=self.messenger)

    def start_module_and_confirm(self, name=None, text=None, user=None):
        return self.core.start_module(text, name, user)

    def module_storage(self, module_name=None):
        module_storage = self.core.local_storage.get("module_storage")
        if module_name is None:
            return module_storage
        # I am now just so free and lazy and assume that a module name is passed from a module that actually exists.
        else:
            return module_storage[module_name]

    @staticmethod
    def translate(text, target_lang='de'):
        try:
            request = Request(
                'https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=' + urllib.parse.quote(
                    target_lang) + '&dt=t&q=' + urllib.parse.quote(
                    text))
            response = urlopen(request)
            answer = json.loads(response.read())
            return answer[0][0][0]
        except:
            return text

    def correct_output(self, core_array, messenger_array):
        if self.messenger_call is True:
            return messenger_array
        else:
            return core_array

    def correct_output_automate(self, text):
        text = text.strip()
        # This function is to correct words that should always be corrected right away,
        # so that correct_output doesn't have to be called every time and corrected manually
        # must be corrected
        if self.messenger_call:
            pass
        else:
            correct_output = self.core.config_data["correct_output"]
            for item in correct_output:
                text = text.replace(item, correct_output[item])
        return text

    def start_hotword_detection(self):
        self.Audio_Input.start(config_data['Local_storage']['wakeword_sentensivity'])

    def stopp_hotword_detection(self):
        self.Audio_Input.stop()

    def speechVariation(self, userInput):
        """
        if not isinstance(input, str):
            parse = random.choice(userInput)
        else:
            parse = userInput
        while "[" in parse and "]" in parse:
            sp0 = parse.split("[", 1)
            front = sp0[0]
            sp1 = sp0[1].split("]", 1)
            middle = sp1[0].split("|", 1)
            end = sp1[1]
            parse = front + random.choice(middle) + end
            """
        # toDo
        return userInput


class Modulewrapper_continuous:
    # The same class for continuous_modules. The peculiarity: The say- and listen-functions
    # are missing (so exactly what the module wrapper was actually there for xD), because continuous_-
    # modules are not supposed to make calls to the outside. For this there is a
    # parameter for the time between two calls of the module.
    def __init__(self, core, intervall_time, modules):
        self.intervall_time = intervall_time
        self.last_call = 0
        self.counter = 0
        self.messenger = core.messenger
        self.core = core
        self.Analyzer = core.analyzer
        self.weather = core.weather
        self.audio_Input = core.Audio_Input
        self.audio_Output = core.Audio_Output
        self.local_storage = core.local_storage
        self.system_name = core.system_name
        self.path = core.path
        self.modules = modules

    def start_module(self, name=None, text=None, user=None):
        # user prediction is not implemented yet, therefore here the workaround
        # user = self.local_storage['user']
        self.modules.start_module(text=text, user=user, name=name)

    def start_module_and_confirm(self, name=None, text=None, user=None):
        return self.core.start_module(name, text, user)

    def module_storage(self, module_name=None):
        module_storage = self.core.local_storage.get("module_storage")
        if module_name is None:
            return module_storage
        # I am now just so free and lazy and assume that a module name is passed from a module that actually exists.
        else:
            return module_storage[module_name]

    def translate(self, ttext, targetLang='de'):
        return Modulewrapper.translate(targetLang)


class Core:
    def __init__(self, conf_dat, modules, analyzer, Audio_Input, Audio_Output, system_name):
        self.local_storage = conf_dat["Local_storage"]
        self.config_data = conf_dat
        self.path = conf_dat["Local_storage"]['CORE_PATH']
        self.__data = {}
        self.modules = modules
        self.analyzer = analyzer
        self.services = Services(self, self.__data, conf_dat)
        self.ai = AIWrapper(self)
        self.skills = Skills()
        self.messenger = None
        self.messenger_queued_users = []  # These users are waiting for a response
        self.messenger_queue_output = {}

        self.users = Users(self)

        self.Audio_Input = Audio_Input
        self.Audio_Output = Audio_Output

        self.active_modules = {}
        self.continuous_modules = {}
        self.system_name = system_name

        self.__fill_data()  # since the path is needed, __fill_data() is called only here

        self.ai = AIWrapper(self)
        self.skills = Skills()

        if self.local_storage["home_location"] == "":
            self.local_storage["home_location"] = requests.get("https://ipinfo.io").json()["city"]

    def __fill_data(self):
        with open(relPath + '/data/api_keys.dat') as api_file:
            self.__data["api_keys"] = json.load(api_file)

    def messenger_thread(self):
        # Verarbeitet eingehende Telegram-Nachrichten, weist ihnen Nutzer zu etc.
        while True:
            for msg in self.messenger.messages.copy():
                # Load the user name from the corresponding table
                try:
                    user = self.users.get_user_by_name(msg['from']['first_name'].lower())
                except KeyError:
                    # Messages from strangers will not be tolerated. They are nevertheless stored.
                    self.local_storage['rejected_messenger_messages'].append(msg)
                    try:
                        logging.warning('[WARNING] Message from unknown Telegram user {}. Access denied.'.format(
                            msg['from']['first_name']))
                    except KeyError:
                        logging.warning('[WARNING] Message from unknown Telegram user {}. Access denied.'.format(
                            msg['from']['id']))
                    self.messenger.say(
                        'Entschuldigung, aber ich darf leider zur Zeit nicht mit Fremden reden.',
                        msg['from']['id'], msg['text'])
                    self.messenger.messages.remove(msg)
                    continue

                # no pictures available
                # if msg['type'] == "photo":
                #    self.messenger.say('Leider kann ich noch nichts mit Bildern anfangen.', self.users.get_user_by_name(user))
                # Message is definitely a (possibly inserted) "new request" ("Jarvis,...").
                if msg['text'].lower().startswith("Jarvis"):
                    self.modules.start_module(text=msg['text'], user=user, messenger=True)
                # Message is not a request at all, but a response (or a module expects such a response)
                elif msg['from']['first_name'].lower() in self.messenger_queued_users:
                    self.messenger_queue_output[msg['from']['first_name'].lower()] = msg
                # Message is a normal request
                else:
                    # self.modules.start_module(text=msg['text'], user=user, messenger=True)
                    th = Thread(target=self.modules.start_module, args=(user, msg['text'], None, True,))
                    th.daemon = True
                    th.start()
                '''if response == False:
                    self.messenger.say('Das habe ich leider nicht verstanden.', self.users.get_user_by_name(user)['messenger_id'])'''
                self.messenger.messages.remove(msg)
            time.sleep(0.5)

    def messenger_listen(self, user):
        # Tell the Telegram thread that you are waiting for a reply,
        # But only when no one else is waiting
        if user not in self.messenger_queued_users:
            self.messenger_queued_users.append(user)

        while True:
            # Schauen, ob die Telegram-Antwort eingegangen ist
            response = self.messenger_queue_output.pop(user, None)
            if response is not None:
                self.messenger_queued_users.remove(user)
                logging.info('[ACTION] --{}-- (Messenger): {}'.format(user.upper(), response['text']))
                return response["text"]
            time.sleep(0.03)

    def webserver_action(self, action):
        if action == 'mute':
            return 'ok'
        else:
            return 'err'

    def reload_system(self):
        reload(self)

    def hotword_detected(self, text):
        user = self.users.get_user_by_name(self.local_storage["user"])
        response = self.ai.proceed_with_user_input(text)
        if isinstance(type(response), str):
            self.Audio_Output.say(response)
        elif isinstance(type(response), type({})):
            self.start_module(text, response["module"], user=user)

    def start_module(self, text, name, user=""):
        # user prediction is not implemented yet, therefore here the workaround
        user = self.local_storage['user']
        self.modules.query_threaded(name, text, user)


class Services:
    def __intit__(self, core, __data, configuration_data):
        self.weather = Weather(__data["api_keys"]["open_weather_map"],
                               configuration_data["Local_storage"]["home_location"],
                               core.skills)
        self.light_system = Light(core)


class Users:
    def __init__(self, core):
        self.users = []
        self.core = core
        self.load_users()

    def get_user_list(self):
        return self.users

    def load_users(self):
        # Load users separately from the users folder
        logging.info('---------- USERS ---------')
        location = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'users')
        subdirs = os.listdir(location)
        try:
            subdirs.remove("README.txt")
            subdirs.remove("README.md")
        except ValueError:
            pass
        # We will now go through the individual subfolders of server/users to set up the users.
        # users. The subfolders conveniently have the names of the users.
        for username in subdirs:
            if not username == 'README.txt' and not username == 'README.md':
                userpath = os.path.join(location, username)
                self.add_user(userpath)
                logging.info('[INFO] User {} loaded'.format(username))
        if self.users == []:
            # self.core.Audio_Output.say("Bitte richte zunächst einen Nutzer ein und starte dann das System wieder neu!")
            pass

    def add_user(self, path):
        with open(path + "/data.json") as user_file:
            user_data = json.load(user_file)["User_Info"]
        with open(path + "/resources/user_storage.json") as user_storage_file:
            user_storage = json.load(user_storage_file)
        user_data["user_storage"] = user_storage
        self.users.append(user_data)

    def get_user_by_name(self, name):
        for user in self.users:
            if user.get('first_name').lower() == name.lower():
                return user
        return None

    def get_user_by_id(self, id):
        for user in self.users:
            if user["id"] == id:
                return user
        return None

    def get_user_by_messenger_id(self, t_id):
        for user in self.users:
            if user["messenger_id"] == t_id:
                return user
        return None


def start(config_data):
    """with open(relPath + "config.json", "r") as config_file:
        config_data = json.load(config_file)
    if not config_data["established"]:
        from setup.setup_wizard import FirstStart
        print('[WARNING] System not yet set up. Setup is started...')
        try:
            setup_wizard = FirstStart()
            setup_done = config_data = setup_wizard.run()
            config_data["established"] = True
            with open(relPath + 'config.json', 'w') as file:
                json.dump(config_data, file)
        except:
            print("[WARNING] There was a problem with the Setup-Wizard!")
            traceback.print_exc()"""

    config_data["Local_storage"]["routines"] = []
    config_data["Local_storage"]["alarm_routines"] = []

    logging.info('--------- Start System ---------\n\n')

    system_name = config_data['System_name']
    home_location = config_data["Local_storage"]["home_location"]
    config_data['Local_storage']['CORE_PATH'] = os.path.dirname(os.path.abspath(__file__))
    # clear unnecessary warnings
    modules = None
    analyzer = Sentence_Analyzer()
    Audio_Output = AudioOutput(voice=config_data["voice"])
    os.system('clear')
    Audio_Input = AudioInput()
    core = Core(config_data, modules, analyzer, Audio_Input, Audio_Output, system_name)
    modules = Modules(core, core.local_storage)
    core.modules = modules
    core.local_storage['CORE_starttime'] = time.time()
    Audio_Input.set_core(core, Audio_Output)
    time.sleep(1)
    # -----------Starting-----------#
    modules.start_continuous()
    Audio_Input.start(sentensivity=config_data['wakeword_sentensivity'])
    Audio_Output.start()
    core.start_module(name="reload_routinen", text="")
    core.services.weather.start()
    time.sleep(0.75)

    start_telegram(core)

    webThr = Thread(target=ws.Webserver, args=[core, Modulewrapper(core, "", None, None, None)])
    webThr.daemon = True
    webThr.start()

    logging.info('--------- DONE ---------\n\n')
    core.Audio_Output.say("Jarvis wurde erfolgreich gestartet!")

    # Starting the main-loop
    # main_loop(Local_storage)
    """memory_control = Thread(target=clear_momory())
    memory_control.daemon = True
    memory_control.start()"""

    while True:
        try:
            time.sleep(10)
        except:
            break

    stop(core)


def start_telegram(core):
    if config_data['messenger']:
        logging.info('[ACTION] Start Telegram...')
        if config_data['messenger_key'] == '':
            logging.error('[INFO] No Telegram-Bot-Token entered!')
        else:
            from resources.messenger import TelegramInterface

            core.messenger = TelegramInterface(config_data['messenger_key'], core)
            core.messenger.start()
            tgt = Thread(target=core.messenger_thread)
            tgt.daemon = True
            tgt.start()


def reload(core):
    logging.info('[ACTION] Reload System...\n')
    time.sleep(0.3)
    with open(relPath + "config.json", "r") as config_file:
        logging.info('[INFO] loading configs...')
        core.config_data = json.load(config_file)
        core.local_storage = core.config_data["Local_storage"]

    with open(relPath + "resources/alias/correct_output.json") as correct_output:
        # dont log loading file, because it is a config too
        core.config_data["correct_output"] = json.load(correct_output)

    time.sleep(0.3)
    if core.messenger == None:
        logging.info('[INFO] Load Telegram-API')
        start_telegram(core)

    time.sleep(0.3)
    logging.info('[ACTION] Reload modules')
    core.modules.load_modules()

    """logging.info('Stop Audio-Devices')
    core.Audio_Input.stop()
    core.Audio_Output.stop()"""

    """time.sleep(1)
    logging.info('Start Audio-Devices')
    core.Audio_Input.start()
    core.Audio_Output.start()"""

    time.sleep(0.3)
    logging.info('[ACTION] Reload Analyzer')
    core.analyzer = Sentence_Analyzer()

    time.sleep(0.9)
    logging.info('[INFO] System reloaded successfully!')
    """if webThr is not None:
        if not webThr.is_alive():
            webThr = Thread(target=ws.Webserver, args=[core])
            webThr.daemon = True
            webThr.start()"""

    """stop(core)
    with open(relPath + "config.json", "r") as reload_file:
        reload_dat = json.load(reload_file)
    start(reload_dat)"""


def stop(core):
    logging.info('[ACTION] Stop System...')
    core.local_storage["users"] = {}
    core.local_storage["rejected_messenger_messages"] = []
    config_data["Local_storage"] = core.local_storage
    core.modules.stop_continuous()
    core.Audio_Input.stop()
    core.Audio_Output.stop()
    logging.info('\n[{}] Goodbye!\n'.format(config_data['System_name'].upper()))

    # with open(str(Path(__file__).parent) + '/config.json', 'w') as file:
    #    json.dump(config_data, file, indent=4)


global config_data
global relPath