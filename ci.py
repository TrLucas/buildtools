# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import glob
import io
import json
import os
from urllib import urlencode
import urllib2

import yaml

class Uploader(object):
    PACKAGE_SUFFIXES = {
        'gecko': '.xpi',
        'chrome': {'pre': '.zip', 'post': '.crx'},
        'safari': '.safariextz',
        'edge': '.appx',
    }

    def __init__(self, base_dir, platform):
        self.base_dir = base_dir
        self.platform = platform
        super(Uploader, self).__init__()

    def find_artifact(self):
        suffix = self.PACKAGE_SUFFIXES[self.platform]
        if isinstance(suffix, dict):
            suffix = suffix['pre']

        match = os.path.join(self.base_dir, '*' + suffix)

        return glob.glob(match)[0]

    def __call__(self):
        filename = self.find_artifact()
        print filename

#    def uploadToMozillaAddons(self):
#        import urllib3
#
#        config = get_config()
#
#        upload_url = ('https://addons.mozilla.org/api/v3/addons/{}/'
#                      'versions/{}/').format(self.extensionID, self.version)
#
#        with open(self.path, 'rb') as file:
#            data, content_type = urllib3.filepost.encode_multipart_formdata({
#                'upload': (
#                    os.path.basename(self.path),
#                    file.read(),
#                    'application/x-xpinstall',
#                ),
#            })
#
#        request = self.generate_mozilla_jwt_request(
#            config.get('extensions', 'amo_key'),
#            config.get('extensions', 'amo_secret'),
#            upload_url,
#            'PUT',
#            data,
#            [('Content-Type', content_type)],
#        )
#
#        try:
#            urllib2.urlopen(request).close()
#        except urllib2.HTTPError as e:
#            shutil.copyfile(
#                self.path,
#                os.path.join(get_config().get('extensions', 'root'),
#                             'failed.' + self.config.packageSuffix),
#            )
#            try:
#                logging.error(e.read())
#            finally:
#                e.close()
#            raise
#
#        self.add_to_downloads_lockfile(
#            self.config.type,
#            {
#                'buildtype': 'devbuild',
#                'app_id': self.extensionID,
#                'version': self.version,
#            },
#        )
#        os.remove(self.path)
#
#    def download_from_mozilla_addons(self, buildtype, version, app_id):
#        config = get_config()
#        iss = config.get('extensions', 'amo_key')
#        secret = config.get('extensions', 'amo_secret')
#
#        url = ('https://addons.mozilla.org/api/v3/addons/{}/'
#               'versions/{}/').format(app_id, version)
#
#        request = self.generate_mozilla_jwt_request(
#            iss, secret, url, 'GET',
#        )
#        response = json.load(urllib2.urlopen(request))
#
#        filename = '{}-{}.xpi'.format(self.basename, version)
#        self.path = os.path.join(
#            config.get('extensions', 'nightliesDirectory'),
#            self.basename,
#            filename,
#        )
#
#        necessary = ['passed_review', 'reviewed', 'processed', 'valid']
#        if all(response[x] for x in necessary):
#            download_url = response['files'][0]['download_url']
#            checksum = response['files'][0]['hash']
#
#            request = self.generate_mozilla_jwt_request(
#                iss, secret, download_url, 'GET',
#            )
#            try:
#                response = urllib2.urlopen(request)
#            except urllib2.HTTPError as e:
#                logging.error(e.read())
#
#            # Verify the extension's integrity
#            file_content = response.read()
#            sha256 = hashlib.sha256(file_content)
#            returned_checksum = '{}:{}'.format(sha256.name, sha256.hexdigest())
#
#            if returned_checksum != checksum:
#                logging.error('Checksum could not be verified: {} vs {}'
#                              ''.format(checksum, returned_checksum))
#
#            with open(self.path, 'w') as fp:
#                fp.write(file_content)
#
#            self.update_link = os.path.join(
#                config.get('extensions', 'nightliesURL'),
#                self.basename,
#                filename,
#            )
#
#            self.remove_from_downloads_lockfile(self.config.type,
#                                                'version',
#                                                version)
#        elif not response['passed_review'] or not response['valid']:
#            # When the review failed for any reason, we want to know about it
#            logging.error(json.dumps(response, indent=4))
#            self.remove_from_downloads_lockfile(self.config.type,
#                                                'version',
#                                                version)


def upload_to_stores(base_dir, platform):
    uploader = Uploader(base_dir, platform)
    uploader()

def lint_gitlab_config(base_dir):
    filename = '.gitlab-ci.yml'

    with io.open(os.path.join(base_dir, filename), 'rt') as fp:
        yaml_data = yaml.load(fp.read())

    post_data = {'content': json.dumps(yaml_data)}
    request = urllib2.Request('https://gitlab.com/api/v4/ci/lint/',
                              data=urlencode(post_data))
    print urllib2.urlopen(request).read()
