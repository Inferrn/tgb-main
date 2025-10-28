import sys
from pathlib import Path
import importlib.util
import types

ROOT = Path(__file__).resolve().parents[1]
# create minimal package modules to allow loading
pkg_app = types.ModuleType('app')
pkg_app.__path__ = [str(ROOT / 'app')]
sys.modules['app'] = pkg_app
pkg_app_data = types.ModuleType('app.data')
pkg_app_data.__path__ = [str(ROOT / 'app' / 'data')]
sys.modules['app.data'] = pkg_app_data

# helper to load module
def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

dm = load_module('app.data.data_models', str(ROOT / 'app' / 'data' / 'data_models.py'))
dl = load_module('app.data.data_loader', str(ROOT / 'app' / 'data' / 'data_loader.py'))
ss = load_module('app.services.survey_service', str(ROOT / 'app' / 'services' / 'survey_service.py'))

survey_data = dl.load_survey_data(str(ROOT / 'app' / 'data' / 'ovz.json'))
service = ss.SurveyService(survey_data)
level = service.get_level('modul_2', 3, 0)
print('level object:', level)
opts = service.get_options_for_level(level)
print('options type:', type(opts), 'len=', len(opts))
print('options sample:', opts)
