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

import logging
import math

from ._jack_mixer import Scale


log = logging.getLogger(__name__)


class Mark:
    """Encapsulates scale linear function edge and coefficients for scale = a * dB + b formula"""

    def __init__(self, db, scale, text=None):
        self.db = db
        self.scale = scale
        if text is None:
            # TODO: l10n
            self.text = "%.0f" % math.fabs(db)
        else:
            self.text = text


class Base:
    """Scale abstraction, various scale implementation derive from this class"""

    def __init__(self, scale_id, description):
        self.marks = []
        self.scale_id = scale_id
        self.description = description
        self.scale = Scale()

    def add_threshold(self, db, scale, is_mark, text=None):
        self.scale.add_threshold(db, scale)
        if is_mark:
            self.marks.append(Mark(db, scale, text))

    def calculate_coefficients(self):
        self.scale.calculate_coefficients()

    def db_to_scale(self, db):
        """Convert dBFS value to number in range 0.0-1.0 used in GUI"""
        # log.debug("db_to_scale(%f)", db)
        return self.scale.db_to_scale(db)

    def scale_to_db(self, scale):
        """Convert number in range 0.0-1.0 used in GUI to dBFS value"""
        return self.scale.scale_to_db(scale)

    def add_mark(self, db):
        self.marks.append(Mark(db, -1.0))

    def get_marks(self):
        return self.marks

    def scale_marks(self):
        for i in self.marks:
            if i.scale == -1.0:
                i.scale = self.db_to_scale(i.db)


# IEC 60268-18 Peak programme level meters - Digital audio peak level meter
# Adapted from meterbridge, may be wrong, I'm not buying standards, even if they cost $45
# If someone has the standard, please either share it with me or fix the code.
class IEC268(Base):
    """IEC 60268-18 Peak programme level meters - Digital audio peak level meter"""

    def __init__(self):
        Base.__init__(
            self,
            "iec_268",
            _("IEC 60268-18 Peak programme level meters - Digital audio peak level meter"),
        )
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


class IEC268Minimalistic(Base):
    """IEC 60268-18 Peak programme level meters - Digital audio peak level meter,
    fewer marks"""

    def __init__(self):
        Base.__init__(
            self,
            "iec_268_minimalistic",
            _(
                "IEC 60268-18 Peak programme level meters - "
                "Digital audio peak level meter, fewer marks"
            ),
        )
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


class Linear70dB(Base):
    """Linear scale with range from -70 to 0 dBFS"""

    def __init__(self):
        Base.__init__(self, "linear_70dB", _("Linear scale with range from -70 to 0 dBFS"))
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


class Linear30dB(Base):
    """Linear scale with range from -30 to +30 dBFS"""

    def __init__(self):
        Base.__init__(self, "linear_30dB", _("Linear scale with range from -30 to +30 dBFS"))
        self.add_threshold(-30.0, 0.0, False)
        self.add_threshold(+30.0, 1.0, True)
        self.calculate_coefficients()
        self.scale_marks()


class K20(Base):
    """K20 scale"""

    def __init__(self):
        Base.__init__(self, "K20", _("K20 scale"))
        self.add_mark(-200, "")
        self.add_mark(-60, "-40")
        self.add_mark(-55, "")
        self.add_mark(-50, "-30")
        self.add_mark(-45, "")
        self.add_mark(-40, "-20")
        self.add_mark(-35, "")
        self.add_mark(-30, "-10")
        self.add_mark(-26, "-6")
        self.add_mark(-23, "-3")
        self.add_mark(-20, "0")
        self.add_mark(-17, "3")
        self.add_mark(-14, "6")
        self.add_mark(-10, "10")
        self.add_mark(-5, "15")
        self.add_mark(0, "20")

    def db_to_scale(self, db):
        v = math.pow(10.0, db / 20.0)
        return self.mapk20(v) / 450.0

    def add_mark(self, db, text):
        self.marks.append(Mark(db, self.db_to_scale(db), text))

    def mapk20(self, v):
        if v < 0.001:
            return 24000 * v
        v = math.log10(v) + 3
        if v < 2.0:
            return 24.3 + v * (100 + v * 16)
        if v > 3.0:
            v = 3.0
        return v * 161.7 - 35.1


class K14(Base):
    """K14 scale"""

    def __init__(self):
        Base.__init__(self, "K14", _("K14 scale"))
        self.add_mark(-200, "")
        self.add_mark(-54, "-40")
        self.add_mark(-35 - 14, "")
        self.add_mark(-30 - 14, "-30")
        self.add_mark(-25 - 14, "")
        self.add_mark(-20 - 14, "-20")
        self.add_mark(-15 - 14, "")
        self.add_mark(-10 - 14, "-10")
        self.add_mark(-6 - 14, "-6")
        self.add_mark(-3 - 14, "-3")
        self.add_mark(-14, "0")
        self.add_mark(3 - 14, "3")
        self.add_mark(6 - 14, "6")
        self.add_mark(10 - 14, "10")
        self.add_mark(14 - 14, "14")

    def db_to_scale(self, db):
        v = math.pow(10.0, db / 20.0)
        return self.mapk14(v) / 448.3

    def add_mark(self, db, text):
        self.marks.append(Mark(db, self.db_to_scale(db), text))

    def mapk14(self, v):
        if v < 0.002:
            return int(12000 * v)
        v = math.log10(v) + 2.7
        if v < 2.0:
            return int(20.3 + v * (80 + v * 32))
        if v > 2.7:
            v = 2.7
        return int(v * 200 - 91.7)


def scale_test1(scale):
    for i in range(-97 * 2, 1, 1):
        db = float(i) / 2.0
        print("%5.1f dB maps to %f" % (db, scale.db_to_scale(db)))


def scale_test2(scale):
    for i in range(101):
        s = float(i) / 100.0
        print("%.2f maps to %.1f dB" % (s, scale.scale_to_db(s)))


def print_db_to_scale(scale, db):
    print("%-.1f dB maps to %f" % (db, scale.db_to_scale(db)))


def scale_test3(scale):
    print_db_to_scale(scale, +77.0)
    print_db_to_scale(scale, +7.0)
    print_db_to_scale(scale, 0.0)
    print_db_to_scale(scale, -107.0)


def _test(*args, **kwargs):
    scale = Linear30dB()
    scale_test1(scale)
    scale_test2(scale)
    scale_test3(scale)


if __name__ == "__main__":
    _test()
