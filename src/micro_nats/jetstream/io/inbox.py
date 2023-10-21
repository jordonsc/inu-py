import base64
import logging
import os

from ... import error
from ...client import Client as NatsClient


class InboxManager:
    """
    Manages a list of subscriptions and their respective tokens, designed for use as reply-to subjects for the
    Jetstream protocol.
    """

    # Number of bytes to use for pre-encoded identity
    ID_SIZE = 12

    def __init__(self, nats_client: NatsClient, max_stowed: int = 5):
        self.active_boxes = []
        self.stowed_boxes = []
        self.client = nats_client
        self.logger = logging.getLogger('mnats.js.inbox')

        # For mapping SID -> inbox token (subject)
        self.token_map = {}

        # Max buffer of unused, but still subscribed, inboxes
        self.max_stowed = max_stowed

        # Prefix we use for inbox subjects
        self.prefix = "_INBOX.MN."

    def __repr__(self):
        return f"<inbox active={str(len(self.active_boxes))} stowed={str(len(self.stowed_boxes))}>"

    def num_active_boxes(self) -> int:
        return len(self.active_boxes)

    def num_stowed_boxes(self) -> int:
        return len(self.stowed_boxes)

    async def flush(self):
        """
        Clears the inbox and kills all consumers.
        """
        for box in self.stowed_boxes:
            await self._destroy_inbox(box)

        for box in self.active_boxes:
            await self._destroy_inbox(box)

    async def get_inbox(self, callback: callable, force_new: bool = False) -> str:
        """
        Returns an inbox, a stowed inbox if one exists, else it will generate a new one and return.
        """
        if not force_new and self.num_stowed_boxes():
            inbox = self.stowed_boxes.pop()
            self.active_boxes.append(inbox)
            self.client.manager.bind_callback(self.token_map[inbox], callback)
            return inbox
        else:
            inbox = await self._create_inbox(callback)
            self.active_boxes.append(inbox)
            return inbox

    async def free_inbox(self, inbox: str, destroy: bool = False):
        """
        Frees an inbox, removing the callback binding and saving it for later use.

        If we already have the maximum number of stowed inboxes, this inbox will be destroyed instead.

        IMPORTANT: if there is any chance additional messages may be sent to this inbox, set `destroy=True` to ensure
        that it is not reused.
        """
        if inbox not in self.active_boxes:
            raise error.NotFoundError(f"Inbox '{inbox}' not in active boxes")

        if destroy or self.num_stowed_boxes() >= self.max_stowed:
            # We have enough stowed inboxes, so destroy the inbox (unsubscribe and delete token) instead -
            await self._destroy_inbox(inbox)
            return

        # Move to stowed
        self.active_boxes.remove(inbox)
        self.stowed_boxes.append(inbox)

        if inbox not in self.token_map:
            # this is a flow control issue - shouldn't happen unless someone is messing with private variables
            self.logger.error(f"ERROR: Inbox '{inbox}' not found in token map when attempting to free")
            return

        try:
            # Remove the callback from the client manager. This will make the manager ignore messages that come in on
            # this subject until the inbox is rebound.
            self.client.manager.unbind_callback(self.token_map[inbox])
        except error.NotFoundError:
            pass

    async def _create_inbox(self, callback: callable) -> str:
        """
        Generates a new inbox token and subscribes to it.

        If you want an inbox, do not call this directly. Instead call `get_inbox()` which may return a stowed inbox
        instead.
        """
        if not self.client.is_connected():
            raise error.NoConnectionError()

        inbox = self._generate_token()
        sid = await self.client.subscribe(inbox, callback)
        self.token_map[inbox] = sid

        return inbox

    async def _destroy_inbox(self, inbox: str):
        """
        Unsubscribes to the inbox and destroys the token reference.
        """
        if inbox in self.active_boxes:
            self.active_boxes.remove(inbox)

        if inbox in self.stowed_boxes:
            self.stowed_boxes.remove(inbox)

        await self.client.unsubscribe(inbox)

        if inbox in self.token_map:
            del self.token_map[inbox]
        else:
            self.logger.error(f"ERROR: Inbox '{inbox}' not found in token map when attempting to destroy")

    def _generate_token(self) -> str:
        """
        Create a new, unique, inbox subject.
        """
        while True:
            # mPy doesn't support string.translate(), so we need to manually replace alt-chars
            ident = base64.b64encode(os.urandom(self.ID_SIZE)).replace(b'=', b'').replace(b'+', b'A') \
                .replace(b'/', b'Z').decode()
            inbox = f"{self.prefix}{ident}"
            if inbox not in self.active_boxes and inbox not in self.stowed_boxes:
                break

        return inbox
