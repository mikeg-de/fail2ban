#!/usr/bin/env python

# This file is part of Fail2Ban.
#
# Fail2Ban is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Fail2Ban is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Fail2Ban; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

# Author: Cyril Jaquier
# 
# $Revision$

__author__ = "Cyril Jaquier"
__version__ = "$Revision$"
__date__ = "$Date$"
__copyright__ = "Copyright (c) 2004 Cyril Jaquier"
__license__ = "GPL"

from distutils.core import setup
from version import version

setup(
        name = "fail2ban",
        version = version,
        description = "Ban IPs that make too many password failure",
        author = "Cyril Jaquier",
        author_email = "lostcontrol@users.sourceforge.net",
        url = "http://www.sourceforge.net/projects/fail2ban",
        scripts = ['fail2ban.py'],
        py_modules = ['version'],
        packages = ['firewall', 'logreader', 'confreader', 'utils']
)
