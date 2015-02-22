#-------------------------------------------------------------------------------
# Name:        main
# Purpose:     IDE for development of the R-31JP system used in MITs course 6.115
#
# Author:      Efraim Helman
#
# Created:     02/7/2015
# Copyright:   (c) EH 2015
# License:     MIT License
#-------------------------------------------------------------------------------


import configparser
import os
import os.path
import queue
import re
import sys
import serial
import shutil
import string
import subprocess
import tempfile
import threading
import time
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *


# assembly instructions in 8051 for R-31JP
INSTRUCTIONS_8051 = ['acall', 'add', 'addc', 'ajmp', 'anl', 'cjne', 'clr', 'cpl',
                    'da', 'dec', 'div', 'djnz', 'inc', 'jb', 'jbc', 'jc', 'jmp',
                    'jnb', 'jnc', 'jnz', 'jz', 'lcall', 'ljmp', 'mov', 'movc',
                    'movx', 'mul', 'nop', 'orl', 'pop', 'push', 'ret', 'reti',
                    'rl', 'rlc', 'rr', 'rrc', 'setb', 'sjmp', 'subb', 'swap',
                    'xch', 'xrl']

# load relative path no matter what working directory IDE is launched from
relative_path = lambda path: os.path.join(os.path.dirname(__file__), path)


class MainWindow(QMainWindow):

    def __init__(self, parent=None):
        super().__init__(parent)

        # appearance
        self.setWindowTitle('6.115 IDE')

        # configuration
        self.config = configparser.ConfigParser()
        self.config.read(relative_path('config.ini'))

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
        # close widgets
        self.code_widget.closeEvent(event)
        self.terminal_widget.closeEvent(event)
        # save configuration
        with open(relative_path('config.ini'), 'w') as config_file:
            self.config.write(config_file)

    def configure(self):
        self.terminal_widget._log_error('Not implemented. Edit config.ini file.')
        self.code_widget.view_temp_files()


class MainToolbar(QToolBar):
    def __init__(self, root, parent=None):
        super().__init__('Main Toolbar', parent)
        self.root = root
        self._add_button('Open', 'open.png', self.root.code_widget.open)
        self._add_button('Save', 'save.png', self.root.code_widget.save)
        self._add_button('New', 'new.png', self.root.code_widget.new)
        self.addSeparator()
        self._add_button('Assemble and send', 'device.png', self.root.code_widget.send)
        self.addSeparator()
        self._add_button('Configure', 'config.png', self.root.configure)

    def _add_button(self, tooltip, icon, action, menu=None):
        # fixme: use QActions?
        # fixme: add shortcuts
        button = QToolButton(self)
        button.clicked.connect(action)
        button.setIcon(QIcon(relative_path('resources/images/%s') % icon))
        button.setToolTip(tooltip)
        self.addWidget(button)


class CodeWidget(QPlainTextEdit):

    def __init__(self, root, parent=None):
        super().__init__(parent)
        self.root = root

        # file paths
        self.file_path = ''
        self.temp_dir_path = tempfile.mkdtemp('terminal')
        self.temp_asm_path = os.path.join(self.temp_dir_path, 'lab.asm')
        self.temp_hex_path = os.path.join(self.temp_dir_path, 'lab.hex')

        # configuration
        self.comment_gap = int(self.root.config['code']['comment_gap'])  # number of spaces between code and comment
        self.line_length = int(self.root.config['code']['line_length'])  # number of chars before comment wraps
        self.tab_length = int(self.root.config['code']['tab_length'])  # number of spaces to replace a tab with

        # monospaced font & line width
        fixed_font = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        fixed_font.setPixelSize(12)
        font_width = QFontMetrics(fixed_font).averageCharWidth()
        self.setFont(fixed_font)
        self.setMinimumWidth(font_width * self.line_length * 1.1)

        # suggestions
        self.prefix = None
        self.suffix = None
        self.suggestion = QListWidget(self)
        self.suggestion.activated.connect(self.suggestion.hide)
        self.suggestion.activated.connect(lambda index: self._apply_suggestion(self.suggestion.itemFromIndex(index).text()))
        self.suggestion.setAttribute(Qt.WA_ShowWithoutActivating)
        self.suggestion.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.suggestion.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.suggestion.setFocusProxy(self)
        self.suggestion.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.suggestion.setSelectionMode(QAbstractItemView.SingleSelection)
        self.suggestion.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.suggestion.show = self._show_suggestion

        # syntax highlighting
        self.syntax_highlighter = SyntaxHighlighter(self.document(), self.root.config)

        # serial
        self.terminal = self.root.terminal_widget

        # logging
        self._log_message = self.terminal._log_message
        self._log_error = self.terminal._log_error

        # open recent file if it exists
        recent_file = self.root.config['file']['last']
        if recent_file and os.path.exists(recent_file):
            self.open(recent_file)
        else:
            self.new()

    def assemble(self):
        # save code to temporary file and
        # add trailing newline to prevent as31 from throwing a syntax error
        with open(self.temp_asm_path, 'w') as temp_asm_file:
            temp_asm_file.write(self.toPlainText() + '\n')

        # choose correct assembler
        if sys.platform == 'darwin':
            assembler = relative_path('resources/as31/as31_osx')
        elif sys.platform == 'win32':
            assembler = relative_path('resources/as31/as31_win')

        # assemble code
        as31_process = subprocess.Popen([assembler, '-l', self.temp_asm_path],
          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, errors = as31_process.communicate()
        errors = errors.decode("utf-8")

        # no errors
        if 'error' not in errors.lower() and 'warning' not in errors.lower():
            # un-mark lines previously marked as errors
            self.setExtraSelections([])
            self._log_message('Code assembled successfully.')
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

    def closeEvent(self, event):
        # fixme: check and ask user to save code if needed
        # clean up temporary files
        if self.temp_dir_path:
            shutil.rmtree(self.temp_dir_path)
            self.temp_dir_path = None
        # save configuration
        self.root.config['file']['last'] = self.file_path

    def dragEnterEvent(self, event):
        # open files through drag and drop
        if event.mimeData().hasUrls() and self._url_can_be_opened(event.mimeData().urls()[0]):
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls() and self._url_can_be_opened(event.mimeData().urls()[0]):
            event.accept()
            event.setDropAction(Qt.CopyAction)
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasUrls() and self._url_can_be_opened(event.mimeData().urls()[0]):
            event.accept()
            self.open(event.mimeData().urls()[0].toLocalFile())
        else:
            event.ignore()

    def keyPressEvent(self, event):

        # if keypress is directed at suggestion popup let it handle it
        if self.suggestion.isVisible() and event.key() in \
                (Qt.Key_Enter, Qt.Key_Return, Qt.Key_Escape,
                 Qt.Key_Tab, Qt.Key_Backtab, Qt.Key_Down, Qt.Key_Up):
            self.suggestion.keyPressEvent(event)
            return

        # if keypress is directed as file io
        if event in (QKeySequence.Save, QKeySequence.Open, QKeySequence.New):
            event.accept()
            if event == QKeySequence.Save:
                self.save()
            elif event == QKeySequence.Open:
                self.open()
            elif event == QKeySequence.New:
                self.new()
            return

        # if keypress is directed at navigation
        if event in range(30, 44):  # 30 -> 43 are QKeySequence.Move...
            super().keyPressEvent(event)
            return

        # if keypress is directed at selection
        if event == QKeySequence.SelectAll or event in range(44, 58):  # 44 -> 57 are QKeySequence.Select...
            super().keyPressEvent(event)
            return

        # if keypress is directed at undo/redo
        if event in (QKeySequence.Undo, QKeySequence.Redo):
            super().keyPressEvent(event)
            return

        # if keypress is directed at copy/cut/paste
        # fixme semi merge with next if, instead of calling keypress again
        if event in (QKeySequence.Copy, QKeySequence.Cut, QKeySequence.Paste):
            event.accept()
            if event == QKeySequence.Copy or event == QKeySequence.Cut:
                if self.textCursor().hasSelection():
                    data = self.createMimeDataFromSelection()
                    QApplication.clipboard().setMimeData(data)
                    if event == QKeySequence.Cut:
                        self.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Backspace, Qt.NoModifier))
            elif event == QKeySequence.Paste:
                data = QApplication.clipboard().mimeData()
                if data and data.hasText() and data.text():
                    data = self._clean(data.text())
                    self.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_A, Qt.NoModifier, data))
            return

        # if keypress is directed at character insertion/removal
        if event.text() and all(c in string.printable for c in event.text()) or event.key() == Qt.Key_Backspace:
            event.accept()
            text = event.text()
            cursor = self.textCursor()
            # auto indent for backspace
            if event.key() == Qt.Key_Backspace:
                text = ''
                # remove previous character
                if not cursor.selectedText():
                    cursor.movePosition(QTextCursor.PreviousCharacter, QTextCursor.KeepAnchor)
                # remove semicolon for comments since can't just remove leading space
                if re.match('[^;]*;$', cursor.block().text()[:cursor.positionInBlock()]):
                    cursor.movePosition(QTextCursor.PreviousCharacter, QTextCursor.KeepAnchor)
            # auto indent for tabs
            elif text == '\t':
                text = ' ' * self.tab_length  # fixme min(tab_length, next_tab_stop)
            # auto indent for newlines
            # fixme: like comments, always, not just at individual char insertion?
            elif text in ('\n', '\r'):
                text = '\n'
                block = cursor.block()
                while block.isValid():
                    # block starts with a comment
                    if re.match(' *;', block.text()):
                        block = block.previous()
                    # block starts with a label
                    elif re.match(' *[a-zA-Z$_][a-zA-Z0-9$_]*:', block.text()):
                        text += re.match('( *)', block.text()).group(1) + ' '*self.tab_length
                        break
                    # block starts with an instruction
                    elif re.match(' +[^ ]', block.text()):
                        text += re.match('( +)', block.text()).group(1)
                        break
                    # block is blank
                    else:
                        break
            position = cursor.position()
            removed = len(cursor.selectedText())
            added = len(text)
            cursor.beginEditBlock()
            cursor.insertText(text)
            self._align(position, removed, added)
            cursor.endEditBlock()

            self.suggestion.show()
        else:
            self.suggestion.hide()

    def new(self):
        self.file_path = ''
        self.document().setPlainText('')
        self.document().clearUndoRedoStacks()
        self.setExtraSelections([])

    def open(self, file_path=None):
        # get file_path
        if not file_path:
            # fixme: default/last path; only allow certain filetypes
            file_path, filter = QFileDialog.getOpenFileName(self, 'Open...', filter='Assembly (*.asm *.txt)')
            if not file_path:
                return
        # open file
        with open(file_path, 'r') as file:
            code = self._clean(file.read())
            self.document().setPlainText(code)
            self._align(0, None, len(code))
            self.document().clearUndoRedoStacks()
            self.setExtraSelections([])
        self.file_path = file_path

    def save(self):
        # get path
        file_path = self.file_path
        if not file_path:
            file_path, filter = QFileDialog.getSaveFileName(self, 'Save as...', filter='Assembly (*.asm)')
            if not file_path:
                return
        # save file
        # add trailing newline to prevent as31 from throwing a syntax error
        with open(file_path, 'w') as file:
            file.write(self.toPlainText() + '\n')
        self.file_path = file_path

    def send(self):
        # assemble code
        if not self.assemble():
            return
        # make sure a port is open
        if not self.terminal.serial_port:
            self._log_error('No open connection.')
            return
        # read hex data from assembled code
        with open(self.temp_hex_path, 'rb') as temp_hex_file:
            hex_data = temp_hex_file.read()
        # send hex data
        self.terminal.serial_download(hex_data)

    def view_temp_files(self):
        # platform dependent
        if sys.platform == 'darwin':
            subprocess.call(['open', self.temp_dir_path])
        elif sys.platform == 'win32':
            os.startfile(self.temp_dir_path)

    def _align(self, position, removed, added):

        # group affected blocks
        cursor = self.textCursor()
        cursor.setPosition(position)
        block = cursor.block()
        blocks = [[block]] if ';' in block.text() else [[], []]
        while True:
            block = block.previous()
            if not block.isValid():
                break
            if ';' not in block.text():
                break
            blocks[0].insert(0, block)
        block = cursor.block()
        while True:
            block = block.next()
            if not block.isValid():
                break
            if ';' not in block.text():
                if block.position() <= position + added:  # =< in case newline since .position() is after
                    blocks.append([])
                else:
                    break
            else:
                blocks[-1].append(block)

        # align comments if needed but leave cursor in same place
        cursor_position = self.textCursor().positionInBlock()
        cursor_block = self.textCursor().block()
        for comment_group in blocks:
            if not comment_group:
                continue
            # get prefix and gap length for each block in group
            lengths = [[len(g) for g in re.match('(.*?)( *);( *)', b.text()).groups()] for b in comment_group]
            # get minimum acceptable comment offset but don't insist on gap when comment is on its own line
            minimum = max(l[0] + self.comment_gap if l[0] else 0 for l in lengths)
            # realign comments that need realigning
            for block, (prefix, gap, post_gap) in zip(comment_group, lengths):
                if not prefix + gap == minimum or not post_gap == 1:
                    text = block.text()
                    text = text[:prefix] + ' '*(minimum-prefix) + '; ' + text[prefix+gap+1+post_gap:]
                    cursor = QTextCursor(block)
                    cursor.setPosition(block.position())
                    cursor.setPosition(block.position() + block.length() - 1, QTextCursor.KeepAnchor)
                    cursor.insertText(text)
                    # reset text cursor if needed
                    if block == cursor_block:
                        if cursor_position > prefix + gap + 1 + post_gap:
                            cursor_position = cursor_position + (minimum - prefix - gap) - (post_gap + 1)
                        elif cursor_position > prefix + gap:
                            cursor_position = minimum + 2
                        cursor.setPosition(cursor_block.position() + cursor_position)
                        self.setTextCursor(cursor)

    def _clean(self, code):
        # exchange tabs for spaces and carriage returns for newlines
        code = code.replace('\t', ' ' * self.tab_length).replace('\r', '\n')
        # remove trailing whitespace
        code = re.sub(' +(?=\n|$)', '', code)
        # remove multi-line gaps
        code = re.sub('\n\n\n+', '\n\n', code)
        return code

    def _apply_suggestion(self, suggestion):
        # fixme: add ' ' for instructions, use ':' for labels, etc; but only if not already there
        new_suffix = suggestion[len(self.prefix):]
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.NextCharacter, QTextCursor.KeepAnchor, len(self.suffix))
        cursor.insertText(new_suffix)
        self.setTextCursor(cursor)

    def _get_suggestion(self):

        suggestion = []
        position = self.textCursor().positionInBlock()
        line = self.textCursor().block().text()
        line_prefix = line[:position]
        line_suffix = line[position:]

        # if instruction
        match = re.match(' *([a-zA-Z]+)$', line_prefix)
        if match:
            self.prefix = match.group(1)
            self.suffix = re.match('([a-zA-Z]*)', line_suffix).group(1)
            suggestion = [ins for ins in INSTRUCTIONS_8051 if ins.startswith(self.prefix)]
            if len(suggestion) == 1 and suggestion[0] == self.prefix + self.suffix:
                suggestion = []

        return suggestion

    def _show_suggestion(self):

        # contents of popup
        suggestion = self._get_suggestion()
        if suggestion:
            self.suggestion.clear()
            self.suggestion.addItems(suggestion)
            if self.prefix + self.suffix in suggestion:
                self.suggestion.setCurrentRow(suggestion.index(self.prefix + self.suffix))
            else:
                self.suggestion.setCurrentRow(0)
        else:
            self.suggestion.hide()
            return

        # size and placement of popup
        screen = QApplication.desktop().availableGeometry(self)
        position = self.mapToGlobal(self.cursorRect().bottomLeft())
        x, y = position.x(), position.y()

        width = self.suggestion.sizeHintForColumn(0) + self.suggestion.verticalScrollBar().sizeHint().width()
        if width > screen.width():
            width = screen.width()
        if x + width > screen.left() + screen.width():
            x = screen.left() + screen.width() - width
        if x < screen.left():
            x = screen.left()

        height = max(self.suggestion.sizeHintForRow(0) * min(7, len(suggestion)) + 6, self.suggestion.minimumHeight())
        cursor_height = self.cursorRect().height()
        top = y - cursor_height - screen.top() + 2
        bottom = screen.bottom() - y
        if height > bottom:
            height = min(max(top, bottom), height)
            if top > bottom:
                y = y - height - cursor_height + 2

        self.suggestion.setGeometry(x, y, width, height)
        if not self.suggestion.isVisible():
            super(QListWidget, self.suggestion).show()

    def _url_can_be_opened(self, url):
        path = url.toLocalFile()
        if path[-4:] in ('.asm', '.txt') and os.path.exists(path):
            return True
        return False


class SyntaxHighlighter(QSyntaxHighlighter):

    def __init__(self, document, config):
        super().__init__(document)
        # fixme: addresses, decl, unknowns, regs, numbers/hex, etc
        self.rules = []
        # comments
        style = SyntaxHighlighter.style(config['syntax']['comment'])
        self.rules.append(('(;.*)(?:\n|$)', style))
        # instructions
        # use reversed() so checks for full instruction instead of stopping 'movx' after finding 'mov'
        style = SyntaxHighlighter.style(config['syntax']['instruction'])
        self.rules.append(('(?:\n|^) *(%s)(?:[ ;]|$)' % '|'.join(reversed(INSTRUCTIONS_8051)), style))
        # labels
        style = SyntaxHighlighter.style(config['syntax']['label'])
        self.rules.append(('(?:\n|^) *([a-zA-Z$_][a-zA-Z0-9$_]*:)', style))

    def style(description=''):
        values = description.split(', ')
        style = QTextCharFormat()
        style.setForeground(QColor(values[0]))  # first value must be a color
        if 'bold' in values:
            style.setFontWeight(QFont.Bold)
        if 'italic' in values:
            style.setFontItalic(True)
        return style

    def highlightBlock(self, text):
        for pattern, style in self.rules:
            for match in re.finditer(pattern, text):
                self.setFormat(match.start(1), match.end(1) - match.start(1), style)


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
        self.setCursor(Qt.ArrowCursor)
        self.setReadOnly(True)
        self.setTextInteractionFlags(self.textInteractionFlags() | Qt.TextSelectableByKeyboard)

        # terminal settings
        self.echo = False
        self.logging_serial = False  # in order to force errors and messages onto their own line
        self.logging_newline = False  # in order to merge \r and \n into one
        self.error_style = SyntaxHighlighter.style('red, bold')
        self.message_style = SyntaxHighlighter.style('blue, bold')
        self.serial_style = QTextCharFormat()

        # serial interface thread
        self.baud_rate = int(self.root.config['serial']['baud_rate'])
        self.port_name = self.root.config['serial']['port_name']
        self.read_timeout = float(self.root.config['serial']['read_timeout'])
        self.serial_port = None
        self.serial_thread = None
        self.serial_thread_close = threading.Event()
        self.serial_queue = queue.Queue()

        # signals needed for communication with thread; it throws errors when trying to manipulate QWidgets directly
        self.data_received.connect(self._log_serial)
        self.log_error.connect(self._log_error)
        self.log_message.connect(self._log_message)

        # start serial interface thread
        self._log_message('Searching for serial device...')
        self.serial_thread = threading.Thread(target=self.serial_interface)
        self.serial_thread.setDaemon(1)  # don't shut down while communicating with device
        self.serial_thread.start()

    def closeEvent(self, event):
        self.serial_close()
        self.root.config['serial']['baud_rate'] = str(self.baud_rate)
        self.root.config['serial']['port_name'] = self.port_name

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
        # send data to serial_thread
        self.serial_queue.put(('download', data))

    def serial_interface(self):

        # used by serial_thread to interface with r31jp device at serial_port
        while not self.serial_thread_close.is_set():

            # open port
            if not self.serial_port:
                # fixme: serial.tools.list_ports.comports()
                port_names = [self.port_name] + ['/dev/tty.usbserial', 'com1']  # default and backup ports to scan
                for port_name in port_names:
                    # try opening a port
                    try:
                        # use a timeout to allow thread to check for serial_thread_close event and not get stuck at read
                        self.serial_port = serial.Serial(port_name, baudrate=self.baud_rate, timeout=self.read_timeout)
                    except serial.SerialException as exception:
                        self.serial_port = None
                    if self.serial_port:
                        # fixme: reset queue?
                        self.log_message.emit('Device connected.')
                        break
                if not self.serial_port:
                    continue

            # read data from device
            # fixme: don'r switch off, causes issues; queue it somehow?
            self._serial_read()

            # write data to device
            if not self.serial_queue.empty():

                action, write_data = self.serial_queue.get()

                if action == 'download':
                    self.log_message.emit('Hit RESET in MON mode to download file...')
                    # wait for r31jp to be ready
                    while True:  # fixme: add a timeout?
                        read_data = self._serial_read()
                        if read_data == b'*':
                            break
                    # initiate transfer
                    self._serial_write(b'DD')
                    while True:  # fixme: add a timeout?
                        read_data = self._serial_read()
                        if read_data == b'>':
                            break
                    # send data
                    self.log_message.emit('Sending data...')
                    self._serial_write(write_data)
                    while True:  # fixme: add a timeout?
                        read_data = self._serial_read()
                        if read_data and not read_data == b'.':
                            break
                    self.log_message.emit('Data sent successfully.')

                elif action == 'write':
                    self._serial_write(write_data)

                else:
                    raise ValueError()

            # fixme: saves some power (?)
            # time.sleep(0.01)

    def serial_write(self, data):
        # check that port is open
        if not self.serial_port:
            self.log_message.emit('No open connection.')
            return
        # make sure data is in byte form
        if not isinstance(data, bytes):
            data = data.encode('utf-8')
        # send data to serial_thread
        self.serial_queue.put(('write', data))

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

    def _log(self, text, style=None):
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.setCharFormat(style)
        cursor.insertText(text)
        self.setTextCursor(cursor)  # scroll to cursor

    def _log_error(self, description):
        text = '\n'+description+'\n' if self.logging_serial and not self.logging_newline else description+'\n'
        self.logging_serial = False
        self._log(text, self.error_style)

    def _log_message(self, message):
        text = '\n'+message+'\n' if self.logging_serial and not self.logging_newline else message+'\n'
        self.logging_serial = False
        self._log(text, self.message_style)

    def _log_serial(self, data):
        # log data received from connected device
        try:
            text = data.decode('utf-8')
        except UnicodeDecodeError as error:
            text = data.decode('utf-8', 'ignore')
            self._log_error('Some data received that could not be encoded in UTF-8.')
        if text:
            print([text])
            # merge \n and \r; minmon uses both orders: runes and incantations?
            text = re.sub('\r\n|\n\r|\r', '\n', text)
            if self.logging_newline or not self.logging_serial:
                # if not logging_serial, already forced onto newline by error or message
                if text[0] in ('\r', '\n'):
                    text = text[1:]
            self.logging_newline = False
            if not text:
                return
            if text[-1] == '\n':
                self.logging_newline = True
            # log communication
            self.logging_serial = True
            self._log(text, self.serial_style)


def launch():
    application = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.resize(1000,600)
    main_window.show()
    sys.exit(application.exec_())

if __name__ == '__main__':
    launch()
