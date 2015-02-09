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

-----
Usage
-----

Should be pretty intuitive, but will eventually write more, because there are some things that could use explaining.

--------
Features
--------

- hyper-terminal and code window in one environment
- automatically searches for and connects to serial device even when plugging in later
- assembles and downloads code with one click
- highlights code that caused assembler to throw errors
- drag and drop asm & txt files in code editor to open
- basic syntax highlighting, though admittedly the default color scheme is awful...

todo:
- some basic toolbar and title-bar additions, including save-as
- some basic icon modifications, including size
- automatically keep comments aligned and neat, fix bugs with current implementation
- test on windows
- extended syntax highlighting
- autocomplete
- tooltips with information on 8051 syntax
- searchable instructions by category like in manual
- automatically maintain and load code appendix
- code explorer/tree? but keep interface simple...
- warn about unsaved work before exiting
- scan ports other than most common two or give option of ports to try

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