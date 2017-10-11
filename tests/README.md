# Buildtools unit tests

## Introduction

Unit tests for buildtools, using the pytest framework.

## Approach

In order to test the buildtools capability of creating WebExtension-packages
for Chrome, Edge and Firefox, an example configuration for each platform is
provided.
Running the tests calls the same API as the cli would, except for releases
(we don't want to trigger our releaseAutomation during tests) - in this case,
a build is manually created and verified)

Each extension is build with different parameters, the resulting package and
it's content is compared against provided expected results:

- Release or build-only, with or without a specific build-number (Edge)
- Release, build-only or developement environment, with or without a specifc
  build-number (Chrome, Firefox), with or without a predefined signing key
  (Chrome)

The expected results for each manifest are provided with the files in
`expecteddata/`.

## Test cases

_(covered platforms are referred to as C=Chrome, E=Edge, F=Firefox)_

- Metadata inheritance (EF)
- correct package filename (CEF)
- Printed warning about non-square icons (CF)
- Presence of javascript unit test files in developement environment (CF) 
- Absence of javascript unit test files in build-only or release (CF)
- Inlcusion of defined contentScripts into the manifest (CF)
- Packaging (and moving) of included icons / scripts / htmls (CEF)
- Presence of files for all configured locales (CEF)
- Correct import of translations with or without placeholders, with or without
  access keys (CEF)
- Translation presence and validity for the Chrome Web Store (C)
- Packaging of modularized script files (CEF)
- Adherence to provided build-number in the manifest (CEF)
- Other content in the manifest (CEF)
- Correct encrypted signature of the package (C)

## Requirements

- [Tox](https://pypi.python.org/pypi/tox) (>= 2.7.0)

_(Tox will take care of installing the other dependencies such as flake8 and
flake8-abp inside a virtualenv.)_

## Usage

To run the tests simply run

```
$ tox
```

in the buildtools' root folder.

## Coverage

Pytest will create a coverage report as output to the terminal, using the
pytest plugin `pytest-cov`.

In order to get an html report you can add `--cov-report=html` to the
pytest-command in tox.ini.

For more information please refer to the
[coverage documentation](https://coverage.readthedocs.io/)
