Starting a New RelengAPI Project
================================

Releng Best Practices call for many well-delineated projects, so begin by creating a new repository for your project.

setup.py
--------

Add a ``setup.py`` containing the following, updated to suit your project:

.. code-block:: none

    # This Source Code Form is subject to the terms of the Mozilla Public
    # License, v. 2.0. If a copy of the MPL was not distributed with this
    # file, You can obtain one at http://mozilla.org/MPL/2.0/.

    from setuptools import setup, find_packages

    data_patterns = [
        'templates/**.html',
        'static/**.jpg',
        'static/**.css',
        'static/**.js',
        'static/**.txt',
    ]

    setup(
        name='relengapi-example',
        version='0.1',
        description='RelengAPI Example Project',
        author='You R. Name',
        author_email='you@mozilla.com',
        url='https://relengapi-example.readthedocs.org/en/latest/',
        relengapi_metadata={
            'repository_of_record': 'https://github.com/you/relengapi-example',
        },
        setup_requires=[
            'relengapi',
        ]
        install_requires=[
            "Flask",
            "relengapi",
        ],
        extras_require = {
            'test': [
                'nose',
                'mock',
                'pep8',
                'pylint<1.2',
            ]
        },
        packages=find_packages(),
        include_package_data=True,
        zip_safe=False,
        namespace_packages=['relengapi', 'relengapi.blueprints'],
        package_data={  # NOTE: these files must *also* be specified in MANIFEST.in
            'relengapi.blueprints.example': data_patterns,
        },
        entry_points={
            "relengapi_blueprints": [
                'example = relengapi.blueprints.example:bp',
            ],
        },
        license='MPL2',
    )

Breaking that down a bit:

 * Name the package with a ``relengapi-`` prefix, so it's easy to find alphabetically.
 * Specify at least a ``repository_of_record`` in the ``relengapi_metadata``.
   This will help users to find the code behind the functionality on the site.
 * The ``setup_requires`` section is required to handle the ``relengapi_metadata`` option.
 * The ``install_requires`` section should include relengapi and Flask, as well as any additional requirements for your project.
 * The ``extras_require.test`` list describes packages required to run the tests.
 * The ``namespace_packages`` line allows multiple packages to share the same Python path::

    namespace_packages=['relengapi', 'relengapi.blueprints'],

 * The ``entry_points.relengapi_blueprints`` list enumerates the blueprints your project adds to the relengapi.
   Most projects will add only one blueprint, but multiple blueprints are possible.

Boilerplate
-----------

Now, create the directory structure:

.. code-block:: none

    relengapi/__init__.py
    relengapi/blueprints/__init__.py
    relengapi/blueprints/example/__init__.py

The first two of the ``__init__.py`` files must have *only* the following contents::

    __import__('pkg_resources').declare_namespace(__name__)

You are also free to add a README, license file, and so on.

In ``relengapi/blueprints/example/__init__.py``, create your Blueprint::

    from flask import Blueprint, jsonify
    bp = Blueprint('example', __name__)
    @bp.route('/some/path')
    def root():
        return "HELLO"

Note that the variable named ``bp`` is important here, as it is referred to from ``entry_points.relengapi_blueprints`` in ``setup.py``.

Build your blueprint following the Flask documentation.
The blueprint is registered with its name as the URL prefix, so the ``root`` function in this example would be available at ``/example/some/path``.
