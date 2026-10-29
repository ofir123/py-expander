from setuptools import setup, find_packages


setup(
    name='pyexpander',
    version='0.1dev',
    packages=find_packages(),
    long_description=open('README.md').read(),
    python_requires='>=3.10',
    install_requires=['logbook', 'guessit', 'subliminal>=2.8,<3', 'babelfish', 'showsformatter',
                      'platformdirs>=3', 'dogpile.cache>=1.0'],
    entry_points={
      'console_scripts': [
          'pyexpand = pyexpander:main',
      ]
    }
)
