TreeStatus
==========

Treestatus uses the `relengapi` database.

The `/trees/<tree>` endpoing gets hit quite frequently, and can optionally cache its values in memcached.
To enable this, set configuration value `TREESTATUS_CACHE` to a list of memcache servers::

    TREESTATUS_CACHE = [
        'memcache1.example.com:11211',
        'memcache2.example.com:11211',
    ]
