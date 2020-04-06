#!/usr/bin/env python
# encoding=utf-8
import os
from setuptools import setup

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.md')).read()

setup(name='rtbot',
      version='0.1.0',  # Use bumpversio to update
      long_description=README,
      classifiers=[
          'Programming Language :: Python',
          'Programming Language :: Python :: 3.5',
          'Programming Language :: Python :: 3.6',
          'Programming Language :: Python :: 3.7',
      ],
      author='Dan Michael O. Heggø',
      author_email='d.m.heggo@ub.uio.no',
      url='https://github.com/scriptotek/rtbot',
      license='MIT',
      install_requires=['python-dotenv',
                        'rt',
                        'requests',
                        'pyyaml',
                        'backoff',
                        'pydash'],
      entry_points={'console_scripts': ['rtbot=rtbot.bot:main']},
      packages=['rtbot']
      )
