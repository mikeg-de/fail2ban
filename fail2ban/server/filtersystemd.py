# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: t -*-
# vi: set ft=python sts=4 ts=4 sw=4 noet :

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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.


__author__ = "Steven Hiscocks"
__copyright__ = "Copyright (c) 2013 Steven Hiscocks"
__license__ = "GPL"

import datetime
import time
from distutils.version import LooseVersion

from systemd import journal
if LooseVersion(getattr(journal, '__version__', "0")) < '204':
	raise ImportError("Fail2Ban requires systemd >= 204")

from .failmanager import FailManagerEmpty
from .filter import JournalFilter
from .mytime import MyTime
from .utils import Utils
from ..helpers import getLogger, logging, splitwords

# Gets the instance of the logger.
logSys = getLogger(__name__)


##
# Journal reader class.
#
# This class reads from systemd journal and detects login failures or anything
# else that matches a given regular expression. This class is instantiated by
# a Jail object.

class FilterSystemd(JournalFilter): # pragma: systemd no cover
	##
	# Constructor.
	#
	# Initialize the filter object with default values.
	# @param jail the jail object

	def __init__(self, jail, **kwargs):
		jrnlargs = FilterSystemd._getJournalArgs(kwargs)
		JournalFilter.__init__(self, jail, **kwargs)
		self.__modified = 0
		# Initialise systemd-journal connection
		self.__journal = journal.Reader(**jrnlargs)
		self.__matches = []
		self.setDatePattern(None)
		logSys.debug("Created FilterSystemd")

	@staticmethod
	def _getJournalArgs(kwargs):
		args = {'converters':{'__CURSOR': lambda x: x}}
		try:
			args['path'] = kwargs.pop('journalpath')
		except KeyError:
			pass

		try:
			args['files'] = kwargs.pop('journalfiles')
		except KeyError:
			pass
		else:
			import glob
			p = args['files']
			if not isinstance(p, (list, set, tuple)):
				p = splitwords(p)
			files = []
			for p in p:
				files.extend(glob.glob(p))
			args['files'] = list(set(files))

		try:
			args['flags'] = kwargs.pop('journalflags')
		except KeyError:
			pass

		return args

	##
	# Add a journal match filters from list structure
	#
	# @param matches list structure with journal matches

	def _addJournalMatches(self, matches):
		if self.__matches:
			self.__journal.add_disjunction() # Add OR
		newMatches = []
		for match in matches:
			newMatches.append([])
			for match_element in match:
				self.__journal.add_match(match_element)
				newMatches[-1].append(match_element)
			self.__journal.add_disjunction()
		self.__matches.extend(newMatches)

	##
	# Add a journal match filter
	#
	# @param match journalctl syntax matches in list structure

	def addJournalMatch(self, match):
		newMatches = [[]]
		for match_element in match:
			if match_element == "+":
				newMatches.append([])
			else:
				newMatches[-1].append(match_element)
		try:
			self._addJournalMatches(newMatches)
		except ValueError:
			logSys.error(
				"Error adding journal match for: %r", " ".join(match))
			self.resetJournalMatches()
			raise
		else:
			logSys.info("Added journal match for: %r", " ".join(match))
	##
	# Reset a journal match filter called on removal or failure
	#
	# @return None 

	def resetJournalMatches(self):
		self.__journal.flush_matches()
		logSys.debug("Flushed all journal matches")
		match_copy = self.__matches[:]
		self.__matches = []
		try:
			self._addJournalMatches(match_copy)
		except ValueError:
			logSys.error("Error restoring journal matches")
			raise
		else:
			logSys.debug("Journal matches restored")

	##
	# Delete a journal match filter
	#
	# @param match journalctl syntax matches

	def delJournalMatch(self, match):
		if match in self.__matches:
			del self.__matches[self.__matches.index(match)]
			self.resetJournalMatches()
		else:
			raise ValueError("Match not found")
		logSys.info("Removed journal match for: %r" % " ".join(match))

	##
	# Get current journal match filter
	#
	# @return journalctl syntax matches

	def getJournalMatch(self):
		return self.__matches

    ##
    # Join group of log elements which may be a mix of bytes and strings
    #
    # @param elements list of strings and bytes
    # @return elements joined as string

	@staticmethod
	def _joinStrAndBytes(elements):
		strElements = []
		for element in elements:
			if isinstance(element, str):
				strElements.append(element)
			else:
				strElements.append(str(element, errors='ignore'))
		return " ".join(strElements)

	##
	# Format journal log entry into syslog style
	#
	# @param entry systemd journal entry dict
	# @return format log line

	@classmethod
	def formatJournalEntry(cls, logentry):
		logelements = [""]
		if logentry.get('_HOSTNAME'):
			logelements.append(logentry['_HOSTNAME'])
		if logentry.get('SYSLOG_IDENTIFIER'):
			logelements.append(logentry['SYSLOG_IDENTIFIER'])
			if logentry.get('SYSLOG_PID'):
				logelements[-1] += ("[%i]" % logentry['SYSLOG_PID'])
			elif logentry.get('_PID'):
				logelements[-1] += ("[%i]" % logentry['_PID'])
			logelements[-1] += ":"
		elif logentry.get('_COMM'):
			logelements.append(logentry['_COMM'])
			if logentry.get('_PID'):
				logelements[-1] += ("[%i]" % logentry['_PID'])
			logelements[-1] += ":"
		if logelements[-1] == "kernel:":
			if '_SOURCE_MONOTONIC_TIMESTAMP' in logentry:
				monotonic = logentry.get('_SOURCE_MONOTONIC_TIMESTAMP')
			else:
				monotonic = logentry.get('__MONOTONIC_TIMESTAMP')[0]
			logelements.append("[%12.6f]" % monotonic.total_seconds())
		if isinstance(logentry.get('MESSAGE',''), list):
			logelements.append(" ".join(logentry['MESSAGE']))
		else:
			logelements.append(logentry.get('MESSAGE', ''))

		try:
			logline = u" ".join(logelements)
		except UnicodeDecodeError:
			# Python 2, so treat as string
			logline = " ".join([str(logline) for logline in logelements])
		except TypeError:
			# Python 3, one or more elements bytes
			logSys.warning("Error decoding log elements from journal: %s" %
				repr(logelements))
			logline =  cls._joinStrAndBytes(logelements)

		date = logentry.get('_SOURCE_REALTIME_TIMESTAMP',
				logentry.get('__REALTIME_TIMESTAMP'))
		logSys.debug("Read systemd journal entry: %r" %
			"".join([date.isoformat(), logline]))
		return (('', date.isoformat(), logline),
			time.mktime(date.timetuple()) + date.microsecond/1.0E6)

	def seekToTime(self, date):
		if not isinstance(date, datetime.datetime):
			date = datetime.datetime.fromtimestamp(date)
		self.__journal.seek_realtime(date)

	##
	# Main loop.
	#
	# Peridocily check for new journal entries matching the filter and
	# handover to FailManager

	def run(self):

		if not self.getJournalMatch():
			logSys.notice(
				"Jail started without 'journalmatch' set. "
				"Jail regexs will be checked against all journal entries, "
				"which is not advised for performance reasons.")

		# Seek to now - findtime in journal
		start_time = datetime.datetime.now() - \
				datetime.timedelta(seconds=int(self.getFindTime()))
		self.seekToTime(start_time)
		# Move back one entry to ensure do not end up in dead space
		# if start time beyond end of journal
		try:
			self.__journal.get_previous()
		except OSError:
			pass # Reading failure, so safe to ignore

		while self.active:
			# wait for records (or for timeout in sleeptime seconds):
			self.__journal.wait(self.sleeptime)
			if self.idle:
				# because journal.wait will returns immediatelly if we have records in journal,
				# just wait a little bit here for not idle, to prevent hi-load:
				if not Utils.wait_for(lambda: not self.idle, 
					self.sleeptime * 10, self.sleeptime
				):
					self.ticks += 1
					continue
			self.__modified = 0
			while self.active:
				logentry = None
				try:
					logentry = self.__journal.get_next()
				except OSError as e:
					logSys.error("Error reading line from systemd journal: %s",
						e, exc_info=logSys.getEffectiveLevel() <= logging.DEBUG)
				self.ticks += 1
				if logentry:
					self.processLineAndAdd(
						*self.formatJournalEntry(logentry))
					self.__modified += 1
					if self.__modified >= 100: # todo: should be configurable
						break
				else:
					break
			if self.__modified:
				try:
					while True:
						ticket = self.failManager.toBan()
						self.jail.putFailTicket(ticket)
				except FailManagerEmpty:
					self.failManager.cleanup(MyTime.time())

		logSys.debug((self.jail is not None and self.jail.name
                      or "jailless") +" filter terminated")
		return True

	def status(self, flavor="basic"):
		ret = super(FilterSystemd, self).status(flavor=flavor)
		ret.append(("Journal matches",
			[" + ".join(" ".join(match) for match in self.__matches)]))
		return ret
