"""Run selected repository regressions against the installed wheel, never a corpus."""
from pathlib import Path
import contextlib
import json
import os
import sys

OUT = Path(__file__).resolve().parent
INSTALLED = Path('/tmp/ahas-pilot3-installed')
PINNED = Path('/tmp/ahas-pilot3-reviewed-repo')
sys.path.insert(0, str(INSTALLED))
import account_history_analyzer
import pytest

assert Path(account_history_analyzer.__file__).is_relative_to(INSTALLED)
os.chdir(PINNED)
arguments = [
    '--import-mode=importlib', '-p', 'no:cacheprovider', '-q',
    'tests/test_text.py',
    'tests/test_config.py',
    'tests/test_style.py::test_STYLE_qualification_scope_and_context',
    'tests/test_windows.py::test_WIN_01_both_word_and_record_guards_required',
    'tests/test_windows.py::test_WIN_02_final_remainder_visible_no_padded_or_reused_records',
    'tests/test_windows.py::test_WIN_03_whole_dominant_record_and_exact_half_threshold',
    'tests/test_windows.py::test_WIN_04_kinds_titles_languages_and_missing_times_separate',
]
with (OUT / 'installed_guard_tests.log').open('w') as log:
    with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        exit_code = pytest.main(arguments)
module_paths = {name: module.__file__ for name, module in sys.modules.items()
                if name.startswith('account_history_analyzer') and getattr(module, '__file__', None)}
all_from_wheel = all(Path(path).is_relative_to(INSTALLED) for path in module_paths.values())
report = {
    'pytest_arguments': arguments,
    'exit_code': int(exit_code),
    'all_ahas_modules_loaded_from_installed_wheel': all_from_wheel,
    'ahas_module_paths': module_paths,
    'corpus_read': False,
    'scope': 'Frozen preprocessor regressions and default product qualification/window guards using repository synthetic fixtures only.',
}
(OUT / 'installed_guard_tests.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
print((OUT / 'installed_guard_tests.log').read_text())
assert all_from_wheel
raise SystemExit(int(exit_code))
