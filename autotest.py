# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import io
import os
import json
import subprocess

import logging


class TestCollection(object):
    def __init__(self, base_dir):
        self._base_dir = base_dir
        self._test_definitions = []

        logging.basicConfig(format='%(levelname)s: %(message)s',
                            level=logging.INFO)

    def collect_tests(self):
        for base, folders, files in os.walk(self._base_dir):
            file_path = os.path.join(self._base_dir, base, 'tests.json')
            if os.path.isfile(file_path):
                with io.open(file_path, encoding='utf-8') as fp:
                    self._test_definitions.append((
                        os.path.join(self._base_dir, base),
                        json.load(fp),
                    ))

    def run_all_tests(self):
        for cwd, definition in self._test_definitions:
            for test in definition:
                logging.info('Running "{}"'.format(test['name']))
                subprocess.check_call(test['cmd'].split(), cwd=cwd)

    def run(self):
        self.collect_tests()
        self.run_all_tests()
