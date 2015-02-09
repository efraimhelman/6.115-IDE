————--------
Requirements
————--------

1. python, pyQt, and pySerial
2. probably only compatible with py3.x
3. only tested on OS X
4. only tested with certain serial ports; it doesn’t know where to look otherwise

————--------
Installation
————--------

1. Suggested installation for OS X
	a. google, download, and install the anaconda python 3.4 distribution
	b. run from the terminal: $ conda install pyserial

2. Suggested installation for Win
	a. none

--------
Features
--------

- hyper-terminal and code window in one environment
- automatically searches for and connects to serial device even when plugging in later
- assembles and downloads code with one click
- highlights code that caused assembler to throw errors

todo:
- syntax highlighting
- keep comments aligned and neat

————---
Credits
————---

Thank you to David Yamnitsky for insights gained from his 6.115 cmd-line script.

————---
License
————---

Distributed under the MIT license, but subject to the licensing of all packages involved: including but not limited to the as31 compiler, pyQt, pySerial, and python. I have no idea how these legalities translate. In the words of the honorable Prof Steven Leeb: You dig?

---------
Changelog
---------

version 0.01
- released with basic features
