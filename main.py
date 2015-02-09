#-------------------------------------------------------------------------------
# Name:        6.115-IDE
# Purpose:     IDE for development of the R-31JP system used in MITs course 6.115
#
# Author:      Efraim Helman
#
# Created:     02/11/2015
# Copyright:   (c) EH 2015
# License:     MIT License
#-------------------------------------------------------------------------------

# first install anaconda, and then run from the terminal $ conda install pyserial

# help: auto cleans, aligns comments!
# code explorer, appendix explorer, but keep simple!

import os
import os.path
import re
import sys
import serial
import shutil
import subprocess
import tempfile
import threading
import time
from PyQt4.QtCore import *
from PyQt4.QtGui import *


class MainWindow(QMainWindow):

    # fixme: syntax highlighting
    # fixme: autocomplete
    # fixme: link error lines to line in asm window
    # red highlight those lines automaticly, don't just report?
    # fixme: separate console from terminal?

    def __init__(self, parent=None):
        super().__init__(parent)

        # widgets
        self.terminal_widget = TerminalWidget(self, self)
        self.code_widget = CodeWidget(self, self)

        # layout
        splitter = QSplitter(self)
        splitter.addWidget(self.terminal_widget)
        splitter.addWidget(self.code_widget)
        self.setCentralWidget(splitter)

        # toolbar
        self.main_toolbar = MainToolbar(self, self)
        self.addToolBar(Qt.TopToolBarArea, self.main_toolbar)

    def closeEvent(self, event):
        self.code_widget.closeEvent(event)
        self.terminal_widget.closeEvent(event)


class MainToolbar(QToolBar):
    def __init__(self, root, parent=None):
        super().__init__('Main Toolbar', parent)
        self.root = root

        self._add_button('Assemble', 'assemble.png', self.root.code_widget.assemble)
        self._add_button('Send', 'refresh.png', self.root.code_widget.send)

    def _add_button(self, tooltip, icon, action):
        button = QToolButton(self)
        button.setToolTip(tooltip)
        button.setIcon(QIcon('resources/images/%s' % icon))
        button.clicked.connect(action)
        self.addWidget(button)


class CodeWidget(QPlainTextEdit):

    def __init__(self, root, parent=None):
        super().__init__(parent)
        self.root = root

        # self.setCenterOnScroll(True)

        # generate file paths
        self.file_path = 'code/lab.asm'
        self.temp_dir_path = tempfile.mkdtemp('terminal')
        self.temp_asm_path = os.path.join(self.temp_dir_path, 'lab.asm')
        self.temp_hex_path = os.path.join(self.temp_dir_path, 'lab.hex')

        # text settings
        self.line_length = 80  # number or characters allowed in line before comment wraps
        self.tab_length = 4  # number of spaces to replace a tab with

        # use monospaced font
        fixed_font = QFont('Monospace')
        fixed_font.setStyleHint(QFont.TypeWriter)
        self.setFont(fixed_font)

        # size the view-port based on line_length and the chosen _fixed_ font
        font_width = QFontMetrics(fixed_font).averageCharWidth()
        # for some reason need to multiply by about 1.15 (found by trial and error)
        self.setMinimumWidth(font_width*self.line_length*1.15)

        # serial
        self.terminal = self.root.terminal_widget

        # logging
        self._log = self.terminal._log
        self._log_error = self.terminal._log_error

        self.open()

    def assemble(self):
        # save current asm to temp_asm
        with open(self.temp_asm_path, 'w') as temp_asm_file:
            asm = self.toPlainText()
            # add trailing newline to prevent assembler throwing error
            asm += '\n'
            temp_asm_file.write(asm)

        # assemble temp_asm
        as31_process = subprocess.Popen(['as31', '-l', self.temp_asm_path],
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE)
        output, errors = as31_process.communicate()
        errors = errors.decode("utf-8")

        # no errors
        if errors == 'Begin Pass #1\nBegin Pass #2\n':
            self.setExtraSelections([])  # clear anything previously highlighted as an error
            self._log('Code assembled successfully.')
            return True

        # yes errors
        else:
            self._log_error('Error assembling code.')
            # highlight lines with errors
            selections = []
            for error in errors.split('\n'):
                match = re.search('line ([0-9]+)', error)
                if match:
                    block = self.document().findBlockByNumber(int(match.group(1)) - 1)
                    selection = QTextEdit.ExtraSelection()
                    selection.cursor = QTextCursor(block)
                    selection.format.setProperty(QTextFormat.FullWidthSelection, True)
                    selection.format.setBackground(Qt.red)  # self.palette().alternateBase()
                    selection.format.setForeground(Qt.white)
                    selections.append(selection)
            self.setExtraSelections(selections)
            # log error information in terminal console
            self._log_error(errors)
            return False

    def clean(self, code):
        # some basic optimizations
        code = code.replace('\t', ' '*self.tab_length)
        code = code.replace('\r', '\n')
        code = re.sub('\n +(?=\n|$)', '\n', code)
        code = re.sub(' +(?=\n|$)', '', code)
        code = re.sub('\n\n\n+', '\n', code)  # fixme: yes? no?
        # code = re.sub('^\n\n+', '\n', code) messes up copies in middle fixme: separate copy and original paste?
        #code = re.sub('\n+$', '', code)
        return code

    def closeEvent(self, event):
        if self.temp_dir_path:
            shutil.rmtree(self.temp_dir_path)

    def insertFromMimeData(self, source):
        # catch any attempt to paste text and clean it up first
        if source.hasText():
            text = source.text()
            text = self.clean(text)
            self.textCursor().insertText(text)

    def keyPressEvent(self, event):
        char = event.text()
        key = event.key()

        # convert tabs to spaces
        if char == '\t':
            event.accept()
            self.textCursor().insertText(' '*self.tab_length)

        # auto-indent newlines
        elif char in ('\n', '\r'):
            event.accept()
            cursor = self.textCursor()
            line = cursor.block()
            text = '\n'
            if line.isValid():
                # current line is a label
                if re.match('[a-zA-Z$_][a-zA-Z0-9$_]*:', line.text()):
                    text += ' '*self.tab_length
                # current line is indented
                elif re.match(' +[^ ]', line.text()):
                    text += re.match('( +)', line.text()).group(1)
            cursor.insertText(text)

        # auto indent and wrap comments
        elif key == Qt.Key_Semicolon:
            event.accept()
            cursor = self.textCursor()
            line = cursor.block()
            # ignore if already in a comment
            if ';' in line.text()[:cursor.positionInBlock()]:
                cursor.insertText(';')
            elif line.text().isspace():
                cursor.select(QTextCursor.BlockUnderCursor)
                cursor.insertText('\n; ')
            else:
                # find minimum acceptable offset
                offset = cursor.positionInBlock()
                other_line = line.previous()
                while other_line.isValid() and ';' in other_line.text():
                    other_offset = other_line.text().find(';')
                    offset = offset if other_offset < offset else other_offset
                    other_line = other_line.previous()
                other_line = line.next()
                while other_line.isValid() and ';' in other_line.text():
                    other_offset = other_line.text().find(';')
                    offset = offset if other_offset < offset else other_offset
                    other_line = other_line.next()
                if offset > cursor.positionInBlock():
                    text = ' ' * (offset - cursor.positionInBlock()) + '; '
                else:
                    text = '; '
                cursor.insertText(text)

        # auto remove a full tab length when backspace is applied to tab area
        # fixme: comment and simplify
        elif key == Qt.Key_Backspace:
            cursor = self.textCursor()
            line = cursor.block()
            position = cursor.positionInBlock()
            if position > 0 and not cursor.selectedText() and line.text()[:position] == ' '*position:
                event.accept()
                amount = len(re.match(' +', line.text()).group()) % self.tab_length
                if amount == 0:
                    amount = self.tab_length
                right_move = self.tab_length - (position % self.tab_length) if position < self.tab_length else 0
                cursor.movePosition(QTextCursor.NextCharacter, QTextCursor.MoveAnchor, right_move)
                left_move = position + right_move if position < self.tab_length else amount
                cursor.movePosition(QTextCursor.PreviousCharacter, QTextCursor.KeepAnchor, left_move)
                cursor.removeSelectedText()
            else:
                super().keyPressEvent(event)

        # anything else let qt handle
        else:
            super().keyPressEvent(event)

    def open(self):
        with open(self.file_path, 'r') as asm_file:
            # text
            code = asm_file.read()
            code = self.clean(code)
            # display
            self.setPlainText(code)

    def save(self):
        pass

    def send(self):
        # make sure a port is open
        if not self.terminal.serial_port:
            self._log_error('No open connection.')
            return
        # assemble code
        if not self.assemble():
            return
        # read hex data from assembled code
        with open(self.temp_hex_path, 'rb') as temp_hex_file:
            hex_data = temp_hex_file.read()
            # hex_data = hex_data.replace(b'\n', b'').replace(b'\r', b'')
        # send hex data
        self.terminal.serial_download(hex_data)


class TerminalWidget(QPlainTextEdit):

    log_error = pyqtSignal(object)  # *args: description(str)
    log_message = pyqtSignal(object)  # *args: message(str)
    data_received = pyqtSignal(object)  # *args: data(bytes)
    data_sent = pyqtSignal(object)  # *args: data(bytes)

    def __init__(self, root, parent=None):
        super().__init__(parent)
        self.root = root

        # appearance
        self.highlighted_line = None
        self.highlighted_format = QTextBlockFormat()
        self.highlighted_format.setBackground(Qt.yellow)
        self.setReadOnly(True)
        self.setCursor(Qt.ArrowCursor)

        # terminal settings
        self.echo = False

        # serial communications
        self.baud_rate = 9600
        self.port_names = ['/dev/tty.usbserial', 'com1']
        self.serial_data = None
        self.serial_port = None
        self.serial_thread = None
        self.serial_thread_close = threading.Event()
        self.serial_thread_connected = threading.Event()
        self.serial_thread_download = threading.Event()
        self.serial_thread_write = threading.Event()
        self.serial_open()

        # signals
        # (needed for communication with thread, throws errors when trying to manipulate QWidgets directly)
        self.data_received.connect(self._log_serial)
        self.log_error.connect(self._log_error)
        self.log_message.connect(self._log)

    def closeEvent(self, event):
        self.serial_close()

    def keyPressEvent(self, event):
        char = event.text()
        if not char:
            super().keyPressEvent(event)
        else:
            event.accept()
            # echo char
            if self.echo:
                self.appendPlainText(event.text())
            # send char
            self.serial_write(char)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)

        cursor = self.cursorForPosition(event.pos())

        # highlight line
        selection = QTextEdit.ExtraSelection()
        selection.cursor = cursor
        selection.format.setProperty(QTextFormat.FullWidthSelection, True)
        selection.format.setBackground(self.palette().alternateBase())
        self.setExtraSelections([selection])

        # link to line in code editor if a msg contains a line number
        line_match = re.search('line ([0-9]+)', cursor.block().text())
        if line_match:
            block = self.root.code_widget.document().findBlockByNumber(int(line_match.group(1)) - 1)
            cursor = QTextCursor(block)
            self.root.code_widget.setTextCursor(cursor)

    def serial_close(self):
        if self.serial_port:
            # tell the listening thread to stop
            self.serial_thread_close.set()
            # wait until thread has finished
            self.serial_thread.join()
            self.serial_thread = None
            # close the port
            self.serial_port.close()

    def serial_download(self, data):
        # check that port is open
        if not self.serial_port:
            self.log_error.emit('No open connection.')
            return
        # send download to serial_thread
        self.serial_data = data
        self.serial_thread_download.set()
        # wait for download to complete
        # fixme: is this waiting necessary?
        while self.serial_thread_download.is_set():
            QCoreApplication.instance().processEvents(QEventLoop.ExcludeUserInputEvents)  # display messages to terminal
            time.sleep(0.1)  # save some power (?)

    def serial_interface(self):
        # used by serial_thread to interface with r31jp device at serial_port
        while not self.serial_thread_close.is_set():

            # open port
            if not self.serial_port:
                for port_name in self.port_names:
                    # try opening a port
                    try:
                        # use a timeout to allow thread to check for serial_thread_close event and not get stuck at read
                        self.serial_port = serial.Serial(port_name, baudrate=self.baud_rate, timeout=1)
                    except serial.SerialException as exception:
                        self.serial_port = None
                    if self.serial_port:
                        self.log_message.emit('Device connected.')
                        self.serial_thread_connected.set()
                        break

            # download data to device
            elif self.serial_thread_download.is_set():
                self.log_message.emit('Hit RESET in MON mode to download file...')
                # wait for r31jp to be ready
                while True:  # fixme: add a timeout?
                    data = self._serial_read()
                    if data == b'*':
                        break
                # initiate transfer
                self._serial_write(b'DD')
                while True:  # fixme: add a timeout?
                    data = self._serial_read()
                    if data == b'>':
                        break
                # send data
                self.log_message.emit('Sending data...')
                self._serial_write(self.serial_data)
                while True:  # fixme: add a timeout?
                    data = self._serial_read()
                    if data and not data == b'.':
                        break
                self.log_message.emit('Data sent successfully.')
                self.serial_thread_download.clear()

            # write data to device
            elif self.serial_thread_write.is_set():
                self._serial_write(self.serial_data)
                self.serial_thread_write.clear()

            # read data from device
            else:
                self._serial_read()

            # don't loop like crazy; once every tenth second should be plenty
            time.sleep(0.1)

    def _serial_read(self):
        try:
            # this method should only be called by the serial_thread
            data = self.serial_port.read()
            # may have timed out
            if data:
                # if there is more data to read
                amount_waiting = self.serial_port.inWaiting()
                if amount_waiting:
                    data += self.serial_port.read(size=amount_waiting)
                # signal that data was received
                self.data_received.emit(data)
            return data
        except Exception as exception:
            # fixme: only specific ones that imply device was disconnected
            # fixme: for _serial_write, and ending calling function too!
            self.log_error.emit('Connection appears to have been lost.')
            self.log_error.emit('[It may be an error in the code\'s try block though.]')
            self.serial_port = None
            self.log_message.emit('Searching for serial device...')

    def _serial_write(self, data):
        # for byte in data:
        self.serial_port.write(data)
        self.serial_port.flush()
        # signal that data was sent
        self.data_sent.emit(data)

    def serial_open(self, port_name=None, baud_rate=None):
        # serial settings
        self.port_names = [port_name] if port_name else self.port_names  # fixme: serial.tools.list_ports.comports()
        self.baud_rate = baud_rate if baud_rate else self.baud_rate
        # initiate interface thread
        self._log('Searching for serial device...')
        self.serial_thread = threading.Thread(target=self.serial_interface)
        self.serial_thread.setDaemon(1)  # don't shut down while of communication with device
        self.serial_thread.start()

    def serial_write(self, data):
        # check that port is open
        if not self.serial_port:
            self.log_message.emit('No open connection.')
            return
        # make sure data is in byte form
        if not isinstance(data, bytes):
            data = data.encode('utf-8')
        # send download to serial_thread
        self.serial_data = data
        self.serial_thread_write.set()
        # wait for download to complete
        # fixme: is this waiting necessary?
        while self.serial_thread_write.is_set():
            QCoreApplication.instance().processEvents(QEventLoop.ExcludeUserInputEvents)  # display messages to terminal
            time.sleep(0.1)  # save some power (?)

    def _log(self, message):
        for line in message.split('\n'):  # since using html, \n doesn't mean anything
            self.appendHtml('<span style="color:blue;font-weight:bold;">%s</span>' % line)

    def _log_error(self, description):
        for line in description.split('\n'):  # since using html, \n doesn't mean anything
            self.appendHtml('<span style="color:red;font-weight:bold;">%s</span>' % line)

    def _log_serial(self, data):
        # insert at end without a newline or any special formatting
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.setCharFormat(QTextCharFormat())
        cursor.insertText(data.decode("utf-8"))
        # scroll to cursor
        self.setTextCursor(cursor)

def launch():
    application = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.resize(1000,600)
    main_window.show()
    sys.exit(application.exec_())


if __name__ == '__main__':
    launch()
