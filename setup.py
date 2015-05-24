from setuptools import setup, find_packages
setup(
    name = 'passh',
    version = '1.0.1',
    packages = find_packages(),
    entry_points = {
        'console_scripts': [
            'passh=passh:main',
        ],
    },
)
