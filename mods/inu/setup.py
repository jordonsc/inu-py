from setuptools import setup

setup(
    name='inu_net',
    version="1.43.1",
    description='The Inu IoT framework',
    url='https://github.com/jordonsc/inu-py',
    author='Jordon Scott',
    author_email='jordonsc@gmail.com',
    license='MIT',
    packages=[
        'inu_net',
        'inu_net.hardware', 'inu_net.hardware.light', 'inu_net.hardware.robotics', 'inu_net.hardware.robotics.control',
        'inu_net.lib',
        'inu_net.schema', 'inu_net.schema.settings',
        'inu_net.updater',
        'inu_net.util',
    ],
    install_requires=['micro_nats'],
    classifiers=[],
)
