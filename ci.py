# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import base64
import glob
import hashlib
import hmac
import io
import json
import logging
import os
import time
import uuid
from urllib import urlencode
import urllib2

# from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_v1_5
import Crypto.Hash.SHA256

from buildtools.packager import (get_extension, get_app_id, readMetadata,
                                 getBuildVersion)


class Uploader(object):
    def __init__(self, base_dir, platform):
        self.base_dir = base_dir
        self.platform = platform

        self.metadata = readMetadata(self.base_dir, self.platform)

        is_release = False
        # TODO: actually distinguish between dev / release builds
        self.extension_id = get_app_id(is_release, self.metadata)
        self.version = getBuildVersion(base_dir, self.metadata, is_release)
        self.basename = self.metadata.get('general', 'basename')

        super(Uploader, self).__init__()

    def __call__(self):
        filename = self.find_artifact()
        if self.platform == 'gecko':
            print 'attempting to upload ' + filename
            self.upload_to_amo(filename)
            tries = 0
            while tries < 10:
                if self.download_from_amo():
                    print 'DONE!'
                    break
                tries += 1
                print 'trying attempt {} in 10 seconds...'.format(tries)
                time.sleep(10)

    def find_artifact(self):
        match = os.path.join(self.base_dir,
                             '*.' + get_extension(self.platform))

        return glob.glob(match)[0]

    def azure_jwt_signature_fnc(self):
        return (
            'RS256',
            lambda s, m: PKCS1_v1_5.new(s).sign(Crypto.Hash.SHA256.new(m)),
        )

    def mozilla_jwt_signature_fnc(self):
        return (
            'HS256',
            lambda s, m: hmac.new(s, msg=m, digestmod=hashlib.sha256).digest(),
        )

    def sign_jwt(self, issuer, secret, url, signature_fnc, jwt_headers={}):
        alg, fnc = signature_fnc()

        header = {'typ': 'JWT'}
        header.update(jwt_headers)
        header.update({'alg': alg})

        issued = int(time.time())
        expires = issued + 60

        payload = {
            'aud': url,
            'iss': issuer,
            'sub': issuer,
            'jti': str(uuid.uuid4()),
            'iat': issued,
            'nbf': issued,
            'exp': expires,
        }

        segments = [base64.urlsafe_b64encode(json.dumps(header)),
                    base64.urlsafe_b64encode(json.dumps(payload))]

        signature = fnc(secret, b'.'.join(segments))
        segments.append(base64.urlsafe_b64encode(signature))
        return b'.'.join(segments)

    def generate_mozilla_jwt_request(self, issuer, secret, url, method,
                                     data=None, add_headers=[]):
        signed = self.sign_jwt(issuer, secret, url,
                               self.mozilla_jwt_signature_fnc)

        request = urllib2.Request(url, data)
        request.add_header('Authorization', 'JWT ' + signed)
        for header in add_headers:
            request.add_header(*header)
        request.get_method = lambda: method

        return request

    def upload_to_amo(self, filename):
        import urllib3

        upload_url = ('https://addons.mozilla.org/api/v3/addons/{}/'
                      'versions/{}/').format(self.extension_id, self.version)

        with open(filename, 'rb') as file:
            data, content_type = urllib3.filepost.encode_multipart_formdata({
                'upload': (
                    os.path.basename(filename),
                    file.read(),
                    'application/x-xpinstall',
                ),
            })

        request = self.generate_mozilla_jwt_request(
            os.environ['AMO_KEY'],
            os.environ['AMO_SECRET'],
            upload_url,
            'PUT',
            data,
            [('Content-Type', content_type)],
        )

        try:
            urllib2.urlopen(request).close()
        except urllib2.HTTPError as e:
            try:
                logging.error(e.read())
            finally:
                e.close()
            raise

    def download_from_amo(self):
        finished = False
        iss = os.environ['AMO_KEY']
        secret = os.environ['AMO_SECRET']

        url = ('https://addons.mozilla.org/api/v3/addons/{}/'
               'versions/{}/').format(self.extension_id, self.version)

        request = self.generate_mozilla_jwt_request(
            iss, secret, url, 'GET',
        )
        response = json.load(urllib2.urlopen(request))

        filename = '{}-{}.{}'.format(self.basename, self.version,
                                     get_extension(self.platform))
        downloaded = os.path.join(
            self.base_dir,
            filename,
        )

        reviewed = response['passed_review'] and response['reviewed']
        processed = response['processed']
        valid = response['valid']
        if all([reviewed, processed, valid]):
            download_url = response['files'][0]['download_url']
            checksum = response['files'][0]['hash']

            request = self.generate_mozilla_jwt_request(
                iss, secret, download_url, 'GET',
            )
            try:
                response = urllib2.urlopen(request)
            except urllib2.HTTPError as e:
                logging.error(e.read())

            # Verify the extension's integrity
            file_content = response.read()
            sha256 = hashlib.sha256(file_content)
            returned_checksum = '{}:{}'.format(sha256.name, sha256.hexdigest())

            if returned_checksum != checksum:
                logging.error('Checksum could not be verified: {} vs {}'
                              ''.format(checksum, returned_checksum))

            with open(downloaded, 'w') as fp:
                fp.write(file_content)

            finished = True

        elif (not reviewed or not valid) and processed:
            # When the review failed for any reason, we want to know about it
            logging.error(json.dumps(response, indent=4))
            raise RuntimeError('Review did not pass!')

        return finished


def upload_to_stores(base_dir, platform):
    uploader = Uploader(base_dir, platform)
    uploader()


def lint_gitlab_config(base_dir):
    import yaml
    filename = '.gitlab-ci.yml'

    with io.open(os.path.join(base_dir, filename), 'rt') as fp:
        yaml_data = yaml.load(fp.read())

    post_data = {'content': json.dumps(yaml_data)}
    request = urllib2.Request('https://gitlab.com/api/v4/ci/lint/',
                              data=urlencode(post_data))
    print urllib2.urlopen(request).read()
