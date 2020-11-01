from setuptools import setup
import sys

if sys.version_info < (3, 6):
    print("Python 3.6 or higher is required")
    sys.exit(1)

setup(name='odea',
      version='1.0',
      description='Ethnographic archives toolkit',
      url='http://mcdrc.org/odea',
      author='Eric Thrift',
      author_email='e.thrift@uwinnipeg.ca',
      license='GPL',
      # packages=['odea'],
      platforms=['POSIX'],
      entry_points={
        'console_scripts': [
            'odea = cli:main'
        ],
        },
      install_requires=[
          'jsons',
          'dataclasses',
          'wsl-path-converter',
          'importlib_resources',
          'json2html',
          'preview-generator',
          'docutils',
          'pathlib',
          'pillow',
          'bs4',
          'sphinx-argparse',
          'soundfile',
          'moviepy',
          'python-slugify'
      ],
      package_data={
          'odea': ['static/*', 'test/*'],
    },
      zip_safe=False)
