# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from distutils.errors import DistutilsSetupError
import json


# utilities used from setup.py

def check_relengapi_metadata(dist, attr, value):
    value = value or {}
    if value != json.loads(json.dumps(value)):
        raise DistutilsSetupError('%s must be JSON-able' % (attr,))
    if 'repository_of_record' not in value:
        raise DistutilsSetupError('relengapi must include `repository_of_record`')


def write_relengapi_metadata(cmd, basename, filename):
    value = getattr(cmd.distribution, 'relengapi_metadata', None)
    value = json.dumps(value) if value else ''
    cmd.write_or_delete_file('relengapi_metadata', filename, value)
