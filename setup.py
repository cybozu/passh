from setuptools import setup, find_packages
setup(
    name = 'passh',
    version = '1.0.2',
    packages = find_packages(),
    entry_points = {
        'console_scripts': [
            'passh=passh:main',
        ],
    },

    # https://docs.python.org/3.4/distutils/setupscript.html#meta-data
    author = 'Yamamoto, Hirotaka',
    author_email = 'ymmt2005@gmail.com',
    maintainer = 'Yamamoto, Hirotaka',
    maintainer_email = 'ymmt2005@gmail.com',
    url = 'https://github.com/cybozu/passh',
    description = 'Python3 asyncio library to run SSH in parallel',
    long_description = '''passh (Parallel Asynchronous SSH) is a Python3 library to run SSH processes in parallel.

As passh depends on `asyncio <https://docs.python.org/3/library/asyncio.html>`_,  Python 3.4 or newer is required.

Features:

* ``PAssh`` class to run SSH in parallel.
  
  * SSH outputs are forwarded to local stdout/stderr.
  * Every line is to be prefixed by the remote hostname.
  * Instead of forwarding, SSH outputs can be collected in memory for later use.

* Non-asyncio apps can use passh as well as asyncio apps.
* A file can be given as inputs for all SSH processes.
* Limit on the number of simultaneous SSH processes.
* Built-in command-line interface.
''',
    license = 'MIT',
    keywords = 'asyncio ssh',
    classifiers = [
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: Software Development :: Libraries',
        'Topic :: System :: Networking',
    ],
)
