from setuptools import setup
from setuptools import find_packages

# Load the Readme file.
with open(file="README.md", mode="r") as readme_handle:
    long_description = readme_handle.read()

setup(
    name = 'clipstitcher',
    author = 'Libor Kudela',
    author_email = 'libor.kudela1@gmail.com',
    version = '0.2.3',
    description = 'A python package for quick cutting video sequences',
    package_data={'': ['styles.css']},
    include_package_data=True,
    long_description = long_description,
    long_description_content_type = 'text/markdown',
    url='https://github.com/LiborKudela/clipsticher',
    install_requires=[
        'numpy>=1.20.2',
        'opencv-python>=4.6.0.66',
        'requests>=2.28.1',
        'selenium>=4.6.0',
        'tqdm>=4.64.1',
        'python-vlc>=3.0.20123',
        'tqdm>=4.66.1',
        'paramiko>=3.2.0',
        ],
    packages = find_packages(),
    keywords = 'video, editing, sequence, rendering',
    python_requires='>3.8.0',
    classifiers=[
        'Natural Language :: English',
        'Development Status :: 2 - Pre-Alpha',
        'Programming Language :: Python :: 3.8',
        'Operating System :: POSIX :: Linux',
    ]
)
