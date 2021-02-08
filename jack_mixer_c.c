/*
 * This file is part of jack_mixer
 *
 * Copyright (C) 2009 Frederic Peters <fpeters@0d.be>
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; version 2 of the License
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301 USA.
 */

#include <Python.h>

#include <stdlib.h>
#include <string.h>
#include <stdbool.h>

#include <structmember.h>

#include "jack_mixer.h"


/** Scale Type **/

typedef struct {
	PyObject_HEAD
	jack_mixer_scale_t scale;
} ScaleObject;

static void
Scale_dealloc(ScaleObject *self)
{
	if (self->scale)
		scale_destroy(self->scale);
	Py_TYPE(self)->tp_free((PyObject*)self);
}

static int
Scale_init(ScaleObject *self, PyObject *args, PyObject *kwds)
{
	self->scale = scale_create();
	return 0;
}

static PyObject*
Scale_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
	ScaleObject *self;

	self = (ScaleObject*)type->tp_alloc(type, 0);

	return (PyObject*)self;
}

static PyObject*
Scale_add_threshold(ScaleObject *self, PyObject *args)
{
	float db, scale_value;

	if (! PyArg_ParseTuple(args, "ff", &db, &scale_value)) return NULL;

	scale_add_threshold(self->scale, db, scale_value);

	Py_INCREF(Py_None);
	return Py_None;
}

static PyObject*
Scale_calculate_coefficients(ScaleObject *self, PyObject *args)
{
	if (! PyArg_ParseTuple(args, "")) return NULL;
	scale_calculate_coefficients(self->scale);
	Py_INCREF(Py_None);
	return Py_None;
}

static PyObject*
Scale_db_to_scale(ScaleObject *self, PyObject *args)
{
	double db;
	if (! PyArg_ParseTuple(args, "d", &db)) return NULL;
	return PyFloat_FromDouble(scale_db_to_scale(self->scale, db));
}

static PyObject*
Scale_scale_to_db(ScaleObject *self, PyObject *args)
{
	double scale_value;
	if (! PyArg_ParseTuple(args, "d", &scale_value)) return NULL;
	return PyFloat_FromDouble(scale_scale_to_db(self->scale, scale_value));
}

static PyMethodDef Scale_methods[] = {
	{"add_threshold", (PyCFunction)Scale_add_threshold, METH_VARARGS, "Add threshold"},
	{"calculate_coefficients", (PyCFunction)Scale_calculate_coefficients,
		METH_VARARGS, "Calculate coefficients"},
	{"db_to_scale", (PyCFunction)Scale_db_to_scale, METH_VARARGS, "dB to scale"},
	{"scale_to_db", (PyCFunction)Scale_scale_to_db, METH_VARARGS, "scale to dB"},
	{NULL}
};

static PyTypeObject ScaleType = {
	PyVarObject_HEAD_INIT(NULL, 0)
	"jack_mixer_c.Scale",    /*tp_name*/
	sizeof(ScaleObject), /*tp_basicsize*/
	0,       /*tp_itemsize*/
	(destructor)Scale_dealloc,       /*tp_dealloc*/
	0,       /*tp_print*/
	0,       /*tp_getattr*/
	0,       /*tp_setattr*/
	0,       /*tp_compare*/
	0,       /*tp_repr*/
	0,       /*tp_as_number*/
	0,       /*tp_as_sequence*/
	0,       /*tp_as_mapping*/
	0,       /*tp_hash */
	0,       /*tp_call*/
	0,       /*tp_str*/
	0,       /*tp_getattro*/
	0,       /*tp_setattro*/
	0,       /*tp_as_buffer*/
	Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,  /*tp_flags*/
	"Scale objects",           /* tp_doc */
	0,		           /* tp_traverse */
	0,		           /* tp_clear */
	0,		           /* tp_richcompare */
	0,		           /* tp_weaklistoffset */
	0,		           /* tp_iter */
	0,		           /* tp_iternext */
	Scale_methods,             /* tp_methods */
	0,             /* tp_members */
	0,           /* tp_getset */
	0,                         /* tp_base */
	0,                         /* tp_dict */
	0,                         /* tp_descr_get */
	0,                         /* tp_descr_set */
	0,                         /* tp_dictoffset */
	(initproc)Scale_init,      /* tp_init */
	0,                         /* tp_alloc */
	Scale_new,                 /* tp_new */
};


/** Channel Type **/

typedef struct {
	PyObject_HEAD
	PyObject *midi_change_callback;
	jack_mixer_channel_t channel;
} ChannelObject;

static void
Channel_dealloc(ChannelObject *self)
{
	Py_XDECREF(self->midi_change_callback);
	Py_TYPE(self)->tp_free((PyObject*)self);
}

static int
Channel_init(ChannelObject *self, PyObject *args, PyObject *kwds)
{
	self->midi_change_callback = NULL;
	return 0;
}

static PyObject*
Channel_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
	ChannelObject *self;

	self = (ChannelObject*)type->tp_alloc(type, 0);

	if (self != NULL) {
		self->channel = NULL;
		self->midi_change_callback = NULL;
	}

	return (PyObject*)self;
}

static PyObject*
Channel_get_is_stereo(ChannelObject *self, void *closure)
{
	PyObject *result;

	bool is_stereo = channel_is_stereo(self->channel);
	if (is_stereo) {
		result = Py_True;
	} else {
		result = Py_False;
	}
	Py_INCREF(result);
	return result;
}

static PyObject*
Channel_get_volume(ChannelObject *self, void *closure)
{
	return PyFloat_FromDouble(channel_volume_read(self->channel));
}

static int
Channel_set_volume(ChannelObject *self, PyObject *value, void *closure)
{
	if (self->channel == NULL) {
		PyErr_SetString(PyExc_RuntimeError, "unitialized channel");
		return -1;
	}
	channel_volume_write(self->channel, PyFloat_AsDouble(value));
	channel_set_midi_cc_volume_picked_up(self->channel, false);
	return 0;
}

static PyObject*
Channel_get_balance(ChannelObject *self, void *closure)
{
	return PyFloat_FromDouble(channel_balance_read(self->channel));
}

static int
Channel_set_balance(ChannelObject *self, PyObject *value, void *closure)
{
	channel_balance_write(self->channel, PyFloat_AsDouble(value));
	channel_set_midi_cc_balance_picked_up(self->channel, false);
	return 0;
}

static PyObject*
Channel_get_out_mute(ChannelObject *self, void *closure)
{
	PyObject *result;

	if (channel_is_out_muted(self->channel)) {
		result = Py_True;
	} else {
		result = Py_False;
	}
	Py_INCREF(result);
	return result;
}

static int
Channel_set_out_mute(ChannelObject *self, PyObject *value, void *closure)
{
	if (value == Py_True) {
		channel_out_mute(self->channel);
	} else {
		channel_out_unmute(self->channel);
	}
	return 0;
}

static PyObject*
Channel_get_solo(ChannelObject *self, void *closure)
{
	PyObject *result;

	if (channel_is_soloed(self->channel)) {
		result = Py_True;
	} else {
		result = Py_False;
	}
	Py_INCREF(result);
	return result;
}

static int
Channel_set_solo(ChannelObject *self, PyObject *value, void *closure)
{
	if (value == Py_True) {
		channel_solo(self->channel);
	} else {
		channel_unsolo(self->channel);
	}
	return 0;
}

static PyObject*
Channel_get_meter(ChannelObject *self, void *closure)
{
	PyObject *result;
	double left, right;

	if (channel_is_stereo(self->channel)) {
		result = PyTuple_New(2);
		channel_stereo_meter_read(self->channel, &left, &right);
		PyTuple_SetItem(result, 0, PyFloat_FromDouble(left));
		PyTuple_SetItem(result, 1, PyFloat_FromDouble(right));
	} else {
		result = PyTuple_New(1);
		channel_mono_meter_read(self->channel, &left);
		PyTuple_SetItem(result, 0, PyFloat_FromDouble(left));
	}
	return result;
}

static PyObject*
Channel_get_kmeter(ChannelObject *self, void *closure, enum meter_mode mode)
{
	PyObject *result;
	double peak_left, peak_right, rms_left, rms_right;
	if (channel_is_stereo(self->channel)) {
		result = PyTuple_New(4);
		channel_stereo_kmeter_read(self->channel,
			&peak_left, &peak_right, &rms_left, &rms_right, mode);
		PyTuple_SetItem(result, 0, PyFloat_FromDouble(peak_left));
		PyTuple_SetItem(result, 1, PyFloat_FromDouble(peak_right));
		PyTuple_SetItem(result, 2, PyFloat_FromDouble(rms_left));
		PyTuple_SetItem(result, 3, PyFloat_FromDouble(rms_right));
	} else {
		result = PyTuple_New(2);
		channel_mono_kmeter_read(self->channel, &peak_left, &rms_left, mode);
		PyTuple_SetItem(result, 0, PyFloat_FromDouble(peak_left));
		PyTuple_SetItem(result, 1, PyFloat_FromDouble(rms_left));
	}
	return result;
}

static PyObject*
Channel_get_kmeter_prefader(ChannelObject *self, void *closure)
{
  return Channel_get_kmeter(self, closure, Pre_Fader);
}

static PyObject*
Channel_get_kmeter_postfader(ChannelObject *self, void *closure)
{
  return Channel_get_kmeter(self, closure, Post_Fader);
}

static PyObject*
Channel_get_abspeak_prefader(ChannelObject *self, void *closure)
{
	return PyFloat_FromDouble(channel_abspeak_read(self->channel, Pre_Fader));
}

static PyObject*
Channel_get_abspeak_postfader(ChannelObject *self, void *closure)
{
	return PyFloat_FromDouble(channel_abspeak_read(self->channel, Post_Fader));
}

static int
Channel_set_abspeak(ChannelObject *self, PyObject *value, void *closure, enum meter_mode mode)
{
	if (value != Py_None) {
		fprintf(stderr, "abspeak can only be reset (set to None)\n");
		return -1;
	}
	channel_abspeak_reset(self->channel, mode);
	return 0;
}

static int
Channel_set_abspeak_prefader(ChannelObject *self, PyObject *value, void *closure) {
  return Channel_set_abspeak(self, value, closure, Pre_Fader);
}

static int
Channel_set_abspeak_postfader(ChannelObject *self, PyObject *value, void *closure) {
  return Channel_set_abspeak(self, value, closure, Post_Fader);
}

static int
Channel_set_midi_scale(ChannelObject *self, PyObject *value, void *closure)
{
	ScaleObject *scale_object = (ScaleObject*)value; /* XXX: check */

	channel_set_midi_scale(self->channel, scale_object->scale);
	return 0;
}


static PyObject*
Channel_get_midi_change_callback(ChannelObject *self, void *closure)
{
	if (self->midi_change_callback) {
		Py_INCREF(self->midi_change_callback);
		return self->midi_change_callback;
	} else {
		Py_INCREF(Py_None);
		return Py_None;
	}
}

static void
channel_midi_callback(void *userdata)
{
	ChannelObject *self = (ChannelObject*)userdata;
	PyGILState_STATE gstate;

	gstate = PyGILState_Ensure();
	PyObject_CallObject(self->midi_change_callback, NULL);
	PyGILState_Release(gstate);
}

static int
Channel_set_midi_change_callback(ChannelObject *self, PyObject *value, void *closure)
{
	if (value == Py_None) {
		self->midi_change_callback = NULL;
		channel_set_midi_change_callback(self->channel, NULL, NULL);
	} else {
		if (!PyCallable_Check(value)) {
			PyErr_SetString(PyExc_TypeError, "value must be callable");
			return -1;
		}
		if (self->midi_change_callback) {
			Py_XDECREF(self->midi_change_callback);
		}
		Py_INCREF(value);
		self->midi_change_callback = value;
		channel_set_midi_change_callback(self->channel,
				channel_midi_callback, self);
	}

	return 0;
}

static PyObject*
Channel_get_name(ChannelObject *self, void *closure)
{
	return PyUnicode_FromString(channel_get_name(self->channel));
}

static int
Channel_set_name(ChannelObject *self, PyObject *value, void *closure)
{
	channel_rename(self->channel, PyUnicode_AsUTF8(value));
	return 0;
}

static PyObject*
Channel_get_balance_midi_cc(ChannelObject *self, void *closure)
{
	return PyLong_FromLong(channel_get_balance_midi_cc(self->channel));
}

static int
Channel_set_balance_midi_cc(ChannelObject *self, PyObject *value, void *closure)
{
	int new_cc;
	unsigned int result;

	new_cc = PyLong_AsLong(value);
	result = channel_set_balance_midi_cc(self->channel, (int8_t)new_cc);
	if (result == 0) {
		return 0;
	}
	if (result == 2) {
		PyErr_SetString(PyExc_RuntimeError, "value out of range");
	}
	return -1;
}

static PyObject*
Channel_get_volume_midi_cc(ChannelObject *self, void *closure)
{
	return PyLong_FromLong(channel_get_volume_midi_cc(self->channel));
}

static int
Channel_set_volume_midi_cc(ChannelObject *self, PyObject *value, void *closure)
{
	int new_cc;
	unsigned int result;

	new_cc = PyLong_AsLong(value);
	result = channel_set_volume_midi_cc(self->channel, (int8_t)new_cc);
	if (result == 0) {
		return 0;
	}
	if (result == 2) {
		PyErr_SetString(PyExc_RuntimeError, "value out of range");
	}
	return -1;
}

static PyObject*
Channel_get_mute_midi_cc(ChannelObject *self, void *closure)
{
	return PyLong_FromLong(channel_get_mute_midi_cc(self->channel));
}

static int
Channel_set_mute_midi_cc(ChannelObject *self, PyObject *value, void *closure)
{
	int new_cc;
	unsigned int result;

	new_cc = PyLong_AsLong(value);
	result = channel_set_mute_midi_cc(self->channel, (int8_t)new_cc);
	if (result == 0) {
		return 0;
	}
	if (result == 2) {
		PyErr_SetString(PyExc_RuntimeError, "value out of range");
	}
	return -1;
}

static PyObject*
Channel_get_solo_midi_cc(ChannelObject *self, void *closure)
{
	return PyLong_FromLong(channel_get_solo_midi_cc(self->channel));
}

static int
Channel_set_solo_midi_cc(ChannelObject *self, PyObject *value, void *closure)
{
	int new_cc;
	unsigned int result;

	new_cc = PyLong_AsLong(value);
	result = channel_set_solo_midi_cc(self->channel, (int8_t)new_cc);
	if (result == 0) {
		return 0;
	}
	if (result == 2) {
		PyErr_SetString(PyExc_RuntimeError, "value out of range");
	}
	return -1;
}

static PyObject*
Channel_get_midi_in_got_events(ChannelObject *self, void *closure)
{
	PyObject *result;

	if (channel_get_midi_in_got_events(self->channel)) {
		result = Py_True;
	} else {
		result = Py_False;
	}
	Py_INCREF(result);
	return result;
}

static PyGetSetDef Channel_getseters[] = {
	{"is_stereo",
		(getter)Channel_get_is_stereo, NULL,
		"mono/stereo", NULL},
	{"volume",
		(getter)Channel_get_volume, (setter)Channel_set_volume,
		"volume", NULL},
	{"balance",
		(getter)Channel_get_balance, (setter)Channel_set_balance,
		"balance", NULL},
	{"out_mute",
		(getter)Channel_get_out_mute, (setter)Channel_set_out_mute,
		"out_mute", NULL},
	{"solo",
		(getter)Channel_get_solo, (setter)Channel_set_solo,
		"solo", NULL},
	{"meter",
		(getter)Channel_get_meter, NULL,
		"meter", NULL},
	{"kmeter_prefader",
		(getter)Channel_get_kmeter_prefader, NULL,
		"kmeter postader", NULL},
	{"kmeter_postfader",
		(getter)Channel_get_kmeter_postfader, NULL,
		"kmeter postfader", NULL},
	{"abspeak_prefader",
		(getter)Channel_get_abspeak_prefader, (setter)Channel_set_abspeak_prefader,
		"abspeak prefader", NULL},
	{"abspeak_postfader",
		(getter)Channel_get_abspeak_postfader, (setter)Channel_set_abspeak_postfader,
		"abspeak postfader", NULL},
	{"midi_scale",
		NULL, (setter)Channel_set_midi_scale,
		"midi scale", NULL},
	{"midi_change_callback",
		(getter)Channel_get_midi_change_callback,
		(setter)Channel_set_midi_change_callback,
		"midi change callback", NULL},
	{"name",
		(getter)Channel_get_name,
		(setter)Channel_set_name,
		"name", NULL},
	{"balance_midi_cc",
		(getter)Channel_get_balance_midi_cc,
		(setter)Channel_set_balance_midi_cc,
		"Balance MIDI CC", NULL},
	{"volume_midi_cc",
		(getter)Channel_get_volume_midi_cc,
		(setter)Channel_set_volume_midi_cc,
		"Volume MIDI CC", NULL},
	{"mute_midi_cc",
		(getter)Channel_get_mute_midi_cc,
		(setter)Channel_set_mute_midi_cc,
		"Mute MIDI CC", NULL},
	{"solo_midi_cc",
		(getter)Channel_get_solo_midi_cc,
		(setter)Channel_set_solo_midi_cc,
		"Mute MIDI CC", NULL},
	{"midi_in_got_events",
		(getter)Channel_get_midi_in_got_events, NULL,
		"Got new MIDI IN events", NULL},
	{NULL}
};

static PyObject*
Channel_remove(ChannelObject *self, PyObject *args)
{
	if (! PyArg_ParseTuple(args, "")) return NULL;
	remove_channel(self->channel);
	Py_INCREF(Py_None);
	return Py_None;
}

static PyObject*
Channel_autoset_volume_midi_cc(ChannelObject *self, PyObject *args)
{
	unsigned int result;
	if (! PyArg_ParseTuple(args, "")) return NULL;

	result = channel_autoset_volume_midi_cc(self->channel);

	if (result < 0) {
		PyErr_SetString(PyExc_RuntimeError, "No free CC for channel volume.");
	}

	return PyLong_FromLong(result);
}

static PyObject*
Channel_autoset_balance_midi_cc(ChannelObject *self, PyObject *args)
{
	unsigned int result;
	if (! PyArg_ParseTuple(args, "")) return NULL;

	result = channel_autoset_balance_midi_cc(self->channel);

	if (result < 0) {
		PyErr_SetString(PyExc_RuntimeError, "No free CC for channel balance.");
	}

	return PyLong_FromLong(result);
}

static PyObject*
Channel_autoset_mute_midi_cc(ChannelObject *self, PyObject *args)
{
	unsigned int result;
	if (! PyArg_ParseTuple(args, "")) return NULL;

	result = channel_autoset_mute_midi_cc(self->channel);

	if (result < 0) {
		PyErr_SetString(PyExc_RuntimeError, "No free CC for channel mute.");
	}

	return PyLong_FromLong(result);
}

static PyObject*
Channel_autoset_solo_midi_cc(ChannelObject *self, PyObject *args)
{
	unsigned int result;
	if (! PyArg_ParseTuple(args, "")) return NULL;

	result = channel_autoset_solo_midi_cc(self->channel);

	if (result < 0) {
		PyErr_SetString(PyExc_RuntimeError, "No free CC channel solo.");
	}

	return PyLong_FromLong(result);
}

static PyMethodDef channel_methods[] = {
	{"remove", (PyCFunction)Channel_remove, METH_VARARGS, "Remove"},
	{"autoset_volume_midi_cc",
		(PyCFunction)Channel_autoset_volume_midi_cc, METH_VARARGS, "Autoset Volume MIDI CC"},
	{"autoset_balance_midi_cc",
		(PyCFunction)Channel_autoset_balance_midi_cc, METH_VARARGS, "Autoset Balance MIDI CC"},
	{"autoset_mute_midi_cc",
		(PyCFunction)Channel_autoset_mute_midi_cc, METH_VARARGS, "Autoset Mute MIDI CC"},
	{"autoset_solo_midi_cc",
		(PyCFunction)Channel_autoset_solo_midi_cc, METH_VARARGS, "Autoset Solo MIDI CC"},
	{NULL}
};

static PyTypeObject ChannelType = {
	PyVarObject_HEAD_INIT(NULL, 0)
	"jack_mixer_c.Channel",    /*tp_name*/
	sizeof(ChannelObject), /*tp_basicsize*/
	0,       /*tp_itemsize*/
	(destructor)Channel_dealloc,       /*tp_dealloc*/
	0,       /*tp_print*/
	0,       /*tp_getattr*/
	0,       /*tp_setattr*/
	0,       /*tp_compare*/
	0,       /*tp_repr*/
	0,       /*tp_as_number*/
	0,       /*tp_as_sequence*/
	0,       /*tp_as_mapping*/
	0,       /*tp_hash */
	0,       /*tp_call*/
	0,       /*tp_str*/
	0,       /*tp_getattro*/
	0,       /*tp_setattro*/
	0,       /*tp_as_buffer*/
	Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,  /*tp_flags*/
	"Channel objects",           /* tp_doc */
	0,		           /* tp_traverse */
	0,		           /* tp_clear */
	0,		           /* tp_richcompare */
	0,		           /* tp_weaklistoffset */
	0,		           /* tp_iter */
	0,		           /* tp_iternext */
	channel_methods,           /* tp_methods */
	0,             /* tp_members */
	Channel_getseters,           /* tp_getset */
	0,                         /* tp_base */
	0,                         /* tp_dict */
	0,                         /* tp_descr_get */
	0,                         /* tp_descr_set */
	0,                         /* tp_dictoffset */
	(initproc)Channel_init,    /* tp_init */
	0,                         /* tp_alloc */
	Channel_new,                 /* tp_new */
};

static PyObject*
Channel_New(jack_mixer_channel_t channel)
{
	ChannelObject *self;
	self = (ChannelObject*)PyObject_NEW(ChannelObject, &ChannelType);
	if (self != NULL) {
		self->channel = channel;
		self->midi_change_callback = NULL;
	}
	return (PyObject*)self;
}

/** Output Channel Type **/

typedef struct {
	PyObject_HEAD
	PyObject *midi_change_callback;
	jack_mixer_output_channel_t *output_channel;
} OutputChannelObject;

static int
OutputChannel_set_prefader(OutputChannelObject *self, PyObject *value, void *closure)
{
	if (value == Py_True) {
		output_channel_set_prefader(self->output_channel, true);
	} else {
		output_channel_set_prefader(self->output_channel, false);
	}
	return 0;
}

static PyObject*
OutputChannel_get_prefader(OutputChannelObject *self, void *closure)
{
	PyObject *result;

	if (output_channel_is_prefader(self->output_channel)) {
		result = Py_True;
	} else {
		result = Py_False;
	}
	Py_INCREF(result);
	return result;
}

static PyGetSetDef OutputChannel_getseters[] = {
	{"prefader",
		(getter)OutputChannel_get_prefader, (setter)OutputChannel_set_prefader,
		"prefader", NULL},
	{NULL}
};

static PyObject*
OutputChannel_remove(OutputChannelObject *self, PyObject *args)
{
	if (! PyArg_ParseTuple(args, "")) return NULL;
	remove_output_channel(self->output_channel);
	Py_INCREF(Py_None);
	return Py_None;
}

static PyObject*
OutputChannel_set_solo(OutputChannelObject *self, PyObject *args)
{
	PyObject *channel;
	unsigned char solo;

	if (! PyArg_ParseTuple(args, "Ob", &channel, &solo)) return NULL;

	output_channel_set_solo(self->output_channel,
			((ChannelObject*)channel)->channel,
			solo);

	Py_INCREF(Py_None);
	return Py_None;
}

static PyObject*
OutputChannel_set_muted(OutputChannelObject *self, PyObject *args)
{
	PyObject *channel;
	unsigned char muted;

	if (! PyArg_ParseTuple(args, "Ob", &channel, &muted)) return NULL;

	output_channel_set_muted(self->output_channel,
			((ChannelObject*)channel)->channel,
			muted);

	Py_INCREF(Py_None);
	return Py_None;
}

static PyObject*
OutputChannel_is_solo(OutputChannelObject *self, PyObject *args)
{
	PyObject *channel;
	PyObject *result;

	if (! PyArg_ParseTuple(args, "O", &channel)) return NULL;

	if (output_channel_is_solo(self->output_channel,
			((ChannelObject*)channel)->channel)) {
		result = Py_True;
	} else {
		result = Py_False;
	}

	Py_INCREF(result);
	return result;
}

static PyObject*
OutputChannel_is_muted(OutputChannelObject *self, PyObject *args)
{
	PyObject *channel;
	PyObject *result;

	if (! PyArg_ParseTuple(args, "O", &channel)) return NULL;

	if (output_channel_is_muted(self->output_channel,
			((ChannelObject*)channel)->channel)) {
		result = Py_True;
	} else {
		result = Py_False;
	}

	Py_INCREF(result);
	return result;
}

static PyObject*
OutputChannel_set_in_prefader(OutputChannelObject *self, PyObject *args)
{
	PyObject *channel;
	unsigned char prefader;

	if (! PyArg_ParseTuple(args, "Ob", &channel, &prefader)) return NULL;

	output_channel_set_in_prefader(self->output_channel,
			((ChannelObject*)channel)->channel,
			prefader);

	Py_INCREF(Py_None);
	return Py_None;
}

static PyObject*
OutputChannel_is_in_prefader(OutputChannelObject *self, PyObject *args)
{
	PyObject *channel;
	PyObject *result;

	if (! PyArg_ParseTuple(args, "O", &channel)) return NULL;

	if (output_channel_is_in_prefader(self->output_channel,
			((ChannelObject*)channel)->channel)) {
		result = Py_True;
	} else {
		result = Py_False;
	}

	Py_INCREF(result);
	return result;
}

static PyMethodDef output_channel_methods[] = {
	{"remove", (PyCFunction)OutputChannel_remove, METH_VARARGS, "Remove"},
	{"set_solo", (PyCFunction)OutputChannel_set_solo, METH_VARARGS, "Set a channel as solo"},
	{"set_muted", (PyCFunction)OutputChannel_set_muted, METH_VARARGS, "Set a channel as muted"},
	{"is_solo", (PyCFunction)OutputChannel_is_solo, METH_VARARGS, "Is a channel set as solo"},
	{"is_muted", (PyCFunction)OutputChannel_is_muted, METH_VARARGS, "Is a channel set as muted"},
	{"set_in_prefader", (PyCFunction)OutputChannel_set_in_prefader, METH_VARARGS, "Set a channel as prefader"},
	{"is_in_prefader", (PyCFunction)OutputChannel_is_in_prefader, METH_VARARGS, "Is a channel set as prefader"},
	{NULL}
};

static PyTypeObject OutputChannelType = {
	PyVarObject_HEAD_INIT(NULL, 0)
	"jack_mixer_c.OutputChannel",    /*tp_name*/
	sizeof(OutputChannelObject), /*tp_basicsize*/
	0,       /*tp_itemsize*/
	0,       /*tp_dealloc*/
	0,       /*tp_print*/
	0,       /*tp_getattr*/
	0,       /*tp_setattr*/
	0,       /*tp_compare*/
	0,       /*tp_repr*/
	0,       /*tp_as_number*/
	0,       /*tp_as_sequence*/
	0,       /*tp_as_mapping*/
	0,       /*tp_hash */
	0,       /*tp_call*/
	0,       /*tp_str*/
	0,       /*tp_getattro*/
	0,       /*tp_setattro*/
	0,       /*tp_as_buffer*/
	Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,  /*tp_flags*/
	"Output Channel objects",           /* tp_doc */
	0,		           /* tp_traverse */
	0,		           /* tp_clear */
	0,		           /* tp_richcompare */
	0,		           /* tp_weaklistoffset */
	0,		           /* tp_iter */
	0,		           /* tp_iternext */
	output_channel_methods,    /* tp_methods */
	0,             /* tp_members */
	OutputChannel_getseters,   /* tp_getset */
	&ChannelType,              /* tp_base */
	0,                         /* tp_dict */
	0,                         /* tp_descr_get */
	0,                         /* tp_descr_set */
	0,                         /* tp_dictoffset */
	0,                         /* tp_init */
	0,                         /* tp_alloc */
	0,                         /* tp_new */
};

static PyObject*
OutputChannel_New(jack_mixer_output_channel_t output_channel)
{
	OutputChannelObject *self;
	self = (OutputChannelObject*)PyObject_NEW(OutputChannelObject, &OutputChannelType);
	if (self != NULL) {
		self->midi_change_callback = NULL;
		self->output_channel = output_channel;
	}
	return (PyObject*)self;
}


/** Mixer Type **/

typedef struct {
	PyObject_HEAD
	jack_mixer_t mixer;
} MixerObject;

static void
Mixer_dealloc(MixerObject *self)
{
	if (self->mixer)
		destroy(self->mixer);
	Py_TYPE(self)->tp_free((PyObject*)self);
}

static PyObject*
Mixer_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
	MixerObject *self;

	self = (MixerObject*)type->tp_alloc(type, 0);

	if (self != NULL) {
		self->mixer = NULL;
	}

	return (PyObject*)self;
}

static int
Mixer_init(MixerObject *self, PyObject *args, PyObject *kwds)
{
	static char *kwlist[] = {"name", "stereo", NULL};
	char *name;
	int stereo = 1;

	if (!PyArg_ParseTupleAndKeywords(args, kwds, "s|b", kwlist, &name, &stereo))
		return -1;

	self->mixer = create(name, (bool)stereo);
	if (self->mixer == NULL) {
		PyErr_SetString(PyExc_RuntimeError,
				"error creating mixer, probably jack is not running");
		return -1;
	}

	return 0;
}

static PyMemberDef Mixer_members[] = {
	{NULL}
};

static PyObject*
Mixer_get_channels_count(MixerObject *self, void *closure)
{
	return PyLong_FromLong(get_channels_count(self->mixer));
}

static PyObject*
Mixer_get_client_name(MixerObject *self, void *closure)
{
	return PyUnicode_FromString(get_client_name(self->mixer));
}

static PyObject*
Mixer_get_last_midi_cc(MixerObject *self, void *closure)
{
	return PyLong_FromLong(get_last_midi_cc(self->mixer));
}

static int
Mixer_set_last_midi_cc(MixerObject *self, PyObject *value, void *closure)
{
	int new_cc;
	unsigned int result;

	new_cc = PyLong_AsLong(value);
	result = set_last_midi_cc(self->mixer, (int8_t)new_cc);
	if (result == 0) {
		return 0;
	}
	return -1;
}

static PyObject*
Mixer_get_midi_behavior_mode(MixerObject *self, void *closure)
{
	return PyLong_FromLong(get_midi_behavior_mode(self->mixer));
}

static int
Mixer_set_midi_behavior_mode(MixerObject *self, PyObject *value, void *closure)
{
	int mode;
	unsigned int result;

	mode = PyLong_AsLong(value);
	result = set_midi_behavior_mode(self->mixer, mode);
	if (result == 0) {
		return 0;
	}
	return -1;
}



static PyGetSetDef Mixer_getseters[] = {
	{"channels_count", (getter)Mixer_get_channels_count, NULL,
		"channels count", NULL},
	{"last_midi_cc", (getter)Mixer_get_last_midi_cc, (setter)Mixer_set_last_midi_cc,
		"last midi channel", NULL},
	{"midi_behavior_mode", (getter)Mixer_get_midi_behavior_mode, (setter)Mixer_set_midi_behavior_mode,
		"midi behavior mode", NULL},
	{NULL}
};

static PyObject*
Mixer_add_channel(MixerObject *self, PyObject *args)
{
	char *name;
	int stereo;
	jack_mixer_channel_t channel;

	if (! PyArg_ParseTuple(args, "si", &name, &stereo)) return NULL;

	channel = add_channel(self->mixer, name, (bool)stereo);

	if (channel == NULL) {
		PyErr_SetString(PyExc_RuntimeError, "error adding channel");
		return NULL;
	}

	return Channel_New(channel);
}

static PyObject*
Mixer_add_output_channel(MixerObject *self, PyObject *args)
{
	char *name;
	int stereo = 1;
	int system = 0;
	jack_mixer_output_channel_t channel;

	if (! PyArg_ParseTuple(args, "s|bb", &name, &stereo, &system)) return NULL;

	channel = add_output_channel(self->mixer, name, (bool)stereo, (bool)system);

	return OutputChannel_New(channel);
}

static PyObject*
Mixer_destroy(MixerObject *self, PyObject *args)
{
	if (self->mixer) {
		destroy(self->mixer);
		self->mixer = NULL;
	}
	Py_INCREF(Py_None);
	return Py_None;
}

static PyMethodDef Mixer_methods[] = {
	{"add_channel", (PyCFunction)Mixer_add_channel, METH_VARARGS, "Add a new channel"},
	{"add_output_channel", (PyCFunction)Mixer_add_output_channel, METH_VARARGS, "Add a new output channel"},
	{"destroy", (PyCFunction)Mixer_destroy, METH_VARARGS, "Destroy JACK Mixer"},
	{"client_name", (PyCFunction)Mixer_get_client_name, METH_VARARGS, "Get jack client name"},
//	{"remove_channel", (PyCFunction)Mixer_remove_channel, METH_VARARGS, "Remove a channel"},
	{NULL}
};

static PyTypeObject MixerType = {
	PyVarObject_HEAD_INIT(NULL, 0)
	"jack_mixer_c.Mixer",    /*tp_name*/
	sizeof(MixerObject), /*tp_basicsize*/
	0,       /*tp_itemsize*/
	(destructor)Mixer_dealloc,       /*tp_dealloc*/
	0,       /*tp_print*/
	0,       /*tp_getattr*/
	0,       /*tp_setattr*/
	0,       /*tp_compare*/
	0,       /*tp_repr*/
	0,       /*tp_as_number*/
	0,       /*tp_as_sequence*/
	0,       /*tp_as_mapping*/
	0,       /*tp_hash */
	0,       /*tp_call*/
	0,       /*tp_str*/
	0,       /*tp_getattro*/
	0,       /*tp_setattro*/
	0,       /*tp_as_buffer*/
	Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,  /*tp_flags*/
	"Mixer objects",           /* tp_doc */
	0,		           /* tp_traverse */
	0,		           /* tp_clear */
	0,		           /* tp_richcompare */
	0,		           /* tp_weaklistoffset */
	0,		           /* tp_iter */
	0,		           /* tp_iternext */
	Mixer_methods,             /* tp_methods */
	Mixer_members,             /* tp_members */
	Mixer_getseters,           /* tp_getset */
	0,                         /* tp_base */
	0,                         /* tp_dict */
	0,                         /* tp_descr_get */
	0,                         /* tp_descr_set */
	0,                         /* tp_dictoffset */
	(initproc)Mixer_init,      /* tp_init */
	0,                         /* tp_alloc */
	Mixer_new,                 /* tp_new */
};


static PyMethodDef jack_mixer_methods[] = {
	{NULL, NULL, 0, NULL}  /* Sentinel */
};


static struct PyModuleDef moduledef = {
	PyModuleDef_HEAD_INIT,
	"jack_mixer_c",                /* m_name */
	"Jack Mixer C Helper Module",  /* m_doc */
	-1,                            /* m_size */
	jack_mixer_methods,            /* m_methods */
	NULL,                          /* m_reload */
	NULL,                          /* m_traverse */
	NULL,                          /* m_clear */
	NULL,                          /* m_free */
};

PyMODINIT_FUNC PyInit_jack_mixer_c(void)
{
	PyObject *m;

	if (PyType_Ready(&MixerType) < 0)
		return NULL;
	if (PyType_Ready(&ChannelType) < 0)
		return NULL;
	if (PyType_Ready(&OutputChannelType) < 0)
		return NULL;
	if (PyType_Ready(&ScaleType) < 0)
		return NULL;

	m = PyModule_Create(&moduledef);
	//m = Py_InitModule3("jack_mixer_c", jack_mixer_methods, "module doc");

	Py_INCREF(&MixerType);
	PyModule_AddObject(m, "Mixer", (PyObject*)&MixerType);
	Py_INCREF(&ChannelType);
	PyModule_AddObject(m, "Channel", (PyObject*)&ChannelType);
	Py_INCREF(&OutputChannelType);
	PyModule_AddObject(m, "OutputChannel", (PyObject*)&OutputChannelType);
	Py_INCREF(&ScaleType);
	PyModule_AddObject(m, "Scale", (PyObject*)&ScaleType);

	return m;
}

