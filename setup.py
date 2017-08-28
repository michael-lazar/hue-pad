import setuptools

setuptools.setup(
    name='hue_pad',
    version='0.1.0',
    description='Control lighting effects with a MIDI Pad Controller',
    url='https://github.com/michael-lazar/hue-pad',
    author='Michael Lazar',
    author_email='lazar.michael22@gmail.com',
    license='MIT',
    py_modules=['hue_pad'],
    install_requires=['pygame', 'phue', 'click'],
    entry_points={'console_scripts': ['hue-pad=hue_pad:main']}
)
