from setuptools import setup

setup(
    name='micro_nats',
    version="1.0.2",
    description='A MicroPython NATS client',
    url='https://github.com/jordonsc/inu-py',
    author='Jordon Scott',
    author_email='jordonsc@gmail.com',
    license='MIT',
    packages=[
        'micro_nats',
        'micro_nats.io',
        'micro_nats.jetstream',
        'micro_nats.jetstream.io', 'micro_nats.jetstream.io.manager',
        'micro_nats.jetstream.protocol',
        'micro_nats.protocol', 'micro_nats.protocol.cmd',
        'micro_nats.util'
    ],
    install_requires=[],
    classifiers=[],
)
