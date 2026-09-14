from pathlib import Path
import pytest
from account_history_analyzer.artifacts import publish_files
from account_history_analyzer.errors import InputError


def test_OUT_06_existing_output(tmp_path):
    out = tmp_path/'out'
    publish_files({'value.json': b'{}\n'}, out)
    with pytest.raises(InputError, match='nonempty'):
        publish_files({'value.json': b'new'}, out)
    assert (out/'value.json').read_bytes() == b'{}\n'
    publish_files({'value.json': b'new'}, out, overwrite=True)
    assert (out/'value.json').read_bytes() == b'new'


@pytest.mark.parametrize('name', ['../escape','/tmp/escape','a/b','a\\b','..'])
def test_OUT_05_path_traversal(tmp_path, name):
    with pytest.raises(InputError):
        publish_files({name:b'data'},tmp_path/'out')
    assert not (tmp_path/'out').exists()


def test_OUT_07_atomic_failure(tmp_path, monkeypatch):
    original = Path.open
    def fail(path, *args, **kwargs):
        if path.name == 'z.json':
            raise OSError('injected write interruption')
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', fail)
    with pytest.raises(OSError):
        publish_files({'a.json':b'{}','z.json':b'{}','checksums.json':b'{}'},tmp_path/'out')
    assert not (tmp_path/'out').exists()
    assert not list(tmp_path.glob('.ahas-staging-*'))


def test_OUT_05_output_cannot_replace_current_directory_ancestor(tmp_path, monkeypatch):
    working = tmp_path/'project'/'subdir'
    working.mkdir(parents=True)
    marker = working/'keep.txt'
    marker.write_text('source')
    monkeypatch.chdir(working)
    for output in ('.', '..', '../subdir/..'):
        with pytest.raises(InputError, match='dedicated directory'):
            publish_files({'report.html':b'report'}, output, overwrite=True)
    assert marker.read_text() == 'source'


def test_OUT_05_symlink_output_ancestor_refused(tmp_path):
    target = tmp_path/'target'
    target.mkdir()
    alias = tmp_path/'alias'
    alias.symlink_to(target, target_is_directory=True)
    with pytest.raises(InputError, match='symlinks'):
        publish_files({'report.html':b'report'}, alias/'output')
    assert not list(target.iterdir())
