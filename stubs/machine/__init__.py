def reset():
    """
    Hard reset. The same as performing a power cycle to the board.
    """
    pass


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


class Pin:
    """
    Class for controlling GPIO pins.
    """

    OUT = 0  # Pin mode for output
    IN = 1  # Pin mode for input

    PULL_DOWN = 1
    PULL_UP = 2

    def __init__(self, pin, mode=IN, pull=None):
        """
        Initialize a Pin object.

        :param int pin: Pin number.
        :param int mode: Pin mode (OUT or IN).
        :param int pull: (Optional) Pin pull-up/pull-down behavior (PULL_UP, PULL_DOWN, OPEN_DRAIN).
        """
        pass

    def value(self, val=None):
        """
        Get or set the digital logic level of the pin.

        :param int val: (Optional) Value to set (0 for low, 1 for high).
        :return: Current pin value (0 for low, 1 for high).
        :rtype: int
        """
        pass

    def mode(self, mode):
        """
        Set the pin mode (OUT or IN).

        :param int mode: Pin mode (OUT or IN).
        """
        pass

    def init(self, mode, pull=None):
        """
        Initialize the pin.

        :param int mode: Pin mode (OUT or IN).
        :param int pull: (Optional) Pin pull-up/pull-down behavior (PULL_UP, PULL_DOWN, OPEN_DRAIN).
        """
        pass

    def irq(self, handler, trigger, *args, **kwargs):
        """
        Enable the interrupt for the pin.

        :param callable handler: Interrupt handler function.
        :param int trigger: Trigger condition (Pin.IRQ_RISING, Pin.IRQ_FALLING, or Pin.IRQ_BOTH).
        :param args: Additional arguments for the interrupt handler.
        :param kwargs: Additional keyword arguments for the interrupt handler.
        """
        pass

    def value_and_irq(self, val=None, handler=None, trigger=None, *args, **kwargs):
        """
        Get or set the digital logic level of the pin, and optionally enable the interrupt.

        :param int val: (Optional) Value to set (0 for low, 1 for high).
        :param callable handler: (Optional) Interrupt handler function.
        :param int trigger: (Optional) Trigger condition (Pin.IRQ_RISING, Pin.IRQ_FALLING, or Pin.IRQ_BOTH).
        :param args: Additional arguments for the interrupt handler.
        :param kwargs: Additional keyword arguments for the interrupt handler.
        :return: Current pin value (0 for low, 1 for high).
        :rtype: int
        """
        pass

    def pull(self, pull):
        """
        Set the pin pull-up/pull-down behavior.

        :param int pull: Pull behavior (PULL_UP, PULL_DOWN, OPEN_DRAIN).
        """
        pass

    def __call__(self, val=None):
        """
        Get or set the digital logic level of the pin.

        :param int val: (Optional) Value to set (0 for low, 1 for high).
        :return: Current pin value (0 for low, 1 for high).
        :rtype: int
        """
        pass

    def on(self):
        """
        Set the pin to high (1).
        """
        pass

    def off(self):
        """
        Set the pin to low (0).
        """
        pass

    def toggle(self):
        """
        Toggle the pin value.
        """
        pass

    def irqtrigger(self, trigger):
        """
        Set the trigger condition for the interrupt.

        :param int trigger: Trigger condition (Pin.IRQ_RISING, Pin.IRQ_FALLING, or Pin.IRQ_BOTH).
        """
        pass

    IRQ_RISING = 1  # Trigger on rising edge
    IRQ_FALLING = 2  # Trigger on falling edge
    IRQ_BOTH = 3  # Trigger on both rising and falling edges


class Timer:
    """
    Class for creating and controlling timers.
    """
    PERIODIC = 0
    ONE_SHOT = 1

    def __init__(self, id: int):
        """
        Construct a Timer object.

        :param int id: Timer ID (0, 1, 2, etc.).
        """
        pass

    def init(self, mode=0, callback=None, period=0, freq=0):
        """
        Initialize the timer.

        :param int mode: (Optional) Timer mode (0 for period, 1 for one-shot).
        :param callable callback: (Optional) Callback function to be executed on timer overflow.
        :param int period: (Optional) Timer period in milliseconds.
        :param int freq: (Optional) Timer frequency in Hz.
        """
        pass

    def deinit(self):
        """
        Deinitialize the timer, releasing any resources associated with it.
        """
        pass

    def value(self):
        """
        Get the current value of the timer.

        :return: Current timer value.
        :rtype: int
        """
        pass

    def start(self, us=-1):
        """
        Start the timer.

        :param int us: (Optional) Time delay in microseconds before starting the timer.
        """
        pass

    def stop(self):
        """
        Stop the timer.
        """
        pass

    def callback(self, callback=None):
        """
        Get or set the callback function.

        :param callable callback: (Optional) Callback function to be executed on timer overflow.
        :return: Current callback function.
        :rtype: callable
        """
        pass


class PWM:
    """
    Class for controlling PWM (Pulse Width Modulation) outputs.
    """

    def __init__(self, pin, freq=1000, duty=512):
        """
        Initialize a PWM object.

        :param machine.Pin pin: Pin object to which PWM is assigned.
        :param int freq: (Optional) Frequency of the PWM signal in Hz (default is 1000).
        :param int duty: (Optional) Initial duty cycle (default is 512).
        """
        pass

    def init(self, freq=1000, duty=512):
        """
        Initialize the PWM.

        :param int freq: (Optional) Frequency of the PWM signal in Hz (default is 1000).
        :param int duty: (Optional) Initial duty cycle (default is 512).
        """
        pass

    def deinit(self):
        """
        Deinitialize the PWM, releasing any resources associated with it.
        """
        pass

    def freq(self, freq=None):
        """
        Get or set the frequency of the PWM signal.

        :param int freq: (Optional) Frequency in Hz.
        :return: Current frequency.
        :rtype: int
        """
        pass

    def duty(self, duty=None):
        """
        Get or set the duty cycle of the PWM signal.

        :param int duty: (Optional) Duty cycle (0 to 1023).
        :return: Current duty cycle.
        :rtype: int
        """
        pass


class TouchPad:
    """
    Class for controlling capacitive touch sensor inputs.
    """

    def __init__(self, pin):
        """
        Initialize a TouchPad object.

        :param machine.Pin pin: Pin object to which the touch sensor is connected.
        """
        pass

    def read(self):
        """
        Read the current value of the touch sensor.

        :return: Current touch sensor value.
        :rtype: int
        """
        pass

    def config(self, value):
        """
        Set the threshold value of the touch sensor.

        :param int value: Threshold value.
        """
        pass


class SPI:
    """
    Class for controlling SPI (Serial Peripheral Interface) communication.
    """

    def __init__(self, id, baudrate=1000000, polarity=0, phase=0, bits=8, firstbit=0, sck=None, mosi=None, miso=None):
        """
        Initialize an SPI object.

        :param int id: SPI ID (0 or 1).
        :param int baudrate: (Optional) Baud rate in Hz (default is 1000000).
        :param int polarity: (Optional) Clock polarity (0 or 1, default is 0).
        :param int phase: (Optional) Clock phase (0 or 1, default is 0).
        :param int bits: (Optional) Number of bits per transfer (default is 8).
        :param int firstbit: (Optional) First bit to send (0 or 1, default is 0).
        :param machine.Pin sck: (Optional) Pin object for the clock signal.
        :param machine.Pin mosi: (Optional) Pin object for the MOSI signal.
        :param machine.Pin miso: (Optional) Pin object for the MISO signal.
        """
        pass

    def init(self, baudrate=1000000, polarity=0, phase=0, bits=8, firstbit=0, sck=None, mosi=None, miso=None):
        """
        Reinitialize the SPI object.

        :param int baudrate: (Optional) Baud rate in Hz (default is 1000000).
        :param int polarity: (Optional) Clock polarity (0 or 1, default is 0).
        :param int phase: (Optional) Clock phase (0 or 1, default is 0).
        :param int bits: (Optional) Number of bits per transfer (default is 8).
        :param int firstbit: (Optional) First bit to send (0 or 1, default is 0).
        :param machine.Pin sck: (Optional) Pin object for the clock signal.
        :param machine.Pin mosi: (Optional) Pin object for the MOSI signal.
        :param machine.Pin miso: (Optional) Pin object for the MISO signal.
        """
        pass

    def write(self, data):
        """
        Write data to the SPI interface.

        :param data: Data to write.
        """
        pass

    def read(self, nbytes):
        """
        Read data from the SPI interface.

        :param nbytes: Number of bytes to read.
        """
        pass

    def deinit(self):
        """
        Deinitialize the SPI object.
        """
        pass


class I2C:
    def __init__(self, bus, scl=None, sda=None, freq=400000):
        pass

    def scan(self):
        pass

    def readfrom(self, addr, nbytes):
        pass

    def readfrom_into(self, addr, buf):
        pass

    def writeto(self, addr, buf):
        pass

    def readfrom_mem(self, addr, memaddr, nbytes):
        pass

    def readfrom_mem_into(self, addr, memaddr, buf):
        pass

    def writeto_mem(self, addr, memaddr, buf):
        pass
