class UART:
    def __init__(self, uart_id, baudrate=9600, bits=8, parity=None, stop=1, tx=None, rx=None, timeout=0,
                 timeout_char=1):
        """
        Initialize a UART object.

        Args:
            uart_id (int): ID of the UART interface to use (0 or 1).
            baudrate (int, optional): Baud rate. Default is 9600.
            bits (int, optional): Number of data bits. Default is 8.
            parity (str, optional): Parity mode ('N', 'E', or 'O'). Default is None.
            stop (int, optional): Number of stop bits. Default is 1.
            tx (int, optional): Pin for transmission (TX). Default is None.
            rx (int, optional): Pin for reception (RX). Default is None.
            timeout (int, optional): Read timeout in milliseconds. Default is 0 (no timeout).
            timeout_char (int, optional): Timeout between characters in milliseconds. Default is 1.
        """
        pass

    def init(self, baudrate=9600, bits=8, parity=None, stop=1, tx=None, rx=None, timeout=0, timeout_char=1):
        """
        Reinitialize the UART object.

        Args:
            baudrate (int, optional): Baud rate. Default is 9600.
            bits (int, optional): Number of data bits. Default is 8.
            parity (str, optional): Parity mode ('N', 'E', or 'O'). Default is None.
            stop (int, optional): Number of stop bits. Default is 1.
            tx (int, optional): Pin for transmission (TX). Default is None.
            rx (int, optional): Pin for reception (RX). Default is None.
            timeout (int, optional): Read timeout in milliseconds. Default is 0 (no timeout).
            timeout_char (int, optional): Timeout between characters in milliseconds. Default is 1.
        """
        pass

    def deinit(self):
        """
        Deinitialize the UART object.
        """
        pass

    def any(self):
        """
        Check if there is any data available to read.

        Returns:
            bool: True if there is data available, False otherwise.
        """
        pass

    def read(self, size=-1):
        """
        Read up to 'size' bytes from the UART.

        Args:
            size (int, optional): Maximum number of bytes to read. Default is -1 (read as much as possible).

        Returns:
            bytes: Data read from the UART.
        """
        pass

    def readinto(self, buf, size=-1):
        """
        Read up to 'size' bytes from the UART into the buffer 'buf'.

        Args:
            buf (bytearray): Buffer to read data into.
            size (int, optional): Maximum number of bytes to read. Default is -1 (read as much as possible).

        Returns:
            int: Number of bytes read.
        """
        pass

    def write(self, data):
        """
        Write data to the UART.

        Args:
            data (bytes): Data to be written.
        """
        pass

    def readline(self):
        """
        Read a line (terminated by '\n') from the UART.

        Returns:
            bytes: Data read from the UART.
        """
        pass

    def irq(self, trigger, handler=None, wake=None):
        """
        Enable or disable interrupts for the UART.

        Args:
            trigger (int): Combination of UART.IRQ_* constants.
            handler (function, optional): Function to be called when the interrupt triggers. Default is None.
            wake (int, optional): Sleep mode to wake up from. Default is None.
        """
        pass

    def ioctl(self, cmd, arg):
        """
        Control various aspects of the UART.

        Args:
            cmd (int): Control command.
            arg (int): Argument associated with the command.

        Returns:
            int: Result of the control command.
        """
        pass

    def sendbreak(self):
        """
        Send a break condition on the UART.
        """
        pass

    def __enter__(self):
        """
        Enter a context managed block.
        """
        pass

    def __exit__(self, exc_type, exc_value, exc_tb):
        """
        Exit a context managed block.
        """
        pass
