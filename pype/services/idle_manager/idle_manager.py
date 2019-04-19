import time
from Qt import QtCore, QtGui, QtWidgets
from pype.vendor.pynput import mouse, keyboard
from pypeapp import Logger


class IdleManager(QtCore.QThread):
    """ Measure user's idle time in seconds.
    Idle time resets on keyboard/mouse input.
    Is able to emit signals at specific time idle.
    """
    time_signals = {}
    idle_time = 0
    signal_reset_timer = QtCore.Signal()

    def __init__(self):
        super(IdleManager, self).__init__()
        self.log = Logger().get_logger(self.__class__.__name__)
        self.signal_reset_timer.connect(self._reset_time)
        self._failed = False
        self._is_running = False

    def tray_start(self):
        self.start()

    def add_time_signal(self, emit_time, signal):
        """ If any module want to use IdleManager, need to use add_time_signal
        :param emit_time: time when signal will be emitted
        :type emit_time: int
        :param signal: signal that will be emitted (without objects)
        :type signal: QtCore.Signal
        """
        if emit_time not in self.time_signals:
            self.time_signals[emit_time] = []
        self.time_signals[emit_time].append(signal)

    @property
    def failed(self):
        return self._failed

    @property
    def is_running(self):
        return self._is_running

    def _reset_time(self):
        self.idle_time = 0

    def stop(self):
        self._is_running = False

    def run(self):
        self.log.info('IdleManager has started')
        self._is_running = True
        thread_mouse = MouseThread(self.signal_reset_timer)
        thread_mouse.start()
        thread_keyboard = KeyboardThread(self.signal_reset_timer)
        thread_keyboard.start()
        while self._is_running:
            self.idle_time += 1
            if self.idle_time in self.time_signals:
                for signal in self.time_signals[self.idle_time]:
                    signal.emit()
            time.sleep(1)

        thread_mouse.signal_stop.emit()
        thread_mouse.terminate()
        thread_mouse.wait()
        thread_keyboard.signal_stop.emit()
        thread_keyboard.terminate()
        thread_keyboard.wait()
        self._failed = True
        self._is_running = False
        self.log.info('IdleManager has stopped')


class MouseThread(QtCore.QThread):
    """Listens user's mouse movement
    """
    signal_stop = QtCore.Signal()

    def __init__(self, signal):
        super(MouseThread, self).__init__()
        self.signal_stop.connect(self.stop)
        self.m_listener = None

        self.signal_reset_timer = signal

    def stop(self):
        if self.m_listener is not None:
            self.m_listener.stop()

    def on_move(self, posx, posy):
        self.signal_reset_timer.emit()

    def run(self):
        self.m_listener = mouse.Listener(on_move=self.on_move)
        self.m_listener.start()


class KeyboardThread(QtCore.QThread):
    """Listens user's keyboard input
    """
    signal_stop = QtCore.Signal()

    def __init__(self, signal):
        super(KeyboardThread, self).__init__()
        self.signal_stop.connect(self.stop)
        self.k_listener = None

        self.signal_reset_timer = signal

    def stop(self):
        if self.k_listener is not None:
            self.k_listener.stop()

    def on_press(self, key):
        self.signal_reset_timer.emit()

    def run(self):
        self.k_listener = keyboard.Listener(on_press=self.on_press)
        self.k_listener.start()
