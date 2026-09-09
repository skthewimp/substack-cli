"""Security boundaries are exercised offline; no real cookies or publications."""
import io
import json
import stat
import urllib.error
import urllib.request
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from test_update import ARTICLE, FakeClient, paragraph

from substack_cli import api, cli, config, security
from substack_cli.errors import CLIError
from substack_cli.md2pm import Converter
from substack_cli.pm2md import ImageStore


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    for key in config.ENV_KEYS.values():
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path / 'config'))
    monkeypatch.setenv('SUBSTACK_BACKUP_DIR', str(tmp_path / 'backups'))


def test_checkout_cannot_redirect_saved_cookie(tmp_path, monkeypatch):
    config.write_config(config.user_config_path(), {
        'publication_url': 'https://trusted.substack.com', 'session_token': 'secret'})
    (tmp_path / '.substack.json').write_text(json.dumps({
        'publication_url': 'https://attacker.example'}))
    monkeypatch.chdir(tmp_path)
    loaded = config.load()
    assert loaded.publication_url == 'https://trusted.substack.com'
    assert loaded.session_token == 'secret'


def test_explicit_config_does_not_inherit_cookie(tmp_path):
    config.write_config(config.user_config_path(), {'session_token': 'secret'})
    chosen = tmp_path / 'chosen.json'
    chosen.write_text('{"publication_url":"https://attacker.example"}')
    with pytest.raises(CLIError):
        assert config.load(chosen).session_token


@pytest.mark.parametrize('key,value', [
    ('SUBSTACK_PUBLICATION_URL', 'https://attacker.example'),
    ('SUBSTACK_SESSION_TOKEN', 'secret'), ('SUBSTACK_HUB_SESSION_TOKEN', 'hub')])
def test_partial_environment_identity_refused(monkeypatch, key, value):
    monkeypatch.setenv(key, value)
    with pytest.raises(CLIError):
        config.load()


@pytest.mark.parametrize('url', ['http://x.substack.com', 'https://u:p@x.substack.com',
    'https://x.substack.com/path', 'https://x.substack.com?next=elsewhere',
    'https://x.substack.com:8080', 'file:///etc/passwd'])
def test_unsafe_origin_rejected(url):
    with pytest.raises(CLIError):
        security.https_origin(url)


@pytest.mark.parametrize('target', ['https://evil.example', 'http://trusted.substack.com',
                                  'https://trusted.substack.com/elsewhere'])
def test_cookie_redirects_refused(target):
    req = urllib.request.Request('https://trusted.substack.com/api/v1/drafts',
                                 headers={'Cookie': 'connect.sid=fake'})
    with pytest.raises(CLIError):
        security.NoRedirect().redirect_request(req, None, 302, 'Found', {}, target)


def test_writes_never_retry_on_ambiguous_server_failure(monkeypatch):
    transport = Mock()
    transport.open.side_effect = urllib.error.HTTPError(
        'https://trusted.substack.com', 503, 'bad', {}, io.BytesIO(b'reflected-secret'))
    monkeypatch.setattr(api, 'opener', lambda: transport)
    client = api.Client(config.Config({'publication_url': 'https://trusted.substack.com',
                                      'session_token': 'fake'}, None))
    with pytest.raises(CLIError) as caught:
        client.post('/drafts', {})
    assert transport.open.call_count == 1
    assert 'reflected-secret' not in str(caught.value)


def test_reads_still_retry(monkeypatch):
    transport = Mock()
    response = Mock()
    response.__enter__ = Mock(return_value=SimpleNamespace(read=lambda: b'{}'))
    response.__exit__ = Mock(return_value=False)
    transport.open.side_effect = [urllib.error.URLError('lost'), response]
    monkeypatch.setattr(api, 'opener', lambda: transport)
    monkeypatch.setattr(api.time, 'sleep', lambda _: None)
    client = api.Client(config.Config({'publication_url': 'https://trusted.substack.com',
                                      'session_token': 'fake'}, None))
    assert client.get('/subscription') == {}
    assert transport.open.call_count == 2


@pytest.mark.parametrize('link', [False, True])
def test_image_cannot_escape_article_directory(tmp_path, link):
    root = tmp_path / 'article'
    root.mkdir()
    secret = tmp_path / 'secret.png'
    secret.write_bytes(b'\x89PNG\r\n\x1a\nprivate')
    if link:
        (root / 'link.png').symlink_to(secret)
    uploader = Mock()
    with pytest.raises(CLIError):
        Converter(base_dir=root, upload=uploader).convert(
            '![](link.png)' if link else '![](../secret.png)')
    uploader.assert_not_called()


def test_non_image_bytes_never_leave_machine(tmp_path, monkeypatch):
    secret = tmp_path / 'pretend.png'
    secret.write_text('a secret')
    monkeypatch.setenv('SUBSTACK_ASSET_ROOT', str(tmp_path))
    client = api.Client(None)
    client.post = Mock()
    with pytest.raises(CLIError):
        client.upload_image(secret)
    client.post.assert_not_called()


def test_private_config_is_atomic_and_replaces_symlink(tmp_path):
    victim = tmp_path / 'victim'
    victim.write_text('untouched')
    target = tmp_path / 'config.json'
    target.symlink_to(victim)
    config.write_config(target, {'session_token': 'fake'})
    assert victim.read_text() == 'untouched'
    assert not target.is_symlink()
    assert stat.S_IMODE(target.stat().st_mode) == 0o600


@pytest.mark.parametrize('url', ['file:///etc/passwd', 'http://127.0.0.1/x',
                                 'https://evil.example/image.png'])
def test_pull_rejects_untrusted_image_urls(tmp_path, monkeypatch, url):
    transport = Mock()
    monkeypatch.setattr('substack_cli.pm2md.opener', lambda: transport)
    store = ImageStore(tmp_path, 'post')
    assert store.fetch(url) is None
    assert store.failures
    transport.open.assert_not_called()


def test_email_requires_explicit_opt_in():
    parser = cli.build_parser()
    assert parser.parse_args(['publish', '1', '--yes']).no_email
    assert not parser.parse_args(['publish', '1', '--yes', '--send-email']).no_email
    assert parser.parse_args(['schedule', '1', '--at', '2027-01-01']).no_email


def test_update_refuses_text_loss_even_with_yes(tmp_path):
    path = tmp_path / 'post.md'
    path.write_text(ARTICLE)
    client = FakeClient(body={'type':'doc', 'content':[paragraph('Irreplaceable text')]})
    with pytest.raises(CLIError, match='requires review'):
        cli.cmd_update(client, cli.build_parser().parse_args(['update', str(path), '--yes']))
    assert not client.calls


def test_reviewed_replacement_backs_up_live_record(tmp_path):
    path = tmp_path / 'post.md'
    path.write_text(ARTICLE)
    client = FakeClient(body={'type':'doc', 'content':[paragraph('Old text')]})
    digest = security.revision(client.record)
    args = cli.build_parser().parse_args(['update', str(path), '--yes',
                                          '--accept-live-sha256', digest])
    cli.cmd_update(client, args)
    files = list((tmp_path / 'backups').glob('*.json'))
    assert len(files) == 1
    assert json.loads(files[0].read_text()) == client.record
    assert len(client.calls) == 2


def test_stale_approval_refused(tmp_path):
    path = tmp_path / 'post.md'
    path.write_text(ARTICLE)
    client = FakeClient()
    args = cli.build_parser().parse_args(['update', str(path), '--yes',
                                         '--accept-live-sha256', '0'*64])
    with pytest.raises(CLIError, match='changed since review'):
        cli.cmd_update(client, args)
    assert not client.calls


def test_equal_image_counts_do_not_hide_replacement(tmp_path):
    path = tmp_path / 'post.md'
    path.write_text(ARTICLE + '\n![caption](https://cdn/new.png)\n')
    live, _ = Converter().convert('![caption](https://cdn/old.png)')
    client = FakeClient(body=live)
    args = cli.build_parser().parse_args(['audit', str(path), '--json'])
    _, fields, body = cli.read_article(path)
    report = cli.audit_report(client, args, path, fields, body)
    assert not report['clean']
    assert report['removed_images'] == ['https://cdn/old.png']


@pytest.mark.parametrize("name", ["connect.sid", "substack.sid"])
def test_publication_request_uses_the_selected_cookie_name(monkeypatch, name):
    transport = Mock()
    response = Mock()
    response.__enter__ = Mock(return_value=SimpleNamespace(read=lambda: b'{}'))
    response.__exit__ = Mock(return_value=False)
    transport.open.return_value = response
    monkeypatch.setattr(api, "opener", lambda: transport)
    client = api.Client(config.Config({
        "publication_url": "https://trusted.substack.com", "session_token": "fake",
        "session_cookie_name": name}, None))
    client.get("/subscription")
    request = transport.open.call_args.args[0]
    assert request.get_header("Cookie") == name + "=fake"


def test_unrecognized_cookie_name_cannot_inject_headers():
    settings = config.Config({"session_cookie_name": "other; injected=value"}, None)
    with pytest.raises(CLIError, match="cookie name"):
        assert settings.session_cookie_name
