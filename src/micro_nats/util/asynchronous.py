import asyncio


class Future:
    """
    Lightweight future implementation, designed to mimic the asyncio.Future implementation for MicroPython.

    Not thread safe.
    """

    # Needs to be a smidge above zero to prevent CPU hammering; the closer to zero, the more idle CPU used.
    SLEEP_TIME = 0.001

    def __init__(self):
        self.state = None
        self.result = None

    def set_result(self, result):
        self.state = True
        self.result = result

    async def cb(self, result):
        self.set_result(result)

    def cancel(self):
        self.state = False
        self.result = None

    def cancelled(self):
        return self.state is False

    def done(self):
        return self.state is True

    async def wait_for_result(self):
        while self.state is None:
            await asyncio.sleep(self.SLEEP_TIME)

        if self.state is True:
            return self.result
        else:
            raise asyncio.CancelledError()

    def __await__(self):
        return self.wait_for_result().__await__()

    def send(self, *args, **kwargs):
        pass


class TaskPool:
    """
    Add a awaitable function to the running loop, without waiting for it to complete.
    """
    pool_size: int = 0

    def __init__(self):
        self.tasks = set()

    def __repr__(self):
        return f"<taskpool local_size={self.local_pool_size()} total_size={TaskPool.total_pool_size()}>"

    def local_pool_size(self):
        return len(self.tasks)

    @staticmethod
    def total_pool_size():
        return TaskPool.pool_size

    def run(self, coro):
        """
        Runs a task in the background, safeguarding it from potential GC destruction.
        """
        def on_done(t):
            self.tasks.remove(t)
            TaskPool.pool_size -= 1

        task = asyncio.create_task(coro)

        # In CPython, you need to store a reference of the task to prevent the GC destroying it. However this isn't
        # an issue in MP, which puts the task on the task queue and you can fire & forget.
        if hasattr(task, "add_done_callback"):
            self.tasks.add(task)
            TaskPool.pool_size += 1
            task.add_done_callback(on_done)
