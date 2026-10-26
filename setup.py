#!/usr/bin/env python3
from setuptools import setup, find_packages

setup(
    name="emoji-pop",
    version="1.0.0",
    description="A Lightweight, Windows-Style Emoji Picker for Pop!_OS and COSMIC",
    author="Pop!_OS Engineering Team",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "emoji_pop": ["assets/*"],
    },
    entry_points={
        "console_scripts": [
            "emoji-pop=emoji_pop.app:main",
        ],
    },
    install_requires=[
        "PyGObject>=3.42.0",
    ],
    python_requires=">=3.10",
)
