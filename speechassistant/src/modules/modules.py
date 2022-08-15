import logging
import pkgutil
import time
import traceback
from pathlib import Path
from threading import Thread

from src.models import User, ContinuousModule
from src.modules import Skills, ModuleWrapper, ModuleWrapperContinuous
from src.modules.continuous import ContinuousModuleHandler


class Modules:
    __instance = None

    @staticmethod
    def get_instance():
        if Modules.__instance is None:
            Modules()
        return Modules.__instance

    def __init__(self) -> None:
        if Modules.__instance is not None:
            raise Exception("Singleton cannot be instantiated more than once!")

        logging.getLogger().setLevel(logging.INFO)
        from src.core import Core

        self.core: Core = Core.get_instance()
        self.local_storage: dict = self.core.local_storage
        self.modules: list = []
        self.continuous_modules: list = []

        self.module_wrapper = ModuleWrapper
        self.module_wrapper_continuous = ModuleWrapperContinuous

        self.continuous_stopped: bool = False
        self.continuous_threads_counter: int = 0
        self.continuous_handler: ContinuousModuleHandler = ContinuousModuleHandler()
        self.module_threads_counter: int = 0

        Modules.__instance = self

        self.load_modules()

    def load_modules(self) -> None:
        self.local_storage["modules"]: dict = {}
        time.sleep(1)
        logging.info("---------- MODULES...  ----------")
        self.modules: list = self.get_modules(self.__get_modules_impl_path())
        if self.modules is []:
            logging.info("[INFO] -- (None present)")
        logging.info("\n----- Continuous MODULES... -----")
        self.continuous_modules: list = self.get_modules(self.__get_continuous_impl_path(), continuous=True)
        if self.continuous_modules is []:
            logging.info("[INFO] -- (None present)")

    def get_modules(self, directory: Path, continuous: bool = False) -> list:
        modules: list = []

        self.__load_all_modules(continuous, directory, modules)

        modules.sort(
            key=lambda module: module.PRIORITY if hasattr(module, "PRIORITY") else 0,
            reverse=True,
        )
        return modules

    def __load_all_modules(self, continuous, directory, modules):
        for finder, name, ispkg in pkgutil.walk_packages(self.__path_with_impl(directory)):
            try:
                mod = self.__load_one_module(finder, name)
            except Exception:
                # catch only exceptions, that are thrown from loader and finder
                self.__handle_loading_error(name)
                continue
            else:
                self.__log_module_status(continuous, name)
                modules.append(mod)

    def __load_one_module(self, finder, name):
        loader = finder.find_module(name)
        mod = loader.load_module(name)
        self.local_storage["modules"][name]: dict = {
            "name": name,
            "status": "loaded",
        }
        return mod

    def __handle_loading_error(self, name):
        logging.debug(traceback.print_exc())
        self.local_storage["modules"][name]: dict = {
            "name": name,
            "status": "error",
        }
        logging.info("[WARNING] Module {} is incorrect and was skipped!".format(name))

    @staticmethod
    def __log_module_status(continuous, name):
        if continuous:
            logging.info("[INFO] Continuous module {} loaded".format(name))
        else:
            logging.info("[INFO] Modul {} loaded".format(name))

    @staticmethod
    def __path_with_impl(path: Path) -> str:
        return str(path.joinpath("impl"))

    def query_threaded(self, name: str, text: str, user: User, messenger: bool = False) -> bool:
        mod_skill: Skills = self.core.skills

        analysis = self.__get_text_analysis(text)

        if name is not None:
            return self.__start_module(analysis, messenger, mod_skill, name, text, user)
        elif text is not None:
            return self.__find_matching_module(analysis, messenger, mod_skill, text, user) is not None

        return False

    def __find_matching_module(self, analysis, messenger, mod_skill, text, user) -> Thread | None:
        for module in self.modules:
            try:
                if module.isValid(str(text).lower()):
                    self.core.active_modules[str(text)] = self.module_wrapper(text, analysis, messenger, user)
                    return self.__start_module_in_new_thread(mod_skill, module, text)
            except AttributeError:
                logging.info(f"[WARNING] {module.__name__} has no isValid() function!")
            except Exception:
                logging.debug(traceback.print_exc())
                logging.info(f"[ERROR] Module {module.__name__} could not be queried!")

    def __start_module(self, analysis, messenger, mod_skill, name, text, user):
        module = next((x for x in self.modules if x.__name__ == name), None)
        if not module:
            logging.info(f"[ERROR] Modul {name} could not be found!")
            return False
        self.core.active_modules[str(text)] = self.module_wrapper(text, analysis, messenger, user)
        self.__start_module_in_new_thread(mod_skill, module, text)
        return True

    def __get_text_analysis(self, text) -> dict:
        if text:
            try:
                return self.core.analyzer.analyze(str(text))
            except Exception:
                logging.debug(traceback.print_exc())
                logging.info("[ERROR] Sentence analysis failed!")
        return {}

    def __start_module_in_new_thread(self, mod_skill, module, text) -> Thread:
        mt: Thread = Thread(target=self.run_threaded_module, args=(text, module, mod_skill))
        mt.daemon = True
        mt.start()
        logging.debug(f"[INFO] Module {module.__name__} started...")
        return mt

    def start_continuous(self) -> None:
        if not self.continuous_modules == []:
            self.__start_all_continuous_modules()
        else:
            logging.info("[INFO] -- (None present)")

    def start_module(
            self,
            user: User = None,
            text: str = None,
            name: str = None,
            messenger: bool = False,
    ) -> bool:
        mod_skill: Skills = self.core.skills
        analysis: dict = self.__get_text_analysis(text)

        if name is not None:
            if not self.__start_module(analysis, messenger, mod_skill, name, text, user):
                return False
            logging.info(f"[ACTION] --Modul {name} was called directly (Parameter: {text})--")
        else:
            thread: Thread = self.__find_matching_module(analysis, messenger, mod_skill, text, user)
            if not thread:
                return False
            self.start_module(user=user, name="wartende_benachrichtigung")
            return True

    def run_threaded_module(self, text: str, module, mod_skill: Skills) -> None:
        try:
            module.handle(text, self.core.active_modules[str(text)], mod_skill)
        except Exception:
            traceback.print_exc()
            logging.info(f"[ERROR] Runtime error in module {module.__name__}. The module was terminated.\n")
            self.core.active_modules[str(text)].say(
                f"Entschuldige, es gab ein Problem mit dem Modul {module.__name__}.")
        finally:
            del self.core.active_modules[str(text)]

    def run_module(self, text: str, module_wrapper: ModuleWrapper, mod_skill: Skills) -> None:
        for module in self.modules:
            if module.isValid(text):
                module.handle(text, module_wrapper, mod_skill)

    def run_continuous(self) -> None:
        # Runs the continuous_modules. Continuous_modules always run in the background,
        # to wait for events other than voice commands (e.g. sensor values, data etc.).
        self.core.continuous_modules = {}

        self.__start_all_continuous_modules()

    def __start_all_continuous_modules(self):
        for module in self.continuous_modules:
            continuous_module: ContinuousModule = ContinuousModule(
                name=module.__name__,
                interval_time=module.INTERVALL if hasattr(module, "INTERVAL") else 0,
                run_function=module.handle
            )
            self.continuous_handler.subscribe(continuous_module)

    def stop_continuous(self) -> None:
        self.continuous_handler.stop_all()

    @staticmethod
    def __get_modules_impl_path() -> Path:
        return Path(__file__).parent.joinpath("on_call")

    @staticmethod
    def __get_continuous_impl_path() -> Path:
        return Path(__file__).parent.joinpath("continuous")
