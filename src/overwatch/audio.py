#!/usr/bin/env python3

from boto3 import Session
from botocore.exceptions import BotoCoreError, ClientError
from contextlib import closing
import os
import subprocess
import hashlib


class AudioController:
    def __init__(self, voice="Emma", engine="neural", output_format="mp3"):
        self.voice = voice
        self.engine = engine
        self.output_format = output_format
        self.tts_cache = os.path.join(os.path.expanduser("~"), ".inu", "tts-cache")

        self.queue = []
        self.process = None

        # Create a client using the credentials and region defined in the [renogy] section of the AWS credentials
        # file (~/.aws/credentials)
        self.session = Session(profile_name="inu")
        self.polly = self.session.client("polly")

    async def process_queue(self):
        """
        Process the audio queue. 

        This function will check if the audio controller is currently playing audio, and if not, will attempt to play
        the next item in the queue.
        """
        # Check if the process is still running, if it is not, mark it as None
        if self.process is not None:
            if self.process.poll() is None:
                # Still playing
                return
            else:
                # Process has exited
                self.process = None

        # If there is no further work to do, we can exit now
        if len(self.queue) == 0:
            return

        # Pull the next item and play it
        fn = self.queue.pop(0)
        self.process = subprocess.Popen(["mpg123", fn], shell=False, stdin=None, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)

    def is_playing(self):
        """
        Check if the audio controller is currently playing audio.
        """
        return self.process is not None and self.process.poll() is None

    def has_content(self):
        """
        Check if the audio controller has any content in the queue, or is currently playing audio.
        """
        return len(self.queue) > 0 or self.is_playing()

    async def enqueue_tts(self, msg, no_cache=False):
        """
        Enqueue a message for text-to-speech synthesis.
        """
        if self.voice is None or self.engine is None:
            return

        msg_hash = self.get_msg_hash(msg)
        
        if no_cache or not self.has_cache(msg_hash):
            await self.synthesise(msg)

        await self.enqueue_from_cache(msg_hash)

    def get_msg_hash(self, msg):
        key = self.voice + "|" + self.engine + "|" + msg
        return hashlib.md5(key.encode('utf-8')).hexdigest()

    def has_cache(self, msg_hash):
        return os.path.isfile(os.path.join(self.tts_cache, msg_hash + "." + self.output_format))

    async def synthesise(self, msg):
        """
        Synthesise a message using Polly and save the audio stream to a file.
        """
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

    async def enqueue_from_cache(self, msg_hash):
        """
        Enqueue a message from a cached message created by the synthesise function.
        """
        self.queue.append(os.path.join(self.tts_cache, msg_hash + "." + self.output_format))

    async def enqueue_from_file(self, fn):
        """
        Enqueue a message from a supported audio file format.
        """
        self.queue.append(fn)

