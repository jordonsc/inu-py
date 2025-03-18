#!/usr/bin/env python3

from boto3 import Session
from botocore.exceptions import BotoCoreError, ClientError
from contextlib import closing
import os
import subprocess
import hashlib


class Tts:
    def __init__(self, voice="Emma", engine="neural", output_format="mp3"):
        self.voice = voice
        self.engine = engine
        self.output_format = output_format
        self.tts_cache = os.path.join(os.path.expanduser("~"), ".inu", "tts-cache")
        self.playing = False

        # Create a client using the credentials and region defined in the [renogy] section of the AWS credentials
        # file (~/.aws/credentials)
        self.session = Session(profile_name="inu")
        self.polly = self.session.client("polly")

    async def play(self, msg, wait=True, no_cache=False):
        if self.voice is None or self.engine is None:
            return

        self.playing = True
        msg_hash = self.get_msg_hash(msg)
        if no_cache or not self.has_cache(msg_hash):
            await self.synthesise(msg)

        await self.play_from_cache(msg_hash, wait=wait)

    def get_msg_hash(self, msg):
        key = self.voice + "|" + self.engine + "|" + msg
        return hashlib.md5(key.encode('utf-8')).hexdigest()

    def has_cache(self, msg_hash):
        return os.path.isfile(os.path.join(self.tts_cache, msg_hash + "." + self.output_format))

    async def synthesise(self, msg):
        try:
            response = self.polly.synthesize_speech(Text=msg, OutputFormat=self.output_format, VoiceId=self.voice,
                                                    Engine=self.engine)
        except (BotoCoreError, ClientError) as e:
            raise Exception("Boto client error: " + str(e))

        # Access the audio stream from the response
        if "AudioStream" in response:
            # Check/create the audio cache file
            if not os.path.exists(self.tts_cache):
                os.makedirs(self.tts_cache)

            # Note: Closing the stream is important because the service throttles on the  number of parallel
            # connections. Here we are using contextlib.closing to ensure the close method of the stream object will be
            # called automatically at the end of the with statement's scope.
            with closing(response["AudioStream"]) as stream:
                output = os.path.join(self.tts_cache, self.get_msg_hash(msg) + "." + self.output_format)

                try:
                    # Open a file for writing the output as a binary stream
                    with open(output, "wb") as file:
                        file.write(stream.read())
                except IOError:
                    raise Exception("IO Error")

        else:
            raise Exception("Audio stream not in response!")

    async def play_from_cache(self, msg_hash, wait=False):
        self.playing = True
        cmd = ["mpg123", os.path.join(self.tts_cache, msg_hash + "." + self.output_format)]
        if wait:
            subprocess.run(cmd, capture_output=True)
        else:
            subprocess.Popen(cmd, shell=False, stdin=None, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             close_fds=True)
        self.playing = False

    async def play_from_file(self, fn, wait=True):
        self.playing = True
        cmd = ["mpg123", fn]
        if wait:
            subprocess.run(cmd, capture_output=True)
        else:
            subprocess.Popen(cmd, shell=False, stdin=None, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             close_fds=True)
        self.playing = False

