# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import os
import shutil
import zipfile
import json
import re
from struct import unpack
import difflib

import pytest
from Crypto.Hash import SHA
from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_v1_5
from xml.etree import ElementTree


from buildtools import packager
from buildtools.packagerChrome import defaultLocale
from buildtools.build import processArgs

LOCALES_MODULE = {
    'test.Foobar': {
        'message': 'Ensuring dict-copy from modules for $domain$',
        'description': 'test description',
        'placeholders': {'content': '$1', 'example': 'www.adblockplus.org'}
    }
}

DTD_TEST = ('<!ENTITY access.key "access key(&amp;a)">'
            '<!ENTITY ampersand "foo &amp;-bar">')

PROPERTIES_TEST = 'description=very descriptive!'

ALL_LANGUAGES = ['en_US', 'de', 'it']


MESSAGES_EN_US = json.dumps({
    'name': {'message': 'Adblock Plus'},
    'name_devbuild': {'message': 'devbuild-marker'},
    'description': {
        'message': 'Adblock Plus is the most popular ad blocker ever, '
                   'and also supports websites by not blocking '
                   'unobstrusive ads by default (configurable).'
    },
})


class Content(object):
    """Base class for a unified ZipFile / Directory interface.

    Base class for providing a unified context manager interface for
    accessing files. This class is subclassed by ZipContent and DirContent,
    which provide the additional methods "namelist()" and "read(path)".
    """

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        self._close()


class ZipContent(Content):
    """Provides a unified context manager for ZipFile access.

    Inherits the context manager API from Content.
    If desired, the specified ZipFile is deleted on exiting the manager.
    """

    def __init__(self, zip_path, delete_on_close=True):
        """Constructor of ZipContent handling the file <zip_path>.

        The parameter 'delete_on_close' causes the context manager to
        delete the handled ZipFile (specified by zip_path) if set to
        True (default).
        """

        self._zip_path = zip_path
        self._zip_file = zipfile.ZipFile(zip_path)
        self._delete_on_close = delete_on_close
        super(ZipContent, self).__init__()

    def _close(self):
        self._zip_file.close()
        if self._delete_on_close:
            # if specified, delete the handled file
            os.remove(self._zip_path)

    def namelist(self):
        return self._zip_file.namelist()

    def read(self, path):
        return self._zip_file.read(path)


class DirContent(Content):
    """Provides a unified context manager for directory access.

    Inherits the context managet API from Content.
    """

    def __init__(self, path):
        """Constructor of DirContent handling <path>.
        """

        self._path = path
        super(DirContent, self).__init__()

    def _close(self):
        pass

    def namelist(self):
        """Generate a list of filenames, as expected from ZipFile.nameslist().
        """

        result = []
        for parent, directories, files in os.walk(self._path):
            for filename in files:
                file_path = os.path.join(parent, filename)
                rel_path = os.path.relpath(file_path, self._path)
                result.append(rel_path)
        return result

    def read(self, path):
        content = None
        with open(os.path.join(self._path, path)) as fp:
            content = fp.read()
        return content


def copy_metadata(filename, tmpdir):
    """Copy the used metadata to the used temporary directory."""
    path = os.path.join(os.path.dirname(__file__), filename)
    destination = str(tmpdir.join(filename))
    shutil.copy(path, destination)


def run_webext_build(ext_type, build_opt, srcdir, buildnum=None, keyfile=None):
    """Run a build process."""
    if build_opt == 'build':
        build_args = ['build']
    elif build_opt == 'release':
        build_args = ['build', '-r']
    else:
        build_args = ['devenv']

    args = ['build.py', '-t', ext_type] + build_args

    if keyfile:
        args += ['-k', keyfile]
    if buildnum:
        args += ['-b', buildnum]

    processArgs(str(srcdir), args)


def locale_files(languages, rootfolder, srcdir):
    """Generate example locales.

    languages: tuple, list or set of languages to include
    rootdir: folder-name to create the locale-folders in
    """
    for lang in languages:
        subfolders = rootfolder.split(os.pathsep) + [lang, 'messages.json']
        json_file = srcdir.ensure(*subfolders)
        if lang == defaultLocale:
            json_file.write(MESSAGES_EN_US)
        else:
            json_file.write('{}')


def assert_all_locales_present(package, prefix):
    names = {x for x in package.namelist() if
             x.startswith(os.path.join(prefix, '_locales'))}
    assert names == {
        os.path.join(prefix, '_locales', lang, 'messages.json')
        for lang in ALL_LANGUAGES
    }


@pytest.fixture
def srcdir(tmpdir):
    """Source directory for building the package."""
    for size in ['44', '50', '150']:
        path = tmpdir.join('chrome', 'icons', 'abp-{}.png'.format(size))
        path.write(size, ensure=True)

    tmpdir.join('bar.json').write(json.dumps({}))
    return tmpdir


@pytest.fixture
def gecko_import(tmpdir):
    tmpdir.mkdir('_imp').mkdir('en-US').join('gecko.dtd').write(DTD_TEST)


@pytest.fixture
def locale_modules(tmpdir):
    mod_dir = tmpdir.mkdir('_modules')
    lang_dir = mod_dir.mkdir('en-US')
    lang_dir.join('module.json').write(json.dumps(LOCALES_MODULE))
    lang_dir.join('unit.properties').write(json.dumps(PROPERTIES_TEST))


@pytest.fixture
def icons(srcdir):
    icons_dir = srcdir.mkdir('icons')
    for filename in ['abp-16.png', 'abp-19.png', 'abp-53.png']:
        shutil.copy(
            os.path.join(os.path.dirname(__file__), filename),
            os.path.join(str(icons_dir), filename),
        )


@pytest.fixture
def all_lang_locales(tmpdir):
    return locale_files(ALL_LANGUAGES, '_locales', tmpdir)


@pytest.fixture
def chrome_metadata(tmpdir):
    filename = 'metadata.chrome'
    copy_metadata(filename, tmpdir)


@pytest.fixture
def gecko_webext_metadata(tmpdir, chrome_metadata):
    filename = 'metadata.gecko'
    copy_metadata(filename, tmpdir)


@pytest.fixture
def edge_metadata(tmpdir):
    filename = 'metadata.edge'
    copy_metadata(filename, tmpdir)

    return packager.readMetadata(str(tmpdir), 'edge')


@pytest.fixture
def keyfile(tmpdir):
    """Test-privatekey for signing chrome release-package"""
    return os.path.join(os.path.dirname(__file__), 'chrome_rsa.pem')


@pytest.fixture
def lib_files(tmpdir):
    files = packager.Files(['lib'], set())
    files['ext/a.js'] = 'var bar;'
    files['lib/b.js'] = 'var foo;'

    tmpdir.mkdir('lib').join('b.js').write(files['lib/b.js'])
    tmpdir.mkdir('ext').join('a.js').write(files['ext/a.js'])

    return files


def comparable_xml(xml):
    """Create a nonambiguous representation of a given XML tree."""
    def get_leafs_string(tree):
        """Recursively build a string representing all xml leaf-nodes."""
        root_str = '{}|{}|{}'.format(tree.tag, tree.tail, tree.text).strip()
        result = []

        if len(tree) > 0:
            for subtree in tree:
                for leaf in get_leafs_string(subtree):
                    result.append('{}__{}'.format(root_str, leaf))
        for k, v in tree.attrib.items():
            result.append('{}__{}:{}'.format(root_str, k, v))
        else:
            result.append(root_str)
        return result

    # XML data itself shall not be sorted, hence we can safely sort
    # our string representations in order to produce a valid unified diff.
    return sorted(get_leafs_string(ElementTree.fromstring(xml)))


def comparable_json(json_string):
    """Create a nonambiguous representation of a given JSON string."""
    return json.dumps(
        json.loads(json_string), sort_keys=True, indent=0
    ).split('\n')


def assert_manifest_content(manifest, expected_path):
    extension = os.path.basename(expected_path).split('.')[-1]

    with open(expected_path, 'r') as fp:
        if extension == 'xml':
            generated = comparable_xml(manifest)
            expected = comparable_xml(fp.read())
        else:
            generated = comparable_json(manifest)
            expected = comparable_json(fp.read())

    diff = list(difflib.unified_diff(generated, expected, n=0))
    assert len(diff) == 0, '\n'.join(diff)


def assert_gecko_locale_conversion(package, prefix):
    locale = json.loads(package.read(os.path.join(
        prefix, '_locales/en_US/messages.json')))

    assert locale.get('test_Foobar', {}) == LOCALES_MODULE['test.Foobar']
    assert locale.get('access_key', {}) == {'message': 'access key'}
    assert locale.get('ampersand', {}) == {'message': 'foo -bar'}
    assert locale.get('_description', {}) == {'message': 'very descriptive!"'}


def assert_convert_js(package, prefix, excluded=False):
    libfoo = package.read(os.path.join(prefix, 'lib/foo.js'))

    assert 'var bar;' in libfoo
    assert 'require.modules["ext_a"]' in libfoo

    assert ('var foo;' in libfoo) != excluded
    assert ('require.modules["b"]' in libfoo) != excluded


def assert_devenv_scripts(package, devenv):
    manifest = json.loads(package.read('manifest.json'))
    filenames = package.namelist()
    scripts = [
            'ext/common.js',
            'ext/background.js',
    ]

    assert ('qunit/index.html' in filenames) == devenv
    assert ('devenvPoller__.js' in filenames) == devenv
    assert ('devenvVersion__' in filenames) == devenv

    if devenv:
        assert '../ext/common.js' in package.read('qunit/index.html')
        assert '../ext/background.js' in package.read('qunit/index.html')

        assert set(manifest['background']['scripts']) == set(
            scripts + ['devenvPoller__.js']
        )
    else:
        assert set(manifest['background']['scripts']) == set(scripts)


def assert_base_files(package, platform):
    filenames = set(package.namelist())

    if platform in {'chrome', 'gecko'}:
        assert 'bar.json' in filenames
        assert 'manifest.json' in filenames
        assert 'lib/foo.js' in filenames
        assert 'foo/logo_50.png' in filenames
        assert 'icons/logo_150.png' in filenames
    else:
        assert 'AppxManifest.xml' in filenames
        assert 'AppxBlockMap.xml' in filenames
        assert '[Content_Types].xml' in filenames

        assert 'Extension/bar.json' in filenames
        assert 'Extension/lib/foo.js' in filenames

        assert package.read('Assets/logo_44.png') == '44'
        assert package.read('Extension/icons/abp-44.png') == '44'


def assert_chrome_signature(filename, keyfile):
    with open(filename, 'r') as fp:
        content = fp.read()

    _, _, l_pubkey, l_signature = unpack('<4sIII', content[:16])
    signature = content[16 + l_pubkey: 16 + l_pubkey + l_signature]

    digest = SHA.new()
    with open(keyfile, 'r') as fp:
        rsa_key = RSA.importKey(fp.read())

    signer = PKCS1_v1_5.new(rsa_key)

    digest.update(content[16 + l_pubkey + l_signature:])
    assert signer.verify(digest, signature)


def assert_locale_upfix(package):
    translations = [
        json.loads(package.read('_locales/{}/messages.json'.format(lang)))
        for lang in ALL_LANGUAGES
    ]

    manifest = package.read('manifest.json')

    # Chrome Web Store requires descriptive translations to be present in
    # every language.
    for match in re.finditer(r'__MSG_(\S+)__', manifest):
        name = match.group(1)

        for other in translations[1:]:
            assert translations[0][name]['message'] == other[name]['message']


@pytest.mark.usefixtures(
    'all_lang_locales',
    'locale_modules',
    'gecko_import',
    'icons',
    'lib_files',
    'chrome_metadata',
    'gecko_webext_metadata',
    'edge_metadata',
)
@pytest.mark.parametrize('platform,dev_build_release,buildnum', [
    ('chrome', 'build', '1337'),
    ('chrome', 'devenv', None),
    ('chrome', 'release', None),
    ('gecko', 'build', '1337'),
    ('gecko', 'devenv', None),
    ('gecko', 'release', None),
    ('edge', 'build', '1337'),
    pytest.param('edge', 'devenv', None, marks=pytest.mark.xfail),
    ('edge', 'release', None),
])
def test_build_webext(platform, dev_build_release, keyfile, tmpdir, srcdir,
                      buildnum, capsys):
    release = dev_build_release == 'release'
    devenv = dev_build_release == 'devenv'

    if platform == 'chrome' and release:
        key = keyfile
    else:
        key = None

    manifests = {
        'gecko': [('', 'manifest', 'json')],
        'chrome': [('', 'manifest', 'json')],
        'edge': [('', 'AppxManifest', 'xml'),
                 ('Extension', 'manifest', 'json')],
    }

    filenames = {
        'gecko': 'adblockplusfirefox-1.2.3{}.xpi',
        'chrome': 'adblockpluschrome-1.2.3{{}}.{}'.format(
            {True: 'crx', False: 'zip'}[release]
        ),
        'edge': 'adblockplusedge-1.2.3{}.appx',
    }

    if platform == 'edge':
        prefix = 'Extension'
    else:
        prefix = ''

    run_webext_build(platform, dev_build_release, srcdir, buildnum=buildnum,
                     keyfile=key)

    # The makeIcons() in packagerChrome.py should warn about non-square
    # icons via stderr.
    if platform in {'chrome', 'gecko'}:
        out, err = capsys.readouterr()
        assert 'icon should be square' in err

    if devenv:
        content_class = DirContent
        out_file_path = os.path.join(str(srcdir), 'devenv.' + platform)
    else:
        content_class = ZipContent

        if release:
            add_version = ''
        else:
            add_version = '.' + buildnum

        out_file = filenames[platform].format(add_version)

        out_file_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__), os.pardir, out_file))
        assert os.path.exists(out_file_path)

    if release and platform == 'chrome':
        assert_chrome_signature(out_file_path, keyfile)

    with content_class(out_file_path) as package:
        assert_base_files(package, platform)
        assert_all_locales_present(package, prefix)
        assert_gecko_locale_conversion(package, prefix)
        assert_convert_js(package, prefix, platform == 'gecko')

        if platform == 'chrome':
            assert_locale_upfix(package)
        if platform in {'chrome', 'gecko'}:
            assert_devenv_scripts(package, devenv)

        for folder, name, ext in manifests[platform]:
            filename = '{{}}_{}_{}.{{}}'.format(platform, dev_build_release)
            expected = os.path.join(
                os.path.dirname(__file__),
                'expecteddata',
                filename.format(name, ext),
            )

            assert_manifest_content(
                package.read(os.path.join(folder, '{}.{}'.format(name, ext))),
                expected,
            )
