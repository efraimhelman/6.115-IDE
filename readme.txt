
————--------
Requirements
————--------

1. A python, pyQt5, and pySerial environment
2. As of now only tested with py3.x and pyQt5, and probably only works with these
3. As of now only tested with OsX, but should work with Windows and Linux
4. As of now only scans for `com1` and `/dev/tty.usbserial` serial ports - edit config.ini if needed

————------------------
Suggested Installation
————------------------

OsX:
1. Install python3.4, pySerial, and pyQt5
    a. open terminal
    b. run $ ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"
    c. follow instructions to install homebrew
    d. run $ brew install python3
    e. run $ brew install pyqt5 --with-python3
    f. run $ pip3 install pyserial
2. Download 6.115-IDE from git and launch main.py

Windows:
1. Install python3.4, pySerial, and pyQt5
    a. google, download, and install a python3.4 windows distribution
    b. google, download, and install the pyQt5 windows distribution
    c. google, download, and install the pySerial windows distribution
2. Download 6.115-IDE from git and launch main.py

Other (Linux, etc):
1. Install python3.4, pySerial, and pyQt5
2. Provide an as31 binary for your system and integrate it with the 6.115-IDE code from git
3. It would be helpful it you could submit your as31 & associated changes for the benefit of others

-----
Usage
-----

- Should be pretty intuitive. Let me know if something needs explaining.
- It should be OK to connect or disconnect your R-31JP at any time.
- I realize that the auto indent and comment alignment features are buggy right now. I will fix these soon.
- Drag & drop is broken in Yosemite. This is a known bug with Qt and unresolvable until the 5.4.1 patch is released.
- Please report other bugs and/or offer suggestions.

--------
Features
--------

- hyper-terminal and code window in one environment
- automatically scans for and connects to your R31JP
- assembles and downloads code with one button press
- highlights any lines in your code that caused the assembler to throw errors
- accepts drag and drop of asm & txt files into the code window
- basic auto completion and syntax highlighting, though admittedly the default color scheme is awful...
- automatically keeps comments neatly aligned

todo:
- add tools to view .hex and .lst files generated from assembly
- add one line brew/tap formula to install code and all dependencies (and/or packager for win/osx ?)
- add launcher for mac/win
- treat \r and \n as one when following in terminal
- add search
- problems with queuing
- show byte data
- g jump routine tool button?
- warn about unsaved work before exiting
- auto wrap comments
- extended syntax highlighting and auto completion
- tooltips with information on 8051 syntax
- ability to maintain a code appendix for labs and print
- ability to upload code to 6.115 when needed
- code explorer/tree?
- scan ports other than the most common two
- give user option of ports to try? I don't like interface complexity though

————---
Credits
————---

Thank you to David Yamnitsky for serial/minmon insights gained from his 6.115 cmd-line script

————---
License
————---

Distributed under the MIT license, but subject to the licensing of all packages involved: including but not limited to the as31 compiler, pyQt, pySerial, and python. I have no idea how these legalities translate. In the words of the honorable Prof Steven Leeb: You dig?

---------
Changelog
---------

version 0.06
- added cursor to terminal and forced errors & messages onto their own line
- fixed bug where would only find relative files when IDE directory was the working directory

version 0.05
- added code to automatically keep comments aligned
- added some basic shortcuts
- fixed bug in syntax highlighter not highlighting indented labels
- fixed bug with undo/redo
- fixed/added other various minor bugs/tweaks

version 0.04
- added workaround for UnicodeDecodeError when unencodable data received
- added proper queueing for the serial interface
- added serial port read_timeout variable to config.ini; affects how responsive terminal/device is

version 0.03
- added as31 source code with instructions for building on individual systems
- added auto completion for 8051 instructions
- added better installation instructions
- fixed bugs in the syntax highlighting
- improved the toolbar and other various modification
- [a regression is possible, as I did not have a chance to test changes on R-31JP yet]

version 0.02
- added as31 for win and os recognition
- added drag and drop txt and asm files
- added configuration file
- added memory of last open file
- added basic syntax highlighting
- added open, save, new and removed assemble
- fixed misc bugs
- [a regression is possible, as I did not have a chance to test changes on R-31JP yet]

version 0.01
- released fully operational version, albeit with limited though useful features
