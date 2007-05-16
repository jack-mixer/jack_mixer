#!/usr/bin/env python
#
# This file is part of jack_mixer
#
# Copyright (C) 2006 Nedko Arnaudov <nedko@arnaudov.name>
#  
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301 USA.

import math
import fpconst
import jack_mixer_c

class threshold:
    '''Encapsulates scale linear function edge and coefficients for scale = a * dB + b formula'''
    def __init__(self, db, scale):
        self.db = db
        self.scale = scale
        self.threshold = jack_mixer_c.threshold_create(db, scale)
        self.text = "%.0f" % math.fabs(db)
        if not self.threshold:
            raise "creating new threshold failed"

    def calculate_coefficients(self, prev):
        jack_mixer_c.threshold_calculate_coefficients(self.threshold, prev.threshold)

    def db_to_scale(self, db):
        return jack_mixer_c.threshold_db_to_scale(self.threshold, db)

    def scale_to_db(self, scale):
        return jack_mixer_c.threshold_scale_to_db(self.threshold, scale)

    def __del__(self):
        if self.threshold:
            jack_mixer_c.threshold_destroy(self.threshold)

class base:
    '''Scale abstraction, various scale implementation derive from this class'''
    def __init__(self, scale_id, description):
        self.marks = []
        self.thresholds = []
        self.scale_id = scale_id
        self.description = description
        self.scale = jack_mixer_c.scale_create()

    def add_threshold(self, db, scale, mark):
        thr = threshold(db, scale)
        #print repr(thr.threshold)
        self.thresholds.append(thr)
        jack_mixer_c.scale_add_threshold(self.scale, thr.threshold)
        if mark:
            self.marks.append(thr)

    def calculate_coefficients(self):
        jack_mixer_c.scale_calculate_coefficients(self.scale)

    def db_to_scale(self, db):
        '''Convert dBFS value to number in range 0.0-1.0 used in GUI'''
        #print "db_to_scale(%f)" % db
        return jack_mixer_c.scale_db_to_scale(self.scale, db)

    def scale_to_db(self, scale):
        '''Convert number in range 0.0-1.0 used in GUI to dBFS value'''
        return jack_mixer_c.scale_scale_to_db(self.scale, scale)

    def add_mark(self, db):
        mark = threshold(db, -1.0)
        self.marks.append(mark)

    def get_marks(self):
        return self.marks

    def scale_marks(self):
        for i in self.marks:
            if i.scale == -1.0:
                i.scale = self.db_to_scale(i.db)

# IEC 60268-18 Peak programme level meters - Digital audio peak level meter
# Adapted from meterpridge, may be wrong, I'm not buying standards, event if they cost $45
# If someone has the standart, please eighter share it with me or fix the code.
class iec_268(base):
    '''IEC 60268-18 Peak programme level meters - Digital audio peak level meter'''
    def __init__(self):
        base.__init__(self, "iec_268", "IEC 60268-18 Peak programme level meters - Digital audio peak level meter")
        self.add_threshold(-70.0, 0.0, False)
        self.add_threshold(-60.0, 0.05, True)
        self.add_threshold(-50.0, 0.075, True)
        self.add_threshold(-40.0, 0.15, True)
        self.add_mark(-35.0)
        self.add_threshold(-30.0, 0.3, True)
        self.add_mark(-25.0)
        self.add_threshold(-20.0, 0.5, True)
        self.add_mark(-15.0)
        self.add_mark(-10.0)
        self.add_mark(-5.0)
        self.add_threshold(0.0, 1.0, True)
        self.calculate_coefficients()
        self.scale_marks()

class iec_268_minimalistic(base):
    '''IEC 60268-18 Peak programme level meters - Digital audio peak level meter, fewer marks'''
    def __init__(self):
        base.__init__(self, "iec_268_minimalistic", "IEC 60268-18 Peak programme level meters - Digital audio peak level meter, fewer marks")
        self.add_threshold(-70.0, 0.0, False)
        self.add_threshold(-60.0, 0.05, True)
        self.add_threshold(-50.0, 0.075, False)
        self.add_threshold(-40.0, 0.15, True)
        self.add_threshold(-30.0, 0.3, True)
        self.add_threshold(-20.0, 0.5, True)
        self.add_mark(-10.0)
        self.add_threshold(0.0, 1.0, True)
        self.calculate_coefficients()
        self.scale_marks()

class linear_70dB(base):
    '''Linear scale with range from -70 to 0 dBFS'''
    def __init__(self):
        base.__init__(self, "linear_70dB", "Linear scale with range from -70 to 0 dBFS")
        self.add_threshold(-70.0, 0.0, False)
        self.add_mark(-60.0)
        self.add_mark(-50.0)
        self.add_mark(-40.0)
        self.add_mark(-35.0)
        self.add_mark(-30.0)
        self.add_mark(-25.0)
        self.add_mark(-20.0)
        self.add_mark(-15.0)
        self.add_mark(-10.0)
        self.add_mark(-5.0)
        self.add_threshold(0.0, 1.0, True)
        self.calculate_coefficients()
        self.scale_marks()

class linear_30dB(base):
    '''Linear scale with range from -30 to +30 dBFS'''
    def __init__(self):
        base.__init__(self, "linear_30dB", "Linear scale with range from -30 to +30 dBFS")
        self.add_threshold(-30.0, 0.0, False)
        self.add_threshold(+30.0, 1.0, True)
        self.calculate_coefficients()
        self.scale_marks()

def scale_test1(scale):
    for i in range(-97 * 2, 1, 1):
        db = float(i)/2.0
        print "%5.1f dB maps to %f" % (db, scale.db_to_scale(db))

def scale_test2(scale):
    for i in range(101):
        s = float(i)/100.0
        print "%.2f maps to %.1f dB" % (s, scale.scale_to_db(s))

def print_db_to_scale(db):
    print "%-.1f dB maps to %f" % (db, scale.db_to_scale(db))

def scale_test3(scale):
    print_db_to_scale(+77.0)
    print_db_to_scale(+7.0)
    print_db_to_scale(0.0)
    print_db_to_scale(-107.0)

#scale = linear_30dB()
#scale_test2(scale)
#scale_test3(scale)
