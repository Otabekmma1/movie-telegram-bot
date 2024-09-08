from setuptools import setup, find_packages


setup(
    name='moviebot',
    version='0.1',
    packages=find_packages(),
    install_requires=[
        'aiogram==3.12.0',
        'aiosqlite',
        # Add other dependencies here
    ],
    entry_points={
        'console_scripts': [
            'start-bot=bot.main:main',
        ],
    },
    python_requires='>=3.7',
)
