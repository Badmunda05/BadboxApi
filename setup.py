from os import path
from setuptools import setup, find_packages

this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='badbox',
    version='1.0.0',
    author='BadMunda',
    author_email='',
    description='Self-hosted file hosting — upload files, get direct URLs.',
    license='MIT',
    classifiers=[
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Topic :: Internet',
        'Topic :: Communications',
        'Topic :: Communications :: Chat',
        'Topic :: Software Development :: Libraries',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    keywords='telegram file hosting upload cdn self-hosted',
    url='https://github.com/BadMunda/badbox',
    packages=find_packages(),
    install_requires=['requests>=2.28.0'],
    long_description=long_description,
    long_description_content_type='text/markdown',
    python_requires='>=3.8',
)
