from setuptools import setup

setup(
    name='pixpy',
    url='https://github.com/willmorrison1/pixpy',
    author='Will Morrison',
    author_email='willmorrison661@gmail.com',
    packages=[
        'pixpy',
    ],
    install_requires=[
        'numpy',
        'pandas',
        'xarray',
        'netCDF4',
        'gpiozero',
        'h5py',
    ],
    version='0.21',
    entry_points={
        'console_scripts': [
            'pixpy_app=pixpy.app:app',
        ]
    },
    license='MIT',
    description='todo The description text',
    long_description='todo The long description text'
)
